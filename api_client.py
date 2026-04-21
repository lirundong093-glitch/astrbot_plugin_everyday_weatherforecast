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
            "X-QW-Api-Key": self.api_key
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

    async def get_weather_daily(self, location_id: str) -> Optional[Dict[str, Any]]:
        """获取每日天气预报（7天）"""
        if not self.WEATHER_DAILY_URL:
            return None

        params = {"location": location_id}
        headers = {"X-QW-Api-Key": self.api_key}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.WEATHER_DAILY_URL, params=params, headers=headers) as resp:
                    if resp.status != 200:
                        logger.error(f"Weather Daily API 请求失败: {resp.status}")
                        return None

                    data = await resp.json()
                    if data.get("code") != "200":
                        logger.error(f"Weather Daily API 返回错误: {data.get('code')}")
                        return None

                    return data
        except Exception as e:
            logger.error(f"获取每日预报异常: {e}")
            return None

    async def get_air_quality(self, location_id: str) -> Optional[Dict[str, Any]]:
        """获取实时空气质量 AQI"""
        if not self.AIR_QUALITY_URL:
            return None

        params = {"location": location_id}
        headers = {"X-QW-Api-Key": self.api_key}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.AIR_QUALITY_URL, params=params, headers=headers) as resp:
                    if resp.status != 200:
                        logger.error(f"Air Quality API 请求失败: {resp.status}")
                        return None

                    data = await resp.json()
                    if data.get("code") != "200":
                        logger.error(f"Air Quality API 返回错误: {data.get('code')}")
                        return None

                    return data
        except Exception as e:
            logger.error(f"获取空气质量异常: {e}")
            return None

    async def get_indices(self, location_id: str) -> Optional[Dict[str, Any]]:
        """获取天气生活指数"""
        if not self.INDICES_URL:
            return None

        params = {
            "location": location_id,
            "type": self.INDICES_TYPES
        }
        headers = {"X-QW-Api-Key": self.api_key}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.INDICES_URL, params=params, headers=headers) as resp:
                    if resp.status != 200:
                        logger.error(f"Indices API 请求失败: {resp.status}")
                        return None

                    data = await resp.json()
                    if data.get("code") != "200":
                        logger.error(f"Indices API 返回错误: {data.get('code')}")
                        return None

                    return data
        except Exception as e:
            logger.error(f"获取生活指数异常: {e}")
            return None

    async def get_complete_weather(self, city: str) -> Optional[Dict[str, Any]]:
        """获取完整的天气数据，整合多个 API 返回"""
        # 1. 获取 Location ID
        loc_result = await self.get_location_id(city)
        if not loc_result:
            return None
        location_id, display_name = loc_result

        # 2. 并发请求所有 API (使用 Python 3.11+ 的 asyncio.TaskGroup)
        try:
            async with asyncio.TaskGroup() as tg:
                task_now = tg.create_task(self.get_weather_now(location_id))
                task_daily = tg.create_task(self.get_weather_daily(location_id))
                task_aqi = tg.create_task(self.get_air_quality(location_id))
                task_indices = tg.create_task(self.get_indices(location_id))
        except Exception as e:
            logger.error(f"并发请求 API 异常: {e}")
            return None

        now_data = task_now.result()
        daily_data = task_daily.result()
        aqi_data = task_aqi.result()
        indices_data = task_indices.result()

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
            "aqi": aqi_data.get("now", {}).get("aqi", "") if aqi_data else "",
            "aqi_category": aqi_data.get("now", {}).get("category", "") if aqi_data else "",
            "indices": indices_data.get("daily", []) if indices_data else [],
            "raw_daily": daily_list,
            "raw_now": now_data,
        }

        return result
