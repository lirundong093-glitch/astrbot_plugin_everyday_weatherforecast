"""LLM 天气指南生成器 — 通过 AstrBot 内置 LLM Provider 生成。"""
from datetime import datetime
from typing import Dict, Any, Optional
from astrbot.api import logger


class LLMGuideGenerator:

    INDEX_NAMES = {
        "1": "运动指数", "2": "洗车指数", "3": "穿衣指数", "4": "钓鱼指数",
        "5": "紫外线指数", "6": "旅游指数", "7": "花粉过敏指数", "8": "舒适度指数",
        "9": "感冒指数", "10": "空气污染扩散条件指数", "11": "空调开启指数",
        "12": "太阳镜指数", "13": "化妆指数", "14": "晾晒指数",
        "15": "交通指数", "16": "防晒指数",
    }

    def __init__(self, context, holiday_checker=None, provider_id: str = ""):
        self.context = context
        self.holiday_checker = holiday_checker
        self.provider_id = provider_id

    def _get_weekday(self) -> str:
        weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        return weekdays[datetime.now().weekday()]

    async def _build_prompt(self, city: str, weather_data: Dict[str, Any]) -> str:
        today = datetime.now()
        weekday = self._get_weekday()
        holiday_name = ""
        is_holiday = False
        if self.holiday_checker:
            is_holiday, holiday_name = await self.holiday_checker.check_today()

        if is_holiday and holiday_name:
            greeting = f"今天是{holiday_name}！🎉"
            holiday_message = "难得的假期，好好享受这放松的时光吧 (◕‿◕)！"
            rest_day_text = cheer_text = ""
        else:
            greeting = f"今天是{weekday}，早上好！☀️"
            days_until_saturday = (6 - today.weekday()) % 7
            if days_until_saturday in (0, 1):
                rest_day_text = "今天是休息日！"
                cheer_text = "好好享受这难得的放松时光吧 (◕‿◕)！"
            elif days_until_saturday == 6:
                rest_day_text = "今天是周一"
                cheer_text = "新的一周开始了，让我们一起加油吧b(￣▽￣)d！"
            elif days_until_saturday == 5:
                rest_day_text = "今天是周二"
                cheer_text = "怎么才周二？已经开始想念周末了(┬┬﹏┬┬)！"
            elif days_until_saturday == 4:
                rest_day_text = "今天是周三"
                cheer_text = "工作日马上就要过去一半了，如果工作有点疲劳的话就休息一下吧(￣﹃￣)！"
            elif days_until_saturday == 3:
                rest_day_text = "今天是周四"
                cheer_text = "加油，再坚持一下，美好的周末就在眼前 (•̀ᴗ•́)و！"
            elif days_until_saturday == 2:
                rest_day_text = "今天是周五，距离休息日还有1天"
                cheer_text = "明天就是周末了，我已经迫不及待了( •̀ ω •́ )✧!"
            holiday_message = ""

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
        precip = weather_data.get("precip", "")
        aqi_category = weather_data.get("aqi_category", "")

        indices = weather_data.get("indices", [])
        lines = []
        for item in indices:
            name = self.INDEX_NAMES.get(item.get("type", ""), "未知")
            category = item.get("category", "")
            text = item.get("text", "")
            if name and text:
                lines.append(f"{name}：{category}（{text}）")
        indices_text = "\n".join(lines) if lines else ""

        prompt = f"""你是一个贴心的天气助手，请根据以下天气信息，为用户生成一段简洁、亲切的今日天气指南（不超过150字）。

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
今日降水量：{precip} mm
空气质量：{aqi} ({aqi_category})

其他生活指数参考：
{indices_text if indices_text else "无"}

请结合今天的天气状况和星期数，用亲切、活泼的语气给用户一些实用的生活建议。
要求：
1. 适当使用 emoji 和颜文字，让回复更生动。
2. 根据气温和天气给出具体的穿衣建议。
3. 如果空气质量不佳要提醒用户防护。
4. 紫外线强度除非大于10，否则不要给防晒建议。
5. 如果今天可能存在降雨或正在降雨，请提醒用户注意带伞。
6. 语言简洁，分段清晰，不要用 markdown 格式。
7. 文字分为三段发送（问好，天气状况，建议），段与段之间隔一行。
8. 总字数不超过150字。
"""
        return prompt

    async def generate_guide(self, city: str, weather_data: Dict[str, Any]) -> Optional[str]:
        """通过 AstrBot 内置 LLM Provider 生成天气指南。"""
        try:
            # 按 provider_id 选择提供商，留空则用默认
            provider = None
            if self.provider_id:
                provider = self.context.get_provider_by_id(self.provider_id)
            if provider is None:
                provider = self.context.get_using_provider()
            if provider is None:
                logger.error("[LLMGuide] 未配置 LLM Provider")
                return None

            prompt = await self._build_prompt(city, weather_data)
            resp = await provider.text_chat(
                prompt=prompt,
                session_id="weather_guide",
                max_tokens=10000,
            )
            if resp and resp.completion_text:
                return resp.completion_text.strip()
            logger.error("[LLMGuide] LLM 返回空内容")
            return None
        except Exception as e:
            logger.error(f"[LLMGuide] 生成指南异常: {e}")
            return None
