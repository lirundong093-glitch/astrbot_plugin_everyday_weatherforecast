import json
import os
from datetime import datetime
from typing import Optional, Dict, Any
import aiohttp
from astrbot.api import logger


class HolidayChecker:
    """节假日检查器（本地缓存 + 免费 API）"""

    API_URL = "https://timor.tech/api/holiday/year"

    def __init__(self, cache_dir: str, enabled: bool = True):
        self.cache_dir = cache_dir
        self.enabled = enabled
        self.cache_file = os.path.join(cache_dir, "holiday_cache.json")
        self._holidays: Dict[str, Dict[str, Any]] = {}
        self._load_cache()

    def _load_cache(self):
        """加载本地缓存"""
        if not self.enabled:
            return
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    self._holidays = json.load(f)
                logger.info(f"节假日缓存已加载，共 {len(self._holidays)} 个节日")
        except Exception as e:
            logger.warning(f"加载节假日缓存失败: {e}")

    def _save_cache(self):
        """保存本地缓存"""
        if not self.enabled:
            return
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self._holidays, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存节假日缓存失败: {e}")

    async def _fetch_year_holidays(self, year: int) -> Optional[Dict[str, Any]]:
        """从 API 获取指定年份的节假日数据"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.API_URL}/{year}") as resp:
                    if resp.status != 200:
                        logger.error(f"获取节假日数据失败: HTTP {resp.status}")
                        return None
                    data = await resp.json()
                    if data.get("code") != 0:
                        logger.error(f"节假日 API 返回错误: {data}")
                        return None
                    # 返回 holiday 字段，key 为日期，value 为节日信息
                    return data.get("holiday", {})
        except Exception as e:
            logger.error(f"获取节假日数据异常: {e}")
            return None

    async def _ensure_year_cache(self, year: int):
        """确保指定年份的缓存存在"""
        if not self.enabled:
            return
        year_str = str(year)
        if year_str in self._holidays:
            return
        logger.info(f"从 API 获取 {year} 年节假日数据...")
        holiday_data = await self._fetch_year_holidays(year)
        if holiday_data:
            self._holidays[year_str] = holiday_data
            self._save_cache()
            logger.info(f"{year} 年节假日数据已缓存")

    async def check_today(self) -> tuple[bool, str]:
        """
        检查今天是否为节假日。
        返回: (is_holiday, holiday_name)
        - is_holiday: 是否为节假日（普通周末不算）
        - holiday_name: 节日名称，如"春节"
        """
        if not self.enabled:
            return (False, "")

        today = datetime.now()
        year = today.year
        date_str = today.strftime("%Y-%m-%d")

        await self._ensure_year_cache(year)

        year_str = str(year)
        if year_str in self._holidays:
            day_info = self._holidays[year_str].get(date_str, {})
            if day_info and day_info.get("holiday", False):
                return (True, day_info.get("name", ""))

        return (False, "")
