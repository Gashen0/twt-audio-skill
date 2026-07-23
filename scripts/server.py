"""twt-audio-mcp: MCP Server — 薄协议层，调用 core，不 redirect_stdout。"""

import sys
from pathlib import Path

_PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(_PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(_PROJECT_DIR))

import json

from fastmcp import FastMCP

from scripts.core import TwtAudioCore, CoreError

# ── 单例 ─────────────────────────────────────────────────────────────

_core = TwtAudioCore(_PROJECT_DIR)
mcp = FastMCP("twt-audio")


# ── Tools ────────────────────────────────────────────────────────────

@mcp.tool()
def tweet_to_audio(tweet_url: str) -> str:
    """Fetch a tweet and generate an audio file.

    Args:
        tweet_url: Tweet URL or ID (e.g. https://x.com/user/status/1234567890)

    Returns:
        Structured result with file path, duration, author info
    """
    result = _core.add_tweet(tweet_url)
    if not result.success:
        return f"Error: {result.error}"
    if result.duplicate:
        return f"Already exists: {result.name} ({result.duration_str})"
    return json.dumps(result.to_dict(), ensure_ascii=False)


@mcp.tool()
def list_audios() -> str:
    """List all audios in the library"""
    audios = _core.list_audios()
    if not audios:
        return "Audio library is empty"
    lines = [f"Audio library ({len(audios)} items)\n"]
    for a in audios:
        author = f" @{a['author']}" if a.get("author") else ""
        created = a.get("created_at", "")
        name = a.get("name", a.get("ascii_name", ""))
        lines.append(f"{a['index']}. {name}")
        lines.append(f"   {a['duration_str']}{author} · {created}")
    return "\n".join(lines)


@mcp.tool()
def get_audio_path(index_or_name: str) -> str:
    """Get the full path of an audio file

    Args:
        index_or_name: Audio index (e.g. 1) or name

    Returns:
        Audio file path
    """
    try:
        audio = _core.get_audio(index_or_name)
    except CoreError as e:
        return f"Error: {e}"
    path = audio.get("send_file") or audio["file"]
    name = audio.get("name", audio.get("ascii_name", ""))
    return f"{name}\n{path}"


@mcp.tool()
def delete_audio(index_or_name: str) -> str:
    """Delete an audio from the library

    Args:
        index_or_name: Audio index (e.g. 1) or name

    Returns:
        Result message
    """
    try:
        audio = _core.delete_audio(index_or_name)
    except CoreError as e:
        return f"Error: {e}"
    name = audio.get("name", audio.get("ascii_name", ""))
    return f"Deleted: {name}"


@mcp.tool()
def check_status() -> str:
    """Check twt-audio-mcp configuration — Twitter Cookie & dependencies"""
    status = _core.check_config()
    parts = ["twt-audio-mcp status"] if status["ok"] else ["Configuration incomplete"]
    for name, check in status["checks"].items():
        icon = "✅" if check.get("ok") else "❌"
        if "count" in check:
            parts.append(f"   {icon} {name}: {check['count']} items")
        elif "msg" in check:
            parts.append(f"   {icon} {name}: {check['msg']}")
        else:
            parts.append(f"   {icon} {name}")
    if not status["ok"]:
        parts.append("\nRun `python scripts/twt_audio.py check` for details")
    return "\n".join(parts)


if __name__ == "__main__":
    print("twt-audio-mcp server starting...")
    mcp.run()
