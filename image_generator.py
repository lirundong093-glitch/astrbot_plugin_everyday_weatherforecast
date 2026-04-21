import io
from PIL import Image, ImageDraw, ImageFont
from typing import Dict, Any
import os


class WeatherImageGenerator:
    """天气图片生成器"""

    def __init__(self):
        # 字体路径，可根据系统调整
        self.font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/System/Library/Fonts/PingFang.ttc",
            "C:/Windows/Fonts/msyh.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"
        ]
        self._load_fonts()

    def _load_fonts(self):
        """加载中文字体"""
        font_path = None
        for path in self.font_paths:
            if os.path.exists(path):
                font_path = path
                break

        if font_path:
            try:
                self.font_large = ImageFont.truetype(font_path, 48)
                self.font_medium = ImageFont.truetype(font_path, 32)
                self.font_small = ImageFont.truetype(font_path, 24)
                self.font_tiny = ImageFont.truetype(font_path, 18)
            except:
                self._use_default_font()
        else:
            self._use_default_font()

    def _use_default_font(self):
        """使用默认字体（可能不支持中文）"""
        self.font_large = ImageFont.load_default()
        self.font_medium = ImageFont.load_default()
        self.font_small = ImageFont.load_default()
        self.font_tiny = ImageFont.load_default()

    def _wind_direction(self, deg: int) -> str:
        """将风向角度转换为中文方向"""
        directions = ["北", "东北", "东", "东南", "南", "西南", "西", "西北"]
        idx = round(deg / 45) % 8
        return directions[idx]

    def generate(self, weather_data: Dict[str, Any]) -> bytes:
        """
        生成天气图片，返回PNG格式的bytes
        """
        # 创建图片画布 (600x400)
        width, height = 600, 400
        img = Image.new("RGB", (width, height), color=(240, 248, 255))
        draw = ImageDraw.Draw(img)

        # 绘制渐变背景
        for i in range(height):
            r = int(240 - i * 0.05)
            g = int(248 - i * 0.02)
            b = 255
            draw.line([(0, i), (width, i)], fill=(max(0, r), max(0, g), b))

        # 绘制标题
        city = weather_data.get("city", "未知")
        title = f"🌤️ {city} 天气预报"
        bbox = draw.textbbox((0, 0), title, font=self.font_large)
        title_width = bbox[2] - bbox[0]
        draw.text(((width - title_width) // 2, 20), title, fill=(30, 30, 30), font=self.font_large)

        # 绘制分隔线
        draw.line([(50, 80), (width - 50, 80)], fill=(200, 200, 200), width=2)

        # 当前温度（大号显示）
        temp = weather_data.get("temperature", 0)
        temp_text = f"{temp}°C"
        bbox = draw.textbbox((0, 0), temp_text,
                             font=ImageFont.truetype(self.font_paths[0] if os.path.exists(self.font_paths[0]) else None,
                                                     64))
        temp_width = bbox[2] - bbox[0]
        draw.text(((width // 2 - temp_width) // 2, 100), temp_text, fill=(220, 20, 60), font=self.font_large)

        # 天气描述
        weather_desc = weather_data.get("weather", "未知")
        draw.text((width // 2 + 20, 110), weather_desc, fill=(100, 100, 100), font=self.font_medium)

        # 绘制详细信息（左侧）
        y_start = 180
        line_height = 35

        details = [
            ("🌡️ 体感温度", f"{weather_data.get('feels_like', 0)}°C"),
            ("💧 湿度", f"{weather_data.get('humidity', 0)}%"),
            ("🌬️ 风速", f"{weather_data.get('wind_speed', 0)} m/s"),
            ("🧭 风向", self._wind_direction(weather_data.get('wind_deg', 0))),
            ("📊 气压", f"{weather_data.get('pressure', 0)} hPa"),
            ("☁️ 云量", f"{weather_data.get('clouds', 0)}%"),
        ]

        for i, (label, value) in enumerate(details):
            y = y_start + i * line_height
            draw.text((50, y), label, fill=(80, 80, 80), font=self.font_small)
            # 右对齐数值
            bbox = draw.textbbox((0, 0), value, font=self.font_small)
            value_width = bbox[2] - bbox[0]
            draw.text((width - 50 - value_width, y), value, fill=(50, 50, 50), font=self.font_small)

        # 绘制天气图标提示
        draw.text((50, height - 30), f"数据来源: OpenWeather", fill=(150, 150, 150), font=self.font_tiny)

        # 转换为bytes
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")
        img_bytes.seek(0)
        return img_bytes.getvalue()