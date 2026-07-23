<div align="center">

# 🎙️ twt-audio-mcp

### Twitter/X Tweet → Audio · One-Click Generation

**Give any AI assistant an "ear": drop a tweet link, get an audio file back**

[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-ready-green)](https://modelcontextprotocol.io)
[![Edge-TTS](https://img.shields.io/badge/TTS-Edge--TTS-orange)](https://github.com/rany2/edge-tts)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen)](https://github.com/Gashen0/twt-audio-mcp/pulls)

---

[English](README_EN.md) · [中文](README.md)

</div>

---

## 💡 Why?

> **"Found a great thread but my eyes are tired."**
> **"Long read on the commute — can't stare at a screen."**
> **"Your AI assistant should be able to read tweets aloud."**

**twt-audio-mcp** is an MCP tool that converts any Twitter/X tweet (including long-form Articles) into MP3 audio. Supports Chinese and English, uses free Edge-TTS, no paid API required.

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| **📥 Tweet Fetching** | Regular tweets + Article long-forms, full text extraction |
| **🔊 TTS** | Free Edge-TTS MP3 generation, auto language detection |
| **📋 Audio Library** | Local storage with list/send/delete commands |
| **🔄 Dedup** | Same tweet won't be downloaded twice |
| **🧩 MCP Protocol** | Works with any MCP-compatible client |
| **🖥️ CLI Mode** | Use without MCP client if preferred |
| **⚡ One-Click Setup** | `bash setup.sh` does it all |

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

#### 🟢 Cursor / Cline / Continue

Same configuration pattern.

---

## 🎯 Usage

### With AI Assistant (MCP Mode)

> "Convert this tweet to audio: https://x.com/elonmusk/status/1234567890"
> "List my audio library"
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
