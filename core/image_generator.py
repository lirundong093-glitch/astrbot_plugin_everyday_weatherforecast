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
        if plugin_dir:
            self.icon_dir = os.path.join(plugin_dir, "resource", "icons")
        else:
            self.icon_dir = os.path.expanduser("~/icons")
        
        if not os.path.exists(self.icon_dir):
            logger.warning(f"图标目录不存在: {self.icon_dir}，图标将无法显示")
        else:
            logger.info(f"图标目录已设置: {self.icon_dir}")

        self.font_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "resource", "DreamHanSans-W17.ttc"))
        logger.info(f"已加载中文字体：{self.font_path}")

        self.font_temp_main = self._load_font(68)
        self.font_temp_feels = self._load_font(24)
        self.font_city = self._load_font(32)
        self.font_date = self._load_font(18)
        self.font_weather = self._load_font(22)
        self.font_label = self._load_font(18)
        self.font_value = self._load_font(18)
        self.font_moon = self._load_font(18)

    # ---------- 字体加载 ----------

    def _load_font(self, size: int) -> ImageFont.FreeTypeFont:
        if self.font_path:
            try:
                return ImageFont.truetype(self.font_path, size)
            except:
                pass
        return ImageFont.load_default()

    def _wind_direction(self, deg: int) -> str:
        dirs = ["北", "东北", "东", "东南", "南", "西南", "西", "西北"]
        return dirs[int((deg + 22.5) // 45) % 8]

    def _get_theme(self, weather_data: Dict[str, Any]) -> str:
        """判断当前天气主题
        返回: "sunny_day" | "cloudy_day" | "rainy_day" | "night"
        """
        from datetime import datetime
        cloud = weather_data.get("cloud", 0)
        precip = weather_data.get("precip", 0)
        sunrise_str = weather_data.get("sunrise")
        sunset_str = weather_data.get("sunset")
        now = datetime.now()
        sunrise_time = datetime.strptime(sunrise_str, "%H:%M").time()
        sunset_time = datetime.strptime(sunset_str, "%H:%M").time()
        current_time = now.time()

        is_daytime = sunrise_time <= current_time <= sunset_time

        if not is_daytime:
            logger.debug(f"主题=night: 当前时间 {current_time} 不在日出日落之间")
            return "night"
        if precip > 0:
            logger.debug(f"主题=rainy_day: 白天 + 降水量 {precip} > 0")
            return "rainy_day"
        if cloud >= 70:
            logger.debug(f"主题=cloudy_day: 白天 + 云量 {cloud} >= 70% + 降水量为0")
            return "cloudy_day"
        logger.debug(f"主题=sunny_day: 白天 + 云量 {cloud} < 70%")
        return "sunny_day"

    def _load_icon(self, icon_code: str, size: int, color_hex: str, context: str = "") -> Optional[Image.Image]:
        if not icon_code:
            logger.debug(f"{context} 图标代码为空，跳过")
            return None

        svg_path = os.path.join(self.icon_dir, f"{icon_code}.svg")
        if not os.path.exists(svg_path):
            logger.warning(f"{context} SVG 图标不存在: {svg_path}")
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
            size_int = int(size)
            png_bytes = cairosvg.svg2png(bytestring=modified_svg.encode('utf-8'),
                                         output_width=size_int, output_height=size_int)
            icon = Image.open(io.BytesIO(png_bytes))
            if icon.mode != 'RGBA':
                icon = icon.convert('RGBA')
            logger.debug(f"{context} 图标加载成功: {icon_code}.svg")
            return icon
        except ImportError:
            logger.error(f"{context} cairosvg 未安装，请执行: pip install cairosvg")
            return None
        except Exception as e:
            logger.error(f"{context} 加载 SVG 图标失败 {icon_code}: {e}", exc_info=True)
            return None

    def _load_raw_icon(self, icon_code: str, size: int, context: str = "", fill_circle_white: bool = False) -> Optional[Image.Image]:
        """加载 SVG 图标，保持原始颜色（不动态改色）
        若 fill_circle_white=True，则将图标圆形区域内的空白（alpha=0）填充为白色。
        """
        if not icon_code:
            return None
        svg_path = os.path.join(self.icon_dir, f"{icon_code}.svg")
        if not os.path.exists(svg_path):
            logger.warning(f"{context} SVG 图标不存在: {svg_path}")
            return None
        try:
            import cairosvg
            with open(svg_path, 'r', encoding='utf-8') as f:
                svg_content = f.read()
            size_int = int(size)
            png_bytes = cairosvg.svg2png(bytestring=svg_content.encode('utf-8'),
                                         output_width=size_int, output_height=size_int)
            icon = Image.open(io.BytesIO(png_bytes))
            if icon.mode != 'RGBA':
                icon = icon.convert('RGBA')

            # 如果需要填充圆形区域内的空白为白色
            if fill_circle_white:
                icon = self._fill_circle_white(icon)

            return icon
        except ImportError:
            logger.error(f"{context} cairosvg 未安装，请执行: pip install cairosvg")
            return None
        except Exception as e:
            logger.error(f"{context} 加载原始 SVG 图标失败 {icon_code}: {e}")
            return None

    def _fill_circle_white(self, img: Image.Image) -> Image.Image:
        """将图像圆形区域内的透明像素填充为白色，保留前景"""
        w, h = img.size
        center_x, center_y = w / 2, h / 2
        radius = min(w, h) / 2 * 0.9  # 半径略小于图像一半，避免边缘干扰
        radius_sq = radius * radius

        pixels = img.load()
        for x in range(w):
            dx = x - center_x
            for y in range(h):
                dy = y - center_y
                if dx*dx + dy*dy <= radius_sq:
                    # 圆形区域内
                    r, g, b, a = pixels[x, y]
                    if a == 0:  # 完全透明 -> 填充白色
                        pixels[x, y] = (255, 255, 255, 255)
                    # 如果需要，也可以将半透明或接近白色的背景填充为纯白，但会破坏月牙形状，故不处理
        return img

    def generate(self, weather_data: Dict[str, Any]) -> bytes:
        width, height = 800, 480
        img = Image.new("RGB", (width, height), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)

        theme = self._get_theme(weather_data)

        if theme == "sunny_day":
            left_bg = (255, 217, 130)  # #FFD982
            right_bg_center = (103, 227, 255)  # (94,206,246) 提亮10%
            right_bg_outer = (94, 206, 246)   # 原色
            right_bg = None  # 径向渐变
            text_main = (0, 0, 0)
            text_secondary = (80, 80, 80)
            line_color = (191, 162, 97)
            icon_color = "#000000"
        elif theme == "cloudy_day":
            left_bg = (225, 228, 234)  # #E1E4EA
            right_bg_top = (165, 175, 189)  # #A5AFBD
            right_bg_bottom = (138, 147, 162)  # #8A93A2
            right_bg = None  # 渐变
            text_main = (37, 41, 51)  # #252933
            text_secondary = (80, 80, 80)
            line_color = (197, 204, 214)  # #C5CCD6
            icon_color = "#525F73"
        elif theme == "rainy_day":
            left_bg = (183, 201, 217)  # #B7C9D9
            right_bg_top = (53, 90, 128)   # #355A80
            right_bg_bottom = (94, 136, 176)  # #5E88B0
            right_bg = None  # 标记为渐变
            text_main = (32, 48, 64)
            text_secondary = (80, 80, 80)
            line_color = (169, 185, 201)  # #A9B9C9
            icon_color = "#E4F3FF"
        else:  # night
            left_bg = (37, 57, 92)  # #25395C
            right_bg_top = (28, 42, 79)  # #1C2A4F
            right_bg_bottom = (26, 37, 53)  # #1A2535
            right_bg = None  # 渐变
            text_main = (255, 255, 255)
            text_secondary = (200, 200, 200)
            line_color = (92, 107, 133)
            icon_color = "#FFFFFF"

        right_width = width // 4
        left_width = width - right_width
        right_x_start = left_width

        draw.rectangle([(0, 0), (left_width, height)], fill=left_bg)
        if right_bg is not None:
            draw.rectangle([(right_x_start, 0), (width, height)], fill=right_bg)
        else:
            if theme == "sunny_day":
                # 径向渐变：以图标为中心，中心提亮10%
                import math
                cx = right_width / 2
                cy = height / 2
                max_dist = math.sqrt(cx * cx + cy * cy)
                for y in range(height):
                    for x in range(right_width):
                        dx = x - cx
                        dy = y - cy
                        t = math.sqrt(dx * dx + dy * dy) / max_dist
                        if t > 1:
                            t = 1
                        r = int(right_bg_center[0] + (right_bg_outer[0] - right_bg_center[0]) * t)
                        g = int(right_bg_center[1] + (right_bg_outer[1] - right_bg_center[1]) * t)
                        b = int(right_bg_center[2] + (right_bg_outer[2] - right_bg_center[2]) * t)
                        draw.point((right_x_start + x, y), fill=(r, g, b))
            else:
                # 竖向渐变：逐行绘制（阴天、雨天、夜晚）
                for y in range(height):
                    t = y / (height - 1) if height > 1 else 0
                    r = int(right_bg_top[0] + (right_bg_bottom[0] - right_bg_top[0]) * t)
                    g = int(right_bg_top[1] + (right_bg_bottom[1] - right_bg_top[1]) * t)
                    b = int(right_bg_top[2] + (right_bg_bottom[2] - right_bg_top[2]) * t)
                    draw.line([(right_x_start, y), (width, y)], fill=(r, g, b))

                # 斜向雨纹——断续短雨丝（仅雨天）
                if theme == "rainy_day":
                    import math, random
                    right_panel = img.crop((right_x_start, 0, width, height)).convert("RGBA")
                    overlay = Image.new("RGBA", right_panel.size, (0, 0, 0, 0))
                    od = ImageDraw.Draw(overlay)
                    rain_alpha = 51  # 20%
                    ang = math.radians(12)
                    # 按降雨量分等级决定雨纹密度
                    precip = weather_data.get("precip", 0)
                    if precip < 10:
                        cols, rows, target = 8, 11, 88
                    elif precip < 25:
                        cols, rows, target = 11, 13, 143
                    elif precip < 50:
                        cols, rows, target = 13, 16, 208
                    else:
                        cols, rows, target = 15, 19, 285
                    cell_w = right_width / cols
                    cell_h = height / rows
                    jitter_x = cell_w * 0.7
                    jitter_y = cell_h * 0.7
                    count = 0
                    for row in range(rows):
                        for col in range(cols):
                            if count >= target:
                                break
                            cx = col * cell_w + cell_w / 2
                            cy = row * cell_h + cell_h / 2
                            x = cx + random.uniform(-jitter_x, jitter_x)
                            y = cy + random.uniform(-jitter_y, jitter_y)
                            L = random.randint(18, 38)
                            dx = L * math.sin(ang)
                            dy = L * math.cos(ang)
                            od.line([(x, y), (x + dx, y + dy)], fill=(255, 255, 255, rain_alpha), width=1)
                            count += 1
                    right_panel = Image.alpha_composite(right_panel, overlay).convert("RGB")
                    img.paste(right_panel, (right_x_start, 0))

        # 右侧大图标
        icon_code = weather_data.get("icon", "100")
        icon_size = 160
        icon = self._load_icon(icon_code, icon_size, icon_color, context="右侧天气图标")
        if icon:
            icon_x = right_x_start + (right_width - icon_size) // 2
            icon_y = (height - icon_size) // 2
            img.paste(icon, (icon_x, icon_y), icon)
        else:
            logger.warning(f"无法加载右侧大图标: {icon_code}")

        left_padding = 25

        # 第1部分：城市、日期
        city = weather_data.get("city", "未知")
        draw.text((left_padding, 20), city, fill=text_main, font=self.font_city)

        now = datetime.now()
        date_str = now.strftime("%Y年%m月%d日 %H:%M")
        draw.text((left_padding, 58), date_str, fill=text_secondary, font=self.font_date)

        draw.line([(left_padding, 90), (left_width - left_padding, 90)], fill=line_color, width=1)

        # 第2部分：温度区域
        temp_y_start = 90
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
        small_icon = self._load_icon(icon_code, 40, icon_color, context="天气小图标")
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
        wind_deg = weather_data.get("wind_deg")
        if not wind_dir and wind_deg is not None:
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

        # ---------- 月相部分：文字在上，图标在下，整体右移一个字宽度 ----------
        if moon_phase:
            char_width = draw.textlength("月", font=self.font_moon)
            moon_text_y = info_y_start + len(right_col_items) * line_gap
            moon_text_x = int(right_col_x + char_width)
            draw.text((right_col_x, moon_text_y), f"月相:    {moon_phase}", fill=text_main, font=self.font_moon)

            if moon_icon_code:
                icon_size = int(2 * line_gap)  # 60px
                moon_icon = self._load_raw_icon(moon_icon_code, icon_size, context="月相图标", fill_circle_white=True)
                if moon_icon:
                    bbox = draw.textbbox((moon_text_x, moon_text_y), f"月相: {moon_phase}", font=self.font_moon)
                    text_center_y = (bbox[1] + bbox[3]) / 2
                    icon_y = text_center_y + 2 * line_gap - icon_size / 2
                    img.paste(moon_icon, (moon_text_x, int(icon_y)), moon_icon)
                else:
                    logger.warning(f"月相图标加载失败: {moon_icon_code}")
            else:
                logger.info("月相图标代码为空，不显示月相图标")
        # 转换为 bytes
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")
        img_bytes.seek(0)
        return img_bytes.getvalue()
