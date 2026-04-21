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
        """获取天气数据 (使用 One Call API 3.0 获取准确的高低温度)"""
        # 注意：需要将 API 端点更新为 3.0 版本以获取准确的每日温度
        # 如果你的 API 密钥已订阅 One Call 3.0，请使用此 URL
        # url = "https://api.openweathermap.org/data/3.0/onecall"
        # 如果未订阅，可暂时使用 2.5 版本 (同样支持每日预报)
        url = "https://api.openweathermap.org/data/2.5/onecall"
    
        params = {
            "lat": lat,
            "lon": lon,
            "exclude": "minutely,hourly",  # 排除不需要的数据以减小响应体积
            "appid": self.api_key,
            "units": "metric",
            "lang": "zh_cn"
        }
    
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as resp:
                    if resp.status != 200:
                        logger.error(f"Weather API 请求失败: {resp.status}")
                        return None

                    data = await resp.json()
                
                    # 提取当前天气数据
                    current = data.get("current", {})
                    daily = data.get("daily", [])
                
                    # 获取今日最高/最低气温
                    temp_max = current.get("temp", 0)
                    temp_min = current.get("temp", 0)
                    if daily:
                        today = daily[0]
                        temp_max = today.get("temp", {}).get("max", current.get("temp", 0))
                        temp_min = today.get("temp", {}).get("min", current.get("temp", 0))

                    return {
                        "city": data.get("timezone", "未知").split("/")[-1],  # 使用地理编码返回的城市名会更好
                        # 移除了 "country" 字段，从而在图片上只显示城市名
                        "dt": current.get("dt"),
                        "timezone": data.get("timezone_offset", 0),
                        "temperature": round(current.get("temp", 0), 1),
                        "feels_like": round(current.get("feels_like", 0), 1),
                        "temp_max": round(temp_max, 1),  # 从 daily 预报中获取的准确最高温度
                        "temp_min": round(temp_min, 1),  # 从 daily 预报中获取的准确最低温度
                        "humidity": current.get("humidity", 0),
                        "pressure": current.get("pressure", 0),
                        "weather": current.get("weather", [{}])[0].get("description", "未知"),
                        "weather_main": current.get("weather", [{}])[0].get("main", ""),
                        "wind_speed": round(current.get("wind_speed", 0), 1),
                        "wind_deg": current.get("wind_deg", 0),
                        "clouds": current.get("clouds", 0),
                        "visibility": current.get("visibility"),
                        "sys": {
                            "sunrise": current.get("sunrise"),
                            "sunset": current.get("sunset")
                        },
                        "icon": current.get("weather", [{}])[0].get("icon", "01d")
                    }
        except Exception as e:
            logger.error(f"获取天气数据异常: {e}")
            return None
