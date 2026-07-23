"""
twt-audio-mcp: Twitter推文转音频 MCP Server
===============================================

把 X/Twitter 推文转成语音音频的 MCP 工具。
任何支持 MCP 的客户端（Claude Desktop、Cursor、Cline 等）都能用。

Usage:
    # 通过 MCP 客户端连接（推荐）
    # 在客户端 MCP 配置中添加:
    {
        "mcpServers": {
            "twt-audio": {
                "command": "python",
                "args": ["-m", "scripts.server"]
            }
        }
    }

    # 或直接运行
    python -m scripts.server
"""

import sys
import os

# 确保项目根目录在 path 中
_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_DIR not in sys.path:
    sys.path.insert(0, _PROJECT_DIR)

import asyncio
import json
from pathlib import Path
from typing import Optional

# pip install fastmcp
from fastmcp import FastMCP

# 导入内部模块
from scripts.twt_read import read_tweet, extract_tweet_id, load_cookies
from scripts.twt_audio import (
    cmd_add, cmd_list, cmd_send, cmd_delete,
    _load_index, _format_duration, _now_cst,
    AUDIO_DIR, INDEX_PATH,
)


# =========================================================================
# MCP Server
# =========================================================================

mcp = FastMCP(
    "twt-audio",
)


@mcp.tool()
def tweet_to_audio(tweet_url: str) -> str:
    """抓取推文并生成音频文件

    Args:
        tweet_url: 推文 URL 或 ID（如 https://x.com/user/status/1234567890）

    Returns:
        生成结果，包含音频文件路径、时长、作者等信息
    """
    # cmd_add 会打印到 stdout，我们捕获输出
    import io
    from contextlib import redirect_stdout

    f = io.StringIO()
    with redirect_stdout(f):
        try:
            cmd_add(tweet_url)
        except SystemExit:
            pass

    output = f.getvalue()

    # 尝试解析最后的 JSON
    json_marker = "__JSON_OUTPUT__"
    if json_marker in output:
        json_str = output.split(json_marker)[1].strip()
        try:
            data = json.loads(json_str)
            if data.get("duplicate"):
                return f"⚠️ 已存在: {data['name']} ({data['duration_str']})"
            return (
                f"✅ 音频已生成: {data['name']}\n"
                f"   作者: {data.get('author', '未知')}\n"
                f"   时长: {data['duration_str']}\n"
                f"   文件: {data['file']}"
            )
        except json.JSONDecodeError:
            pass

    return output


@mcp.tool()
def list_audios() -> str:
    """列出音频库中的所有音频"""
    index = _load_index()
    audios = index.get("audios", [])

    if not audios:
        return "📭 音频库为空"

    lines = [f"📚 音频库 ({len(audios)}条)\n"]
    for i, audio in enumerate(audios, 1):
        dur = _format_duration(audio.get("duration", 0))
        author = audio.get("author", "")
        author_str = f" @{author}" if author else ""
        created = audio.get("created_at", "")
        name = audio.get("name", audio.get("ascii_name", ""))
        lines.append(f"{i}. {name}")
        lines.append(f"   {dur}{author_str} · {created}")

    return "\n".join(lines)


@mcp.tool()
def get_audio_path(index_or_name: str) -> str:
    """获取音频文件的完整路径

    Args:
        index_or_name: 音频编号（如 1）或名称

    Returns:
        音频文件路径，可用于发送/分享
    """
    import io
    from contextlib import redirect_stdout

    f = io.StringIO()
    with redirect_stdout(f):
        try:
            cmd_send(index_or_name)
        except SystemExit:
            pass

    output = f.getvalue()

    # 尝试解析最后的 JSON
    json_marker = "__JSON_OUTPUT__"
    if json_marker in output:
        json_str = output.split(json_marker)[1].strip()
        try:
            data = json.loads(json_str)
            return f"📤 {data['name']}\n📁 {data['file']}"
        except json.JSONDecodeError:
            pass

    return output


@mcp.tool()
def delete_audio(index_or_name: str) -> str:
    """删除音频库中的某条音频

    Args:
        index_or_name: 音频编号（如 1）或名称

    Returns:
        删除结果
    """
    import io
    from contextlib import redirect_stdout

    f = io.StringIO()
    with redirect_stdout(f):
        try:
            cmd_delete(index_or_name)
        except SystemExit:
            pass

    return f.getvalue().strip()


@mcp.tool()
def check_status() -> str:
    """检查 twt-audio-mcp 配置状态 — 是否已配置 Twitter Cookie"""
    try:
        cookies = load_cookies()
        auth_token = cookies.get("auth_token", "")
        ct0 = cookies.get("ct0", "")
        twid = cookies.get("twid", "")

        missing = []
        if not auth_token:
            missing.append("auth_token")
        if not ct0:
            missing.append("ct0")
        if not twid:
            missing.append("twid")

        if missing:
            return (
                "❌ Cookie 配置不完整\n"
                f"   缺少: {', '.join(missing)}\n"
                f"   配置文件: {Path(__file__).parent.parent / 'data' / 'secrets' / 'x_cookies.json'}\n"
                "   从浏览器 X.com 登录后复制 auth_token, ct0, twid"
            )

        # 检查 TTS 依赖
        try:
            import edge_tts
            edge_ok = True
        except ImportError:
            edge_ok = False

        audio_count = len(_load_index().get("audios", []))

        parts = [
            "✅ twt-audio-mcp 状态",
            f"   Twitter Cookie: ✅ 已配置",
            f"   Edge-TTS: {'✅' if edge_ok else '❌'} {'已安装' if edge_ok else '未安装 (pip install edge-tts)'}",
            f"   音频库: {audio_count} 条",
            f"   数据目录: {AUDIO_DIR}",
        ]

        return "\n".join(parts)
    except FileNotFoundError:
        return (
            "❌ Cookie 文件未找到\n"
            f"   路径: {Path(__file__).parent.parent / 'data' / 'secrets' / 'x_cookies.json'}\n"
            "   从浏览器 X.com 登录后复制 cookie"
        )


# =========================================================================
# 主入口
# =========================================================================

if __name__ == "__main__":
    print("🚀 twt-audio-mcp server starting...")
    mcp.run()
