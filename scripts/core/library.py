"""音频库管理 — 索引文件读写、文件名生成、增删查。

不依赖 config / x_client / tts，只操作 json 和文件系统。"""

import hashlib
import json
import re
import unicodedata
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from .models import CoreError


class AudioLibrary:
    """音频库：索引文件读写 + 名称生成 + CRUD。"""

    def __init__(self, index_path: str | Path, audio_dir: str | Path, max_filename_len: int = 30):
        self._index_path = Path(index_path)
        self._audio_dir = Path(audio_dir)
        self._max_fn_len = max_filename_len

    # ── 索引 I/O ────────────────────────────────────────────────────

    def _load(self) -> dict:
        if not self._index_path.exists():
            return {"audios": []}
        with open(self._index_path, encoding="utf-8") as f:
            return json.load(f)

    def _save(self, data: dict):
        self._audio_dir.mkdir(parents=True, exist_ok=True)
        with open(self._index_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _now_cst(self) -> datetime:
        return datetime.now(timezone(timedelta(hours=8)))

    # ── 文件名生成 ──────────────────────────────────────────────────

    def make_ascii_filename(self, display_name: str, text: str = "",
                            article_title: str = "") -> str:
        """从展示名生成 ASCII slug 文件名。五层 fallback 策略。"""
        # Case 1: article_title 纯英文
        if article_title and re.match(r"^[a-zA-Z0-9\s\-_.,!?'\"]+$", article_title):
            slug = re.sub(r"[^\w\s-]", "", article_title)
            slug = re.sub(r"\s+", "_", slug).strip("_")
            return slug[:self._max_fn_len].lower()

        # Case 2: display_name 纯英文
        if re.match(r"^[a-zA-Z0-9\s\-_]+$", display_name):
            slug = re.sub(r"\s+", "_", display_name).strip("_")
            return slug[:self._max_fn_len].lower()

        # Case 3: 从推文正文抽英文关键词
        eng = re.findall(r"[a-zA-Z]{3,}", text)
        if len(eng) >= 2:
            slug = "_".join(eng[:4]).lower()
            return slug[:self._max_fn_len]

        # Case 4: 拼音
        try:
            from pypinyin import lazy_pinyin, Style
            parts = lazy_pinyin(display_name, style=Style.NORMAL)
            slug = re.sub(r"[^a-zA-Z0-9_]", "", "_".join(parts))
            slug = re.sub(r"_+", "_", slug).strip("_")
            if slug and len(slug) >= 3:
                if len(slug) > self._max_fn_len:
                    words = slug.split("_")
                    out, total = [], 0
                    for w in words:
                        if total + len(w) + 1 > self._max_fn_len:
                            break
                        out.append(w)
                        total += len(w) + 1
                    slug = "_".join(out) if out else slug[:self._max_fn_len]
                return slug.lower()
        except ImportError:
            pass

        # Case 5: hash fallback
        h = hashlib.md5(display_name.encode()).hexdigest()[:8]
        return f"twt_{h}"

    def sanitize_display_name(self, text: str, author: str = "",
                              article_title: str = "") -> str:
        """生成展示名（含 CJK，不截断特殊符号尾部）。"""
        if article_title:
            name = article_title
        else:
            clean = re.sub(r"https?://\S+", "", text)
            clean = re.sub(r"#\S+", "", clean)
            clean = re.sub(r"@\w+", "", clean)
            clean = "".join(c for c in clean if not unicodedata.category(c).startswith("So"))
            clean = re.sub(r"\s+", " ", clean).strip()
            first = re.split(r"[。，！？\n]", clean)[0].strip()
            if first:
                name = first
            elif author:
                name = f"{author}的推文"
            else:
                name = "推文音频"

        # 清理不合规字符
        name = re.sub(r'[<>:"/\\|?*]', "", name)
        name = re.sub(r"\s+", " ", name).strip()

        # CJK 截断后去除尾部符号
        max_w = 20
        width, truncated = 0, ""
        for ch in name:
            w = 2 if "\u4e00" <= ch <= "\u9fff" or "\u3000" <= ch <= "\u303f" else 1
            if width + w > max_w:
                break
            width += w
            truncated += ch
        name = truncated.rstrip().rstrip(".").rstrip()
        return name or "untitled"

    # ── CRUD ────────────────────────────────────────────────────────

    def list_all(self) -> list[dict]:
        """返回带序号和 duration_str 的音频列表。"""
        index = self._load()
        audios = []
        for i, a in enumerate(index.get("audios", []), 1):
            entry = dict(a)
            entry["index"] = i
            d = entry.get("duration", 0)
            entry["duration_str"] = f"{d // 60}分{d % 60}秒" if d >= 60 else f"{d}秒"
            audios.append(entry)
        return audios

    def find(self, identifier: str | int) -> dict:
        """按序号或名称查找。精确匹配优先 → 子串 fallback。"""
        audios = self._load().get("audios", [])
        if not audios:
            raise CoreError("音频库为空")

        # 数字索引
        if isinstance(identifier, int) or (isinstance(identifier, str) and identifier.isdigit()):
            idx = int(identifier) - 1
            if 0 <= idx < len(audios):
                return audios[idx]

        # 字符串匹配：精确优先
        if isinstance(identifier, str):
            id_lower = identifier.lower()
            # 精确匹配
            for a in audios:
                for key in ("name", "ascii_name"):
                    if a.get(key, "").lower() == id_lower:
                        return a
            # 子串模糊
            for a in audios:
                for key in ("name", "ascii_name"):
                    if id_lower in a.get(key, "").lower():
                        return a

        raise CoreError(f"未找到音频: {identifier}")

    def add_entry(self, entry: dict):
        """追加一条索引记录并保存。"""
        index = self._load()
        index["audios"].append(entry)
        self._save(index)

    def remove(self, identifier: str | int) -> dict:
        """删除条目 + 清理物理文件。返回被删除的 dict。"""
        audios = self._load().get("audios", [])

        target_idx = None
        if isinstance(identifier, int) or (isinstance(identifier, str) and identifier.isdigit()):
            idx = int(identifier) - 1
            if 0 <= idx < len(audios):
                target_idx = idx

        if target_idx is None and isinstance(identifier, str):
            id_lower = identifier.lower()
            for i, a in enumerate(audios):
                for key in ("name", "ascii_name"):
                    if id_lower in a.get(key, "").lower():
                        target_idx = i
                        break
                if target_idx is not None:
                    break

        if target_idx is None:
            raise CoreError(f"未找到音频: {identifier}")

        audio = audios.pop(target_idx)

        # 删除物理文件（兼容旧索引多种 key）
        deleted_files = []
        for key in ("file", "send_file", "ogg_file", "audio_path", "file_path"):
            fpath = audio.get(key)
            if fpath:
                p = Path(fpath)
                if p.exists():
                    try:
                        p.unlink()
                        deleted_files.append(str(p))
                    except OSError:
                        pass

        # 保存更新后的索引
        index = self._load()
        index["audios"] = audios
        self._save(index)

        audio["_deleted_files"] = deleted_files
        return audio

    def ascii_name_exists(self, ascii_name: str) -> bool:
        """检查 ASCII 文件名是否已存在（去重用）。"""
        existing = self._load().get("audios", [])
        return any(a.get("ascii_name") == ascii_name for a in existing)

    def tweet_id_exists(self, tweet_id: str) -> Optional[dict]:
        """按 tweet_id 查重。返回已有条目或 None。"""
        existing = self._load().get("audios", [])
        for a in existing:
            if a.get("tweet_id") == str(tweet_id):
                return a
        return None
