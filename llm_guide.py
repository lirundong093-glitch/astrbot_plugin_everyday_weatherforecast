import json
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional
from astrbot.api import logger

try:
    import aiohttp
except ImportError:
    aiohttp = None


class LLMGuideGenerator:
    """LLM 天气指南生成器（支持节假日问候）"""

    # 和风天气指数类型映射表（已根据官方文档修正）
    INDEX_NAMES = {
        "1": "运动指数",
        "2": "洗车指数",
        "3": "穿衣指数",
        "4": "钓鱼指数",
        "5": "紫外线指数",
        "6": "旅游指数",
        "7": "花粉过敏指数",
        "8": "舒适度指数",
        "9": "感冒指数",
        "10": "空气污染扩散条件指数",
        "11": "空调开启指数",
        "12": "太阳镜指数",
        "13": "化妆指数",
        "14": "晾晒指数",
        "15": "交通指数",
        "16": "防晒指数",
    }

    def __init__(self, provider: str = "openai", api_key: str = "", base_url: str = "", model: str = "gpt-4o-mini", holiday_checker=None):
        self.provider = provider
        self.api_key = api_key
        self.base_url = base_url or "https://api.openai.com/v1/chat/completions"
        self.model = model
        self.holiday_checker = holiday_checker

    def _get_weekday(self) -> str:
        """获取当前星期数（中文）"""
        weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        return weekdays[datetime.now().weekday()]

    async def _build_prompt(self, city: str, weather_data: Dict[str, Any]) -> str:
        """构建发送给 LLM 的提示词（包含节假日问候）"""
        today = datetime.now()
        weekday = self._get_weekday()

        # ---------- 节假日判断 ----------
        holiday_name = ""
        is_holiday = False
        if self.holiday_checker:
            is_holiday, holiday_name = await self.holiday_checker.check_today()

        if is_holiday and holiday_name:
            greeting = f"今天是{holiday_name}，{weekday}！🎉"
            holiday_message = "难得的假期，好好享受这放松的时光吧 (◕‿◕)！"
            rest_day_text = ""
            cheer_text = ""
        else:
            greeting = f"今天是{weekday}，早上好！☀️"
            days_until_saturday = (5 - today.weekday()) % 7
            if days_until_saturday == 0:
                rest_day_text = "今天是休息日！"
                cheer_text = "好好享受这难得的放松时光吧 (◕‿◕)！"
            elif days_until_saturaday == 5:
                rest_day_text = f"今天是周一"
                cheer_text = "新的一周开始了，让我们一起加油吧b(￣▽￣)d！"
            elif days_until_saturaday == 4:
                rest_day_text = f"今天是周二"
                cheer_text = "怎么才周二？已经开始想念周末了(┬┬﹏┬┬)！"
            elif days_until_saturaday == 3:
                rest_day_text = f"今天是周三"
                cheer_text = "工作日马上就要过去一半了，如果工作有点疲劳的话就休息一下吧(￣﹃￣)！"
            else:
                rest_day_text = f"距离休息日还有 {days_until_saturday} 天"
                cheer_text = "加油，再坚持一下，美好的周末就在眼前 (•̀ᴗ•́)و！"
            holiday_message = ""

        # 提取天气数据
        temp = weather_data.get("temperature", 0)
        temp_max = weather_data.get("temp_max", 0)
        temp_min = weather_data.get("temp_min", 0)
        feels_like = weather_data.get("feels_like", 0)
        weather_text = weather_data.get("weather", "未知")
        humidity = weather_data.get("humidity", 0)
        wind_dir = weather_data.get("wind_dir", "")
        wind_speed = weather_data.get("wind_speed", 0)
        uv_index = weather_data.get("uv_index", 0)
        aqi = weather_data.get("aqi", "")
        aqi_category = weather_data.get("aqi_category", "")

        # 提取舒适度和花粉过敏指数
        comfort_text = "暂无"
        pollen_text = "暂无"
        indices_text = ""
        for idx in weather_data.get("indices", []):
            idx_type = str(idx.get("type", ""))
            idx_category = idx.get("category", "")
            idx_text = idx.get("text", "")         
            idx_name = self.INDEX_NAMES.get(idx_type, f"指数{idx_type}")
            if idx_category or idx_text:
                indices_text += f"- {idx_name}: {idx_category}，{idx_text}\n"

        # 构建完整提示词
        prompt = f"""你是一个贴心的天气助手，请根据以下天气信息，为用户生成一段简洁、亲切的今日天气指南（不超过200字）。

{greeting}
"""
        if rest_day_text:
            prompt += f"{rest_day_text}。{cheer_text}\n\n"
        if holiday_message:
            prompt += f"{holiday_message}\n\n"

        prompt += f"""下面是今日天气信息：
城市：{city}
天气状况：{weather_text}
当前温度：{temp}°C
体感温度：{feels_like}°C
今日温度范围：{temp_min}°C ~ {temp_max}°C
相对湿度：{humidity}%
风向风速：{wind_dir} {wind_speed} km/h
紫外线强度：{uv_index}
空气质量：{aqi} ({aqi_category})

其他生活指数参考：
{indices_text if indices_text else "无"}

请结合今天的天气状况和星期数，用亲切、活泼的语气给用户一些实用的生活建议（比如穿衣、出行、是否适合晾晒/运动等）。
要求：
1. 适当使用 emoji 和颜文字，让回复更生动（例如 🌞☁️🌧️💨 (◕‿◕) (•̀ᴗ•́)و）。
2. 根据气温和天气给出具体的穿衣建议。
3. 如果空气质量不佳或紫外线强，要提醒用户防护。
4. 语言简洁，分段清晰，不要用 markdown 格式。"""

        return prompt

    async def generate_guide(self, city: str, weather_data: Dict[str, Any]) -> Optional[str]:
        """调用 LLM 生成天气指南"""
        if not aiohttp:
            logger.error("aiohttp 未安装，无法调用 LLM")
            return None

        prompt = await self._build_prompt(city, weather_data)

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "你是一个贴心的天气助手，回复要亲切、简洁，使用适当的 emoji 和颜文字。"},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 500
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.base_url, headers=headers, json=payload) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        logger.error(f"LLM API 请求失败: {resp.status}, {error_text}")
                        return None

                    data = await resp.json()
                    return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            logger.error(f"LLM 生成指南异常: {e}")
            return None
