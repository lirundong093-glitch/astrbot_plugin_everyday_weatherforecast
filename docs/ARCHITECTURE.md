# 🌤️ Everyday WeatherForecast 插件架构文档

> **版本**: v1.1.2 | **作者**: Lucy | **许可证**: MIT

---

## 一、文件结构

```
astrbot_plugin_everyday_weatherforecast/
├── main.py                          # 插件入口，注册指令与生命周期管理
├── metadata.yaml                    # AstrBot 插件元数据
├── _conf_schema.json                # 用户配置 Schema 定义
├── requirements.txt                 # Python 依赖列表
├── README.md                        # 项目说明文档
├── LICENSE                          # MIT 开源协议
├── holiday_cache.json               # 节假日本地缓存
├── logo.png                         # 插件 Logo
│
├── core/                            # 核心业务模块
│   ├── __init__.py                  # 包标识（空文件）
│   ├── api_client.py                # 和风天气 API 客户端
│   ├── config.py                    # 插件配置管理
│   ├── holiday.py                   # 节假日检查器
│   ├── image_generator.py           # 天气图片生成引擎
│   ├── llm_guide.py                 # LLM 天气指南生成器
│   └── scheduler.py                 # 定时任务调度器
│
├── resource/                        # 静态资源
│   ├── icons/                       # SVG 天气图标（500+ 个）
│   ├── image_to_show/               # 示例预览图片
│   │   ├── image_to_show_sunnyday.png
│   │   ├── image_to_show_foggyday.png
│   │   ├── image_to_show_rainyday.png
│   │   └── image_to_show_night.png
│   └── China-City-List-latest.csv   # 中国城市 LocationID 映射表
│
└── docs/                            # 文档（本目录）
    └── ARCHITECTURE.md              # 本文档
```

---

## 二、模块概览与依赖关系

```
main.py (插件入口)
  ├── config.py          ← AstrBotConfig 封装，管理所有用户配置项
  ├── api_client.py      ← 和风天气 API 请求（实时、逐日、AQI、生活指数）
  ├── image_generator.py ← PIL 图片渲染引擎（左右分栏布局，昼夜主题）
  ├── scheduler.py       ← APScheduler 定时任务，驱动每日推送
  ├── llm_guide.py       ← 调用 AstrBot 内置 LLM Provider 生成文字指南
  └── holiday.py         ← 节假日检测（本地缓存 + timor.tech API）
```

**调用链**：

```
用户指令 /weather
  → main.py.weather()
    → api_client.get_complete_weather(city)
    → image_generator.generate(weather_data)
    → 返回天气图片

定时推送 (scheduler 触发)
  → main.py._daily_push()
    → api_client.get_complete_weather(city)
    → image_generator.generate(weather_data)
    → llm_guide.generate_guide(city, weather_data) [可选]
    → 向白名单群发送图片 + LLM 文字
```

---

## 三、核心文件详解

### 3.1 `main.py` — 插件入口

**类**: `WeatherPlugin(Star)`

| 方法 | 功能 |
| :--- | :--- |
| `__init__()` | 初始化所有子模块（API 客户端、图片生成器、调度器、LLM 指南、节假日检查器） |
| `_daily_push()` | 每日定时推送：获取天气 → 生成图片 → 生成 LLM 指南 → 推送到白名单群 |
| `weather()` | `/weather [城市]` 指令处理 |
| `weather_test_push()` | `/weather_test_push` 调试指令，手动触发一次推送 |
| `weather_config()` | `/weather_config` 查看当前全量配置（仅管理员） |
| `start()` / `terminate()` | 生命周期管理：启动/关闭调度器 |

**关键逻辑**：
- `_daily_push()` 中天气获取有 **3 次重试**，每次间隔 10 秒
- 推送采用 `MessageChain().message(...).file_image(...)` 图文消息链
- 推送完成后自动清理临时 PNG 文件

---

### 3.2 `core/api_client.py` — API 客户端

**类**: `QWeatherClient`

**核心能力**：
- 从本地 CSV 表加载 5000+ 中国城市的 `LocationID` 映射
- 并发请求 4 个 API：实时天气、3 日预报、空气质量、生活指数
- 自动兼容两种 API 响应格式：
  - **和风标准格式**（`code: "200"`）
  - **TomTom cn-mee 格式**（无 `code` 字段，有 `days`）

**端点**：
| API | URL |
| :--- | :--- |
| 城市搜索 | `{host}/geo/v2/city/lookup` |
| 实时天气 | `{host}/v7/weather/now` |
| 3日预报 | `{host}/v7/weather/3d` |
| 空气质量 | `{host}/airquality/v1/daily/{lat}/{lon}` |
| 生活指数 | `{host}/v7/indices/1d` |

**返回的 `get_complete_weather()` 数据结构**：
```python
{
    "city": str,           # 城市名
    "temperature": float,  # 当前温度
    "feels_like": float,   # 体感温度
    "humidity": int,       # 湿度 %
    "wind_speed": float,   # 风速 km/h
    "wind_dir": str,       # 风向文字
    "icon": str,           # 天气图标代码 (如 "100"="晴")
    "weather": str,        # 天气描述
    "temp_max/min": float, # 今日最高/最低温
    "sunrise/sunset": str, # 日出/日落时间
    "moon_phase": str,     # 月相名称
    "moon_icon": str,      # 月相图标代码
    "uv_index": int,       # 紫外线指数
    "aqi": str,            # 空气质量数值
    "aqi_category": str,   # 空气质量等级
    "precip": float,       # 降水量 mm
    "indices": list,       # 生活指数列表
    ...
}
```

---

### 3.3 `core/config.py` — 配置管理

**类**: `PluginConfig`

**职责**：
- 封装 `AstrBotConfig`，提供属性式访问
- 自动迁移旧的 `user_config.json` 到 AstrBot 配置系统
- `update_config()` 方法支持动态修改配置项（无需重启）

**支持的动态配置项**：

| Key | 说明 |
| :--- | :--- |
| `qweather_key` | 和风天气 API Key |
| `api_host` | API 主机地址 |
| `default_city` | 默认城市 |
| `daily_push_time` | 推送时间 |
| `indices_types` | 生活指数类型 |
| `llm_enabled` | 开关 LLM |
| `holiday_cache_enabled` | 开关节假日 |
| `whitelist_add/remove` | 白名单增删 |
| `admin_add/remove` | 管理员增删 |

---

### 3.4 `core/image_generator.py` — 图片生成器

**类**: `WeatherImageGenerator`

**布局**: 800×480 像素，**左右分栏**

```
┌──────────────────────────┬──────────┐
│                          │          │
│   左栏 (600px)            │ 右栏     │
│                          │ (200px)  │
│   城市、日期、温度、      │ 大天气   │
│   详细信息（风力/湿度/    │ 图标     │
│   AQI/月相…）             │ (160px)  │
│                          │          │
└──────────────────────────┴──────────┘
```

**4 种昼夜主题**（根据日出日落时间 + 云量 + 降水量自动切换）：

| 主题 | 触发条件 | 配色特点 |
| :--- | :--- | :--- |
| `sunny_day` | 白天 + 云量 < 70% | 暖黄左栏 + 天蓝渐变右栏 |
| `cloudy_day` | 白天 + 云量 ≥ 70% + 无降水 | 灰白左栏 + 蓝灰渐变右栏 |
| `rainy_day` | 白天 + 降水量 > 0 | 淡蓝左栏 + 深蓝渐变右栏 + 斜向雨纹 |
| `night` | 非白天时段 | 深蓝左栏 + 暗蓝渐变右栏 + 白色文字 |

**关键技术**：
- SVG 图标使用 `cairosvg` 渲染为 PNG，支持动态改色
- 月相图标使用 `_load_raw_icon()` 保持原始颜色，并自动填充圆形白色背景
- 雨天主题使用 PIL 逐像素绘制斜向断续雨丝

---

### 3.5 `core/scheduler.py` — 定时调度器

**类**: `WeatherScheduler`

**依赖**: `apscheduler` (AsyncIOScheduler + CronTrigger)

**核心逻辑**：
1. 根据 `daily_push_time`（如 `08:00`）创建 Cron 任务
2. 时区使用 `pytz`，默认 `Asia/Shanghai`
3. 插件启动时自动恢复调度，卸载时自动关闭
4. 每次更新 `push_time` 会先移除旧任务再创建新任务

---

### 3.6 `core/llm_guide.py` — LLM 天气指南

**类**: `LLMGuideGenerator`

**工作流程**：
1. `_build_prompt()` 根据天气数据 + 节假日信息 + 星期几构建 Prompt
2. 通过 AstrBot 内置 `provider.text_chat()` 调用 LLM
3. 要求 LLM 输出 **不超过 150 字**，分 3 段（问好 / 天气状况 / 建议）

**Prompt 特色**：
- 内置 7 种**工作日/休息日话术**（周一加油 → 周五期待周末 → 周末享受）
- 节假日自动融入节日祝福（如春节、中秋等）
- 强制要求输出 emoji + 颜文字，语言亲切活泼

**生活指数编码映射**：
| 编号 | 名称 | 编号 | 名称 |
| :--- | :--- | :--- | :--- |
| 1 | 运动指数 | 9 | 感冒指数 |
| 3 | 穿衣指数 | 10 | 空气污染扩散 |
| 5 | 紫外线指数 | 11 | 空调开启指数 |
| 6 | 旅游指数 | 14 | 晾晒指数 |
| 7 | 花粉过敏指数 | 15 | 交通指数 |
| 8 | 舒适度指数 | — | — |

---

### 3.7 `core/holiday.py` — 节假日检查器

**类**: `HolidayChecker`

**数据源**: [timor.tech](https://timor.tech/api/holiday) 免费节假日 API

**缓存策略**：
- 首次查询某年时从 API 拉取，写入 `holiday_cache.json`
- 后续查询直接读缓存，避免重复请求
- 可通过配置关闭节假日功能

**返回**: `(is_holiday: bool, holiday_name: str)`

---

## 四、配置文件

### `_conf_schema.json` 配置项

| 配置项 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| `qweather_key` | string | `""` | **必填** 和风天气 API Key |
| `api_host` | string | `""` | API 主机地址 |
| `default_city` | string | `"北京"` | 默认查询城市 |
| `daily_push_enabled` | bool | `true` | 是否开启每日定时推送 |
| `daily_push_time` | string | `"08:00"` | 推送时间 (HH:MM) |
| `timezone` | string | `"Asia/Shanghai"` | 时区 |
| `whitelist_groups` | list | `[]` | 白名单群聊列表 |
| `admin_users` | list | `[]` | 插件管理员 ID 列表 |
| `llm_enabled` | bool | `false` | 是否启用 LLM 天气指南 |
| `provider_id` | string | `""` | LLM 提供商 ID |
| `indices_types` | string | `"1,3,5,..."` | 生活指数类型 |
| `holiday_cache_enabled` | bool | `true` | 是否启用节假日问候 |

### `requirements.txt` 依赖

```
Pillow          # 图片生成
pytz            # 时区处理
aiohttp         # 异步 HTTP 请求
apscheduler     # 定时任务调度
cairosvg        # SVG 图标渲染
```

---

## 五、数据流总览

```
                    ┌─────────────────────┐
                    │   用户 /weather     │
                    └────────┬────────────┘
                             │
              ┌──────────────▼──────────────┐
              │     main.py: weather()      │
              └──────────────┬──────────────┘
                             │
              ┌──────────────▼──────────────┐
              │  api_client.get_            │
              │  complete_weather(city)     │
              │  ├── get_location_id()      │
              │  ├── get_weather_now()      │
              │  ├── get_weather_daily()    │
              │  ├── get_air_daily()        │
              │  └── get_indices()          │
              └──────────────┬──────────────┘
                             │
              ┌──────────────▼──────────────┐
              │  image_generator.generate() │
              │  ├── 判断主题 (day/night)   │
              │  ├── 渲染背景渐变           │
              │  ├── 渲染 SVG 图标          │
              │  └── 排版文字信息           │
              └──────────────┬──────────────┘
                             │
                    ┌────────▼────────┐
                    │  PNG bytes 输出 │
                    └─────────────────┘

定时推送 (scheduler 触发):
  _daily_push() 额外步骤:
    └── llm_guide.generate_guide()
        ├── holiday.check_today()
        ├── _build_prompt()
        └── provider.text_chat()
                  │
                  ▼
            LLM 文字指南
```
