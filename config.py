import json
import os
from typing import List, Optional
from astrbot.api import logger


class PluginConfig:
    """插件配置管理类"""

    def __init__(self, plugin_dir: str):
        self.plugin_dir = plugin_dir
        self._config_path = os.path.join(plugin_dir, "_conf_schema.json")
        self._user_config_path = os.path.join(plugin_dir, "user_config.json")
        self._load_config()

    def _load_config(self):
        """加载配置文件"""
        defaults = self._load_defaults()
        user_config = self._load_user_config()
        # 合并配置，用户配置覆盖默认值
        self.api_key = user_config.get("api_key") or defaults.get("api_key", "")
        self.default_city = user_config.get("default_city") or defaults.get("default_city", "北京")
        self.daily_push_time = user_config.get("daily_push_time") or defaults.get("daily_push_time", "08:00")
        self.whitelist_groups = user_config.get("whitelist_groups") or defaults.get("whitelist_groups", [])

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
            return True  # 白名单为空时允许所有群
        return str(group_id) in [str(g) for g in self.whitelist_groups]