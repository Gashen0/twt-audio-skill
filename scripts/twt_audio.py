#!/usr/bin/env python3
"""
Twitter-to-Audio Pipeline
抓取推文 → TTS生成音频 → 存储到库 → 按需发送

Usage:
 python3 twt_audio.py add <tweet_url_or_id>     抓取推文并生成音频
 python3 twt_audio.py list                       列出音频库
 python3 twt_audio.py send <name_or_number>      输出音频文件路径
 python3 twt_audio.py delete <name_or_number>    删除音频
"""

import argparse
import asyncio
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

# Add scripts dir to path for twt_read import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from twt_read import read_tweet, extract_tweet_id

import edge_tts

# ---------------------------------------------------------------------------
# Configuration — loaded from config.yaml, with hardcoded fallbacks
# ---------------------------------------------------------------------------

_PROJECT_DIR = Path(__file__).resolve().parent.parent  # twt-audio-mcp/
_CONFIG_PATH = _PROJECT_DIR / "config.yaml"
_DATA_DIR = _PROJECT_DIR / "data"


def _load_config() -> dict:
    """Load config.yaml; return empty dict on failure."""
    try:
        import yaml
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except (ImportError, FileNotFoundError):
        return {}


_CFG = _load_config()

_tts_cfg = _CFG.get("tts", {})
_path_cfg = _CFG.get("paths", {})

# Data paths
AUDIO_DIR = _DATA_DIR / _path_cfg.get("audio_dir", "twts")
INDEX_PATH = AUDIO_DIR / _path_cfg.get("index_file", "twts/index.json").split("/")[-1]

# TTS voices (configurable)
VOICES = _tts_cfg.get("voices", {
    "zh": "zh-CN-XiaoxiaoNeural",
    "en": "en-US-JennyNeural",
})

# Default TTS rate: +20% for faster generation, smaller files, minimal
# perceptual difference. Can be overridden via --rate flag.
DEFAULT_TTS_RATE = _tts_cfg.get("default_rate", "+20%")

# Max filename lengths
MAX_CJK_NAME_WIDTH = 20  # CJK chars count as 2 width
MAX_ASCII_NAME_LEN = _tts_cfg.get("max_filename_len", 30)


def _load_index() -> dict:
    """Load audio index from disk."""
    if not INDEX_PATH.exists():
        return {"audios": []}
    with open(INDEX_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_index(data: dict):
    """Save audio index to disk."""
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _sanitize_filename(name: str) -> str:
    """Clean a name for use as filename (internal/display name, may be CJK).

    Removes special characters, truncates based on display width
    (CJK chars count as 2 width).
    """
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    name = re.sub(r'[\s\n]+', ' ', name).strip()
    width = 0
    truncated = ""
    for ch in name:
        w = 2 if '\u4e00' <= ch <= '\u9fff' or '\u3000' <= ch <= '\u303f' else 1
        if width + w > MAX_CJK_NAME_WIDTH:
            break
        width += w
        truncated += ch
    name = truncated.rstrip()
    name = name.rstrip('.')
    return name or "untitled"


def _cjk_to_ascii(cjk_name: str) -> str:
    """Convert CJK display name to ASCII filename for upload compatibility.

    Some upload APIs reject non-ASCII filenames (40009 error).
    Strategy: pypinyin (pinyin romanization) → extract English words → hash fallback.
    """
    try:
        from pypinyin import lazy_pinyin, Style
        parts = lazy_pinyin(cjk_name, style=Style.NORMAL)
        slug = '_'.join(parts)
        slug = re.sub(r'[^a-zA-Z0-9_]', '', slug)
        slug = re.sub(r'_+', '_', slug).strip('_')
        if slug and len(slug) >= 3:
            if len(slug) > MAX_ASCII_NAME_LEN:
                words = slug.split('_')
                truncated = []
                total = 0
                for w in words:
                    if total + len(w) + 1 > MAX_ASCII_NAME_LEN:
                        break
                    truncated.append(w)
                    total += len(w) + 1
                slug = '_'.join(truncated) if truncated else slug[:MAX_ASCII_NAME_LEN]
            return slug.lower()
    except ImportError:
        pass

    # Try extracting English words from the name
    ascii_parts = re.sub(r'[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]', '', cjk_name)
    ascii_parts = re.sub(r'[^a-zA-Z0-9\s_-]', '', ascii_parts)
    ascii_parts = re.sub(r'[\s_]+', '_', ascii_parts).strip('_')
    if ascii_parts and len(ascii_parts) >= 3:
        return ascii_parts[:MAX_ASCII_NAME_LEN].lower()

    # Last resort: hash-based name
    import hashlib
    h = hashlib.md5(cjk_name.encode('utf-8')).hexdigest()[:8]
    return f"twt_{h}"


def _generate_name(text: str, author: str = "", article_title: str = "") -> str:
    """Generate a short descriptive name from tweet text."""
    if article_title:
        return _sanitize_filename(article_title)

    clean = re.sub(r'https?://\S+', '', text)
    clean = re.sub(r'#\S+', '', clean)
    clean = re.sub(r'@\w+', '', clean)
    clean = ''.join(c for c in clean if not unicodedata.category(c).startswith('So'))
    clean = re.sub(r'\s+', ' ', clean).strip()

    first_phrase = re.split(r'[。，！？\n]', clean)[0].strip()

    if first_phrase:
        name = first_phrase
    elif author:
        name = f"{author}的推文"
    else:
        name = "推文音频"

    return _sanitize_filename(name)


def _generate_ascii_name(display_name: str, text: str = "", article_title: str = "") -> str:
    """Generate ASCII filename for upload compatibility.

    CRITICAL: Some upload APIs reject non-ASCII filenames with 40009.
    The ASCII filename must meaningfully describe the content.
    """
    if article_title and re.match(r'^[a-zA-Z0-9\s\-_.,!?\'"]+$', article_title):
        slug = re.sub(r'[^\w\s-]', '', article_title)
        slug = re.sub(r'[\s]+', '_', slug).strip('_')
        return slug[:MAX_ASCII_NAME_LEN].lower()

    if re.match(r'^[a-zA-Z0-9\s\-_]+$', display_name):
        slug = re.sub(r'[\s]+', '_', display_name).strip('_')
        return slug[:MAX_ASCII_NAME_LEN].lower()

    # CJK name: try to extract meaningful English from the text
    english_words = re.findall(r'[a-zA-Z]{3,}', text)
    if len(english_words) >= 2:
        slug = '_'.join(english_words[:4]).lower()
        return slug[:MAX_ASCII_NAME_LEN]

    return _cjk_to_ascii(display_name)


def _detect_language(text: str) -> str:
    """Detect if text is primarily Chinese or English."""
    cn_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    en_chars = len(re.findall(r'[a-zA-Z]', text))
    return "zh" if cn_chars > en_chars else "en"


def _get_voice(text: str, voice_override: str = None) -> str:
    """Select TTS voice based on text language."""
    if voice_override:
        return voice_override
    lang = _detect_language(text)
    return VOICES.get(lang, VOICES["en"])


def _get_duration(file_path: str) -> int:
    """Get duration of audio file in seconds.

    Uses mutagen if available, falls back to size-based estimation.
    """
    try:
        import mutagen
        audio = mutagen.File(file_path)
        if audio:
            return int(audio.info.length)
    except (ImportError, Exception):
        pass
    # Fallback: estimate from file size (~32kbps = 4KB/sec for edge-tts)
    try:
        file_size = os.path.getsize(file_path)
        return int(file_size / 4000)
    except OSError:
        return 0


def _format_duration(seconds: int) -> str:
    """Format seconds as M分S秒."""
    minutes = seconds // 60
    secs = seconds % 60
    if minutes > 0:
        return f"{minutes}分{secs}秒"
    return f"{secs}秒"


def _now_cst():
    """Get current time in China Standard Time (UTC+8)."""
    from datetime import datetime, timezone, timedelta
    CST = timezone(timedelta(hours=8))
    return datetime.now(CST)


async def _generate_audio(text: str, output_path: str, voice: str, rate: str = DEFAULT_TTS_RATE):
    """Generate audio using edge-tts.

    Args:
        text: Text content to synthesize.
        output_path: Output mp3 file path.
        voice: Edge-TTS voice name (e.g. zh-CN-XiaoxiaoNeural).
        rate: Speech rate string (e.g. '+20%', '+0%').
    """
    communicate = edge_tts.Communicate(text, voice, rate=rate)
    await communicate.save(output_path)


def cmd_add(tweet_input: str, voice: str = None, ascii_name_override: str = None, rate: str = None):
    """Fetch tweet and generate audio.

    Steps:
        1. Extract tweet ID (cheap, do first)
        2. Check for duplicate BEFORE fetching (avoid wasted API call)
        3. Fetch tweet via GraphQL
        4. Generate display name and ASCII filename
        5. Generate mp3 audio via edge-tts
        6. Save to index

    Args:
        tweet_input: Tweet URL or numeric ID.
        voice: TTS voice override (e.g. 'zh-CN-YunxiNeural').
        ascii_name_override: Override ASCII filename for upload compatibility.
        rate: TTS speech rate override (e.g. '+0%', '+50%').
    """
    # 1. Extract tweet ID (cheap, do first)
    tweet_id = extract_tweet_id(tweet_input)

    # 2. Check for duplicate BEFORE fetching (avoid wasted API call)
    index = _load_index()
    for a in index.get("audios", []):
        if a.get("tweet_id") == str(tweet_id):
            print(f"⚠️ 已存在: {a.get('name', a.get('ascii_name', ''))} (#{index['audios'].index(a)+1})")
            output = {
                "success": True,
                "name": a.get("name", a.get("ascii_name", "")),
                "ascii_name": a.get("ascii_name", ""),
                "file": a.get("send_file") or a.get("file", ""),
                "duration": a.get("duration", 0),
                "duration_str": _format_duration(a.get("duration", 0)),
                "tweet_id": str(tweet_id),
                "author": a.get("author", ""),
                "duplicate": True,
            }
            print(f"\n__JSON_OUTPUT__{json.dumps(output, ensure_ascii=False)}")
            return

    # 3. Fetch tweet
    print(f"📡 抓取推文: {tweet_input}")
    try:
        result = read_tweet(tweet_id)
    except Exception as e:
        print(f"❌ 抓取失败: {e}", file=sys.stderr)
        sys.exit(1)

    text = result["text"]
    author = result["author"]
    article_title = result.get("article_title", "")

    if not text:
        print("❌ 推文内容为空", file=sys.stderr)
        sys.exit(1)

    print(f"✅ 抓取成功: {author} ({len(text)}字)")

    # 4. Generate display name and ASCII filename
    display_name = _generate_name(text, author, article_title)

    if ascii_name_override:
        ascii_name = re.sub(r'[^a-zA-Z0-9_-]', '', ascii_name_override)[:MAX_ASCII_NAME_LEN]
    else:
        ascii_name = _generate_ascii_name(display_name, text, article_title)

    # Check for duplicate ascii_name and add suffix
    existing_ascii = [a.get("ascii_name", "") for a in index["audios"]]
    base_ascii = ascii_name
    counter = 2
    while ascii_name in existing_ascii:
        ascii_name = f"{base_ascii}_{counter}"
        counter += 1

    # 5. Generate audio (mp3 only)
    selected_voice = _get_voice(text, voice)
    tts_rate = rate or DEFAULT_TTS_RATE
    mp3_path = AUDIO_DIR / f"{ascii_name}.mp3"
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    print(f"🔊 生成音频: {display_name} → {ascii_name} (voice: {selected_voice}, rate: {tts_rate})")
    asyncio.run(_generate_audio(text, str(mp3_path), selected_voice, rate=tts_rate))

    # 6. Get duration and update index
    duration = _get_duration(str(mp3_path))

    entry = {
        "name": display_name,
        "ascii_name": ascii_name,
        "file": str(mp3_path),
        "send_file": str(mp3_path),
        "tweet_id": tweet_id,
        "author": author,
        "text_length": len(text),
        "duration": duration,
        "voice": selected_voice,
        "rate": tts_rate,
        "created_at": _now_cst().strftime("%Y-%m-%d %H:%M"),
    }
    index["audios"].append(entry)
    _save_index(index)

    print(f"✅ 音频已保存: {display_name} ({_format_duration(duration)})")

    # Output JSON for programmatic use
    output = {
        "success": True,
        "name": display_name,
        "ascii_name": ascii_name,
        "file": str(mp3_path),
        "duration": duration,
        "duration_str": _format_duration(duration),
        "tweet_id": tweet_id,
        "author": author,
    }
    print(f"\n__JSON_OUTPUT__{json.dumps(output, ensure_ascii=False)}")


def cmd_list():
    """List all audios in the library."""
    index = _load_index()
    audios = index.get("audios", [])

    if not audios:
        print("📭 音频库为空")
        return

    print(f"📚 音频库 ({len(audios)}条)\n")
    for i, audio in enumerate(audios, 1):
        dur = _format_duration(audio.get("duration", 0))
        author = audio.get("author", "")
        author_str = f" @{author}" if author else ""
        created = audio.get("created_at", "")
        name = audio.get("name", audio.get("ascii_name", ""))
        print(f"{i}. {name}")
        print(f"   {dur}{author_str} · {created}")

    # JSON output
    output = {
        "count": len(audios),
        "audios": [
            {
                "index": i,
                "name": a.get("name", a.get("ascii_name", "")),
                "ascii_name": a.get("ascii_name", ""),
                "file": a["file"],
                "duration": a.get("duration", 0),
                "duration_str": _format_duration(a.get("duration", 0)),
                "author": a.get("author", ""),
            }
            for i, a in enumerate(audios, 1)
        ],
    }
    print(f"\n__JSON_OUTPUT__{json.dumps(output, ensure_ascii=False)}")


def cmd_send(identifier: str):
    """Get audio file path for sending.

    Args:
        identifier: Audio name or index number (1-based).
    """
    index = _load_index()
    audios = index.get("audios", [])

    if not audios:
        print("❌ 音频库为空", file=sys.stderr)
        sys.exit(1)

    # Try numeric index
    try:
        idx = int(identifier) - 1
        if 0 <= idx < len(audios):
            audio = audios[idx]
            path = audio.get("send_file") or audio["file"]
            if os.path.exists(path):
                name = audio.get("name", audio.get("ascii_name", ""))
                print(f"📤 {name}")
                print(f"📁 {path}")
                output = {"success": True, "name": name, "file": path}
                print(f"\n__JSON_OUTPUT__{json.dumps(output, ensure_ascii=False)}")
                return
            else:
                print(f"❌ 文件不存在: {path}", file=sys.stderr)
                sys.exit(1)
    except ValueError:
        pass

    # Try name match (both display name and ascii name)
    identifier_lower = identifier.lower()
    for i, audio in enumerate(audios, 1):
        names_to_check = [
            audio.get("name", "").lower(),
            audio.get("ascii_name", "").lower(),
        ]
        if any(identifier_lower in n for n in names_to_check):
            path = audio.get("send_file") or audio["file"]
            if os.path.exists(path):
                name = audio.get("name", audio.get("ascii_name", ""))
                print(f"📤 {name}")
                print(f"📁 {path}")
                output = {"success": True, "name": name, "file": path, "index": i}
                print(f"\n__JSON_OUTPUT__{json.dumps(output, ensure_ascii=False)}")
                return

    print(f"❌ 未找到: {identifier}", file=sys.stderr)
    sys.exit(1)


def cmd_delete(identifier: str):
    """Delete an audio from the library.

    Args:
        identifier: Audio name or index number (1-based).
    """
    index = _load_index()
    audios = index.get("audios", [])

    if not audios:
        print("❌ 音频库为空", file=sys.stderr)
        sys.exit(1)

    target_idx = None

    # Try numeric index
    try:
        idx = int(identifier) - 1
        if 0 <= idx < len(audios):
            target_idx = idx
    except ValueError:
        pass

    # Try name match
    if target_idx is None:
        identifier_lower = identifier.lower()
        for i, audio in enumerate(audios):
            names_to_check = [
                audio.get("name", "").lower(),
                audio.get("ascii_name", "").lower(),
            ]
            if any(identifier_lower in n for n in names_to_check):
                target_idx = i
                break

    if target_idx is None:
        print(f"❌ 未找到: {identifier}", file=sys.stderr)
        sys.exit(1)

    audio = audios[target_idx]
    name = audio.get("name", audio.get("ascii_name", ""))

    # Delete files
    for key in ("file", "send_file"):
        fpath = audio.get(key)
        if fpath and os.path.exists(fpath):
            try:
                os.remove(fpath)
            except OSError:
                pass
    # Also clean up legacy ogg files if they exist
    for key in ("ogg_file",):
        fpath = audio.get(key)
        if fpath and os.path.exists(fpath):
            try:
                os.remove(fpath)
            except OSError:
                pass

    # Remove from index
    audios.pop(target_idx)
    _save_index(index)

    print(f"🗑️ 已删除: {name}")


def main():
    parser = argparse.ArgumentParser(
        description="Twitter-to-Audio Pipeline",
        epilog="Config: project_root/config.yaml",
    )
    subparsers = parser.add_subparsers(dest="command", help="Command")

    # add
    add_parser = subparsers.add_parser("add", help="Fetch tweet and generate audio")
    add_parser.add_argument("input", help="Tweet URL or ID")
    add_parser.add_argument("--voice", help="TTS voice override")
    add_parser.add_argument("--ascii-name", help="Override ASCII filename (for upload compatibility)")
    add_parser.add_argument(
        "--rate",
        help=f"TTS speech rate (default: {DEFAULT_TTS_RATE}, e.g. +0%% for normal, +50%% for very fast)",
    )

    # list
    subparsers.add_parser("list", help="List all audios")

    # send
    send_parser = subparsers.add_parser("send", help="Get audio file for sending")
    send_parser.add_argument("identifier", help="Audio name or index number")

    # delete
    delete_parser = subparsers.add_parser("delete", help="Delete an audio")
    delete_parser.add_argument("identifier", help="Audio name or index number")

    args = parser.parse_args()

    if args.command == "add":
        cmd_add(args.input, args.voice, getattr(args, 'ascii_name', None), getattr(args, 'rate', None))
    elif args.command == "list":
        cmd_list()
    elif args.command == "send":
        cmd_send(args.identifier)
    elif args.command == "delete":
        cmd_delete(args.identifier)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
