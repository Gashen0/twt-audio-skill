#!/usr/bin/env python3
"""twt-audio-mcp CLI — 薄包装层，调用 core，负责用户交互打印。"""

import argparse
import json
import sys
from pathlib import Path

_PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(_PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(_PROJECT_DIR))

from scripts.twt_core import TwtAudioCore, CoreError


def _format_duration(seconds: int) -> str:
    m, s = divmod(seconds, 60)
    return f"{m}分{s}秒" if m else f"{s}秒"


def cmd_add(core: TwtAudioCore, tweet_input: str, voice=None, ascii_name=None, rate=None):
    result = core.add_tweet(tweet_input, voice, ascii_name, rate)
    if result.duplicate:
        print(f"⚠️ 已存在: {result.name} (#{result.duration_str})")
    elif result.success:
        print(f"✅ 音频已保存: {result.name} ({_format_duration(result.duration)})")
    else:
        print(f"❌ {result.error}", file=sys.stderr)
        sys.exit(1)
    print(f"\n__JSON_OUTPUT__{json.dumps(result.to_dict(), ensure_ascii=False)}")


def cmd_list(core: TwtAudioCore):
    audios = core.list_audios()
    if not audios:
        print("📭 音频库为空")
        print(f"\n__JSON_OUTPUT__{json.dumps({'count': 0, 'audios': []})}")
        return
    print(f"📚 音频库 ({len(audios)}条)\n")
    for a in audios:
        author_str = f" @{a['author']}" if a.get("author") else ""
        created = a.get("created_at", "")
        print(f"{a['index']}. {a.get('name', a.get('ascii_name', ''))}")
        print(f"   {a['duration_str']}{author_str} · {created}")
    output = {
        "count": len(audios),
        "audios": [
            {"index": a["index"], "name": a.get("name", a.get("ascii_name", "")),
             "ascii_name": a.get("ascii_name", ""), "file": a["file"],
             "duration": a["duration"], "duration_str": a["duration_str"],
             "author": a.get("author", "")}
            for a in audios
        ],
    }
    print(f"\n__JSON_OUTPUT__{json.dumps(output, ensure_ascii=False)}")


def cmd_send(core: TwtAudioCore, identifier: str):
    try:
        audio = core.get_audio(identifier)
    except CoreError as e:
        print(f"❌ {e}", file=sys.stderr)
        sys.exit(1)
    path = audio.get("send_file") or audio["file"]
    if not Path(path).exists():
        print(f"❌ 文件不存在: {path}", file=sys.stderr)
        sys.exit(1)
    name = audio.get("name", audio.get("ascii_name", ""))
    print(f"📤 {name}")
    print(f"📁 {path}")
    output = {"success": True, "name": name, "file": path}
    print(f"\n__JSON_OUTPUT__{json.dumps(output, ensure_ascii=False)}")


def cmd_delete(core: TwtAudioCore, identifier: str):
    try:
        audio = core.delete_audio(identifier)
    except CoreError as e:
        print(f"❌ {e}", file=sys.stderr)
        sys.exit(1)
    name = audio.get("name", audio.get("ascii_name", ""))
    print(f"🗑️ 已删除: {name}")


def cmd_check(core: TwtAudioCore):
    status = core.check_config()
    if status["ok"]:
        print("✅ 配置完整")
    else:
        for name, check in status["checks"].items():
            if check.get("ok"):
                if "count" in check:
                    print(f"  ✅ {name}: {check['count']}条音频")
                else:
                    print(f"  ✅ {name}")
            else:
                print(f"  ❌ {name}: {check['msg']}")


def main():
    parser = argparse.ArgumentParser(
        description="Twitter-to-Audio Pipeline",
        epilog="Config: project_root/config.yaml",
    )
    subparsers = parser.add_subparsers(dest="command", help="Command")

    # add
    add_p = subparsers.add_parser("add", help="Fetch tweet and generate audio")
    add_p.add_argument("input", help="Tweet URL or ID")
    add_p.add_argument("--voice", help="TTS voice override (e.g. zh-CN-YunxiNeural)")
    add_p.add_argument("--ascii-name", help="Override ASCII filename")
    add_p.add_argument("--rate", help=f"TTS speech rate (default from config, e.g. +0%, +50%)")

    # list
    subparsers.add_parser("list", help="List all audios")

    # send
    send_p = subparsers.add_parser("send", help="Get audio file for sending")
    send_p.add_argument("identifier", help="Audio name or index number")

    # delete
    del_p = subparsers.add_parser("delete", help="Delete an audio")
    del_p.add_argument("identifier", help="Audio name or index number")

    # check
    subparsers.add_parser("check", help="Check configuration status")

    args = parser.parse_args()
    core = TwtAudioCore(_PROJECT_DIR)

    if args.command == "add":
        cmd_add(core, args.input, args.voice, getattr(args, "ascii_name", None), args.rate)
    elif args.command == "list":
        cmd_list(core)
    elif args.command == "send":
        cmd_send(core, args.identifier)
    elif args.command == "delete":
        cmd_delete(core, args.identifier)
    elif args.command == "check":
        cmd_check(core)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
