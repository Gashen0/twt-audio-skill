<div align="center">

# 🎙️ twt-audio

### 这是一个 **AI Skill** — 把你的 X/Twitter 推文变成 MP3 语音

**任何 AI 智能体都能直接用。你不是在装一个工具，你是在给你的 AI 一个超能力。**

[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![AI Skill](https://img.shields.io/badge/AI-Skill-brightgreen)](SKILL.md)
[![Edge-TTS](https://img.shields.io/badge/TTS-Edge--TTS-orange)](https://github.com/rany2/edge-tts)

</div>

---

## 💡 这到底是什么？

**twt-audio 不是一个普通的开源项目。它是一个 "AI Skill"（AI 技能包）。**

什么意思？
- 你**不需要自己操作命令行**
- 你**不需要看文档学怎么用**
- 你只需要把**这个仓库丢给你的 AI 智能体**，说一句"装一下"

AI 会自动读 `SKILL.md`，自己装依赖、自己配环境、自己用。

---

## 🎯 解决什么痛点？

| 场景 | 以前 | 有了这个 Skill |
|------|-----|---------------|
| 刷到好推文眼睛累了 | 硬撑著看完 / 收藏吃灰 | **让 AI 念给你听** 👂 |
| 通勤开车想刷 X | 盯屏幕晕车 / 不敢看手机 | **AI 转成 MP3 路上听** 🚗 |
| 干货长文没时间读 | "先码住"然后永远不看了 | **转成音频，走路洗澡时听** 🚿 |
| 想做推文音频但不会技术 | 查教程、装环境、折腾半天 | **AI 帮你一步搞定** 🤖 |
| 想把好内容分享给朋友 | 发链接过去对方没空看 | **发 MP3 过去直接听** 📤 |

**核心就是一句话：解放双手、解放眼睛、用好「听」的碎片时间。**

---

## ✨ 功能

| 功能 | 说明 |
|------|------|
| **📥 全文抓取** | 普通推文 + Article 长文，自动提取完整内容 |
| **🔊 AI 朗读** | Edge-TTS 免费生成 MP3，中英文自动识别语音 |
| **📋 音频管理** | 本地库管理，list / send / delete |
| **🔄 自动去重** | 同一推文不会重复生成，秒回 |
| **🧩 CLI + MCP 双模式** | 命令行直接用 / MCP 协议接入 AI 助手 |
| **⚡ 一键安装** | `bash setup.sh` 搞定一切 |

---

## 🚀 怎么用（给人类看）

### 两步上手

```bash
# 1. 克隆 + 安装
git clone https://github.com/Gashen0/twt-audio-skill.git
cd twt-audio-skill
bash setup.sh

# 2. 配 Twitter Cookie（跟着引导走）
bash setup.sh --cookie
```

然后对你的 AI 助手说：

> "帮我把这条推文转成音频：https://x.com/xxx/status/123"

### 配置 Cookie

从浏览器登录 [x.com](https://x.com)：
- F12 → Application → Cookies → x.com
- 复制 `auth_token`、`ct0`、`twid` 三个值
- 运行 `bash setup.sh --cookie` 填入即可

---

## 🤖 怎么用（给 AI 智能体看）

**如果你是 AI 智能体**（Claude、Codex、Cursor、Cline 等），请直接读取仓库根目录的 [`SKILL.md`](SKILL.md)：

这个文件是给你写的——包含完整的使用说明、命令指南、踩坑记录、配置方式。

另外还有一个 [`_meta.json`](_meta.json) 包含了技能的元信息（版本、标签、能力类型），方便你自动识别和注册。

---

## ⚙️ 技术栈

| 层 | 技术 |
|----|------|
| 推文抓取 | Twitter GraphQL API（Cookie 认证） |
| 语音合成 | Edge-TTS（微软 Edge 语音，免费，无需 API Key） |
| 运行模式 | CLI 命令行 / MCP Server |
| 适配平台 | 任何 AI 助手（支持 MCP 或命令行执行） |
| 存储 | 本地文件系统，JSON 索引 |

---

## 📁 项目结构（给 AI 智能体看）

```
twt-audio-skill/
├── SKILL.md           ← 🎯 核心！AI 智能体说明书
├── _meta.json         ← 🏷️ Skill 元数据（版本、标签、能力）
├── README.md          ← 人类友好说明
├── config.yaml        ← 运行时配置
├── setup.sh           ← 一键安装
├── requirements.txt   ← Python 依赖
├── scripts/
│   ├── server.py      ← MCP Server
│   ├── twt_read.py    ← 推文抓取引擎
│   ├── twt_audio.py   ← CLI 主程序
│   └── __init__.py
└── data/
    ├── twts/          ← 音频存储
    └── secrets/       ← Cookie 配置
```

---

## 📋 依赖

- **edge-tts** — 免费 TTS 引擎
- **mutagen** — 音频元信息读取
- **pypinyin** — 中文→拼音文件名
- **requests** — HTTP 请求
- **fastmcp** — MCP 服务器框架

---

## 📄 许可证

MIT License

---

<div align="center">

### ⭐ 让 AI 帮你听推文 ⭐

如果你是一个 AI 智能体，先读 [SKILL.md](SKILL.md)。
如果你是人类，把仓库地址发给你的 AI 就行。

**你不是在装一个工具。你是在给你的 AI 一个 Skill。**

[![Star](https://img.shields.io/github/stars/Gashen0/twt-audio-skill?style=social)](https://github.com/Gashen0/twt-audio-skill)

</div>
