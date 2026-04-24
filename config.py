import os
import json
from typing import List, Any
from astrbot.api import AstrBotConfig, logger


class PluginConfig:
    """插件配置管理类（封装 AstrBotConfig）"""

    def __init__(self, astr_config: AstrBotConfig, plugin_dir: str):
        self._astr_config = astr_config
        self.plugin_dir = plugin_dir
        self._user_config_path = os.path.join(plugin_dir, "user_config.json")
        self._migrate_legacy_config()
        self._sync_from_astr_config()

    def _migrate_legacy_config(self):
        """如果存在旧的 user_config.json，将其合并到 AstrBotConfig 中并删除"""
        if not os.path.exists(self._user_config_path):
            return
        try:
            with open(self._user_config_path, "r", encoding="utf-8") as f:
                legacy = json.load(f)
            logger.info("检测到旧版 user_config.json，正在迁移到 AstrBot 配置系统...")
            for key, value in legacy.items():
                if key not in self._astr_config or self._astr_config.get(key) in [None, "", []]:
                    self._astr_config[key] = value
            self._astr_config.save_config()
            os.rename(self._user_config_path, self._user_config_path + ".bak")
            logger.info("旧版配置已迁移并备份为 .bak")
        except Exception as e:
            logger.error(f"迁移旧配置失败: {e}")

    def _sync_from_astr_config(self):
        """从 AstrBotConfig 同步所有配置属性"""
        # 和风天气
        self.qweather_key: str = self._astr_config.get("qweather_key", "")
        self.api_host: str = self._astr_config.get("api_host", "devapi.qweather.com")
        self.default_city: str = self._astr_config.get("default_city", "北京")
        self.daily_push_time: str = self._astr_config.get("daily_push_time", "08:00")
        self.whitelist_groups: List[str] = self._astr_config.get("whitelist_groups", [])
        self.platform_name: str = self._astr_config.get("platform_name", "aiocqhttp")
        
        # 管理员
        self.admin_users: List[str] = self._astr_config.get("admin_users", [])
        
        # LLM
        self.llm_enabled: bool = self._astr_config.get("llm_enabled", False)
        self.llm_provider: str = self._astr_config.get("llm_provider", "openai")
        self.llm_api_key: str = self._astr_config.get("llm_api_key", "")
        self.llm_base_url: str = self._astr_config.get("llm_base_url", "https://api.openai.com/v1/chat/completions")
        self.llm_model: str = self._astr_config.get("llm_model", "gpt-4o-mini")
        
        # 节假日
        self.holiday_cache_enabled: bool = self._astr_config.get("holiday_cache_enabled", True)

        #时区配置
        self.timezone: str = self._astr_config.get("timezone", "Asia/Shanghai")    
        
    def update_config(self, key: str, value: str) -> str:
        """更新单项配置并自动保存，返回提示信息"""
        key_mapping = {
            "qweather_key": "和风天气 API Key",
            "api_host": "API Host",
            "default_city": "默认城市",
            "daily_push_time": "推送时间",
            "platform_name": "平台名称",
            "llm_provider": "LLM 提供商",
            "llm_api_key": "LLM API Key",
            "llm_base_url": "LLM Base URL",
            "llm_model": "LLM 模型",
        }

        if key in key_mapping:
            self._astr_config[key] = value
            self._astr_config.save_config()
            self._sync_from_astr_config()
            return f"✅ {key_mapping[key]} 已更新为: {value}"

        elif key == "llm_enabled":
            enabled = value.lower() in ["true", "1", "yes", "on"]
            self._astr_config[key] = enabled
            self._astr_config.save_config()
            self._sync_from_astr_config()
            return f"✅ LLM 天气指南已{'开启' if enabled else '关闭'}"

        elif key == "holiday_cache_enabled":
            enabled = value.lower() in ["true", "1", "yes", "on"]
            self._astr_config[key] = enabled
            self._astr_config.save_config()
            self._sync_from_astr_config()
            return f"✅ 节假日功能已{'开启' if enabled else '关闭'}"

        elif key == "whitelist_add":
            current = list(self._astr_config.get("whitelist_groups", []))
            if value not in current:
                current.append(value)
                self._astr_config["whitelist_groups"] = current
                self._astr_config.save_config()
                self._sync_from_astr_config()
            return f"✅ 群 {value} 已加入白名单"

        elif key == "whitelist_remove":
            current = list(self._astr_config.get("whitelist_groups", []))
            if value in current:
                current.remove(value)
                self._astr_config["whitelist_groups"] = current
                self._astr_config.save_config()
                self._sync_from_astr_config()
            return f"✅ 群 {value} 已从白名单移除"

        elif key == "admin_add":
            current = list(self._astr_config.get("admin_users", []))
            if value not in current:
                current.append(value)
                self._astr_config["admin_users"] = current
                self._astr_config.save_config()
                self._sync_from_astr_config()
            return f"✅ 用户 {value} 已添加为管理员"

        elif key == "admin_remove":
            current = list(self._astr_config.get("admin_users", []))
            if value in current:
                current.remove(value)
                self._astr_config["admin_users"] = current
                self._astr_config.save_config()
                self._sync_from_astr_config()
            return f"✅ 用户 {value} 已从管理员列表移除"

        else:
            return f"❌ 未知配置项: {key}"

    def is_group_allowed(self, group_id: str) -> bool:
        """检查群聊是否在白名单中"""
        if not self.whitelist_groups:
            return True
        return str(group_id) in [str(g) for g in self.whitelist_groups]
