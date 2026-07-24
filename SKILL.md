---
name: twt-audio
description: X/Twitter 推文转音频 Skill — 丢一条推文链接，AI 自动抓取全文并生成 MP3 语音
version: 2.0.0
author: Gashen0
license: MIT
metadata:
  hermes:
    tags: [twitter, audio, tts, mcp, edge-tts, feishu]
    category: media
    related_skills: []
---

# twt-audio: 推文转音频 Skill

## 这是什么

一个 **AI 智能体可以直接用的技能包**。把这条推文的链接丢给 AI，AI 会自动：

1. 抓取推文全文（普通推文 + Article 长文都能抓）
2. 用 Edge-TTS 免费生成 MP3 音频
3. 返回音频文件给你

> 👉 **你不用自己装、不用自己配**。AI 拿到这个 Skill 包就知道怎么用了。

## 对用户的价值

| 痛点 | 解决 |
|------|------|
| 刷到好推文眼睛累了 | 转成音频**听**，不用看屏幕 |
| 通勤/开车/运动想看内容 | AI 念给你听，解放双手和眼睛 |
| 干货长文没时间读完 | 转成 MP3，走路洗澡时听 |
| 不懂技术不会装工具 | AI 帮你跑，你只说一句"帮我转成音频" |

## 核心流程

```
用户发推文链接
  ↓
提取 tweet ID → 查重（重复则秒回）
  ↓
GraphQL 抓取推文全文
  ├─ 普通推文：1 次请求
  └─ Article 长文：2 次请求
  ↓
Edge-TTS 生成 MP3（免费，无需 API Key）
  ↓
返回音频文件路径
```

## AI 智能体使用说明

### 先决条件

1. Python 3.10+
2. 安装依赖：`pip install -r requirements.txt`
3. 配置 Twitter Cookie（见下方说明）

### 配置 Twitter Cookie（必须）

X/Twitter 需要 cookie 认证才能抓取推文。

**让用户帮你操作：**

> "请打开浏览器登录 x.com，打开开发者工具 → Application → Cookies → x.com，复制三个值：auth_token、ct0、twid"

然后运行：
```bash
bash setup.sh --cookie
```

或手动写入 `data/secrets/x_cookies.json`：
```json
{
  "auth_token": "xxx",
  "ct0": "xxx",
  "twid": "xxx"
}
```

### CLI 命令

```bash
# 添加推文 → 生成音频
python scripts/twt_audio.py add "https://x.com/user/status/1234567890"

# 查看音频库
python scripts/twt_audio.py list

# 获取第 1 条音频路径（发给用户）
python scripts/twt_audio.py send 1

# 删除第 1 条
python scripts/twt_audio.py delete 1
```

### MCP 模式（可选）

如果 AI 平台支持 MCP（Claude Desktop、Cursor、Cline 等），可以用 MCP 服务器模式：

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

MCP 模式下暴露的工具：

| 工具 | 说明 |
|------|------|
| `tweet_to_audio(url)` | 抓取推文 → 生成音频 |
| `list_audios()` | 列出音频库 |
| `get_audio_path(index)` | 获取音频文件路径 |
| `delete_audio(index)` | 删除音频 |
| `check_status()` | 检查配置状态 |

### 性能参考

| 场景 | 耗时 |
|------|------|
| 重复推文（命中缓存） | 0s |
| 短推文（~100字） | ~7s |
| Article 长文（~10k字） | ~30s |

## 配置文件

编辑 `config.yaml` 即可调整行为，无需改代码：

```yaml
tts:
  voices:
    zh: "zh-CN-XiaoxiaoNeural"   # 中文女声
    en: "en-US-JennyNeural"       # 英文女声
  default_rate: "+20%"            # 语速（+0%=正常，+20%=稍快）

twitter:
  rate_limit_seconds: 5           # API 请求间隔
  bearer: ""                      # Bearer Token（从 X 网页版获取）
```

## 踩坑记录（AI 智能体注意）

1. **飞书上传不支持中文文件名** — 已用 pypinyin 自动转拼音，无需处理
2. **Article 推文需要两次 GraphQL 请求** — TweetDetail 只返回摘要，需再调 TweetResultByRestId 拿 Draft.js 完整内容
3. **GraphQL queryId 会过期** — 从 X 的 JS bundle 提取，更新 config.yaml 中 `twitter` 段
4. **Cookie 认证比 Bearer token 稳定** — Bearer token 公开但限流严格
5. **速率限制** — 默认 5 秒间隔，防封

## 目录结构

```
twt-audio-mcp/
├── SKILL.md              # 🎯 本文件 — AI 智能体的使用说明书
├── _meta.json            # Skill 元数据
├── README.md             # 人类友好的说明
├── config.yaml           # 配置文件
├── requirements.txt      # Python 依赖
├── setup.sh              # 一键安装脚本
├── scripts/
│   ├── server.py         # MCP Server
│   ├── twt_read.py       # 推文抓取引擎
│   ├── twt_audio.py      # CLI 主程序
│   └── __init__.py
└── data/
    ├── twts/             # 音频存储
    └── secrets/          # Cookie 配置（用户自行填写）
```

## 触发词（AI 理解用）

用户说以下任何一句，就是要用这个 Skill：

- "帮我把这条推文转成音频"
- "念给我听这条推文"
- "把这篇长文转成 MP3"
- "列出音频库"
- "把第 X 条音频发给我"
