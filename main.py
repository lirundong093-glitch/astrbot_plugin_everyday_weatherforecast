import asyncio
import os
import astrbot.api.message_components as Comp
from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from typing import Optional

from .config import PluginConfig
from .api_client import OpenWeatherClient
from .image_generator import WeatherImageGenerator
from .scheduler import WeatherScheduler


@register("astrbot_plugin_weather", "Your Name", "天气预报插件", "1.0.0")
class WeatherPlugin(Star):
    def __init__(self, context: Context, config: Optional[dict] = None):
        super().__init__(context)

        # 初始化配置
        self.plugin_dir = os.path.dirname(os.path.abspath(__file__)) 
        self.config = PluginConfig(self.plugin_dir)

        # 初始化API客户端
        self.api_client = OpenWeatherClient(self.config.api_key)

        # 初始化图片生成器
        self.image_generator = WeatherImageGenerator()

        # 初始化定时调度器
        self.scheduler = WeatherScheduler()
        self.scheduler.set_callback(self._daily_push)
        self._update_schedule_from_config()

        logger.info("天气预报插件已初始化")

    def _update_schedule_from_config(self):
        """从配置更新定时任务"""
        if self.config.daily_push_time:
            self.scheduler.update_schedule(self.config.daily_push_time)

    def _check_whitelist(self, event: AstrMessageEvent) -> bool:
        """检查消息来源是否在白名单中"""
        group_id = event.get_group_id()
        if group_id:
            return self.config.is_group_allowed(group_id)
        # 私聊消息始终允许
        return True

    async def _get_weather_image(self, city: str) -> Optional[bytes]:
        """获取指定城市的天气图片"""
        # 获取坐标
        coords = await self.api_client.get_coordinates(city)
        if not coords:
            return None

        lat, lon, display_name = coords

        # 获取天气数据
        weather_data = await self.api_client.get_weather(lat, lon)
        if not weather_data:
            return None

        weather_data["city"] = display_name

        # 生成图片
        return self.image_generator.generate(weather_data)

    async def _daily_push(self):
        """每日定时推送"""
        if not self.config.api_key:
            logger.warning("API密钥未配置，跳过定时推送")
            return

        logger.info(f"开始每日天气推送，默认城市: {self.config.default_city}")

        # 生成天气图片
        image_bytes = await self._get_weather_image(self.config.default_city)
        if not image_bytes:
            logger.error("生成天气图片失败")
            return

        # 向白名单群聊发送
        for group_id in self.config.whitelist_groups:
            try:
                # 构建消息链
                chain = [
                    Comp.Plain(f"☀️ 每日天气预报 - {self.config.default_city}"),
                    Comp.Image.from_bytes(image_bytes)
                ]
                await self.context.send_message(group_id, chain)
                await asyncio.sleep(0.5)  # 避免发送过快
            except Exception as e:
                logger.error(f"向群 {group_id} 发送失败: {e}")

    @filter.command("weather")
    async def weather(self, event: AstrMessageEvent):
        """查询天气指令：/weather 或 /weather 城市名"""
        # 检查白名单
        if not self._check_whitelist(event):
            return

        # 检查API密钥
        if not self.config.api_key:
            yield event.plain_result("⚠️ 请先配置 OpenWeather API 密钥")
            return

        # 解析参数
        message = event.message_str.strip()
        parts = message.split(maxsplit=1)

        if len(parts) > 1:
            city = parts[1].strip()
        else:
            city = self.config.default_city

        if not city:
            yield event.plain_result("⚠️ 请指定城市名称，或先配置默认城市")
            return

        # 获取天气图片
        logger.info(f"查询天气: {city}")
        image_bytes = await self._get_weather_image(city)

        if not image_bytes:
            yield event.plain_result(f"❌ 无法获取「{city}」的天气信息，请检查城市名称是否正确")
            return

        # 发送图片
        chain = [
            Comp.Plain(f"📍 {city} 当前天气："),
            Comp.Image.from_bytes(image_bytes)
        ]
        yield event.chain_result(chain)

    @filter.command("weather_config")
    async def weather_config(self, event: AstrMessageEvent, key: str = None, value: str = None):
        """
        配置指令：/weather_config [key] [value]
        支持的配置项：api_key, default_city, push_time, whitelist_add, whitelist_remove
        """
        # 仅管理员可用（可自行添加权限检查）

        if not key:
            # 显示当前配置
            info = f"""📋 当前配置：
• API密钥: {'已设置' if self.config.api_key else '❌ 未设置'}
• 默认城市: {self.config.default_city}
• 推送时间: {self.config.daily_push_time or '未设置'}
• 白名单群: {', '.join(self.config.whitelist_groups) if self.config.whitelist_groups else '全部群聊'}"""
            yield event.plain_result(info)
            return

        if not value:
            yield event.plain_result("⚠️ 请提供配置值")
            return

        # 加载现有配置
        import json
        import os
        config_path = os.path.join(self.plugin_dir, "user_config.json")
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                user_config = json.load(f)
        except:
            user_config = {}

        # 处理配置
        if key == "api_key":
            user_config["api_key"] = value
            self.config.api_key = value
            self.api_client.api_key = value
            msg = f"✅ API密钥已更新"

        elif key == "default_city":
            user_config["default_city"] = value
            self.config.default_city = value
            msg = f"✅ 默认城市已设置为: {value}"

        elif key == "push_time":
            user_config["daily_push_time"] = value
            self.config.daily_push_time = value
            self._update_schedule_from_config()
            msg = f"✅ 推送时间已设置为: {value}"

        elif key == "whitelist_add":
            if "whitelist_groups" not in user_config:
                user_config["whitelist_groups"] = self.config.whitelist_groups.copy()
            if value not in user_config["whitelist_groups"]:
                user_config["whitelist_groups"].append(value)
                self.config.whitelist_groups = user_config["whitelist_groups"]
            msg = f"✅ 群 {value} 已加入白名单"

        elif key == "whitelist_remove":
            if "whitelist_groups" in user_config and value in user_config["whitelist_groups"]:
                user_config["whitelist_groups"].remove(value)
                self.config.whitelist_groups = user_config["whitelist_groups"]
            msg = f"✅ 群 {value} 已从白名单移除"

        else:
            yield event.plain_result(f"❌ 未知配置项: {key}")
            return

        # 保存配置
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(user_config, f, ensure_ascii=False, indent=2)

        yield event.plain_result(msg)

    async def start(self):
        """插件启动时调用"""
        await super().start()
        self.scheduler.start()
        logger.info("天气预报插件已启动")

    async def terminate(self):
        """插件卸载时调用"""
        self.scheduler.shutdown()
        logger.info("天气预报插件已卸载")
