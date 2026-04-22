import io
import os
import platform
import math
from datetime import datetime, timezone, timedelta
from PIL import Image, ImageDraw, ImageFont
from typing import Dict, Any, Optional, List
from astrbot.api import logger


class WeatherImageGenerator:
    """天气图片生成器 - 仿 open-weather-image 风格 (右侧大图标 + 月相)"""

    def __init__(self):
        # 跨平台字体搜索
        self.font_search_paths = self._build_font_paths()
        self.font_path = self._find_chinese_font()
        if not self.font_path:
            logger.warning("未找到任何中文字体，中文可能显示异常。")
        else:
            logger.info(f"已加载中文字体：{self.font_path}")

        # 预加载常用字号
        self.font_temp_large = self._load_font(68)      # 大温度数字
        self.font_city = self._load_font(26)            # 城市名
        self.font_weather = self._load_font(22)         # 天气描述
        self.font_label = self._load_font(18)           # 标签文字
        self.font_value = self._load_font(18)           # 数值
        self.font_small = self._load_font(14)           # 日出日落等

        # 图标目录（用户下载的和风天气官方图标位置，建议提前转为 PNG）
        self.plugin_dir = plugin_dir
        self.icon_dir = os.path.join(self.plugin_dir, "icons")
        if not os.path.exists(self.icon_dir):
            logger.warning(f"图标目录不存在: {self.icon_dir}，请确保已下载和风天气官方图标")
        else:
            logger.info(f"图标目录已设置: {self.icon_dir}")

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

    # ---------- 图标加载 ----------
    def _get_icon_path(self, icon_code: str) -> str:
        """获取图标文件路径，优先 SVG，其次 PNG。"""
        if not icon_code:
            icon_code = "100"  # 默认晴天图标
        # 图标统一存放在项目根目录的 /icons/ 下，您可以根据自己的部署位置调整
        icon_file = os.path.join(self.icon_dir, f"{icon_code}.svg")
        if os.path.exists(svg_path):
            return svg_path
        return ""

    def _load_icon(self, icon_code: str, size: int = 110) -> Optional[Image.Image]:
        """加载并缩放图标（支持 SVG 和 PNG）。"""
        icon_path = self._get_icon_path(icon_code)
        if not icon_path:
            logger.warning(f"图标文件不存在: {icon_code}")
            return None

        try:
            ext = os.path.splitext(icon_path)[1].lower()
            try:
                import cairosvg
                # 将 SVG 转换为 PNG 字节流
                png_bytes = cairosvg.svg2png(url=icon_path, output_width=size, output_height=size)
                icon = Image.open(io.BytesIO(png_bytes))
            except ImportError:
                logger.error("cairosvg 未安装，无法加载 SVG 图标。请执行: pip install cairosvg")
                return None
        
            # 确保图标为 RGBA 模式，以支持透明背景
            if icon.mode != 'RGBA':
                icon = icon.convert('RGBA')
            return icon
        except Exception as e:
            logger.error(f"加载图标失败 {icon_code}: {e}")
            return None
        
    # ---------- 核心绘图 ----------
    def generate(self, weather_data: Dict[str, Any]) -> bytes:
        width, height = 800, 420
        img = Image.new("RGB", (width, height))
        draw = ImageDraw.Draw(img)

        # 昼夜主题色
        is_day = self._is_daytime(weather_data)
        if is_day:
            left_color = (255, 217, 130)   # #FFD982
            right_color = (94, 206, 246)   # #5ECEF6
            text_main = (20, 20, 20)
            text_secondary = (60, 60, 60)
        else:
            left_color = (37, 57, 92)      # #25395C
            right_color = (28, 42, 79)     # #1C2A4F
            text_main = (240, 240, 240)
            text_secondary = (200, 200, 200)

        # 渐变背景
        for x in range(width):
            ratio = x / width
            r = int(left_color[0] + (right_color[0] - left_color[0]) * ratio)
            g = int(left_color[1] + (right_color[1] - left_color[1]) * ratio)
            b = int(left_color[2] + (right_color[2] - left_color[2]) * ratio)
            draw.line([(x, 0), (x, height)], fill=(r, g, b))

        # ---------- 左半区 (0~480px)：主要信息 ----------
        left_x = 30
        city = weather_data.get("city", "未知")
        draw.text((left_x, 25), city, fill=text_main, font=self.font_city)

        temp = weather_data.get("temperature", 0)
        temp_str = f"{temp:.0f}°" if temp == int(temp) else f"{temp:.1f}°"
        draw.text((left_x, 70), temp_str, fill=text_main, font=self.font_temp_large)

        weather_desc = weather_data.get("weather", "未知")
        draw.text((left_x, 155), weather_desc, fill=text_secondary, font=self.font_weather)

        temp_max = weather_data.get("temp_max", 0)
        temp_min = weather_data.get("temp_min", 0)
        range_text = f"最高 {temp_max:.0f}°  最低 {temp_min:.0f}°"
        draw.text((left_x, 195), range_text, fill=text_secondary, font=self.font_label)

        feels = weather_data.get("feels_like", 0)
        feels_str = f"体感温度 {feels:.0f}°" if feels == int(feels) else f"体感温度 {feels:.1f}°"
        draw.text((left_x, 230), feels_str, fill=text_secondary, font=self.font_label)

        sys_data = weather_data.get("sys", {})
        sunrise = sys_data.get("sunrise")
        sunset = sys_data.get("sunset")
        tz_offset = weather_data.get("timezone", 0)
        if sunrise and sunset:
            sr = self._format_time(sunrise, tz_offset)
            ss = self._format_time(sunset, tz_offset)
            sun_str = f"日出 {sr}  日落 {ss}"
            draw.text((left_x, 265), sun_str, fill=text_secondary, font=self.font_small)

        # ---------- 右半区 (480~800px)：详细信息 ----------
        right_x = 500
        y_start = 60
        line_gap = 40

        # 提取风向风力，分开显示
        wind_dir = weather_data.get("wind_dir", "")
        wind_speed = weather_data.get("wind_speed", 0)
        wind_deg = weather_data.get("wind_deg", 0)
        if not wind_dir and wind_deg:
            wind_dir = self._wind_direction(wind_deg)

        details = [
            ("湿度", f"{weather_data.get('humidity', 0)}%"),
            ("风向", wind_dir if wind_dir else "未知"),
            ("风力", f"{wind_speed:.0f} km/h" if wind_speed else "未知"),
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
            draw.text((right_x + 150 - value_width, y), value, fill=text_main, font=self.font_value)

        # ---------- 右上角：主天气图标 (约占右侧 1/3) ----------
        icon_code = weather_data.get("icon", "100")
        icon = self._load_icon(icon_code, size=110)
        if icon:
            icon_x = width - 140
            icon_y = 30
            img.paste(icon, (icon_x, icon_y), icon)
        else:
            logger.warning(f"无法加载天气图标: {icon_code}")

        # ---------- 月相图标 (主图标下方) ----------
        moon_icon_code = weather_data.get("moon_icon", "")
        if moon_icon_code:
            moon_icon = self._load_icon(moon_icon_code, size=45)  # 月相图标尺寸稍小
            if moon_icon:
                moon_x = left_x  # 与体感温度文字左对齐
                moon_y = 265     # 定位在体感温度下方 (原体感温度 Y 坐标为 230)
                img.paste(moon_icon, (moon_x, moon_y), moon_icon)
            else:
                logger.warning(f"无法加载月相图标: {moon_icon_code}")

        # 底部装饰线
        draw.line([(30, height - 30), (width - 30, height - 30)], fill=text_secondary, width=1)

        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")
        img_bytes.seek(0)
        return img_bytes.getvalue()
