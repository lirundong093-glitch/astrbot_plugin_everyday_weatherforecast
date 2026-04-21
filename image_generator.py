import io
import os
import platform
import math
from datetime import datetime, timezone, timedelta
from PIL import Image, ImageDraw, ImageFont
from typing import Dict, Any, Optional, List
from astrbot.api import logger


class WeatherImageGenerator:
    """天气图片生成器 - 仿 open-weather-image 风格 (带天气图标)"""

    def __init__(self):
        # 跨平台字体搜索
        self.font_search_paths = self._build_font_paths()
        self.font_path = self._find_chinese_font()
        if not self.font_path:
            logger.warning("未找到任何中文字体，中文可能显示异常。")
        else:
            logger.info(f"已加载中文字体：{self.font_path}")

        # 预加载常用字号
        self.font_temp_large = self._load_font(72)      # 大温度数字
        self.font_city = self._load_font(26)            # 城市名
        self.font_weather = self._load_font(22)         # 天气描述
        self.font_label = self._load_font(18)           # 标签文字
        self.font_value = self._load_font(18)           # 数值
        self.font_small = self._load_font(14)           # 日出日落等

    # ---------- 字体查找与加载 ----------
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

    # ---------- 辅助函数 ----------
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

    # ---------- 核心绘图 (带天气图标) ----------
    def _draw_weather_icon(self, draw: ImageDraw.Draw, x: int, y: int, icon_code: str, is_day: bool):
        """根据 OpenWeather 图标代码在指定位置绘制天气图标"""
        size = 80  # 图标大小
        color = (50, 50, 50) if is_day else (240, 240, 240)  # 根据昼夜选择颜色

        # 根据图标代码的前两位数字判断天气类型
        code = icon_code[:2]

        # 晴天 (01d / 01n)
        if code == "01":
            # 绘制太阳/月亮
            bbox = [x, y, x + size, y + size]
            draw.ellipse(bbox, fill=color, outline=color, width=2)
            # 如果是晴天，添加光芒
            if is_day:
                center_x, center_y = x + size // 2, y + size // 2
                for angle in range(0, 360, 45):
                    rad = math.radians(angle)
                    dx = math.cos(rad) * (size // 2 + 5)
                    dy = math.sin(rad) * (size // 2 + 5)
                    draw.line([(center_x + dx, center_y + dy), (center_x + dx * 0.8, center_y + dy * 0.8)], fill=color, width=3)

        # 少云 (02d / 02n)
        elif code == "02":
            # 太阳/月亮 + 云
            # 云
            cloud_points = [
                (x + 20, y + 40), (x + 40, y + 20), (x + 60, y + 20),
                (x + 70, y + 40), (x + 60, y + 60), (x + 20, y + 60)
            ]
            draw.polygon(cloud_points, fill=color)
            # 露出部分太阳/月亮
            bbox = [x + 10, y + 10, x + 40, y + 40]
            draw.ellipse(bbox, fill=color)

        # 多云 (03d / 03n, 04d / 04n)
        elif code in ["03", "04"]:
            # 绘制两个云朵
            for offset in [(0, 10), (20, -5)]:
                cx, cy = x + 20 + offset[0], y + 40 + offset[1]
                draw.ellipse([cx - 15, cy - 15, cx + 15, cy + 15], fill=color)
                draw.ellipse([cx + 10, cy - 10, cx + 30, cy + 10], fill=color)
                draw.ellipse([cx - 25, cy - 5, cx - 5, cy + 15], fill=color)

        # 雨 (09d / 09n, 10d / 10n)
        elif code in ["09", "10"]:
            # 云 + 雨滴
            # 云
            draw.ellipse([x + 10, y + 20, x + 40, y + 50], fill=color)
            draw.ellipse([x + 30, y + 10, x + 60, y + 40], fill=color)
            draw.ellipse([x + 50, y + 20, x + 80, y + 50], fill=color)
            # 雨滴
            for i in range(3):
                drop_x = x + 20 + i * 15
                drop_y = y + 60 + i * 10
                draw.line([(drop_x, drop_y), (drop_x - 5, drop_y + 10)], fill=color, width=2)

        # 雷暴 (11d / 11n)
        elif code == "11":
            # 云 + 闪电
            draw.ellipse([x + 10, y + 20, x + 40, y + 50], fill=color)
            draw.ellipse([x + 30, y + 10, x + 60, y + 40], fill=color)
            draw.ellipse([x + 50, y + 20, x + 80, y + 50], fill=color)
            # 闪电
            points = [(x + 35, y + 55), (x + 25, y + 70), (x + 45, y + 75), (x + 35, y + 90)]
            draw.polygon(points, fill=(255, 200, 0))

        # 雪 (13d / 13n)
        elif code == "13":
            # 云 + 雪花
            draw.ellipse([x + 10, y + 20, x + 40, y + 50], fill=color)
            draw.ellipse([x + 30, y + 10, x + 60, y + 40], fill=color)
            draw.ellipse([x + 50, y + 20, x + 80, y + 50], fill=color)
            # 雪花 (简单的星形)
            for i in range(2):
                sx, sy = x + 25 + i * 20, y + 60 + i * 15
                draw.line([(sx - 5, sy), (sx + 5, sy)], fill=color, width=2)
                draw.line([(sx, sy - 5), (sx, sy + 5)], fill=color, width=2)
                draw.line([(sx - 3, sy - 3), (sx + 3, sy + 3)], fill=color, width=2)
                draw.line([(sx + 3, sy - 3), (sx - 3, sy + 3)], fill=color, width=2)

        # 雾/薄雾 (50d / 50n)
        elif code == "50":
            # 绘制水平线条
            for i in range(3):
                line_y = y + 30 + i * 15
                draw.line([(x + 10, line_y), (x + size - 10, line_y)], fill=color, width=3)

        # 默认：绘制一个通用云朵
        else:
            draw.ellipse([x + 10, y + 20, x + 40, y + 50], fill=color)
            draw.ellipse([x + 30, y + 10, x + 60, y + 40], fill=color)
            draw.ellipse([x + 50, y + 20, x + 80, y + 50], fill=color)

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
        draw.text((left_x, 25), city, fill=text_main, font=self.font_city)

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

        # --- 右半区：天气图标 + 详细信息 ---
        # 1. 绘制天气图标 (右上角)
        icon_code = weather_data.get("icon", "01d")
        icon_x = width - 120  # 图标 X 坐标
        icon_y = 30           # 图标 Y 坐标
        self._draw_weather_icon(draw, icon_x, icon_y, icon_code, is_day)

        # 2. 绘制详细信息 (纯文本标签，无 Emoji)
        right_x = 440
        y_start = 120  # 因为图标占用了顶部空间，下移
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
