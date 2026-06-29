<div align="center">

[![Moe Counter](https://count.getloli.com/get/@lirundong093-glitch?theme=moebooru)](https://github.com/lirundong093-glitch/astrbot_plugin_everyday_weatherforecast)

</div>

# 🌤️ 和风天气预报插件 (astrbot_plugin_everyday_weatherforecast)

基于 AstrBot 框架与和风天气 API 开发的智能天气查询与推送插件，目前只支持 aiocqhttp。支持生成可视化天气图片、每日定时推送、AI 智能生成生活指南（可选）、分群配置不同推送城市。

<p align="center">
  <img src="https://img.shields.io/badge/version-v1.1.2-blue" alt="Version">
  <img src="https://img.shields.io/badge/Python-3.8%2B-blue" alt="Python">
  <img src="https://img.shields.io/badge/AstrBot-%E6%8F%92%E4%BB%B6%E6%A1%86%E6%9E%B6-brightgreen" alt="AstrBot">
  <img src="https://img.shields.io/badge/license-AGPL_v3-blue" alt="License">
</p>

## ✨ 主要特性

- **实时天气查询**：支持指定城市查询，返回包含温度、风力、湿度、空气质量、未来预报等信息的美观图片。
- **每日定时推送**：可设置推送时间，自动向白名单群聊发送当日天气预报。
- **分群城市映射**：可通过 Dashboard 管理页面为不同群聊配置专属推送城市，未配置的群使用默认城市。
- **可视化图片生成**：内置图片渲染引擎，无需依赖外部图片生成服务。
- **AI 生活指南（可选）**：接入大语言模型，根据天气数据生成穿衣、出行、紫外线防护等生活建议。
- **节假日检测联动**：结合节假日数据，AI 指南会融入节日氛围提示（需开启 LLM）。
- **灵活配置**：支持通过 WebUI 配置面板和聊天指令动态修改配置，无需重启机器人。

## 生成图片示例
<div align="center">
  
![image_to_show](https://github.com/lirundong093-glitch/astrbot_plugin_everyday_weatherforecast/blob/main/resource/image_to_show/image_to_show_sunnyday.png?raw=true) 
### 当时间为白天且云量小于70时

 </div> 
 <div align="center">
  
![image_to_show](https://github.com/lirundong093-glitch/astrbot_plugin_everyday_weatherforecast/blob/main/resource/image_to_show/image_to_show_foggyday.png?raw=true) 
### 当时间为白天，云量大于70且降水量为0时

 </div> 
 <div align="center">
  
![image_to_show](https://github.com/lirundong093-glitch/astrbot_plugin_everyday_weatherforecast/blob/main/resource/image_to_show/image_to_show_rainyday.png?raw=true) 
### 当时间为白天且降水量大于0时

 </div> 
 <div align="center">
  
![image_to_show](https://github.com/lirundong093-glitch/astrbot_plugin_everyday_weatherforecast/blob/main/resource/image_to_show/image_to_show_night.png?raw=true) 
### 当时间为晚上时

 </div> 
 
## 📥 安装与配置

1. 将插件放入 AstrBot 的 `plugins` 目录。
2. 获取和风天气 API Key 以及 API Host：前往 [和风天气控制台](https://console.qweather.com) 注册并创建应用。
3. 在 AstrBot Dashboard → 插件配置 中填入 Key 和 Host，保存即可。

## 🖥️ Dashboard 管理页面

### 分群城市映射

插件内置了一个 Dashboard 内嵌管理页面，用于配置不同群聊对应的推送城市：

1. 在 AstrBot Dashboard 的「已安装插件」中找到本插件
2. 点击「分群城市映射」进入管理页面
3. 填写群聊标识符（格式：`平台名:消息类型:群号`，如 `napcat:GroupMessage:1350989414`）和对应的城市名
4. 保存后，该群每日推送将使用对应城市；未配置的群使用**默认城市**

> 💡 群聊标识符可以在 `/weather_config` 指令输出的「白名单群」中查看。

### 功能说明

| 操作 | 说明 |
|:---|:---|
| 添加映射 | 在表单中填写群标识符和城市名，点击「保存映射」 |
| 编辑映射 | 点击表格中的「编辑」按钮，修改城市名后保存 |
| 删除映射 | 点击「删除」按钮并确认 |

## 🤖 指令列表

| 指令 | 说明 |
| :--- | :--- |
| `/weather [城市名]` | 查询指定城市天气。不带参数时查询默认城市。 |
| `/weather_test_push` | **调试指令**：立即执行一次每日推送流程。 |
| `/weather_config` | 查看当前所有配置项状态（仅管理员可用）。 |

## 🔄 定时推送逻辑说明

- 定时任务仅会向 `whitelist_groups` 中配置的群聊发送消息。
- 每个群聊可配置独立的推送城市（通过「分群城市映射」页面管理），未配置的群使用 `default_city`。
- 同一城市的天气数据只获取一次，多个群共享同一城市的天气，避免重复 API 调用。
- 推送内容包含：天气图片 + （若开启 LLM）AI 生成的文字指南。
- 插件启动时会在日志中打印当前调度任务状态及下次运行时间。

## 🛠️ 开发与依赖

- **框架**：AstrBot API
- **数据源**：和风天气 API
- **图片生成**：PIL / Pillow（内置渲染）
- **AI 增强**：OpenAI 兼容格式的 LLM 接口

## 📝 许可证

[GNU AGPL v3.0](LICENSE)

## 🙏 鸣谢

- [和风天气](https://www.qweather.com/) 提供稳定准确的天气数据。
- [open-weather-image](https://github.com/Kira-Kitsune/open-weather-image) 提供生图思路。

---

<p align="center">Made with ❤️ by <a href="https://github.com/lirundong093-glitch">Lucy</a></p>
