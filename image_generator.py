import io
import os
import platform
from datetime import datetime, timezone, timedelta
from PIL import Image, ImageDraw, ImageFont
from typing import Dict, Any, Optional, List
from astrbot.api import logger


class WeatherImageGenerator:
    """天气图片生成器 - 仿 open-weather-image 风格 (纯文本，无 Emoji)"""

    def __init__(self):
        self.font_search_paths = self._build_font_paths()
        self.font_path = self._find_chinese_font()
        if not self.font_path:
            logger.warning("未找到任何中文字体，中文可能显示异常。")
        else:
            logger.info(f"已加载中文字体：{self.font_path}")

        self.font_temp_large = self._load_font(72)      # 大温度数字
        self.font_city = self._load_font(26)            # 城市名
        self.font_weather = self._load_font(22)         # 天气描述
        self.font_label = self._load_font(18)           # 标签文字
        self.font_value = self._load_font(18)           # 数值
        self.font_small = self._load_font(14)           # 日出日落等

    def _build_font_paths(self) -> List[str]:
        paths = []
        system = platform.system()
        if system == "Linux":
            paths.extend([
                "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
                "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
                "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                os.path.expanduser("~/.fonts/wqy-microhei.ttf"),
            ])
        elif system == "Windows":
            windir = os.environ.get("WINDIR", "C:\\Windows")
            paths.extend([
                os.path.join(windir, "Fonts", "msyh.ttc"),
                os.path.join(windir, "Fonts", "simhei.ttf"),
                os.path.join(windir, "Fonts", "simsun.ttc"),
            ])
        elif system == "Darwin":
            paths.extend([
                "/System/Library/Fonts/PingFang.ttc",
                "/System/Library/Fonts/STHeiti Light.ttc",
                "/Library/Fonts/Arial Unicode MS.ttf",
            ])
        env_font = os.environ.get("ASTRBOT_CHINESE_FONT_PATH")
        if env_font:
            paths.insert(0, env_font)
        return [p for p in paths if p]

    def _find_chinese_font(self) -> Optional[str]:
        for path in self.font_search_paths:
            if os.path.exists(path):
                try:
                    ImageFont.truetype(path, 12).getmask("中")
                    return path
                except:
                    continue
        return None

    def _load_font(self, size: int) -> ImageFont.FreeTypeFont:
        if self.font_path:
            try:
                return ImageFont.truetype(self.font_path, size)
            except:
                pass
        return ImageFont.load_default()

    def _wind_direction(self, deg: int) -> str:
        dirs = ["北", "东北", "东", "东南", "南", "西南", "西", "西北"]
        return dirs[round(deg / 45) % 8]

    def _is_daytime(self, data: Dict[str, Any]) -> bool:
        dt = data.get("dt")
        sys = data.get("sys", {})
        sunrise = sys.get("sunrise")
        sunset = sys.get("sunset")
        if dt and sunrise and sunset:
            return sunrise <= dt <= sunset
        icon = data.get("icon", "")
        return icon.endswith("d")

    def _format_time(self, timestamp: int, tz_offset: int) -> str:
        if not timestamp:
            return "--:--"
        tz = timezone(timedelta(seconds=tz_offset))
        dt = datetime.fromtimestamp(timestamp, tz)
        if platform.system() == "Windows":
            return dt.strftime("%#H:%M")
        return dt.strftime("%-H:%M")

    def generate(self, weather_data: Dict[str, Any]) -> bytes:
        width, height = 800, 400
        img = Image.new("RGB", (width, height))
        draw = ImageDraw.Draw(img)

        # 昼夜主题色
        is_day = self._is_daytime(weather_data)
        if is_day:
            left_color = (255, 217, 130)
            right_color = (94, 206, 246)
            text_main = (20, 20, 20)
            text_secondary = (60, 60, 60)
        else:
            left_color = (37, 57, 92)
            right_color = (28, 42, 79)
            text_main = (240, 240, 240)
            text_secondary = (200, 200, 200)

        # 渐变背景
        for x in range(width):
            ratio = x / width
            r = int(left_color[0] + (right_color[0] - left_color[0]) * ratio)
            g = int(left_color[1] + (right_color[1] - left_color[1]) * ratio)
            b = int(left_color[2] + (right_color[2] - left_color[2]) * ratio)
            draw.line([(x, 0), (x, height)], fill=(r, g, b))

        # 左半区
        left_x = 30
        city = weather_data.get("city", "未知")
        country = weather_data.get("country", "")
        location = f"{city}, {country}" if country else city
        draw.text((left_x, 25), location, fill=text_main, font=self.font_city)

        temp = weather_data.get("temperature", 0)
        temp_str = f"{temp:.0f}°" if temp == int(temp) else f"{temp:.1f}°"
        draw.text((left_x, 70), temp_str, fill=text_main, font=self.font_temp_large)

        weather_desc = weather_data.get("weather", "未知")
        draw.text((left_x, 160), weather_desc, fill=text_secondary, font=self.font_weather)

        temp_max = weather_data.get("temp_max", 0)
        temp_min = weather_data.get("temp_min", 0)
        range_text = f"最高 {temp_max:.0f}°  最低 {temp_min:.0f}°"
        draw.text((left_x, 200), range_text, fill=text_secondary, font=self.font_label)

        feels = weather_data.get("feels_like", 0)
        feels_str = f"体感温度 {feels:.0f}°" if feels == int(feels) else f"体感温度 {feels:.1f}°"
        draw.text((left_x, 235), feels_str, fill=text_secondary, font=self.font_label)

        sys = weather_data.get("sys", {})
        sunrise = sys.get("sunrise")
        sunset = sys.get("sunset")
        tz_offset = weather_data.get("timezone", 0)
        if sunrise and sunset:
            sr = self._format_time(sunrise, tz_offset)
            ss = self._format_time(sunset, tz_offset)
            sun_str = f"日出 {sr}  日落 {ss}"
            draw.text((left_x, 270), sun_str, fill=text_secondary, font=self.font_small)

        # 右半区 (纯文本标签，无 Emoji)
        right_x = 440
        y_start = 60
        line_gap = 45

        details = [
            ("湿度", f"{weather_data.get('humidity', 0)}%"),
            ("风速", f"{weather_data.get('wind_speed', 0)} m/s"),
            ("风向", self._wind_direction(weather_data.get('wind_deg', 0))),
            ("气压", f"{weather_data.get('pressure', 0)} hPa"),
            ("云量", f"{weather_data.get('clouds', 0)}%"),
        ]
        visibility = weather_data.get("visibility")
        if visibility:
            vis_km = visibility / 1000
            details.append(("能见度", f"{vis_km:.1f} km"))

        for i, (label, value) in enumerate(details):
            y = y_start + i * line_gap
            draw.text((right_x, y), label + ":", fill=text_main, font=self.font_label)
            bbox = draw.textbbox((0, 0), value, font=self.font_value)
            value_width = bbox[2] - bbox[0]
            draw.text((right_x + 220 - value_width, y), value, fill=text_main, font=self.font_value)

        # 底部装饰线
        draw.line([(30, height - 30), (width - 30, height - 30)], fill=text_secondary, width=1)

        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")
        img_bytes.seek(0)
        return img_bytes.getvalue()
