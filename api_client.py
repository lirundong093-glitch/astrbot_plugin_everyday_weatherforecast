import aiohttp
import asyncio
from typing import Optional, Tuple, Dict, Any
from astrbot.api import logger

class QWeatherClient:
    """和风天气 API 客户端 (使用 API Host + X-QW-Api-Key)"""

    def __init__(self, api_key: str, api_host: str = ""):
        self.api_key = api_key
        self.api_host = api_host.rstrip('/')
        self._build_endpoints()

    def _build_endpoints(self):
        """根据 API Host 动态构建完整的端点 URL"""
        if not self.api_host:
            logger.error("未配置 API Host，无法构建请求 URL。")
            self.GEO_URL = ""
            self.WEATHER_NOW_URL = ""
            self.WEATHER_DAILY_URL = ""
            self.AIR_QUALITY_URL = ""
            self.INDICES_URL = ""
            return

        # 关键修改：使用你专属的 api_host 构建所有 URL
        self.GEO_URL = f"https://{self.api_host}/geo/v2/city/lookup"
        self.WEATHER_NOW_URL = f"https://{self.api_host}/v7/weather/now"
        self.WEATHER_DAILY_URL = f"https://{self.api_host}/v7/weather/7d"
        self.AIR_QUALITY_URL = f"https://{self.api_host}/v7/air/now"
        self.INDICES_URL = f"https://{self.api_host}/v7/indices/1d"
        logger.info(f"API 端点已构建，使用 Host: {self.api_host}")

    INDICES_TYPES = "1,2,5,6,7,8,10,12,13,14"

    async def get_location_id(self, city_name: str) -> Optional[Tuple[str, str]]:
        """通过城市名获取 Location ID 和显示名称"""
        if not self.GEO_URL:
            return None

        params = {
            "location": city_name,
            "number": 1
        }
        headers = {
            "X-QW-Api-Key": self.api_key  # 核心修改：通过 Header 传递认证信息
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.GEO_URL, params=params, headers=headers) as resp:
                    if resp.status != 200:
                        logger.error(f"GeoAPI 请求失败: {resp.status}")
                        return None

                    data = await resp.json()
                    if data.get("code") != "200":
                        logger.error(f"GeoAPI 返回错误: {data.get('code')}")
                        return None

                    locations = data.get("location", [])
                    if not locations:
                        logger.warning(f"未找到城市: {city_name}")
                        return None

                    loc = locations[0]
                    location_id = loc.get("id")
                    display_name = loc.get("name", city_name)
                    return (location_id, display_name)
        except Exception as e:
            logger.error(f"获取城市坐标异常: {e}")
            return None

    async def get_weather_now(self, location_id: str) -> Optional[Dict[str, Any]]:
        """获取实时天气数据"""
        if not self.WEATHER_NOW_URL:
            return None

        params = {"location": location_id}
        headers = {"X-QW-Api-Key": self.api_key}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.WEATHER_NOW_URL, params=params, headers=headers) as resp:
                    if resp.status != 200:
                        logger.error(f"Weather Now API 请求失败: {resp.status}")
                        return None
                    data = await resp.json()
                    if data.get("code") != "200":
                        logger.error(f"Weather Now API 返回错误: {data.get('code')}")
                        return None
                    return data
        except Exception as e:
            logger.error(f"获取实时天气异常: {e}")
            return None

    # 以下 get_weather_daily, get_air_quality, get_indices, get_complete_weather 方法
    # 也需要做相同的修改：在请求中加入 headers = {"X-QW-Api-Key": self.api_key}
    # 为了简洁，这里省略了它们的具体实现，请你在实际替换时也一并修改。
