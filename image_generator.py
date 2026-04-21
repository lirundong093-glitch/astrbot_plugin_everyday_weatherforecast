import io
import os
import sys
import platform
import math
from PIL import Image, ImageDraw, ImageFont
from typing import Dict, Any, Optional, List
from astrbot.api import logger

class WeatherImageGenerator:
    """天气图片生成器 (仿 open-weather-image 风格版)"""

    def __init__(self):
        # 1. 动态构建各平台中文字体优先搜索列表
        self.font_search_paths = self._build_font_paths()
        # 2. 尝试加载中文字体，失败则降级到默认字体并记录警告
        self.font_path = self._find_chinese_font()
        if not self.font_path:
            logger.warning("未找到任何中文字体，图片中的中文可能无法正常显示。")
        else:
            logger.info(f"已加载中文字体：{self.font_path}")

        # 3. 预加载不同大小的字体对象以提升性能
        self.font_large = self._load_font(48)    # 温度显示
        self.font_medium = self._load_font(24)   # 标题/正文
        self.font_small = self._load_font(18)    # 细节标签
        self.font_tiny = self._load_font(14)     # 日出日落时间

    def _build_font_paths(self) -> List[str]:
        """构建跨平台的中文字体搜索路径列表"""
        paths = []
        system = platform.system()

        # Linux / WSL / Docker
        if system == "Linux":
            paths.extend([
                "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
                "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
                "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
                os.path.expanduser("~/.fonts/wqy-microhei.ttf"),
                os.path.expanduser("~/.local/share/fonts/wqy-microhei.ttf"),
                "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            ])
        # Windows
        elif system == "Windows":
            windows_font_dir = os.environ.get("WINDIR", "C:\\Windows")
            paths.extend([
                os.path.join(windows_font_dir, "Fonts", "msyh.ttc"),
                os.path.join(windows_font_dir, "Fonts", "msyhbd.ttc"),
                os.path.join(windows_font_dir, "Fonts", "simhei.ttf"),
                os.path.join(windows_font_dir, "Fonts", "simsun.ttc"),
                os.path.join(windows_font_dir, "Fonts", "simkai.ttf"),
            ])
        # macOS
        elif system == "Darwin":
            paths.extend([
                "/System/Library/Fonts/PingFang.ttc",
                "/System/Library/Fonts/STHeiti Light.ttc",
                "/System/Library/Fonts/STHeiti Medium.ttc",
                "/Library/Fonts/Arial Unicode MS.ttf",
                "/System/Library/Fonts/Supplemental/Songti.ttc",
            ])

        # 通用备选
        paths.extend([
            os.environ.get("ASTRBOT_CHINESE_FONT_PATH", ""),
            "./fonts/simhei.ttf",
            "./fonts/msyh.ttc",
            "./fonts/wqy-microhei.ttf",
        ])
        return [p for p in paths if p]

    def _find_chinese_font(self) -> Optional[str]:
        """在预定义的搜索路径中查找第一个存在的中文字体"""
        for path in self.font_search_paths:
            if os.path.exists(path):
                try:
                    test_font = ImageFont.truetype(path, 12)
                    _ = test_font.getmask("中")
                    return path
                except Exception as e:
                    logger.debug(f"字体 {path} 存在但可能无效：{e}")
                    continue
        return None

    def _load_font(self, size: int) -> ImageFont.FreeTypeFont:
        """加载指定大小的字体，优先使用找到的中文字体"""
        if self.font_path:
            try:
                return ImageFont.truetype(self.font_path, size)
            except Exception as e:
                logger.error(f"加载字体 {self.font_path} 失败：{e}，使用默认字体")
        return ImageFont.load_default()

    def _wind_direction(self, deg: int) -> str:
        """将风向角度转换为中文方向"""
        directions = ["北", "东北", "东", "东南", "南", "西南", "西", "西北"]
        idx = round(deg / 45) % 8
        return directions[idx]

    def _format_time(self, timestamp: int, timezone_offset: int) -> str:
        """将时间戳转换为本地时间字符串（HH:MM）"""
        import datetime
        local_time = datetime.datetime.fromtimestamp(timestamp + timezone_offset)
        return local_time.strftime("%-H:%M" if platform.system() != "Windows" else "%#H:%M")

    def generate(self, weather_data: Dict[str, Any]) -> bytes:
        """
        生成天气图片，返回PNG格式的bytes
        """
        # 图片尺寸 (宽度 x 高度) - 与参考图片类似
        width, height = 450, 550
        img = Image.new("RGB", (width, height), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)

        # --- 绘制背景（浅灰色，模拟 open-weather-image 风格）---
        draw.rectangle([(0, 0), (width, height)], fill=(245, 245, 245))

        # --- 顶部：地点、日期 ---
        city = weather_data.get("city", "未知")
        country = weather_data.get("country", "")  # 需要在 api_client 中获取国家代码
        location = f"{city}, {country}" if country else city
        draw.text((20, 15), location, fill=(50, 50, 50), font=self.font_medium)

        # 获取并格式化日期时间
        import datetime
        dt = weather_data.get("dt")
        timezone_offset = weather_data.get("timezone", 0)
        if dt:
            local_time = datetime.datetime.fromtimestamp(dt + timezone_offset)
            date_str = local_time.strftime("%a %d %B // %-I:%M %p" if platform.system() != "Windows" else "%a %d %B // %#I:%M %p")
        else:
            date_str = "Date unavailable"
        draw.text((20, 45), date_str, fill=(100, 100, 100), font=self.font_small)

        # --- 当前温度（大号显示）---
        temp = weather_data.get("temperature", 0)
        temp_text = f"{temp:.0f}°C" if temp == int(temp) else f"{temp:.1f}°C"
        # 测量文本宽度以实现右对齐
        bbox = draw.textbbox((0, 0), temp_text, font=self.font_large)
        temp_width = bbox[2] - bbox[0]
        draw.text((width - temp_width - 20, 70), temp_text, fill=(50, 50, 50), font=self.font_large)

        # --- 体感温度 ---
        feels_like = weather_data.get("feels_like", 0)
        feels_text = f"体感 {feels_like:.0f}°C" if feels_like == int(feels_like) else f"体感 {feels_like:.1f}°C"
        bbox = draw.textbbox((0, 0), feels_text, font=self.font_small)
        feels_width = bbox[2] - bbox[0]
        draw.text((width - feels_width - 20, 130), feels_text, fill=(100, 100, 100), font=self.font_small)

        # --- 今日气温范围（最高/最低）---
        temp_max = weather_data.get("temp_max", 0)
        temp_min = weather_data.get("temp_min", 0)
        range_text = f"{temp_max:.0f}°C / {temp_min:.0f}°C"
        bbox = draw.textbbox((0, 0), range_text, font=self.font_small)
        range_width = bbox[2] - bbox[0]
        draw.text((width - range_width - 20, 155), range_text, fill=(100, 100, 100), font=self.font_small)

        # --- 天气描述 ---
        weather_desc = weather_data.get("weather", "未知")
        draw.text((20, 200), weather_desc, fill=(80, 80, 80), font=self.font_medium)

        # --- 分隔线 ---
        draw.line([(20, 235), (width - 20, 235)], fill=(200, 200, 200), width=1)

        # --- 详细信息（使用 Unicode 字符代替 Emoji）---
        y_start = 250
        line_height = 35

        # 1. 风速与风向
        wind_speed = weather_data.get("wind_speed", 0)
        wind_deg = weather_data.get("wind_deg", 0)
        wind_dir = self._wind_direction(wind_deg)
        wind_text = f"● 风速: {wind_speed} m/s ({wind_dir})"
        draw.text((20, y_start), wind_text, fill=(80, 80, 80), font=self.font_small)

        # 2. 湿度
        humidity = weather_data.get("humidity", 0)
        humidity_text = f"● 湿度: {humidity}%"
        draw.text((20, y_start + line_height), humidity_text, fill=(80, 80, 80), font=self.font_small)

        # 3. 气压
        pressure = weather_data.get("pressure", 0)
        pressure_text = f"● 气压: {pressure} hPa"
        draw.text((20, y_start + 2 * line_height), pressure_text, fill=(80, 80, 80), font=self.font_small)

        # 4. 云量
        clouds = weather_data.get("clouds", 0)
        clouds_text = f"● 云量: {clouds}%"
        draw.text((20, y_start + 3 * line_height), clouds_text, fill=(80, 80, 80), font=self.font_small)

        # 5. 能见度 (如果可用)
        visibility = weather_data.get("visibility")
        if visibility:
            vis_km = visibility / 1000
            vis_text = f"● 能见度: {vis_km:.1f} km"
            draw.text((20, y_start + 4 * line_height), vis_text, fill=(80, 80, 80), font=self.font_small)

        # --- 日出日落时间 ---
        sys_data = weather_data.get("sys", {})
        sunrise = sys_data.get("sunrise")
        sunset = sys_data.get("sunset")
        if sunrise and sunset:
            sunrise_str = self._format_time(sunrise, timezone_offset)
            sunset_str = self._format_time(sunset, timezone_offset)
            sun_text = f"日出: {sunrise_str}  ·  日落: {sunset_str}"
            bbox = draw.textbbox((0, 0), sun_text, font=self.font_tiny)
            sun_width = bbox[2] - bbox[0]
            draw.text(((width - sun_width) // 2, height - 25), sun_text, fill=(100, 100, 100), font=self.font_tiny)

        # --- 注意：已移除“数据来源: OpenWeather” ---

        # 转换为bytes
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")
        img_bytes.seek(0)
        return img_bytes.getvalue()
