import asyncio
import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Any
from datetime import datetime

import astrbot.api.message_components as Comp
from astrbot.api.event import filter, AstrMessageEvent, MessageChain
from astrbot.api.star import Context, Star
from astrbot.api import FunctionTool, logger, AstrBotConfig
from astrbot.core.agent.tool import ToolExecResult
from astrbot.core.agent.run_context import ContextWrapper
from astrbot.core.astr_agent_context import AstrAgentContext
from astrbot.core.utils.astrbot_path import get_astrbot_data_path

from .core.config import PluginConfig
from .core.api_client import QWeatherClient
from .core.image_generator import WeatherImageGenerator
from .core.scheduler import WeatherScheduler
from .core.llm_guide import LLMGuideGenerator
from .core.holiday import HolidayChecker
from .web.routes import register_routes


# ==================== LLM FunctionTool 注册 ====================

@dataclass
class WeatherTool(FunctionTool):
    """查询天气工具 — 供 LLM 调用 /weather 指令。"""

    plugin: Any = None

    name: str = "weather"
    description: str = (
        "查询指定城市的实时天气信息。返回天气数据文本摘要，包括当前温度、体感温度、天气状况、"
        "湿度、风向风速、今日最高/最低温度、空气质量指数(AQI)、紫外线指数、日出日落时间等。"
        "当用户询问天气相关问题时，优先使用此工具。"
    )
    parameters: dict = field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "要查询的城市名称，例如：北京、上海、广州、深圳、杭州、成都、东京等",
                }
            },
            "required": ["city"],
        }
    )

    async def call(
        self, context: ContextWrapper[AstrAgentContext], **kwargs: Any
    ) -> ToolExecResult:
        city = kwargs.get("city", "").strip()
        if not city:
            city = getattr(self.plugin.config, "default_city", "")
        if not city:
            return ToolExecResult(
                json.dumps(
                    {"ok": False, "error": "请指定城市名称"},
                    ensure_ascii=False,
                )
            )

        weather_data = await self.plugin.api_client.get_complete_weather(city)
        if not weather_data:
            return ToolExecResult(
                json.dumps(
                    {"ok": False, "error": f"无法获取「{city}」的天气信息，请检查城市名称"},
                    ensure_ascii=False,
                )
            )

        summary = {
            "ok": True,
            "city": weather_data.get("city", city),
            "temperature": weather_data.get("temperature", 0),
            "feels_like": weather_data.get("feels_like", 0),
            "weather": weather_data.get("weather", ""),
            "humidity": weather_data.get("humidity", 0),
            "wind_dir": weather_data.get("wind_dir", ""),
            "wind_speed": weather_data.get("wind_speed", 0),
            "temp_max": weather_data.get("temp_max", 0),
            "temp_min": weather_data.get("temp_min", 0),
            "aqi": weather_data.get("aqi", ""),
            "aqi_category": weather_data.get("aqi_category", ""),
            "uv_index": weather_data.get("uv_index", 0),
            "precip": weather_data.get("precip", 0),
            "sunrise": weather_data.get("sunrise", ""),
            "sunset": weather_data.get("sunset", ""),
            "update_time": weather_data.get("update_time", ""),
        }
        return ToolExecResult(json.dumps(summary, ensure_ascii=False))


class WeatherPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        if config is None:
            config = {}
        self.plugin_dir = os.path.dirname(os.path.abspath(__file__))
        self.config = PluginConfig(config, self.plugin_dir)

        # 遵循 AstrBot 插件开发规范：运行时数据存储在 data/plugin_data/ 下
        self.plugin_data_dir = (
            Path(get_astrbot_data_path()) / "plugin_data" / "astrbot_plugin_everyday_weatherforecast"
        )
        self.plugin_data_dir.mkdir(parents=True, exist_ok=True)

        self.api_client = QWeatherClient(
            self.config.qweather_key,
            self.config.api_host,
            self.plugin_dir,
            indices_types=self.config.indices_types
        )
        self.image_generator = WeatherImageGenerator(plugin_dir=self.plugin_dir)
        self.holiday_checker = HolidayChecker(
            data_dir=str(self.plugin_data_dir),
            enabled=self.config.holiday_cache_enabled,
        )

        if self.config.llm_enabled:
            self.llm_generator = LLMGuideGenerator(
                context=self.context,
                holiday_checker=self.holiday_checker,
                provider_id=self.config.provider_id,
            )
        else:
            self.llm_generator = None

        self.scheduler = WeatherScheduler(timezone_str=self.config.timezone)
        self.scheduler.set_callback(self._daily_push)
        if self.config.daily_push_enabled and self.config.daily_push_time:
            self.scheduler.update_schedule(self.config.daily_push_time)
            self.scheduler.start()

        # 注册 /weather 为 LLM 可调用的 FunctionTool
        self.context.add_llm_tools(WeatherTool(plugin=self))

        # 注册 Web API（分群城市映射管理页面）
        register_routes(self.context, self)

        logger.info("天气预报插件已初始化")

    def _get_unified_origins(self) -> List[str]:
        """返回白名单中填写的完整会话标识符列表（直接用于发送）"""
        return self.config.whitelist_groups or []

    def _check_admin(self, event: AstrMessageEvent) -> bool:
        """检查消息发送者是否在插件管理员列表中，未配置则拒绝"""
        sender_id = event.get_sender_id()
        admin_users = self.config.admin_users
        if not admin_users:
            # 未配置管理员列表时，拒绝所有操作，引导配置
            return False
        return str(sender_id) in [str(uid) for uid in admin_users]

    async def _get_weather_image(self, city: str) -> Optional[bytes]:
        """根据城市获取天气数据并生成图片字节流"""
        weather_data = await self.api_client.get_complete_weather(city)
        if not weather_data:
            return None
        return self.image_generator.generate(weather_data)

    async def _daily_push(self):
        """每日定时推送任务（被调度器回调）"""
        logger.warning(f"[DailyPush] ========== 开始执行每日天气推送 ==========")
        logger.warning(f"[DailyPush] 当前时间: {datetime.now()}")
        logger.warning(f"[DailyPush] 默认城市: {self.config.default_city}")

        # 1. 检查基本配置
        if not self.config.qweather_key or not self.config.api_host:
            logger.error("[DailyPush] API Key 或 Host 未配置，跳过推送")
            return

        if not self.config.whitelist_groups:
            logger.warning("[DailyPush] 白名单群列表为空，无法推送")
            return

        mappings = self.config.group_city_mapping or {}
        default_city = self.config.default_city or "北京"
        origins = self._get_unified_origins()

        # 2. 收集每个群对应的城市 → 按城市分组
        origin_city_map: dict[str, str] = {}
        for origin in origins:
            city = mappings.get(origin) or default_city
            origin_city_map[origin] = city

        unique_cities = list(set(origin_city_map.values()))
        logger.warning(f"[DailyPush] 共 {len(origins)} 个群, {len(unique_cities)} 个不同城市: {unique_cities}")

        # 3. 按城市获取天气数据 + 生成图片
        city_data: dict[str, dict | None] = {}  # city → weather_data or None
        city_images: dict[str, bytes | None] = {}  # city → image bytes
        city_guides: dict[str, str] = {}  # city → LLM guide text
        city_tmp_files: dict[str, str] = {}  # city → temp file path

        for city in unique_cities:
            # 获取天气
            weather_data = None
            for retry in range(3):
                weather_data = await self.api_client.get_complete_weather(city)
                if weather_data:
                    break
                if retry < 2:
                    logger.warning(f"[DailyPush] {city} 获取失败，10秒后重试 ({retry+1}/3)")
                    await asyncio.sleep(10)

            if not weather_data:
                logger.error(f"[DailyPush] {city} 3次重试均失败")
                city_data[city] = None
                city_images[city] = None
                city_guides[city] = ""
                continue

            city_data[city] = weather_data

            # 生成图片
            image_bytes = self.image_generator.generate(weather_data)
            city_images[city] = image_bytes

            # 写入临时文件
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
                tmp_file.write(image_bytes)
            city_tmp_files[city] = tmp_file.name

            # 生成 LLM 指南
            guide = ""
            if self.config.llm_enabled and self.llm_generator:
                guide = await self.llm_generator.generate_guide(
                    city=city, weather_data=weather_data
                )
            city_guides[city] = guide

            logger.warning(f"[DailyPush] {city} 天气数据已就绪, 图片: {len(image_bytes)} bytes")

        # 4. 向每个群发送对应城市的天气
        success_count = 0
        for origin in origins:
            city = origin_city_map[origin]

            # 如果该城市天气获取失败，跳过
            if not city_data.get(city):
                logger.warning(f"[DailyPush] ⏭ 跳过 {origin}（{city} 获取失败）")
                continue

            tmp_path = city_tmp_files.get(city)
            if not tmp_path or not os.path.exists(tmp_path):
                logger.error(f"[DailyPush] ⏭ 跳过 {origin}（{city} 临时文件缺失）")
                continue

            try:
                image_chain = MessageChain() \
                    .message(f"☀️ 每日天气预报 - {city}") \
                    .file_image(tmp_path)
                await self.context.send_message(origin, image_chain)

                guide = city_guides.get(city, "")
                if guide:
                    await self.context.send_message(
                        origin,
                        MessageChain().message(guide)
                    )
                success_count += 1
                logger.warning(f"[DailyPush] ✅ 成功向 {origin} 发送（{city}）")
                await asyncio.sleep(0.5)
            except Exception as e:
                logger.error(f"[DailyPush] ❌ 向 {origin} 发送失败: {e}", exc_info=True)

        logger.warning(f"[DailyPush] 推送完成: {success_count}/{len(origins)}")

        # 5. 清理所有临时文件
        for tmp_path in city_tmp_files.values():
            try:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
            except OSError:
                pass

    # ==================== 指令注册 ====================

    @filter.command("weather")
    async def weather(self, event: AstrMessageEvent):
        """查询天气指令：/weather 或 /weather 城市名"""

        if not self.config.qweather_key or not self.config.api_host:
            yield event.plain_result("⚠️ 请先配置和风天气 API Key 和 API Host")
            return

        message = event.message_str.strip()
        parts = message.split(maxsplit=1)

        if len(parts) > 1:
            city = parts[1].strip()
        else:
            city = self.config.default_city

        if not city:
            yield event.plain_result("⚠️ 请指定城市名称，或先配置默认城市")
            return

        logger.info(f"查询天气: {city}")
        image_bytes = await self._get_weather_image(city)

        if not image_bytes:
            yield event.plain_result(f"❌ 无法获取「{city}」的天气信息")
            return

        chain = [
            Comp.Plain(f"📍 {city} 当前天气："),
            Comp.Image.fromBytes(image_bytes)
        ]
        yield event.chain_result(chain)

    @filter.command("weather_test_push")
    async def weather_test_push(self, event: AstrMessageEvent):
        """手动触发一次定时推送（调试用）"""
        logger.info("[TestPush] 收到手动推送指令")
        await self._daily_push()
        yield event.plain_result("✅ 手动推送已执行，请查看日志")

    @filter.command("weather_config")
    async def weather_config(self, event: AstrMessageEvent):
        """查看当前全量配置（仅管理员可查看）"""
        if not self._check_admin(event):
            yield event.plain_result("⛔ 权限不足：您不是插件管理员。请在 _conf_schema.json 的 admin_users 中添加您的 ID。")
            return

        whitelist_display = ', '.join(str(g) for g in self.config.whitelist_groups) if self.config.whitelist_groups else '全部群聊'
        admin_display = ', '.join(str(uid) for uid in self.config.admin_users) if self.config.admin_users else '未配置'

        # LLM 可用性检查
        llm_status = '关闭'
        llm_detail = ''
        if self.config.llm_enabled:
            try:
                provider = None
                if self.config.provider_id:
                    provider = self.context.get_provider_by_id(self.config.provider_id)
                if provider is None:
                    provider = self.context.get_using_provider()
                if provider:
                    model = provider.get_model() or '未知'
                    llm_status = '✅ 已连接'
                    llm_detail = f'\n• 当前模型: {model}'
                else:
                    llm_status = '❌ 不可用'
            except Exception as e:
                llm_status = f'❌ 异常: {e}'

        info = f"""📋 当前配置：
• 和风天气 Key: {'已设置' if self.config.qweather_key else '❌ 未设置'}
• API Host: {self.config.api_host or '❌ 未设置'}
• 默认城市: {self.config.default_city}
• 每日播报: {'开启' if self.config.daily_push_enabled else '关闭'}
• 推送时间: {self.config.daily_push_time}
• 白名单群: {whitelist_display}
• 管理员列表: {admin_display}
• LLM 指南: {llm_status}
• 节假日功能: {'开启' if self.config.holiday_cache_enabled else '关闭'}{llm_detail}"""
        yield event.plain_result(info)

    # ==================== 生命周期管理 ====================

    async def start(self):
        await super().start()
        if self.config.daily_push_enabled and self.config.daily_push_time:
            self.scheduler.update_schedule(self.config.daily_push_time)
        self.scheduler.start()
        jobs = self.scheduler.scheduler.get_jobs()
        logger.warning(f"[Main] 调度器已启动，当前任务数: {len(jobs)}")

    async def terminate(self):
        self.scheduler.shutdown()
        logger.info("和风天气预报插件已卸载")