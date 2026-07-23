"""
twt-audio-mcp: Twitter Tweet to Audio MCP Server
=================================================

Convert X/Twitter tweets to audio via MCP protocol.
Works with any MCP-compatible client (Claude Desktop, Cursor, Cline, OpenClaw, etc.)

Usage:
    # Via MCP client (recommended)
    # Add to your MCP client config:
    {
        "mcpServers": {
            "twt-audio": {
                "command": "python",
                "args": ["-m", "scripts.server"]
            }
        }
    }

    # Or run directly
    python -m scripts.server
"""

import sys
import os

# Ensure project root is on the path
_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_DIR not in sys.path:
    sys.path.insert(0, _PROJECT_DIR)

import asyncio
import json
from pathlib import Path
from typing import Optional

from fastmcp import FastMCP

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
    """Fetch a tweet and generate audio file

    Args:
        tweet_url: Tweet URL or ID (e.g. https://x.com/user/status/1234567890)

    Returns:
        Result with file path, duration, author info
    """
    import io
    from contextlib import redirect_stdout

    f = io.StringIO()
    with redirect_stdout(f):
        try:
            cmd_add(tweet_url)
        except SystemExit:
            pass

    output = f.getvalue()

    # Try to parse the trailing JSON
    json_marker = "__JSON_OUTPUT__"
    if json_marker in output:
        json_str = output.split(json_marker)[1].strip()
        try:
            data = json.loads(json_str)
            if data.get("duplicate"):
                return f"Already exists: {data['name']} ({data['duration_str']})"
            return (
                f"Audio generated: {data['name']}\n"
                f"   Author: {data.get('author', 'unknown')}\n"
                f"   Duration: {data['duration_str']}\n"
                f"   File: {data['file']}"
            )
        except json.JSONDecodeError:
            pass

    return output


@mcp.tool()
def list_audios() -> str:
    """List all audios in the library"""
    index = _load_index()
    audios = index.get("audios", [])

    if not audios:
        return "Audio library is empty"

    lines = [f"Audio library ({len(audios)} items)\n"]
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
    """Get the full path of an audio file

    Args:
        index_or_name: Audio index (e.g. 1) or name

    Returns:
        Audio file path
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

    # Try to parse the trailing JSON
    json_marker = "__JSON_OUTPUT__"
    if json_marker in output:
        json_str = output.split(json_marker)[1].strip()
        try:
            data = json.loads(json_str)
            return f"{data['name']}\n{data['file']}"
        except json.JSONDecodeError:
            pass

    return output


@mcp.tool()
def delete_audio(index_or_name: str) -> str:
    """Delete an audio from the library

    Args:
        index_or_name: Audio index (e.g. 1) or name

    Returns:
        Result message
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
    """Check twt-audio-mcp configuration status — Twitter Cookie & dependencies"""
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
                "Cookie config incomplete\n"
                f"   Missing: {', '.join(missing)}\n"
                f"   Config: {Path(__file__).parent.parent / 'data' / 'secrets' / 'x_cookies.json'}\n"
                "   Login to X.com in browser, copy auth_token, ct0, twid from DevTools"
            )

        # Check TTS dependency
        try:
            import edge_tts
            edge_ok = True
        except ImportError:
            edge_ok = False

        audio_count = len(_load_index().get("audios", []))

        parts = [
            "twt-audio-mcp status",
            f"   Twitter Cookie: configured",
            f"   Edge-TTS: {'installed' if edge_ok else 'missing (pip install edge-tts)'}",
            f"   Audio library: {audio_count} items",
            f"   Data dir: {AUDIO_DIR}",
        ]

        return "\n".join(parts)
    except FileNotFoundError:
        return (
            "Cookie file not found\n"
            f"   Path: {Path(__file__).parent.parent / 'data' / 'secrets' / 'x_cookies.json'}\n"
            "   Login to X.com in browser, copy cookies"
        )


# =========================================================================
# Entry point
# =========================================================================

if __name__ == "__main__":
    print("twt-audio-mcp server starting...")
    mcp.run()
