# api_client.py (修改后完整内容)
import aiohttp
import asyncio
import csv
import os
from typing import Optional, Tuple, Dict, Any
from astrbot.api import logger


class QWeatherClient:
    """和风天气 API 客户端（支持 TomTom 格式自动转换）"""

    def __init__(self, api_key: str, api_host: str = "", plugin_dir: str = ""):
        self.api_key = api_key
        raw_host = api_host.strip() if api_host else ""
        self.api_host = raw_host.replace("https://", "").replace("http://", "").rstrip('/')
        self.plugin_dir = plugin_dir
        self._city_id_map = {}
        self._load_city_list()
        self._build_endpoints()

    def _load_city_list(self):
        csv_path = os.path.join(self.plugin_dir, "China-City-List-latest.csv")
        if not os.path.exists(csv_path):
            logger.warning(f"城市列表文件不存在: {csv_path}，将仅依赖 GeoAPI 查询")
            return
        try:
            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                next(reader, None)
                for row in reader:
                    if len(row) >= 3:
                        loc_id = row[0].strip()
                        city_zh = row[2].strip()
                        if loc_id and city_zh:
                            self._city_id_map[city_zh] = loc_id
            logger.info(f"已加载 {len(self._city_id_map)} 个城市 Location ID 映射")
        except Exception as e:
            logger.error(f"加载城市列表失败: {e}")

    def _build_endpoints(self):
        if not self.api_host:
            logger.error("未配置 API Host，请使用 /weather_config api_host 进行配置。")
            self.GEO_URL = ""
            self.WEATHER_NOW_URL = ""
            self.WEATHER_DAILY_URL = ""
            self.AIR_DAILY_URL = ""
            self.INDICES_URL = ""
            return
        self.GEO_URL = f"https://{self.api_host}/geo/v2/city/lookup"
        self.WEATHER_NOW_URL = f"https://{self.api_host}/v7/weather/now"
        self.WEATHER_DAILY_URL = f"https://{self.api_host}/v7/weather/3d"
        self.AIR_DAILY_URL = f"https://{self.api_host}/airquality/v1/daily/"
        self.INDICES_URL = f"https://{self.api_host}/v7/indices/1d"
        logger.info(f"API 端点已构建，使用 Host: {self.api_host}")

    INDICES_TYPES = "1,3,5,6,7,8,9,10,11,14,15,16"

    async def _request(self, url: str, params: dict) -> Optional[Dict[str, Any]]:
        """统一请求，自动兼容和风标准格式与 TomTom 格式"""
        if not url:
            logger.error("请求 URL 为空，请检查 API Host 配置")
            return None

        headers = {
            "X-QW-Api-Key": self.api_key,
            "User-Agent": "AstrBot-Weather-Plugin/2.0"
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, headers=headers) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        logger.error(f"API 请求失败: {url} 状态码: {resp.status}, 响应: {error_text[:300]}")
                        return None
                    data = await resp.json()

                    # 标准和风天气格式
                    if "code" in data:
                        if data.get("code") != "200":
                            logger.error(f"API 返回业务错误: {data}")
                            return None
                        return data

                    # TomTom 空气质素预报格式 (无 code，有 days)
                    if "days" in data:
                        logger.info("检测到 TomTom 格式响应，自动包装为和风兼容格式")
                        # 包装成和风标准结构
                        wrapped = {
                            "code": "200",
                            "updateTime": data.get("metadata", {}).get("tag", ""),
                            "tomtom_original": data  # 保留原始数据
                        }
                        return wrapped

                    # 其他未知格式
                    logger.warning(f"未知 API 响应格式，字段: {list(data.keys())}")
                    return data
        except Exception as e:
            logger.error(f"API 请求异常: {e}", exc_info=True)
            return None

    async def _get_location_id_from_geoapi(self, city_name: str) -> Optional[Tuple[str, str]]:
        if not self.GEO_URL:
            return None
        params = {"location": city_name, "number": 1}
        data = await self._request(self.GEO_URL, params)
        if not data:
            return None
        locations = data.get("location", [])
        if not locations:
            logger.warning(f"GeoAPI 未找到城市: {city_name}")
            return None
        loc = locations[0]
        return (loc.get("id"), loc.get("name", city_name))

    async def _get_lat_lon_from_geoapi(self, city_name: str) -> Tuple[Optional[float], Optional[float]]:
        if not self.GEO_URL:
            return None, None
        params = {"location": city_name, "number": 1}
        data = await self._request(self.GEO_URL, params)
        if not data:
            return None, None
        locations = data.get("location", [])
        if not locations:
            logger.warning(f"GeoAPI 未找到城市经纬度: {city_name}")
            return None, None
        loc = locations[0]
        lat = loc.get("lat")
        lon = loc.get("lon")
        if lat and lon:
            try:
                return float(lat), float(lon)
            except ValueError:
                return None, None
        return None, None

    async def get_location_id(self, city_name: str) -> Optional[Tuple[str, str]]:
        loc_id = self._city_id_map.get(city_name)
        if loc_id:
            logger.info(f"从本地 CSV 匹配到 LocationID: {city_name} -> {loc_id}")
            return (loc_id, city_name)
        if city_name.endswith("市"):
            city_without_suffix = city_name[:-1]
            loc_id = self._city_id_map.get(city_without_suffix)
            if loc_id:
                logger.info(f"从本地 CSV 模糊匹配到 LocationID: {city_name} -> {loc_id}")
                return (loc_id, city_name)
        logger.info(f"本地 CSV 未匹配到 {city_name}，尝试 GeoAPI 查询")
        return await self._get_location_id_from_geoapi(city_name)

    async def get_weather_now(self, location_id: str) -> Optional[Dict[str, Any]]:
        return await self._request(self.WEATHER_NOW_URL, {"location": location_id})

    async def get_weather_daily(self, location_id: str) -> Optional[Dict[str, Any]]:
        return await self._request(self.WEATHER_DAILY_URL, {"location": location_id})

    async def get_air_daily_forecast(self, lat: float, lon: float) -> Optional[Dict[str, Any]]:
        url = f"{self.AIR_DAILY_URL}/{lat:.2f}/{lon:.2f}"
        return await self._request(url, {})

    async def get_indices(self, location_id: str) -> Optional[Dict[str, Any]]:
        return await self._request(self.INDICES_URL, {"location": location_id, "type": self.INDICES_TYPES})

    async def get_complete_weather(self, city: str) -> Optional[Dict[str, Any]]:
        logger.info(f"开始查询天气: {city}")

        loc_result = await self.get_location_id(city)
        if not loc_result:
            logger.error(f"获取 LocationID 失败: {city}")
            return None
        location_id, display_name = loc_result
        logger.info(f"使用 LocationID: {location_id}, 显示名称: {display_name}")

        lat, lon = await self._get_lat_lon_from_geoapi(city)
        if lat is None or lon is None:
            logger.error(f"获取经纬度失败: {city}")
            return None
        logger.info(f"获取到经纬度: lat={lat:.2f}, lon={lon:.2f}")

        try:
            now_data, daily_data, aqi_data, indices_data = await asyncio.gather(
                self.get_weather_now(location_id),
                self.get_weather_daily(location_id),
                self.get_air_daily_forecast(lat, lon),
                self.get_indices(location_id),
                return_exceptions=True
            )
        except Exception as e:
            logger.error(f"并发请求 API 异常: {e}", exc_info=True)
            return None

        # 检查关键数据
        if isinstance(now_data, Exception) or now_data is None:
            logger.error("now API 数据无效")
            return None
        if isinstance(daily_data, Exception) or daily_data is None:
            logger.error("daily API 数据无效")
            return None

        now = now_data.get("now", {})
        daily_list = daily_data.get("daily", [])
        today = daily_list[0] if daily_list else {}

        # ---------- 空气质量解析：兼容 TomTom (cn-mee) 和和风 (qaqi) ----------
        aqi_value = ""
        aqi_category = ""
        if aqi_data and not isinstance(aqi_data, Exception):
            # 检查是否为 TomTom 格式（包装后的数据中有 tomtom_original）
            tomtom_original = aqi_data.get("tomtom_original")
            if tomtom_original and "days" in tomtom_original:
                # TomTom 格式：取第一个 days 的 indexes 中 code 为 "cn-mee" 的条目
                days_list = tomtom_original.get("days", [])
                if days_list:
                    indexes = days_list[0].get("indexes", [])
                    for idx in indexes:
                        if idx.get("code") == "cn-mee":
                            aqi_value = str(idx.get("aqi", ""))
                            aqi_category = idx.get("category", "")
                            break
            else:
                # 和风标准格式：查找 indexes 中 code 为 "qaqi"
                daily_air = aqi_data.get("daily", [])
                if daily_air:
                    indexes = daily_air[0].get("indexes", [])
                    for idx in indexes:
                        if idx.get("code") == "qaqi":
                            aqi_value = str(idx.get("aqi", ""))
                            aqi_category = idx.get("category", "")
                            break

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
            "precip": float(today.get("precip", 0)),
            "temp_max": float(today.get("tempMax", 0)),
            "temp_min": float(today.get("tempMin", 0)),
            "sunrise": today.get("sunrise", ""),
            "sunset": today.get("sunset", ""),
            "moonrise": today.get("moonrise", ""),
            "moonset": today.get("moonset", ""),
            "moon_phase": today.get("moonPhase", ""),
            "moon_icon": today.get("moonPhaseIcon", ""),
            "uv_index": today.get("uvIndex", 0),
            "aqi": aqi_value,
            "aqi_category": aqi_category,
            "indices": indices_data.get("daily", []) if indices_data and not isinstance(indices_data, Exception) else [],
            "raw_daily": daily_list,
            "raw_now": now_data,
        }

        return result
