#!/usr/bin/env python3
"""twt-audio-mcp CLI — 薄包装层，调用 core，负责用户交互打印。"""

import argparse
import json
import sys
from pathlib import Path

_PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(_PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(_PROJECT_DIR))

from scripts.core import TwtAudioCore, CoreError


def cmd_add(core: TwtAudioCore, tweet_input: str, voice=None, ascii_name=None, rate=None):
    result = core.add_tweet(tweet_input, voice, ascii_name, rate)
    if result.duplicate:
        print(f"⚠️ 已存在: {result.name} ({result.duration_str})")
    elif result.success:
        print(f"✅ 音频已保存: {result.name} ({result.duration_str})")
    else:
        print(f"❌ {result.error}", file=sys.stderr)
        sys.exit(1)


def cmd_list(core: TwtAudioCore):
    audios = core.list_audios()
    if not audios:
        print("📭 音频库为空")
        return
    print(f"📚 音频库 ({len(audios)}条)\n")
    for a in audios:
        author = f" @{a['author']}" if a.get("author") else ""
        created = a.get("created_at", "")
        name = a.get("name", a.get("ascii_name", ""))
        print(f"{a['index']}. {name}")
        print(f"   {a['duration_str']}{author} · {created}")


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


def cmd_delete(core: TwtAudioCore, identifier: str):
    try:
        audio = core.delete_audio(identifier)
    except CoreError as e:
        print(f"❌ {e}", file=sys.stderr)
        sys.exit(1)
    name = audio.get("name", audio.get("ascii_name", ""))
    del_files = audio.get("_deleted_files", [])
    print(f"🗑️ 已删除: {name}")
    if del_files:
        for f in del_files:
            print(f"   📄 已清理: {f}")


def cmd_check(core: TwtAudioCore):
    status = core.check_config()
    if status["ok"]:
        print("✅ 配置完整")
    for name, check in status["checks"].items():
        icon = "✅" if check.get("ok") else "❌"
        if "count" in check:
            print(f"  {icon} {name}: {check['count']}条音频")
        elif "msg" in check:
            print(f"  {icon} {name}: {check['msg']}")
        else:
            print(f"  {icon} {name}")


def main():
    parser = argparse.ArgumentParser(
        description="Twitter-to-Audio Pipeline",
        epilog="Config: project_root/config.yaml",
    )
    subparsers = parser.add_subparsers(dest="command")

    add_p = subparsers.add_parser("add", help="Fetch tweet and generate audio")
    add_p.add_argument("input", help="Tweet URL or ID")
    add_p.add_argument("--voice", help="TTS voice override")
    add_p.add_argument("--ascii-name", help="Override ASCII filename")
    add_p.add_argument("--rate", help="TTS speech rate (e.g. +0%, +50%)")

    subparsers.add_parser("list", help="List all audios")
    send_p = subparsers.add_parser("send", help="Get audio file path")
    send_p.add_argument("identifier", help="Audio name or index")
    del_p = subparsers.add_parser("delete", help="Delete an audio")
    del_p.add_argument("identifier", help="Audio name or index")
    subparsers.add_parser("check", help="Check configuration")

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
