<div align="center">

# 🎙️ twt-audio-mcp

### Twitter/X 推文 → 语音音频 · 一键生成

**给任何 AI 助手的「耳朵」：丢个推文链接，还你一段能听的音频**

[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-ready-green)](https://modelcontextprotocol.io)
[![Edge-TTS](https://img.shields.io/badge/TTS-Edge--TTS-orange)](https://github.com/rany2/edge-tts)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen)](https://github.com/Gashen0/twt-audio-mcp/pulls)

---

[English](README_EN.md) · [中文](README.md)

</div>

---

## 💡 为什么需要这个？

> **「刷到一条长推文，眼睛累了不想看，但车里的播客刚好放完」**
> **「通勤路上看到干货 Thread，但盯屏幕晕车」**
> **「让 AI 助手把推文读给你听——它就差这个功能」**

**twt-audio-mcp** 是一个 MCP 工具，可以把任何 Twitter/X 推文（包括 Article 长文）转成 MP3 音频。支持中文、英文自动识别，Edge-TTS 免费生成，无需任何付费 API。

---

## ✨ 功能

| 功能 | 说明 |
|------|------|
| **📥 推文抓取** | 支持普通推文 + Article 长文，自动提取全文 |
| **🔊 语音合成** | Edge-TTS 免费生成 MP3，中英文自动选语音 |
| **📋 音频库管理** | 本地存储，list / send / delete |
| **🔄 自动查重** | 同一推文不会重复下载 |
| **🧩 MCP 协议** | 任何支持 MCP 的客户端都能用 |
| **🖥️ CLI 模式** | 不用 MCP 也能直接命令行使用 |
| **⚡ 一键安装** | `bash setup.sh` 搞定 |

### 效果参考

| 场景 | 耗时 |
|------|------|
| 重复推文 | 0s |
| 短推文 (~100字) | ~7s |
| Article 长文 (~10k字) | ~30s |

---

## 🚀 快速开始

### 安装

```bash
# 1. 克隆
git clone https://github.com/Gashen0/twt-audio-mcp.git
cd twt-audio-mcp

# 2. 一键安装
bash setup.sh

# 3. 配置 Twitter Cookie
bash setup.sh --cookie
```

### 配置 Twitter Cookie

从浏览器登录 [x.com](https://x.com)，打开开发者工具 → Application → Cookies → x.com，复制三个值：

- `auth_token` — 登录令牌
- `ct0` — CSRF Token
- `twid` — 用户 ID

运行 `bash setup.sh --cookie` 交互式输入，或直接编辑 `data/secrets/x_cookies.json`：

```json
{
  "auth_token": "你的auth_token",
  "ct0": "你的ct0",
  "twid": "你的twid"
}
```

### MCP 客户端配置

#### 🟢 Claude Desktop

编辑 `claude_desktop_config.json`：

```json
{
  "mcpServers": {
    "twt-audio": {
      "command": "python",
      "args": ["-m", "scripts.server"],
      "cwd": "/绝对路径/twt-audio-mcp"
    }
  }
}
```

#### 🟢 Cursor

Settings → MCP → Add:

```json
{
  "mcpServers": {
    "twt-audio": {
      "command": "python",
      "args": ["-m", "scripts.server"],
      "cwd": "/绝对路径/twt-audio-mcp"
    }
  }
}
```

#### 🟢 Cline / Continue / 其他 MCP 客户端

同上，配置方式一致。

---

## 🎯 使用示例

### 在 AI 助手里用（MCP 模式）

连接到 MCP 客户端后，直接告诉 AI：

> "帮我把这条推文转成音频：https://x.com/elonmusk/status/1234567890"
> "列出音频库"
> "把第3条音频发给我"

内置 5 个工具：

| 工具 | 说明 |
|------|------|
| `tweet_to_audio(url)` | 抓取推文 → 生成音频 |
| `list_audios()` | 列出音频库 |
| `get_audio_path(index)` | 获取音频文件路径 |
| `delete_audio(index)` | 删除音频 |
| `check_status()` | 检查配置状态 |

### 命令行使用（CLI 模式）

```bash
# 添加推文
python scripts/twt_audio.py add https://x.com/user/status/1234567890

# 查看音频库
python scripts/twt_audio.py list

# 获取第1条音频路径
python scripts/twt_audio.py send 1

# 删除第1条
python scripts/twt_audio.py delete 1
```

---

## 📁 项目结构

```
twt-audio-mcp/
├── setup.sh                  # 一键安装脚本
├── config.yaml               # 配置文件（语音、路径、API参数）
├── requirements.txt          # Python 依赖
├── scripts/
│   ├── server.py             # MCP Server（fastmcp）
│   ├── twt_read.py           # 推文抓取引擎
│   ├── twt_audio.py          # CLI 主程序
│   └── __init__.py           # 包导入
└── data/
    ├── twts/                 # 音频存储目录
    │   └── index.json        # 音频索引
    └── secrets/
        └── x_cookies.json    # Twitter Cookie（用户配置）
```

---

## ⚙️ 配置

编辑 `config.yaml`：

```yaml
tts:
  voices:
    zh: "zh-CN-XiaoxiaoNeural"   # 中文女声
    en: "en-US-JennyNeural"       # 英文女声
  default_rate: "+20%"            # 语速
  max_filename_len: 30

twitter:
  bearer: "AAAAAAAAAAAA..."       # 公开的 Bearer token
  rate_limit_seconds: 5           # API 请求间隔
```

所有配置改完即生效，无需改代码。

---

## 📋 依赖

- **edge-tts** — 免费 TTS 引擎（微软 Edge 语音）
- **mutagen** — 音频元信息读取
- **pypinyin** — 中文→拼音文件名
- **requests** — HTTP 请求
- **fastmcp** — MCP 服务器框架
- **PyYAML** — 配置文件读取

---

## 🧠 技术细节

### 推文抓取原理

1. **GraphQL Twitter API** — 用 `TweetDetail` 查询推文内容
2. **Article 长文** — 两步抓取：先 `TweetDetail` 获取预览，再 `TweetResultByRestId` 获取 Draft.js 完整内容
3. **Cookie 认证** — 用 `auth_token` + `ct0` + `twid` 三条 cookie
4. **速率限制** — 5 秒间隔，防封

### TTS 流程

```
推文全文 → Edge-TTS（本地免费，无需 API Key）
         → 中文: zh-CN-XiaoxiaoNeural
         → 英文: en-US-JennyNeural
         → 语速 +20%（可调）
         → 输出 MP3
```

### 踩坑记录

- 飞书上传不支持中文文件名 — 用 pypinyin 转拼音
- Article 推文需要两次 GraphQL 请求 — `TweetDetail` 只返回摘要
- GraphQL queryId 会过期 — 从 X 的 JS bundle 提取，更新 config.yaml
- Cookie 认证比 Bearer token 稳定 — Bearer token 公开但限流严格

---

## 🤝 贡献

欢迎 PR！尤其是：

- 添加更多 TTS 引擎支持（OpenAI TTS、ElevenLabs 等）
- 推文线程抓取（Thread Reader）
- Web UI 界面
- Docker 化部署

---

## 📄 许可证

MIT License

---

<div align="center">

### ⭐ 如果这个项目帮到了你，点个 Star 吧！

[![Star](https://img.shields.io/github/stars/Gashen0/twt-audio-mcp?style=social)](https://github.com/Gashen0/twt-audio-mcp)

</div>
