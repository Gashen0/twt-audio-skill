<div align="center">

# 🎙️ twt-audio

### This is an **AI Skill** — Turn X/Twitter tweets into MP3 audio

**Any AI agent can use it directly. You're not installing a tool — you're giving your AI a superpower.**

[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![AI Skill](https://img.shields.io/badge/AI-Skill-brightgreen)](SKILL.md)
[![Edge-TTS](https://img.shields.io/badge/TTS-Edge--TTS-orange)](https://github.com/rany2/edge-tts)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen)](https://github.com/Gashen0/twt-audio-mcp/pulls)

---

[English](README_EN.md) · [中文](README.md)

</div>

---

## 💡 Why?

> **Found a great thread but your eyes are tired?**
> **Long read on the commute — can't stare at a screen?**
> **Cooking, working out, or in bed — wish you could *listen* to tweets?**

**twt-audio-mcp** gives your AI assistant one more skill: grab any Twitter/X tweet (including long-form Articles), turn it into MP3, and read it aloud. No paid APIs, fully free.

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| **📥 Full Text** | Regular tweets + Articles, full content extraction |
| **🔊 AI Narration** | Free Edge-TTS MP3, auto language detection (CN/EN) |
| **📋 Audio Library** | Local storage with list/send/delete |
| **🔄 Dedup** | Same tweet won't be generated twice |
| **🧩 MCP Protocol** | Works with any MCP-compatible AI assistant |
| **🖥️ CLI Mode** | Works without MCP client if preferred |
| **⚡ One-Click** | `bash setup.sh` does it all |

### Performance

| Scenario | Time |
|----------|------|
| Duplicate tweet | 0s |
| Short tweet (~100 chars) | ~7s |
| Article (~10k chars) | ~30s |

---

## 🚀 Quick Start

```bash
# 1. Clone
git clone https://github.com/Gashen0/twt-audio-mcp.git
cd twt-audio-mcp

# 2. One-click install
bash setup.sh

# 3. Configure Twitter Cookie
bash setup.sh --cookie
```

### Cookie Setup

Log into [x.com](https://x.com) in your browser, open DevTools → Application → Cookies → x.com, copy:

- `auth_token`
- `ct0`
- `twid`

Edit `data/secrets/x_cookies.json`:

```json
{
  "auth_token": "your_auth_token",
  "ct0": "your_ct0",
  "twid": "your_twid"
}
```

### MCP Configuration

#### 🟢 Claude Desktop

```json
{
  "mcpServers": {
    "twt-audio": {
      "command": "python",
      "args": ["-m", "scripts.server"],
      "cwd": "/absolute/path/twt-audio-mcp"
    }
  }
}
```

#### 🟢 Cursor / Cline / OpenClaw / Continue

Same configuration pattern.

---

## 🎯 Usage

### With AI Assistant (MCP Mode)

> "Read this tweet to me: https://x.com/elonmusk/status/1234567890"
> "What's in my audio library?"
> "Send me audio #3"

5 built-in tools:

| Tool | Description |
|------|-------------|
| `tweet_to_audio(url)` | Fetch tweet → generate audio |
| `list_audios()` | List audio library |
| `get_audio_path(index)` | Get audio file path |
| `delete_audio(index)` | Delete audio |
| `check_status()` | Check configuration status |

### CLI Mode

```bash
# Add tweet
python scripts/twt_audio.py add https://x.com/user/status/1234567890

# List library
python scripts/twt_audio.py list

# Get audio path
python scripts/twt_audio.py send 1

# Delete
python scripts/twt_audio.py delete 1
```

---

## 📁 Project Structure

```
twt-audio-mcp/
├── setup.sh                  # One-click installer
├── config.yaml               # Configuration
├── requirements.txt          # Python dependencies
├── scripts/
│   ├── server.py             # MCP Server (fastmcp)
│   ├── twt_read.py           # Tweet fetching engine
│   ├── twt_audio.py          # CLI main program
│   └── __init__.py           # Package imports
└── data/
    ├── twts/                 # Audio storage
    │   └── index.json        # Audio index
    └── secrets/
        └── x_cookies.json    # Twitter cookies (user configured)
```

---

## ⚙️ Configuration

Edit `config.yaml`:

```yaml
tts:
  voices:
    zh: "zh-CN-XiaoxiaoNeural"
    en: "en-US-JennyNeural"
  default_rate: "+20%"
  max_filename_len: 30

twitter:
  bearer: "AAAAAAAAAAAA..."
  rate_limit_seconds: 5
```

---

## 📄 License

MIT License

---

<div align="center">

### ⭐ Star this repo if you find it useful!

[![Star](https://img.shields.io/github/stars/Gashen0/twt-audio-mcp?style=social)](https://github.com/Gashen0/twt-audio-mcp)

</div>
