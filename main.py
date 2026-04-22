import asyncio
import os
import json
from datetime import datetime
from typing import Optional

import astrbot.api.message_components as Comp
from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger

from .config import PluginConfig
from .api_client import QWeatherClient
from .image_generator import WeatherImageGenerator
from .scheduler import WeatherScheduler
from .llm_guide import LLMGuideGenerator
from .holiday import HolidayChecker

@register("astrbot_plugin_weather", "Your Name", "和风天气预报插件", "2.0.0")
class WeatherPlugin(Star):
    def __init__(self, context: Context, config: Optional[dict] = None):
        super().__init__(context)

        # 插件目录
        self.plugin_dir = os.path.dirname(os.path.abspath(__file__))
        self.config = PluginConfig(self.plugin_dir)

        # 和风天气客户端
        self.api_client = QWeatherClient(
            self.config.qweather_key, 
            self.config.api_host,
            self.plugin_dir
        )
        
        # 图片生成器
        self.image_generator = WeatherImageGenerator(plugin_dir=self.plugin_dir)

        # 定时调度器
        self.scheduler = WeatherScheduler()
        self.scheduler.set_callback(self._daily_push)
        self._update_schedule_from_config()
        self.holiday_checker = HolidayChecker(
            cache_dir=self.plugin_dir,
            enabled=self.config.llm_enabled  
        )
        
        # LLM 指南生成器（如果启用）
        if self.config.llm_enabled:
            self.llm_generator = LLMGuideGenerator(
                provider=self.config.llm_provider,
                api_key=self.config.llm_api_key,
                base_url=self.config.llm_base_url,
                model=self.config.llm_model,
                holiday_checker=self.holiday_checker, 
            )
        else:
            self.llm_generator = None

        logger.info("和风天气预报插件已初始化")

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
        """获取指定城市的天气图片（bytes）"""
        if not self.config.qweather_key:
            logger.error("和风天气 API Key 未配置")
            return None

        weather_data = await self.api_client.get_complete_weather(city)
        if not weather_data:
            return None

        return self.image_generator.generate(weather_data)

    async def _daily_push(self):
        """每日定时推送任务"""
        if not self.config.qweather_key:
            logger.warning("和风天气 API Key 未配置，跳过定时推送")
            return

        logger.info(f"开始每日天气推送，默认城市: {self.config.default_city}")

        # 获取完整天气数据（LLM 生成指南也需要这份数据）
        weather_data = await self.api_client.get_complete_weather(self.config.default_city)
        if not weather_data:
            logger.error("获取天气数据失败，定时推送中止")
            return

        # 生成天气图片
        image_bytes = self.image_generator.generate(weather_data)

        # 如果启用 LLM，生成天气指南
        guide_text = ""
        if self.config.llm_enabled and self.llm_generator:
            guide_text = await self.llm_generator.generate_guide(
                city=self.config.default_city,
                weather_data=weather_data
            )
            if not guide_text:
                logger.warning("LLM 生成天气指南失败，将仅发送天气图片")

        # 向白名单群聊发送
        for group_id in self.config.whitelist_groups:
            try:
                chain = [
                    Comp.Plain(f"☀️ 每日天气预报 - {self.config.default_city}"),
                    Comp.Image.fromBytes(image_bytes)
                ]
                if guide_text:
                    chain.append(Comp.Plain(f"\n\n📋 **今日天气指南**\n{guide_text}"))

                await self.context.send_message(group_id, chain)
                await asyncio.sleep(0.5)
            except Exception as e:
                logger.error(f"向群 {group_id} 发送失败: {e}")

    @filter.command("weather")
    async def weather(self, event: AstrMessageEvent):
        """查询天气指令：/weather 或 /weather 城市名"""
        if not self._check_whitelist(event):
            return

        if not self.config.qweather_key:
            yield event.plain_result("⚠️ 请先配置和风天气 API Key")
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
            yield event.plain_result(f"❌ 无法获取「{city}」的天气信息，请检查城市名称是否正确")
            return

        chain = [
            Comp.Plain(f"📍 {city} 当前天气："),
            Comp.Image.fromBytes(image_bytes)
        ]
        yield event.chain_result(chain)

    @filter.command("weather_config")
    async def weather_config(self, event: AstrMessageEvent, key: str = None, value: str = None):
        """
        配置指令：/weather_config [key] [value]
        支持的配置项：
            qweather_key, default_city, push_time,
            whitelist_add, whitelist_remove,
            llm_enabled, llm_provider, llm_api_key, llm_base_url, llm_model
        """
        # 可在此处添加管理员权限检查
        # if not event.is_admin():
        #     yield event.plain_result("⛔ 权限不足")
        #     return

        if not key:
            # 显示当前配置
            info = f"""📋 当前配置：
• 和风天气 Key: {'已设置' if self.config.qweather_key else '❌ 未设置'}
• API Host: {self.config.api_host or '❌ 未设置'}
• 默认城市: {self.config.default_city}
• 推送时间: {self.config.daily_push_time or '未设置'}
• 白名单群: {', '.join(self.config.whitelist_groups) if self.config.whitelist_groups else '全部群聊'}
• LLM 指南: {'开启' if self.config.llm_enabled else '关闭'}
• LLM 提供商: {self.config.llm_provider}
• LLM 模型: {self.config.llm_model}"""
            yield event.plain_result(info)
            return

        if not value and key not in ["llm_enabled"]:
            yield event.plain_result("⚠️ 请提供配置值")
            return

        config_path = os.path.join(self.plugin_dir, "user_config.json")
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                user_config = json.load(f)
        except:
            user_config = {}

        msg = ""

        if key == "qweather_key":
            user_config["qweather_key"] = value
            self.config.qweather_key = value
            self.api_client.api_key = value
            msg = "✅ 和风天气 API Key 已更新"

        elif key == "api_host":
            user_config["api_host"] = value.strip()
            self.config.api_host = value.strip()
            self.api_client.api_host = value.strip()   # 动态更新客户端中的值
            self.api_client._build_endpoints()         # 重新构建 URL
            msg = f"✅ API Host 已更新为: {value}"
        
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

        elif key == "holiday_cache_enabled":
            enabled = value.lower() in ["true", "1", "yes", "on"]
            user_config["holiday_cache_enabled"] = enabled
            self.config.holiday_cache_enabled = enabled
            if hasattr(self, 'holiday_checker'):
                self.holiday_checker.enabled = enabled
            msg = f"✅ 节假日功能已{'开启' if enabled else '关闭'}"
    
        elif key == "llm_enabled":
            enabled = value.lower() in ["true", "1", "yes", "on"]
            user_config["llm_enabled"] = enabled
            self.config.llm_enabled = enabled
            if enabled and not self.llm_generator:
                self.llm_generator = LLMGuideGenerator(
                    provider=self.config.llm_provider,
                    api_key=self.config.llm_api_key,
                    base_url=self.config.llm_base_url,
                    model=self.config.llm_model,
                )
            elif not enabled:
                self.llm_generator = None
            msg = f"✅ LLM 天气指南已{'开启' if enabled else '关闭'}"

        elif key == "llm_provider":
            user_config["llm_provider"] = value
            self.config.llm_provider = value
            if self.llm_generator:
                self.llm_generator.provider = value
            msg = f"✅ LLM 提供商已设置为: {value}"

        elif key == "llm_api_key":
            user_config["llm_api_key"] = value
            self.config.llm_api_key = value
            if self.llm_generator:
                self.llm_generator.api_key = value
            msg = "✅ LLM API Key 已更新"

        elif key == "llm_base_url":
            user_config["llm_base_url"] = value
            self.config.llm_base_url = value
            if self.llm_generator:
                self.llm_generator.base_url = value
            msg = f"✅ LLM Base URL 已设置为: {value}"

        elif key == "llm_model":
            user_config["llm_model"] = value
            self.config.llm_model = value
            if self.llm_generator:
                self.llm_generator.model = value
            msg = f"✅ LLM 模型已设置为: {value}"

        else:
            yield event.plain_result(f"❌ 未知配置项: {key}")
            return

        # 保存配置
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(user_config, f, ensure_ascii=False, indent=2)

        yield event.plain_result(msg)

    async def start(self):
        await super().start()
        self.scheduler.start()
        logger.info("和风天气预报插件已启动")

    async def terminate(self):
        self.scheduler.shutdown()
        logger.info("和风天气预报插件已卸载")
