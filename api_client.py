import aiohttp
from typing import Optional, Tuple, Dict, Any
from astrbot.api import logger


class OpenWeatherClient:
    """OpenWeather API 客户端"""

    GEO_URL = "http://api.openweathermap.org/geo/1.0/direct"
    WEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def get_coordinates(self, city_name: str) -> Optional[Tuple[float, float, str]]:
        """
        通过城市名获取经纬度坐标
        返回: (lat, lon, display_name) 或 None
        """
        params = {
            "q": city_name,
            "limit": 1,
            "appid": self.api_key
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.GEO_URL, params=params) as resp:
                    if resp.status != 200:
                        logger.error(f"Geocoding API 请求失败: {resp.status}")
                        return None

                    data = await resp.json()
                    if not data:
                        logger.warning(f"未找到城市: {city_name}")
                        return None

                    item = data[0]
                    lat = item.get("lat")
                    lon = item.get("lon")
                    name = item.get("local_names", {}).get("zh") or item.get("name", city_name)
                    return (lat, lon, name)
        except Exception as e:
            logger.error(f"获取城市坐标异常: {e}")
            return None


    async def get_weather(self, lat: float, lon: float) -> Optional[Dict[str, Any]]:
        """获取天气数据 (已增强)"""
        params = {
            "lat": lat,
            "lon": lon,
            "appid": self.api_key,
            "units": "metric",
            "lang": "zh_cn"
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.WEATHER_URL, params=params) as resp:
                    if resp.status != 200:
                        logger.error(f"Weather API 请求失败: {resp.status}")
                        return None

                    data = await resp.json()
                    return {
                        "city": data.get("name", "未知"),
                        "country": data.get("sys", {}).get("country", ""),  # 新增：国家代码
                        "dt": data.get("dt"),  # 新增：数据时间戳
                        "timezone": data.get("timezone", 0),  # 新增：时区偏移
                        "temperature": round(data["main"]["temp"], 1),
                        "feels_like": round(data["main"]["feels_like"], 1),
                        "temp_max": round(data["main"]["temp_max"], 1),  # 新增：最高气温
                        "temp_min": round(data["main"]["temp_min"], 1),  # 新增：最低气温
                        "humidity": data["main"]["humidity"],
                        "pressure": data["main"]["pressure"],
                        "weather": data["weather"][0]["description"],
                        "weather_main": data["weather"][0]["main"],
                        "wind_speed": round(data["wind"]["speed"], 1),
                        "wind_deg": data["wind"].get("deg", 0),
                        "clouds": data["clouds"]["all"],
                        "visibility": data.get("visibility"),  # 新增：能见度
                        "sys": data.get("sys", {}),  # 新增：系统数据（含日出日落）
                        "icon": data["weather"][0]["icon"]
                    }
        except Exception as e:
            logger.error(f"获取天气数据异常: {e}")
            return None
