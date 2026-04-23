<div align="center">

[![Moe Counter](https://count.getloli.com/get/@lirundong093-glitch?theme=moebooru)](https://github.com/lirundong093-glitch/astrbot_plugin_everyday_weatherforecast)

</div>

# 🌤️ 和风天气预报插件 (astrbot_plugin_weather)

基于 AstrBot 框架与和风天气 API 开发的智能天气查询与推送插件，目前只支持aiohttp。支持生成可视化天气图片、每日定时推送、AI 智能生成生活指南（可选）。

## ✨ 主要特性

- **实时天气查询**：支持指定城市查询，返回包含温度、风力、湿度、空气质量、未来预报等信息的美观图片。
- **每日定时推送**：可设置推送时间，自动向白名单群聊发送当日天气预报。
- **可视化图片生成**：内置图片渲染引擎，无需依赖外部图片生成服务。
- **AI 生活指南（可选）**：接入大语言模型，根据天气数据生成穿衣、出行、紫外线防护等生活建议。
- **节假日检测联动**：结合节假日数据，AI 指南会融入节日氛围提示（需开启 LLM）。
- **灵活配置**：支持通过聊天指令动态修改配置，无需重启机器人。

## 生成图片示例
![image_to_show](https://github.com/lirundong093-glitch/astrbot_plugin_everyday_weatherforecast/blob/main/image_to_show.png?raw=true)

## 📥 安装与配置

1. 将插件放入 AstrBot 的 `addons` 目录。
2. 获取和风天气 API Key以及API host：前往 [和风天气控制台](https://console.qweather.com) 注册并创建应用。
3. 该插件目前只支持通过指令来配置，请根据下列指令进行配置。

## 🤖 指令列表

| 指令 | 说明 |
| :--- | :--- |
| `/weather [城市名]` | 查询指定城市天气。不带参数时查询默认城市。 |
| `/weather_test_push` | **调试指令**：立即执行一次每日推送流程。 |
| `/weather_config` | 查看当前所有配置项状态。 |
| `/weather_config <key> <value>` | 修改指定配置项（详见下方表格）。 |

### 配置项 Key 对照表

| Key | 说明 | 取值示例 |
| :--- | :--- | :--- |
| `platfome_name` | astrbot平台名称 | Lucy |
| `qweather_key` | 和风天气 API Key | `abc123def456` |
| `api_host` | 接口地址 | `devapi.qweather.com` |
| `default_city` | 默认查询城市 | `北京` |
| `push_time` | 每日推送时间 | `08:00` |
| `whitelist_add` | 添加推送白名单群 | `123456789` |
| `whitelist_remove` | 移除推送白名单群 | `123456789` |
| `llm_enabled` | 开关 AI 指南功能 | `true` / `false` |
| `llm_provider` | LLM 供应商标识 | `openai` / `deepseek` |
| `llm_api_key` | LLM 密钥 | `sk-xxxxxx` |
| `llm_base_url` | LLM 接口地址 | `https://api.deepseek.com/chat/completions` |
| `llm_model` | LLM 模型名称 | `deepseek-chat` |
| `holiday_cache_enabled` | 开关节假日缓存 | `true` / `false` |

## 🔄 定时推送逻辑说明

- 定时任务仅会向 `whitelist_groups` 中配置的群聊发送消息。
- 推送内容包含：天气图片 + （若开启 LLM）AI 生成的文字指南。
- 插件启动时会在日志中打印当前调度任务状态及下次运行时间。

## 🛠️ 开发与依赖

- **框架**：AstrBot API
- **数据源**：和风天气 API
- **图片生成**：PIL / Pillow（内置渲染）
- **AI 增强**：OpenAI 兼容格式的 LLM 接口（可选）

## 🙏 鸣谢

- [和风天气](https://www.qweather.com/) 提供稳定准确的天气数据。
- [open-weather-image](https://github.com/Kira-Kitsune/open-weather-image) 提供生图思路。
- [AstrBot Repo](https://github.com/AstrBotDevs/AstrBot)
- [AstrBot Plugin Development Docs (Chinese)](https://docs.astrbot.app/dev/star/plugin-new.html)
- [AstrBot Plugin Development Docs (English)](https://docs.astrbot.app/en/dev/star/plugin-new.html)
