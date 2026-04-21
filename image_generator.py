import io
import os
import sys
import platform
from PIL import Image, ImageDraw, ImageFont
from typing import Dict, Any, Optional, List
from astrbot.api import logger


class WeatherImageGenerator:
    """天气图片生成器（跨平台中文支持版）"""
    
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
        self.font_large = self._load_font(48)
        self.font_medium = self._load_font(32)
        self.font_small = self._load_font(24)
        self.font_tiny = self._load_font(18)
    
    def _build_font_paths(self) -> List[str]:
        """构建跨平台的中文字体搜索路径列表"""
        paths = []
        system = platform.system()
        
        # Linux / WSL / Docker
        if system == "Linux":
            paths.extend([
                # 系统字体目录
                "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",      # 文泉驿微米黑（最常用）
                "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",        # 文泉驿正黑
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",     # DejaVu（部分中文）
                "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", # Noto CJK
                "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
                "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
                # 用户字体目录
                os.path.expanduser("~/.fonts/wqy-microhei.ttf"),
                os.path.expanduser("~/.local/share/fonts/wqy-microhei.ttf"),
                # 作为备选，列出所有可能包含中文字体的路径
                "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            ])
        
        # Windows
        elif system == "Windows":
            windows_font_dir = os.environ.get("WINDIR", "C:\\Windows")
            paths.extend([
                os.path.join(windows_font_dir, "Fonts", "msyh.ttc"),        # 微软雅黑
                os.path.join(windows_font_dir, "Fonts", "msyhbd.ttc"),      # 微软雅黑粗体
                os.path.join(windows_font_dir, "Fonts", "simhei.ttf"),      # 黑体
                os.path.join(windows_font_dir, "Fonts", "simsun.ttc"),      # 宋体
                os.path.join(windows_font_dir, "Fonts", "simkai.ttf"),      # 楷体
                os.path.join(windows_font_dir, "Fonts", "FZSTK.TTF"),       # 方正舒体
            ])
        
        # macOS
        elif system == "Darwin":
            paths.extend([
                "/System/Library/Fonts/PingFang.ttc",                     # 苹方
                "/System/Library/Fonts/STHeiti Light.ttc",                # 华文黑体
                "/System/Library/Fonts/STHeiti Medium.ttc",
                "/Library/Fonts/Arial Unicode MS.ttf",                    # Arial Unicode
                "/System/Library/Fonts/Supplemental/Songti.ttc",          # 宋体
            ])
        
        # 通用备选：尝试使用 matplotlib 或 环境变量指定
        paths.extend([
            os.environ.get("ASTRBOT_CHINESE_FONT_PATH", ""),  # 允许通过环境变量指定
            "./fonts/simhei.ttf",  # 插件目录下的字体文件
            "./fonts/msyh.ttc",
            "./fonts/wqy-microhei.ttf",
        ])
        
        # 过滤掉空路径
        return [p for p in paths if p]
    
    def _find_chinese_font(self) -> Optional[str]:
        """在预定义的搜索路径中查找第一个存在的中文字体"""
        for path in self.font_search_paths:
            if os.path.exists(path):
                # 快速验证字体是否真的包含中文字形（可选，但推荐）
                try:
                    test_font = ImageFont.truetype(path, 12)
                    # 简单测试：如果获取不到字体信息，可能损坏
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
        # 降级到 Pillow 默认字体（通常不支持中文）
        return ImageFont.load_default()
    
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
        # 获取字体，支持回退
        title_font = self.font_large
        bbox = draw.textbbox((0, 0), title, font=title_font)
        title_width = bbox[2] - bbox[0]
        draw.text(((width - title_width) // 2, 20), title, fill=(30, 30, 30), font=title_font)
        
        # 绘制分隔线
        draw.line([(50, 80), (width - 50, 80)], fill=(200, 200, 200), width=2)
        
        # 当前温度（大号显示）
        temp = weather_data.get("temperature", 0)
        temp_text = f"{temp}°C"
        # 使用大号字体显示温度
        temp_font = self.font_large
        bbox = draw.textbbox((0, 0), temp_text, font=temp_font)
        temp_width = bbox[2] - bbox[0]
        draw.text(((width // 2 - temp_width) // 2, 100), temp_text, fill=(220, 20, 60), font=temp_font)
        
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
        
        # 绘制数据来源
        draw.text((50, height - 30), "数据来源: OpenWeather", fill=(150, 150, 150), font=self.font_tiny)
        
        # 转换为bytes
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")
        img_bytes.seek(0)
        return img_bytes.getvalue()
