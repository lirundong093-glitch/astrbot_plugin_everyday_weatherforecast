import aiohttp
import asyncio
from typing import Optional, Tuple, Dict, Any
from astrbot.api import logger


class QWeatherClient:
    """和风天气 API 客户端 (支持 API Host)"""

    def __init__(self, api_key: str, api_host: str = ""):
        self.api_key = api_key
        self.api_host = api_host.rstrip('/')
        self._build_endpoints()

    def _build_endpoints(self):
        """根据 API Host 动态构建完整的端点 URL"""
        if self.api_host:
            self.GEO_URL = f"https://{self.api_host}/geo/v2/city/lookup"
            self.WEATHER_NOW_URL = f"https://{self.api_host}/v7/weather/now"
            self.WEATHER_DAILY_URL = f"https://{self.api_host}/v7/weather/7d"
            self.AIR_QUALITY_URL = f"https://{self.api_host}/v7/air/now"
            self.INDICES_URL = f"https://{self.api_host}/v7/indices/1d"
        else:
            # 降级：如果未配置 API Host，则使用开发环境共享地址（不建议用于生产）
            logger.warning("未配置 API Host，将使用开发环境共享地址，可能影响稳定性。")
            self.GEO_URL = "https://devapi.qweather.com/geo/v2/city/lookup"
            self.WEATHER_NOW_URL = "https://devapi.qweather.com/v7/weather/now"
            self.WEATHER_DAILY_URL = "https://devapi.qweather.com/v7/weather/7d"
            self.AIR_QUALITY_URL = "https://devapi.qweather.com/v7/air/now"
            self.INDICES_URL = "https://devapi.qweather.com/v7/indices/1d"

    # 需要的生活指数类型 ID (按用户需求)
    INDICES_TYPES = "1,2,5,6,7,8,10,12,13,14"

    async def get_location_id(self, city_name: str) -> Optional[Tuple[str, str]]:
        """通过城市名获取 Location ID 和显示名称"""
        params = {
            "location": city_name,
            "key": self.api_key,
            "number": 1
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.GEO_URL, params=params) as resp:
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
        params = {
            "location": location_id,
            "key": self.api_key
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.WEATHER_NOW_URL, params=params) as resp:
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
        params = {
            "location": location_id,
            "key": self.api_key
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.WEATHER_DAILY_URL, params=params) as resp:
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
        params = {
            "location": location_id,
            "key": self.api_key
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.AIR_QUALITY_URL, params=params) as resp:
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
        params = {
            "location": location_id,
            "key": self.api_key,
            "type": self.INDICES_TYPES
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.INDICES_URL, params=params) as resp:
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

        # 2. 并发请求所有 API
        async with asyncio.TaskGroup() as tg:
            task_now = tg.create_task(self.get_weather_now(location_id))
            task_daily = tg.create_task(self.get_weather_daily(location_id))
            task_aqi = tg.create_task(self.get_air_quality(location_id))
            task_indices = tg.create_task(self.get_indices(location_id))

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

        # 构建统一的返回结构（兼容原有 image_generator 的字段名）
        result = {
            "city": display_name,
            # 实时天气
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
            # 每日预报（今日）
            "temp_max": float(today.get("tempMax", 0)),
            "temp_min": float(today.get("tempMin", 0)),
            "sunrise": today.get("sunrise", ""),
            "sunset": today.get("sunset", ""),
            "moonrise": today.get("moonrise", ""),
            "moonset": today.get("moonset", ""),
            "moon_phase": today.get("moonPhase", ""),
            "uv_index": today.get("uvIndex", 0),
            # 空气质量
            "aqi": aqi_data.get("now", {}).get("aqi", "") if aqi_data else "",
            "aqi_category": aqi_data.get("now", {}).get("category", "") if aqi_data else "",
            # 生活指数
            "indices": indices_data.get("daily", []) if indices_data else [],
            # 原始数据保留
            "raw_daily": daily_list,
            "raw_now": now_data,
        }

        return result
