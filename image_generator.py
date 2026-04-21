import io
import os
import platform
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from typing import Dict, Any, Optional, List
from astrbot.api import logger


class WeatherImageGenerator:
    """天气图片生成器 - 使用和风天气官方图标"""

    def __init__(self):
        # 跨平台字体搜索
        self.font_search_paths = self._build_font_paths()
        self.font_path = self._find_chinese_font()
        if not self.font_path:
            logger.warning("未找到任何中文字体，中文可能显示异常。")
        else:
            logger.info(f"已加载中文字体：{self.font_path}")

        # 预加载常用字号
        self.font_temp_large = self._load_font(72)
        self.font_city = self._load_font(26)
        self.font_weather = self._load_font(22)
        self.font_label = self._load_font(18)
        self.font_value = self._load_font(18)
        self.font_small = self._load_font(14)

        # 图标目录（用户下载的官方图标位置）
        self.icon_dir = os.path.expanduser("~/icons")
        if not os.path.exists(self.icon_dir):
            logger.warning(f"图标目录不存在: {self.icon_dir}，请确保已下载和风天气官方图标")

    def _build_font_paths(self) -> List[str]:
        paths = []
        system = platform.system()
        if system == "Linux":
            paths.extend([
                "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
                "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
                "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                os.path.expanduser("~/.fonts/wqy-microhei.ttf"),
            ])
        elif system == "Windows":
            windir = os.environ.get("WINDIR", "C:\\Windows")
            paths.extend([
                os.path.join(windir, "Fonts", "msyh.ttc"),
                os.path.join(windir, "Fonts", "simhei.ttf"),
            ])
        elif system == "Darwin":
            paths.extend([
                "/System/Library/Fonts/PingFang.ttc",
                "/System/Library/Fonts/STHeiti Light.ttc",
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

    def _is_daytime(self, icon_code: str) -> bool:
        """根据图标代码判断昼夜（1xx 为白天，15x 为夜晚）"""
        if not icon_code:
            return True
        code = int(icon_code)
        return 100 <= code < 150

    def _get_icon_path(self, icon_code: str) -> str:
        """获取图标文件路径"""
        if not icon_code:
            icon_code = "100"
        # 和风天气图标命名规则：{code}.svg
        icon_file = os.path.join(self.icon_dir, f"{icon_code}.svg")
        if os.path.exists(icon_file):
            return icon_file
        # 降级到默认图标
        return os.path.join(self.icon_dir, "999.svg")

    def _load_icon(self, icon_code: str, size: int = 100) -> Optional[Image.Image]:
        """加载并缩放图标（支持 SVG 自动转 PNG）"""
        icon_path = self._get_icon_path(icon_code)
        if not os.path.exists(icon_path):
            logger.warning(f"图标文件不存在: {icon_path}")
            return None
    
        try:
            # 判断文件扩展名
            ext = os.path.splitext(icon_path)[1].lower()
            
            if ext == '.svg':
                # 使用 cairosvg 将 SVG 转换为 PNG 字节流
                import cairosvg
                png_bytes = cairosvg.svg2png(url=icon_path, output_width=size, output_height=size)
                icon = Image.open(io.BytesIO(png_bytes))
            else:
                # 直接打开 PNG 等格式
                icon = Image.open(icon_path)
                icon = icon.resize((size, size), Image.Resampling.LANCZOS)
        
            # 确保图标为 RGBA 模式（支持透明背景）
            if icon.mode != 'RGBA':
                icon = icon.convert('RGBA')
            return icon
        except ImportError:
            logger.error("cairosvg 未安装，无法加载 SVG 图标。请执行: pip install cairosvg")
            return None
        except Exception as e:
            logger.error(f"加载图标失败 {icon_code}: {e}")
            return None

    def generate(self, weather_data: Dict[str, Any]) -> bytes:
        width, height = 800, 400
        img = Image.new("RGB", (width, height))
        draw = ImageDraw.Draw(img)

        icon_code = weather_data.get("icon", "100")
        is_day = self._is_daytime(icon_code)

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

        for x in range(width):
            ratio = x / width
            r = int(left_color[0] + (right_color[0] - left_color[0]) * ratio)
            g = int(left_color[1] + (right_color[1] - left_color[1]) * ratio)
            b = int(left_color[2] + (right_color[2] - left_color[2]) * ratio)
            draw.line([(x, 0), (x, height)], fill=(r, g, b))

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

        sunrise = weather_data.get("sunrise", "")
        sunset = weather_data.get("sunset", "")
        if sunrise and sunset:
            sun_str = f"日出 {sunrise}  日落 {sunset}"
            draw.text((left_x, 270), sun_str, fill=text_secondary, font=self.font_small)

        # 右侧详细信息
        right_x = 440
        y_start = 60
        line_gap = 45

        wind_dir = weather_data.get("wind_dir", "")
        wind_speed = weather_data.get("wind_speed", 0)
        wind_text = f"{wind_dir} {wind_speed} km/h" if wind_dir else f"{wind_speed} km/h"

        details = [
            ("湿度", f"{weather_data.get('humidity', 0)}%"),
            ("风速", wind_text),
            ("气压", f"{weather_data.get('pressure', 0)} hPa"),
            ("云量", f"{weather_data.get('cloud', 0)}%"),
        ]

        vis = weather_data.get("vis", 0)
        if vis:
            details.append(("能见度", f"{vis:.1f} km"))

        aqi = weather_data.get("aqi", "")
        if aqi:
            aqi_cat = weather_data.get("aqi_category", "")
            aqi_display = f"{aqi} ({aqi_cat})" if aqi_cat else str(aqi)
            details.append(("AQI", aqi_display))

        uv = weather_data.get("uv_index", 0)
        if uv:
            details.append(("紫外线", str(uv)))

        for i, (label, value) in enumerate(details):
            y = y_start + i * line_gap
            draw.text((right_x, y), label + ":", fill=text_main, font=self.font_label)
            bbox = draw.textbbox((0, 0), value, font=self.font_value)
            value_width = bbox[2] - bbox[0]
            draw.text((right_x + 220 - value_width, y), value, fill=text_main, font=self.font_value)

        # 右上角加载和风天气官方图标
        icon = self._load_icon(icon_code, size=100)
        if icon:
            icon_x = width - 130
            icon_y = 30
            img.paste(icon, (icon_x, icon_y), icon if icon.mode == "RGBA" else None)
        else:
            logger.warning(f"无法加载图标: {icon_code}")

        draw.line([(30, height - 30), (width - 30, height - 30)], fill=text_secondary, width=1)

        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")
        img_bytes.seek(0)
        return img_bytes.getvalue()
