import io
import os
import platform
import xml.etree.ElementTree as ET
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from typing import Dict, Any, Optional, List, Tuple
from astrbot.api import logger


class WeatherImageGenerator:
    """天气图片生成器 - 左右分栏布局，动态昼夜配色，SVG 图标动态改色"""

    def __init__(self, plugin_dir: str = ""):
        # 图标目录：插件目录下的 icons 文件夹
        if plugin_dir:
            self.icon_dir = os.path.join(plugin_dir, "icons")
        else:
            self.icon_dir = os.path.expanduser("~/icons")
        
        if not os.path.exists(self.icon_dir):
            logger.warning(f"图标目录不存在: {self.icon_dir}，图标将无法显示")
        else:
            logger.info(f"图标目录已设置: {self.icon_dir}")

        # 跨平台字体搜索
        self.font_search_paths = self._build_font_paths()
        self.font_path = self._find_chinese_font()
        if not self.font_path:
            logger.warning("未找到任何中文字体，中文可能显示异常。")
        else:
            logger.info(f"已加载中文字体：{self.font_path}")

        # 预加载常用字号
        self.font_temp_main = self._load_font(68)
        self.font_temp_feels = self._load_font(24)
        self.font_city = self._load_font(32)
        self.font_date = self._load_font(18)
        self.font_weather = self._load_font(22)
        self.font_label = self._load_font(18)
        self.font_value = self._load_font(18)
        self.font_moon = self._load_font(18)

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

    # ---------- 增强的昼夜判断 ----------
    def _is_daytime(self, weather_data: Dict[str, Any]) -> bool:
        cloud = weather_data.get("cloud", 0)
        dt = weather_data.get("dt")
        sys = weather_data.get("sys", {})
        sunrise = sys.get("sunrise")
        sunset = sys.get("sunset")
        is_day_by_time = False
        if dt and sunrise and sunset:
            is_day_by_time = sunrise <= dt <= sunset
        else:
            icon = weather_data.get("icon", "")
            is_day_by_time = icon.endswith("d")
        return is_day_by_time and cloud < 70

    # ---------- SVG 图标加载并动态改色 ----------
    def _load_icon(self, icon_code: str, size: int, color_hex: str) -> Optional[Image.Image]:
        """加载 SVG 图标，修改填充色，转换为 PIL Image"""
        if not icon_code:
            return None

        svg_path = os.path.join(self.icon_dir, f"{icon_code}.svg")
        if not os.path.exists(svg_path):
            logger.warning(f"SVG 图标不存在: {svg_path}")
            return None

        try:
            with open(svg_path, 'r', encoding='utf-8') as f:
                svg_content = f.read()

            ET.register_namespace('', "http://www.w3.org/2000/svg")
            root = ET.fromstring(svg_content)
            
            def set_fill(element, color):
                if 'fill' in element.attrib:
                    element.set('fill', color)
                for child in element:
                    set_fill(child, color)
            set_fill(root, color_hex)

            modified_svg = ET.tostring(root, encoding='unicode')
            import cairosvg
            png_bytes = cairosvg.svg2png(bytestring=modified_svg.encode('utf-8'),
                                         output_width=size, output_height=size)
            icon = Image.open(io.BytesIO(png_bytes))
            if icon.mode != 'RGBA':
                icon = icon.convert('RGBA')
            return icon
        except ImportError:
            logger.error("cairosvg 未安装，无法加载 SVG 图标。请执行: pip install cairosvg")
            return None
        except Exception as e:
            logger.error(f"加载 SVG 图标失败 {icon_code}: {e}")
            return None

    # ---------- 核心绘图 ----------
    def generate(self, weather_data: Dict[str, Any]) -> bytes:
        width, height = 800, 480
        img = Image.new("RGB", (width, height), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)

        # 判断白天模式
        is_day_mode = self._is_daytime(weather_data)

        # 根据模式设定左右背景色、字体颜色、分割线颜色、图标颜色
        if is_day_mode:
            left_bg = (255, 217, 130)   # #FFD982
            right_bg = (94, 206, 246)   # #5ECEF6
            text_main = (0, 0, 0)
            text_secondary = (80, 80, 80)
            line_color = (191, 162, 97) # #BFA261
            icon_color = "#000000"      # 黑色
        else:
            left_bg = (37, 57, 92)      # #25395C
            right_bg = (28, 42, 79)     # #1C2A4F
            text_main = (255, 255, 255)
            text_secondary = (200, 200, 200)
            line_color = (92, 107, 133) # #5C6B85
            icon_color = "#FFFFFF"      # 白色

        # 分区
        right_width = width // 4
        left_width = width - right_width
        right_x_start = left_width

        # 绘制左右背景
        draw.rectangle([(0, 0), (left_width, height)], fill=left_bg)
        draw.rectangle([(right_x_start, 0), (width, height)], fill=right_bg)

        # 右侧大图标
        icon_code = weather_data.get("icon", "100")
        icon_size = 160
        icon = self._load_icon(icon_code, icon_size, icon_color)
        if icon:
            icon_x = right_x_start + (right_width - icon_size) // 2
            icon_y = (height - icon_size) // 2
            img.paste(icon, (icon_x, icon_y), icon)
        else:
            logger.warning(f"无法加载右侧大图标: {icon_code}")

        # 左侧布局
        left_padding = 25

        # 第1部分：城市、日期
        city = weather_data.get("city", "未知")
        draw.text((left_padding, 20), city, fill=text_main, font=self.font_city)

        now = datetime.now()
        date_str = now.strftime("%Y年%m月%d日 %H:%M")
        draw.text((left_padding, 58), date_str, fill=text_secondary, font=self.font_date)

        draw.line([(left_padding, 90), (left_width - left_padding, 90)], fill=line_color, width=1)

        # 第2部分：温度区域
        temp_y_start = 110
        temp = weather_data.get("temperature", 0)
        temp_str = f"{temp:.0f}°" if temp == int(temp) else f"{temp:.1f}°"
        draw.text((left_padding, temp_y_start), temp_str, fill=text_main, font=self.font_temp_main)

        feels = weather_data.get("feels_like", 0)
        feels_str = f"体感 {feels:.0f}°" if feels == int(feels) else f"体感 {feels:.1f}°"
        feels_x = left_padding + 130
        draw.text((feels_x, temp_y_start + 28), feels_str, fill=text_secondary, font=self.font_temp_feels)

        temp_max = weather_data.get("temp_max", 0)
        temp_min = weather_data.get("temp_min", 0)
        range_text = f"↑{temp_max:.0f}°  ↓{temp_min:.0f}°"
        draw.text((left_padding, temp_y_start + 85), range_text, fill=text_secondary, font=self.font_label)

        weather_text = weather_data.get("weather", "未知")
        small_icon = self._load_icon(icon_code, 40, icon_color)
        if small_icon:
            img.paste(small_icon, (left_padding, temp_y_start + 120), small_icon)
        draw.text((left_padding + 50, temp_y_start + 128), weather_text, fill=text_main, font=self.font_weather)

        line_y = temp_y_start + 175
        draw.line([(left_padding, line_y), (left_width - left_padding, line_y)], fill=line_color, width=1)

        # 第3部分：两列信息
        info_y_start = line_y + 20
        line_gap = 30

        wind_dir = weather_data.get("wind_dir", "")
        wind_speed = weather_data.get("wind_speed", 0)
        wind_deg = weather_data.get("wind_deg", 0)
        if not wind_dir and wind_deg:
            wind_dir = self._wind_direction(wind_deg)

        humidity = weather_data.get("humidity", 0)
        cloud = weather_data.get("cloud", 0)
        uv = weather_data.get("uv_index", 0)
        precip = weather_data.get("precip", 0)
        aqi = weather_data.get("aqi", "")
        aqi_category = weather_data.get("aqi_category", "")
        sunrise = weather_data.get("sunrise", "")
        sunset = weather_data.get("sunset", "")
        moon_phase = weather_data.get("moon_phase", "")
        moon_icon_code = weather_data.get("moon_icon", "")

        left_col_items = [
            ("风力", f"{wind_speed:.0f} km/h ({wind_dir})" if wind_dir else f"{wind_speed:.0f} km/h"),
            ("湿度", f"{humidity}%"),
            ("云量", f"{cloud}%"),
            ("紫外线", str(uv)),
            ("降水量", f"{precip} mm"),
            ("AQI", f"{aqi} {aqi_category}" if aqi else "无数据"),
        ]

        # 右列信息（仅日出日落）
        right_col_items = [
            ("日出", sunrise if sunrise else "--:--"),
            ("日落", sunset if sunset else "--:--"),
        ]

        left_col_x = left_padding
        for i, (label, value) in enumerate(left_col_items):
            y = info_y_start + i * line_gap
            draw.text((left_col_x, y), f"{label}:", fill=text_main, font=self.font_label)
            draw.text((left_col_x + 70, y), value, fill=text_main, font=self.font_value)

        right_col_x = left_padding + 250
        for i, (label, value) in enumerate(right_col_items):
            y = info_y_start + i * line_gap
            draw.text((right_col_x, y), f"{label}:", fill=text_main, font=self.font_label)
            draw.text((right_col_x + 55, y), value, fill=text_main, font=self.font_value)

        # 月相：位于日落下方，间距为 line_gap
        if moon_phase:
            moon_text_y = info_y_start + 2 * line_gap  # 日落后的下一行
            draw.text((right_col_x, moon_text_y), f"月相: {moon_phase}", fill=text_main, font=self.font_moon)
            # 月相图标放在文字下方，大小约两行字高 (32x32)
            if moon_icon_code:
                moon_icon = self._load_icon(moon_icon_code, 32, icon_color)
                if moon_icon:
                    icon_y = moon_text_y + 24  # 文字高度估算，留出间距
                    img.paste(moon_icon, (right_col_x, icon_y), moon_icon)

        # 转换为 bytes
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")
        img_bytes.seek(0)
        return img_bytes.getvalue()
