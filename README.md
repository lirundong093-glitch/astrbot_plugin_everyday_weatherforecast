# astrbot-plugin-everyday-weatherforecast

一个专门用于QQ群聊每日播报天气的插件

# 🌤️ 和风天气预报插件 (astrbot_plugin_weather)

基于 AstrBot 框架与和风天气 API 开发的智能天气查询与推送插件。支持生成可视化天气图片、每日定时推送、AI 智能生成生活指南（可选）。

## ✨ 主要特性

- **实时天气查询**：支持指定城市查询，返回包含温度、风力、湿度、空气质量、未来预报等信息的美观图片。
- **每日定时推送**：可设置推送时间，自动向白名单群聊发送当日天气预报。
- **可视化图片生成**：内置图片渲染引擎，无需依赖外部图片生成服务。
- **AI 生活指南（可选）**：接入大语言模型，根据天气数据生成穿衣、出行、紫外线防护等生活建议。
- **节假日检测联动**：结合节假日数据，AI 指南会融入节日氛围提示（需开启 LLM）。
- **灵活配置**：支持通过聊天指令动态修改配置，无需重启机器人。

## 📥 安装与配置

1. 将插件放入 AstrBot 的 `addons` 目录。
2. 获取和风天气 API Key：前往 [和风天气控制台](https://console.qweather.com) 注册并创建应用。
3. 在插件目录下编辑或通过指令生成 `user_config.json` 配置文件。


# Supports

- [AstrBot Repo](https://github.com/AstrBotDevs/AstrBot)
- [AstrBot Plugin Development Docs (Chinese)](https://docs.astrbot.app/dev/star/plugin-new.html)
- [AstrBot Plugin Development Docs (English)](https://docs.astrbot.app/en/dev/star/plugin-new.html)
