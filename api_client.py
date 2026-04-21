import aiohttp
import asyncio
from typing import Optional, Tuple, Dict, Any
from astrbot.api import logger


class QWeatherClient:
    """和风天气 API 客户端 (兼容 Python 3.7+ 版本)"""

    def __init__(self, api_key: str, api_host: str = "", use_location_id: bool = False):
        self.api_key = api_key
        self.api_host = api_host.rstrip('/')
        self.use_location_id = use_location_id
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

        self.GEO_URL = f"https://{self.api_host}/geo/v2/city/lookup"
        self.WEATHER_NOW_URL = f"https://{self.api_host}/v7/weather/now"
        self.WEATHER_DAILY_URL = f"https://{self.api_host}/v7/weather/7d"
        self.AIR_QUALITY_URL = f"https://{self.api_host}/v7/air/now"
        self.INDICES_URL = f"https://{self.api_host}/v7/indices/1d"
        logger.info(f"API 端点已构建，使用 Host: {self.api_host}")

    INDICES_TYPES = "1,2,5,6,7,8,10,12,13,14"

    async def _request(self, url: str, params: dict) -> Optional[Dict[str, Any]]:
        """统一发起请求，添加 X-QW-Api-Key 头"""
        if not url:
            return None
        headers = {"X-QW-Api-Key": self.api_key}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, headers=headers) as resp:
                    if resp.status != 200:
                        logger.error(f"API 请求失败: {url} {resp.status}")
                        return None
                    data = await resp.json()
                    if data.get("code") != "200":
                        logger.error(f"API 返回错误: {data.get('code')}")
                        return None
                    return data
        except Exception as e:
            logger.error(f"API 请求异常: {e}")
            return None

    async def get_location_id(self, city_name: str) -> Optional[Tuple[str, str]]:
        """通过城市名获取 Location ID 和显示名称"""
        if not self.GEO_URL:
            return None
        params = {"location": city_name, "number": 1}
        data = await self._request(self.GEO_URL, params)
        if not data:
            return None
        locations = data.get("location", [])
        if not locations:
            logger.warning(f"未找到城市: {city_name}")
            return None
        loc = locations[0]
        return (loc.get("id"), loc.get("name", city_name))

    async def get_weather_now(self, location: str) -> Optional[Dict[str, Any]]:
        """获取实时天气数据 (location 可为 LocationID 或城市名)"""
        return await self._request(self.WEATHER_NOW_URL, {"location": location})

    async def get_weather_daily(self, location: str) -> Optional[Dict[str, Any]]:
        """获取每日天气预报（7天）"""
        return await self._request(self.WEATHER_DAILY_URL, {"location": location})

    async def get_air_quality(self, location: str) -> Optional[Dict[str, Any]]:
        """获取实时空气质量 AQI"""
        return await self._request(self.AIR_QUALITY_URL, {"location": location})

    async def get_indices(self, location: str) -> Optional[Dict[str, Any]]:
        """获取天气生活指数"""
        return await self._request(self.INDICES_URL, {"location": location, "type": self.INDICES_TYPES})

    async def get_complete_weather(self, city: str) -> Optional[Dict[str, Any]]:
        """获取完整的天气数据，整合多个 API 返回"""
        logger.info(f"开始查询天气: {city} (use_location_id={self.use_location_id})")

        # 1. 确定查询参数
        if self.use_location_id:
            loc_result = await self.get_location_id(city)
            if not loc_result:
                return None
            location_id, display_name = loc_result
            logger.info(f"获取到 LocationID: {location_id}, 显示名称: {display_name}")
        else:
            location_id = city
            display_name = city

        # 2. 并发请求所有 API (兼容 Python 3.7+)
        try:
            now_data, daily_data, aqi_data, indices_data = await asyncio.gather(
                self.get_weather_now(location_id),
                self.get_weather_daily(location_id),
                self.get_air_quality(location_id),
                self.get_indices(location_id),
                return_exceptions=True
            )
        except Exception as e:
            logger.error(f"并发请求 API 异常: {e}")
            return None

        # 检查是否有异常
        if isinstance(now_data, Exception) or isinstance(daily_data, Exception):
            logger.error(f"获取天气数据时发生异常")
            return None

        if not now_data or not daily_data:
            logger.error("获取天气数据失败")
            return None

        # 3. 整合数据
        now = now_data.get("now", {})
        daily_list = daily_data.get("daily", [])
        today = daily_list[0] if daily_list else {}

        result = {
            "city": display_name,
            "temperature": float(now.get("temp", 0)),
            "feels_like": float(now.get("feelsLike", 0)),
            "humidity": int(now.get("humidity", 0)),
            "pressure": int(now.get("pressure", 0)),
            "wind_speed": float(now.get("windSpeed", 0)),
            "wind_deg": int(now.get("wind360", 0)),
            "wind_dir": now.get("windDir", ""),
            "vis": float(now.get("vis", 0)),
            "cloud": int(now.get("cloud", 0)),
            "icon": now.get("icon", "100"),
            "weather": now.get("text", ""),
            "update_time": now_data.get("updateTime", ""),
            "temp_max": float(today.get("tempMax", 0)),
            "temp_min": float(today.get("tempMin", 0)),
            "sunrise": today.get("sunrise", ""),
            "sunset": today.get("sunset", ""),
            "moonrise": today.get("moonrise", ""),
            "moonset": today.get("moonset", ""),
            "moon_phase": today.get("moonPhase", ""),
            "uv_index": today.get("uvIndex", 0),
            "aqi": aqi_data.get("now", {}).get("aqi", "") if aqi_data and not isinstance(aqi_data, Exception) else "",
            "aqi_category": aqi_data.get("now", {}).get("category", "") if aqi_data and not isinstance(aqi_data, Exception) else "",
            "indices": indices_data.get("daily", []) if indices_data and not isinstance(indices_data, Exception) else [],
            "raw_daily": daily_list,
            "raw_now": now_data,
        }

        return result
