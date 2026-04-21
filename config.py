import json
import os
from typing import List, Optional
from astrbot.api import logger


class PluginConfig:
    """插件配置管理类"""

    def __init__(self, plugin_dir: str):
        self.plugin_dir = plugin_dir
        self.use_location_id = user_config.get("use_location_id") or defaults.get("use_location_id", False)
        self._config_path = os.path.join(plugin_dir, "_conf_schema.json")
        self._user_config_path = os.path.join(plugin_dir, "user_config.json")
        self._load_config()

    def _load_config(self):
        """加载配置文件"""
        defaults = self._load_defaults()
        user_config = self._load_user_config()

        # 和风天气配置
        self.api_host = user_config.get("api_host") or defaults.get("api_host", "")
        self.qweather_key = user_config.get("qweather_key") or defaults.get("qweather_key", "")
        self.default_city = user_config.get("default_city") or defaults.get("default_city", "北京")
        self.daily_push_time = user_config.get("daily_push_time") or defaults.get("daily_push_time", "08:00")
        self.whitelist_groups = user_config.get("whitelist_groups") or defaults.get("whitelist_groups", [])

        # LLM 配置
        self.llm_enabled = user_config.get("llm_enabled")
        if self.llm_enabled is None:
            self.llm_enabled = defaults.get("llm_enabled", False)
        self.llm_provider = user_config.get("llm_provider") or defaults.get("llm_provider", "openai")
        self.llm_api_key = user_config.get("llm_api_key") or defaults.get("llm_api_key", "")
        self.llm_base_url = user_config.get("llm_base_url") or defaults.get("llm_base_url", "")
        self.llm_model = user_config.get("llm_model") or defaults.get("llm_model", "gpt-4o-mini")

    def _load_defaults(self) -> dict:
        """从 _conf_schema.json 加载默认值"""
        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                schema = json.load(f)
            defaults = {}
            for key, value in schema.items():
                if "default" in value:
                    defaults[key] = value["default"]
            return defaults
        except Exception as e:
            logger.warning(f"加载默认配置失败: {e}")
            return {}

    def _load_user_config(self) -> dict:
        """加载用户自定义配置"""
        try:
            with open(self._user_config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return {}

    def save_user_config(self, config: dict):
        """保存用户配置"""
        with open(self._user_config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        self._load_config()

    def is_group_allowed(self, group_id: str) -> bool:
        """检查群聊是否在白名单中"""
        if not self.whitelist_groups:
            return True
        return str(group_id) in [str(g) for g in self.whitelist_groups]
