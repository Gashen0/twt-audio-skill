#!/usr/bin/env python3
"""twt-audio-mcp Core Library — 纯函数，无副作用，可测试。

分层：TwtAudioCore 封装所有逻辑，不 print，不 sys.exit，不 redirect_stdout。
MCP Server 和 CLI 都是这个类的薄包装。
"""

import hashlib
import json
import re
import sys
import time
import unicodedata
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import requests
import yaml

# ========================================================================
# 数据模型
# ========================================================================


class TweetResult:
    """推文抓取结果"""

    def __init__(self, text: str, author: str, tweet_id: str, is_article: bool = False, article_title: str = ""):
        self.text = text
        self.author = author
        self.tweet_id = tweet_id
        self.is_article = is_article
        self.article_title = article_title

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "author": self.author,
            "tweet_id": self.tweet_id,
            "is_article": self.is_article,
            "article_title": self.article_title,
        }


class AddResult:
    """添加音频的结果"""

    def __init__(
        self,
        success: bool,
        name: str = "",
        ascii_name: str = "",
        file: str = "",
        duration: int = 0,
        tweet_id: str = "",
        author: str = "",
        duplicate: bool = False,
        error: str = "",
    ):
        self.success = success
        self.name = name
        self.ascii_name = ascii_name
        self.file = file
        self.duration = duration
        self.tweet_id = tweet_id
        self.author = author
        self.duplicate = duplicate
        self.error = error

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "name": self.name,
            "ascii_name": self.ascii_name,
            "file": self.file,
            "duration": self.duration,
            "duration_str": self._format_duration(self.duration),
            "tweet_id": self.tweet_id,
            "author": self.author,
            "duplicate": self.duplicate,
            "error": self.error,
        }

    @property
    def duration_str(self) -> str:
        return self._format_duration(self.duration)

    @staticmethod
    def _format_duration(seconds: int) -> str:
        minutes = seconds // 60
        secs = seconds % 60
        if minutes > 0:
            return f"{minutes}分{secs}秒"
        return f"{secs}秒"


class AudioEntry:
    """音频库条目"""

    def __init__(self, name: str, ascii_name: str, file: str, tweet_id: str, author: str,
                 text_length: int, duration: int, voice: str, rate: str, created_at: str):
        self.name = name
        self.ascii_name = ascii_name
        self.file = file
        self.tweet_id = tweet_id
        self.author = author
        self.text_length = text_length
        self.duration = duration
        self.voice = voice
        self.rate = rate
        self.created_at = created_at

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "ascii_name": self.ascii_name,
            "file": self.file,
            "tweet_id": self.tweet_id,
            "author": self.author,
            "text_length": self.text_length,
            "duration": self.duration,
            "voice": self.voice,
            "rate": self.rate,
            "created_at": self.created_at,
        }


class CoreError(Exception):
    """Core 层错误"""
    pass


# ========================================================================
# TwtAudioCore — 主核心类
# ========================================================================


class TwtAudioCore:
    """纯函数核心：获取推文 → TTS → 管理音频库。不 print，不 sys.exit。"""

    def __init__(self, project_dir: str | Path):
        self._project_dir = Path(project_dir)
        self._config = self._load_config()
        self._data_dir = self._project_dir / "data"

        # 从配置拉取值
        _tw_cfg = self._config.get("twitter", {})
        _tts_cfg = self._config.get("tts", {})
        _path_cfg = self._config.get("paths", {})

        # API 配置
        self.bearer = _tw_cfg.get(
            "bearer",
            "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA",
        )
        self.tweet_detail_query_id = _tw_cfg.get("tweet_detail_query_id", "_i0BBmP_dK_ZLFa2Y-ei9Q")
        self.tweet_result_query_id = _tw_cfg.get("tweet_result_by_rest_id_query_id", "uEyKTt72BfzaY84WLGC5Dw")
        self.min_interval = _tw_cfg.get("rate_limit_seconds", 5)
        self.rate_limit_margin = _tw_cfg.get("rate_limit_margin", 0.1)

        # TTS 配置
        self.voices = _tts_cfg.get("voices", {"zh": "zh-CN-XiaoxiaoNeural", "en": "en-US-JennyNeural"})
        self.default_rate = _tts_cfg.get("default_rate", "+20%")
        self.max_filename_len = _tts_cfg.get("max_filename_len", 30)

        # 路径
        self.audio_dir = self._data_dir / _path_cfg.get("audio_dir", "twts")
        self.index_path = self._data_dir / _path_cfg.get("index_file", "twts/index.json")
        self.cookie_path = self._data_dir / _path_cfg.get("cookie_file", "secrets/x_cookies.json")

        # 内部状态
        self._last_request_time = 0

    def _load_config(self) -> dict:
        config_path = self._project_dir / "config.yaml"
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except (FileNotFoundError, yaml.YAMLError):
            return {}

    # ------------------------------------------------------------------
    # 配置检查
    # ------------------------------------------------------------------

    def check_config(self) -> dict:
        """检查配置完整性，返回诊断结果。"""
        status = {"ok": True, "checks": {}}

        # Cookie
        try:
            cookies = self._load_cookies()
            missing = [k for k in ("auth_token", "ct0", "twid") if not cookies.get(k)]
            if missing:
                status["checks"]["cookie"] = {"ok": False, "msg": f"缺少: {', '.join(missing)}"}
                status["ok"] = False
            else:
                status["checks"]["cookie"] = {"ok": True}
        except FileNotFoundError:
            status["checks"]["cookie"] = {"ok": False, "msg": f"Cookie 文件未找到: {self.cookie_path}"}
            status["ok"] = False
        except json.JSONDecodeError:
            status["checks"]["cookie"] = {"ok": False, "msg": "Cookie 文件格式错误"}
            status["ok"] = False

        # TTS 依赖
        try:
            import edge_tts  # noqa: F401
            status["checks"]["edge_tts"] = {"ok": True}
        except ImportError:
            status["checks"]["edge_tts"] = {"ok": False, "msg": "edge-tts 未安装"}
            status["ok"] = False

        # 音频库
        audio_count = len(self._load_index().get("audios", []))
        status["checks"]["audio_library"] = {"ok": True, "count": audio_count}

        return status

    # ------------------------------------------------------------------
    # Cookie / 会话
    # ------------------------------------------------------------------

    def _load_cookies(self) -> dict:
        if not self.cookie_path.exists():
            raise FileNotFoundError(f"Cookie 文件未找到: {self.cookie_path}")
        with open(self.cookie_path, "r") as f:
            return json.load(f)

    def _make_session(self) -> requests.Session:
        cookies = self._load_cookies()
        session = requests.Session()
        session.cookies.set("auth_token", cookies["auth_token"], domain=".x.com")
        session.cookies.set("ct0", cookies["ct0"], domain=".x.com")
        session.cookies.set("twid", cookies["twid"], domain=".x.com")
        session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/136.0.0.0 Safari/537.36"
            ),
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Authorization": f"Bearer {self.bearer}",
            "X-Csrf-Token": cookies["ct0"],
        })
        return session

    def _rate_limit(self):
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self.min_interval:
            wait = self.min_interval - elapsed + self.rate_limit_margin
            time.sleep(wait)
        self._last_request_time = time.time()

    # ------------------------------------------------------------------
    # 推文抓取
    # ------------------------------------------------------------------

    FEATURES = {
        "rweb_tipjar_consumption_enabled": True,
        "responsive_web_graphql_exclude_directive_enabled": True,
        "verified_phone_label_enabled": False,
        "creator_subscriptions_tweet_preview_api_enabled": True,
        "responsive_web_graphql_timeline_navigation_enabled": True,
        "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
        "communities_web_enable_tweet_community_results_fetch": True,
        "c9s_tweet_anatomy_moderator_badge_enabled": True,
        "articles_preview_enabled": True,
        "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
        "view_counts_everywhere_api_enabled": True,
        "longform_notetweets_consumption_enabled": True,
        "responsive_web_twitter_article_tweet_consumption_enabled": True,
        "longform_notetweets_rich_text_read_enabled": True,
        "longform_notetweets_inline_media_enabled": True,
    }

    def extract_tweet_id(self, input_str: str) -> str:
        input_str = input_str.strip()
        if re.match(r"^\d+$", input_str):
            return input_str
        m = re.search(r"/status/(\d+)", input_str)
        if m:
            return m.group(1)
        raise CoreError(f"无法从输入中提取推文 ID: {input_str}")

    def _find_tweet_results(self, data) -> list:
        results = []

        def _walk(obj):
            if isinstance(obj, dict):
                if "result" in obj and isinstance(obj["result"], dict):
                    result = obj["result"]
                    typename = result.get("__typename")
                    if typename == "Tweet":
                        results.append(result)
                    elif typename == "TweetWithVisibilityResults":
                        tweet = result.get("tweet", {})
                        if tweet.get("__typename") == "Tweet":
                            results.append(tweet)
                    elif "tweet" in result:
                        tweet = result.get("tweet", {})
                        if tweet.get("__typename") == "Tweet":
                            results.append(tweet)
                for v in obj.values():
                    _walk(v)
            elif isinstance(obj, list):
                for item in obj:
                    _walk(item)

        _walk(data)
        return results

    def _extract_text_from_tweet(self, tweet_result: dict) -> str:
        text_parts = []
        legacy = tweet_result.get("legacy", {})
        full_text = legacy.get("full_text", "")
        if full_text:
            text_parts.append(full_text)
        note_tweet = tweet_result.get("note_tweet", {})
        if note_tweet:
            note_result = note_tweet.get("note_tweet_results", {}).get("result", {})
            note_text = note_result.get("text", "")
            if note_text:
                text_parts = [note_text]
        return text_parts[0] if text_parts else ""

    def _extract_article_blocks(self, data) -> list:
        blocks = []

        def _walk(obj, depth=0):
            if depth > 20:
                return
            if isinstance(obj, dict):
                if "blocks" in obj and isinstance(obj["blocks"], list):
                    if len(obj["blocks"]) > 5:
                        blocks.extend(obj["blocks"])
                for v in obj.values():
                    _walk(v, depth + 1)
            elif isinstance(obj, list):
                for item in obj:
                    _walk(item, depth + 1)

        _walk(data)
        return blocks

    def _blocks_to_text(self, blocks: list) -> str:
        texts = []
        for block in blocks:
            text = block.get("text", "")
            btype = block.get("type", "")
            if btype == "header-two":
                texts.append(f"\n{text}\n")
            elif btype == "unordered-list-item":
                texts.append(f"· {text}")
            elif btype == "ordered-list-item":
                texts.append(f"- {text}")
            elif btype == "blockquote":
                texts.append(f"> {text}")
            else:
                texts.append(text)
        return "\n".join(texts)

    def _fetch_article_content(self, session: requests.Session, tweet_id: str) -> Optional[str]:
        variables = {
            "tweetId": str(tweet_id),
            "includePromotedContent": False,
            "withCommunity": False,
            "withVoice": False,
        }
        field_toggles = {
            "withArticleRichContentState": True,
            "withArticlePlainText": True,
            "withArticleSummaryText": True,
            "withArticleVoiceOver": False,
            "withGrokAnalyze": False,
            "withDisallowedReplyControls": False,
        }
        params = {
            "variables": json.dumps(variables),
            "features": json.dumps(self.FEATURES),
            "fieldToggles": json.dumps(field_toggles),
        }
        url = f"https://x.com/i/api/graphql/{self.tweet_result_query_id}/TweetResultByRestId"
        self._rate_limit()
        resp = session.get(url, params=params, timeout=30)
        if resp.status_code != 200:
            return None
        data = resp.json()
        article_blocks = self._extract_article_blocks(data)
        if article_blocks:
            return self._blocks_to_text(article_blocks)
        return None

    def fetch_tweet(self, tweet_id: str) -> TweetResult:
        """抓取一条推文，返回结构化结果。"""
        session = self._make_session()

        # Step 1: TweetDetail
        variables = {
            "focalTweetId": str(tweet_id),
            "includePromotedContent": True,
            "withCommunity": False,
            "withQuickPromoteEligibilityTweetFields": True,
            "withBirdwatchNotes": False,
            "withVoice": False,
            "withV2TimelineNotifications": False,
            "withRuxedTransitions": False,
            "withDownvotePerspective": False,
            "withReactions": False,
            "withReactionsMigration": False,
            "withReplies": True,
            "rankingMode": "Relevance",
        }
        field_toggles = {
            "withArticleRichContentState": True,
            "withArticlePlainText": True,
            "withArticleSummaryText": True,
            "withArticleVoiceOver": False,
            "withGrokAnalyze": False,
            "withDisallowedReplyControls": False,
        }
        params = {
            "variables": json.dumps(variables),
            "features": json.dumps(self.FEATURES),
            "fieldToggles": json.dumps(field_toggles),
        }
        url = f"https://x.com/i/api/graphql/{self.tweet_detail_query_id}/TweetDetail"

        self._rate_limit()
        resp = session.get(url, params=params, timeout=30)
        if resp.status_code != 200:
            raise CoreError(f"HTTP {resp.status_code}: {resp.text[:200]}")

        data = resp.json()
        all_tweets = self._find_tweet_results(data)
        if not all_tweets:
            raise CoreError("响应中未找到推文")

        focal_text = ""
        author_name = ""
        author_id = None
        is_article = False
        article_title = ""

        for tweet in all_tweets:
            text = self._extract_text_from_tweet(tweet)
            legacy = tweet.get("legacy", {})
            tweet_id_str = str(legacy.get("id_str", ""))
            uid = str(legacy.get("user_id_str", ""))

            if tweet_id_str == str(tweet_id):
                author_id = uid
                article = tweet.get("article", {})
                if article:
                    is_article = True
                    article_result = article.get("article_results", {}).get("result", {})
                    article_title = article_result.get("title", "")

                note_tweet = tweet.get("note_tweet", {})
                if note_tweet:
                    note_result = note_tweet.get("note_tweet_results", {}).get("result", {})
                    note_text = note_result.get("text", "")
                    if note_text:
                        focal_text = note_text
                if not focal_text:
                    focal_text = text

            core = tweet.get("core", {})
            user_results = core.get("user_results", {}).get("result", {})
            legacy_user = user_results.get("legacy", {})
            if legacy_user.get("name"):
                author_name = legacy_user["name"]
            elif uid and uid == author_id:
                thread_text = self._extract_text_from_tweet(tweet)
                if thread_text:
                    focal_text += "\n\n" + thread_text

        # Step 2: Article 全文
        if is_article:
            article_content = self._fetch_article_content(session, tweet_id)
            if article_content:
                if article_title:
                    focal_text = f"{article_title}\n\n{article_content}"
                else:
                    focal_text = article_content

        return TweetResult(
            text=focal_text.strip(),
            author=author_name,
            tweet_id=str(tweet_id),
            is_article=is_article,
            article_title=article_title if is_article else "",
        )

    # ------------------------------------------------------------------
    # 文件名生成（合并三个函数为一个）
    # ------------------------------------------------------------------

    def _make_ascii_filename(self, display_name: str, text: str = "", article_title: str = "") -> str:
        """从展示名生成 ASCII 文件名，用于跨平台兼容。

        策略：article_title 纯英文→直接 slug；display_name 英文→直接 slug；
              否则从推文正文抽英文关键词；最后拼音或 hash fallback。
        """
        # Case 1: article_title 本身就是英文
        if article_title and re.match(r"^[a-zA-Z0-9\s\-_.,!?'\"]+$", article_title):
            slug = re.sub(r"[^\w\s-]", "", article_title)
            slug = re.sub(r"[\s]+", "_", slug).strip("_")
            return slug[:self.max_filename_len].lower()

        # Case 2: display_name 是英文
        if re.match(r"^[a-zA-Z0-9\s\-_]+$", display_name):
            slug = re.sub(r"[\s]+", "_", display_name).strip("_")
            return slug[:self.max_filename_len].lower()

        # Case 3: 从推文原文抽英文关键词
        english_words = re.findall(r"[a-zA-Z]{3,}", text)
        if len(english_words) >= 2:
            slug = "_".join(english_words[:4]).lower()
            return slug[:self.max_filename_len]

        # Case 4: 拼音
        try:
            from pypinyin import lazy_pinyin, Style
            parts = lazy_pinyin(display_name, style=Style.NORMAL)
            slug = "_".join(parts)
            slug = re.sub(r"[^a-zA-Z0-9_]", "", slug)
            slug = re.sub(r"_+", "_", slug).strip("_")
            if slug and len(slug) >= 3:
                if len(slug) > self.max_filename_len:
                    words = slug.split("_")
                    truncated = []
                    total = 0
                    for w in words:
                        if total + len(w) + 1 > self.max_filename_len:
                            break
                        truncated.append(w)
                        total += len(w) + 1
                    slug = "_".join(truncated) if truncated else slug[:self.max_filename_len]
                return slug.lower()
        except ImportError:
            pass

        # Case 5: hash fallback
        h = hashlib.md5(display_name.encode("utf-8")).hexdigest()[:8]
        return f"twt_{h}"

    def _sanitize_display_name(self, text: str, author: str = "", article_title: str = "") -> str:
        """从推文生成展示用的短名称（允许 CJK）。"""
        if article_title:
            name = article_title
        else:
            clean = re.sub(r"https?://\S+", "", text)
            clean = re.sub(r"#\S+", "", clean)
            clean = re.sub(r"@\w+", "", clean)
            clean = "".join(c for c in clean if not unicodedata.category(c).startswith("So"))
            clean = re.sub(r"\s+", " ", clean).strip()
            first_phrase = re.split(r"[。，！？\n]", clean)[0].strip()
            if first_phrase:
                name = first_phrase
            elif author:
                name = f"{author}的推文"
            else:
                name = "推文音频"

        # 清理不合规字符
        name = re.sub(r'[<>:"/\\|?*]', "", name)
        name = re.sub(r"[\s\n]+", " ", name).strip()
        # CJK 截断（2字符宽度）
        max_cjk_width = 20
        width = 0
        truncated = ""
        for ch in name:
            w = 2 if "\u4e00" <= ch <= "\u9fff" or "\u3000" <= ch <= "\u303f" else 1
            if width + w > max_cjk_width:
                break
            width += w
            truncated += ch
        name = truncated.rstrip().rstrip(".")
        return name or "untitled"

    # ------------------------------------------------------------------
    # 语言检测
    # ------------------------------------------------------------------

    def _detect_language(self, text: str) -> str:
        cn_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
        en_chars = len(re.findall(r"[a-zA-Z]", text))
        return "zh" if cn_chars > en_chars else "en"

    # ------------------------------------------------------------------
    # 音频库管理
    # ------------------------------------------------------------------

    def _load_index(self) -> dict:
        if not self.index_path.exists():
            return {"audios": []}
        with open(self.index_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_index(self, data: dict):
        self.audio_dir.mkdir(parents=True, exist_ok=True)
        with open(self.index_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _now_cst(self) -> datetime:
        CST = timezone(timedelta(hours=8))
        return datetime.now(CST)

    def list_audios(self) -> list[dict]:
        index = self._load_index()
        audios = []
        for i, a in enumerate(index.get("audios", []), 1):
            entry = dict(a)
            entry["index"] = i
            entry["duration_str"] = f"{entry['duration']//60}分{entry['duration']%60}秒" if entry.get("duration", 0) >= 60 else f"{entry.get('duration', 0)}秒"
            audios.append(entry)
        return audios

    def get_audio(self, identifier: str | int) -> dict:
        """按序号或名称查找。返回条目 dict，找不到 raise CoreError。"""
        audios = self._load_index().get("audios", [])
        if not audios:
            raise CoreError("音频库为空")

        # 数字索引
        if isinstance(identifier, int) or (isinstance(identifier, str) and identifier.isdigit()):
            idx = int(identifier) - 1
            if 0 <= idx < len(audios):
                return audios[idx]

        # 字符串匹配
        if isinstance(identifier, str):
            id_lower = identifier.lower()
            for a in audios:
                names_to_check = [
                    a.get("name", "").lower(),
                    a.get("ascii_name", "").lower(),
                ]
                if any(id_lower in n for n in names_to_check):
                    return a

        raise CoreError(f"未找到音频: {identifier}")

    def delete_audio(self, identifier: str | int) -> dict:
        """删除音频条目。返回被删除条目的 dict。"""
        audios = self._load_index().get("audios", [])

        target_idx = None
        # 数字索引
        if isinstance(identifier, int) or (isinstance(identifier, str) and identifier.isdigit()):
            idx = int(identifier) - 1
            if 0 <= idx < len(audios):
                target_idx = idx

        # 字符串匹配
        if target_idx is None and isinstance(identifier, str):
            id_lower = identifier.lower()
            for i, a in enumerate(audios):
                names_to_check = [a.get("name", "").lower(), a.get("ascii_name", "").lower()]
                if any(id_lower in n for n in names_to_check):
                    target_idx = i
                    break

        if target_idx is None:
            raise CoreError(f"未找到音频: {identifier}")

        audio = audios[target_idx]

        # 删除文件
        file_keys = ["file", "send_file", "ogg_file", "audio_path", "file_path"]
        for key in file_keys:
            fpath = audio.get(key)
            if fpath and Path(fpath).exists():
                try:
                    Path(fpath).unlink()
                except OSError:
                    pass

        # 删除索引
        audios.pop(target_idx)
        index = self._load_index()
        index["audios"] = audios
        self._save_index(index)

        return audio

    # ------------------------------------------------------------------
    # TTS
    # ------------------------------------------------------------------

    async def _generate_audio_async(self, text: str, output_path: str, voice: str, rate: str):
        import edge_tts
        communicate = edge_tts.Communicate(text, voice, rate=rate)
        await communicate.save(output_path)

    def generate_tts(self, text: str, output_path: str, voice: Optional[str] = None, rate: Optional[str] = None):
        """同步包装：生成 TTS 音频。"""
        import asyncio

        if voice is None:
            lang = self._detect_language(text)
            voice = self.voices.get(lang, self.voices["en"])
        if rate is None:
            rate = self.default_rate

        asyncio.run(self._generate_audio_async(text, output_path, voice, rate))

    def _get_duration(self, file_path: str) -> int:
        try:
            import mutagen
            audio = mutagen.File(file_path)
            if audio:
                return int(audio.info.length)
        except (ImportError, Exception):
            pass
        try:
            file_size = Path(file_path).stat().st_size
            return int(file_size / 4000)
        except OSError:
            return 0

    # ------------------------------------------------------------------
    # 主流程：add_tweet
    # ------------------------------------------------------------------

    def add_tweet(self, tweet_input: str, voice: Optional[str] = None,
                  ascii_name_override: Optional[str] = None, rate: Optional[str] = None) -> AddResult:
        """完整流程：提取ID → 去重检查 → 抓取推文 → TTS → 入库。"""
        try:
            tweet_id = self.extract_tweet_id(tweet_input)
        except CoreError as e:
            return AddResult(success=False, error=str(e))

        # 去重检查
        index = self._load_index()
        for a in index.get("audios", []):
            if a.get("tweet_id") == str(tweet_id):
                return AddResult(
                    success=True,
                    name=a.get("name", a.get("ascii_name", "")),
                    ascii_name=a.get("ascii_name", ""),
                    file=a.get("send_file") or a.get("file", ""),
                    duration=a.get("duration", 0),
                    tweet_id=str(tweet_id),
                    author=a.get("author", ""),
                    duplicate=True,
                )

        # 抓取推文
        try:
            result = self.fetch_tweet(tweet_id)
        except CoreError as e:
            return AddResult(success=False, error=f"抓取失败: {e}")
        except Exception as e:
            return AddResult(success=False, error=f"抓取异常: {e}")

        text = result.text
        author = result.author
        article_title = result.article_title

        if not text:
            return AddResult(success=False, error="推文内容为空")

        # 命名
        display_name = self._sanitize_display_name(text, author, article_title)
        if ascii_name_override:
            ascii_name = re.sub(r"[^a-zA-Z0-9_-]", "", ascii_name_override)[:self.max_filename_len]
        else:
            ascii_name = self._make_ascii_filename(display_name, text, article_title)

        # 去重 ascii_name
        existing_ascii = [a.get("ascii_name", "") for a in index["audios"]]
        base_ascii = ascii_name
        counter = 2
        while ascii_name in existing_ascii:
            ascii_name = f"{base_ascii}_{counter}"
            counter += 1

        # TTS
        selected_voice = voice or self.voices.get(self._detect_language(text), self.voices["en"])
        tts_rate = rate or self.default_rate
        mp3_path = self.audio_dir / f"{ascii_name}.mp3"
        self.audio_dir.mkdir(parents=True, exist_ok=True)

        try:
            self.generate_tts(text, str(mp3_path), selected_voice, tts_rate)
        except Exception as e:
            return AddResult(success=False, error=f"TTS 生成失败: {e}")

        # 入库
        duration = self._get_duration(str(mp3_path))
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
            "created_at": self._now_cst().strftime("%Y-%m-%d %H:%M"),
        }
        index["audios"].append(entry)
        self._save_index(index)

        return AddResult(
            success=True,
            name=display_name,
            ascii_name=ascii_name,
            file=str(mp3_path),
            duration=duration,
            tweet_id=tweet_id,
            author=author,
        )
