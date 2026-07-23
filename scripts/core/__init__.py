"""core — twt-audio-mcp 核心库。

组合模式：ConfigLoader + XClient + TTSEngine + AudioLibrary → TwtAudioCore。
外部只需要 `from scripts.core import TwtAudioCore`。
"""

from pathlib import Path
from typing import Optional

from .models import AddResult, CoreError
from .config import ConfigLoader
from .x_client import XClient
from .tts import TTSEngine
from .library import AudioLibrary


class TwtAudioCore:
    """核心组合器。接收 project_dir，内部实例化四个模块。"""

    def __init__(self, project_dir: str | Path):
        self._project_dir = Path(project_dir)

        # 配置
        self._cfg = ConfigLoader(project_dir)

        # X API 客户端
        self._x = XClient(
            bearer=self._cfg.bearer,
            tweet_detail_qid=self._cfg.tweet_detail_query_id,
            tweet_result_qid=self._cfg.tweet_result_query_id,
            rate_limit_seconds=self._cfg.rate_limit_seconds,
            rate_limit_margin=self._cfg.rate_limit_margin,
        )

        # TTS 引擎
        self._tts = TTSEngine(
            voices=self._cfg.voices,
            default_rate=self._cfg.default_rate,
        )

        # 音频库
        self._lib = AudioLibrary(
            index_path=self._cfg.index_path,
            audio_dir=self._cfg.audio_dir,
            max_filename_len=self._cfg.max_filename_len,
        )

    # ── 配置检查 ────────────────────────────────────────────────────

    def check_config(self) -> dict:
        """诊断配置完整性。返回 {ok, checks}。"""
        status = self._cfg.diagnose()
        audio_count = len(self._lib.list_all())
        status["checks"]["audio_library"] = {"ok": True, "count": audio_count}
        return status

    # ── 提取推文 ID ─────────────────────────────────────────────────

    def extract_tweet_id(self, input_str: str) -> str:
        return XClient.extract_tweet_id(input_str)

    # ── 抓取 ────────────────────────────────────────────────────────

    def fetch_tweet(self, tweet_id: str):
        """抓取推文（需要 cookie 就绪）。"""
        cookies = self._cfg.load_cookies()
        return self._x.fetch_tweet(tweet_id, cookies)

    # ── 主流程 ──────────────────────────────────────────────────────

    def add_tweet(self, tweet_input: str, voice: Optional[str] = None,
                  ascii_name_override: Optional[str] = None,
                  rate: Optional[str] = None) -> AddResult:
        """完整流程：提取ID → 去重检查 → 抓取推文 → TTS → 入库。"""
        try:
            tweet_id = self.extract_tweet_id(tweet_input)
        except CoreError as e:
            return AddResult(success=False, error=str(e))

        # 去重检查（只用一次索引加载）
        dup = self._lib.tweet_id_exists(tweet_id)
        if dup:
            return AddResult(
                success=True,
                name=dup.get("name", dup.get("ascii_name", "")),
                ascii_name=dup.get("ascii_name", ""),
                file=dup.get("send_file") or dup.get("file", ""),
                duration=dup.get("duration", 0),
                tweet_id=str(tweet_id),
                author=dup.get("author", ""),
                duplicate=True,
            )

        # 抓取
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
        display_name = self._lib.sanitize_display_name(text, author, article_title)
        if ascii_name_override:
            ascii_name = re.sub(r"[^a-zA-Z0-9_-]", "", ascii_name_override)[:self._cfg.max_filename_len]
        else:
            ascii_name = self._lib.make_ascii_filename(display_name, text, article_title)

        # ASCII 文件名去重
        import re
        base = ascii_name
        counter = 2
        while self._lib.ascii_name_exists(ascii_name):
            ascii_name = f"{base}_{counter}"
            counter += 1

        # TTS
        selected_voice = voice or self._cfg.voices.get(
            TTSEngine.detect_language(text),
            self._cfg.voices.get("en", "en-US-JennyNeural"),
        )
        tts_rate = rate or self._cfg.default_rate
        mp3_path = self._cfg.audio_dir / f"{ascii_name}.mp3"

        try:
            self._tts.generate(text, str(mp3_path), selected_voice, tts_rate)
        except Exception as e:
            return AddResult(success=False, error=f"TTS 生成失败: {e}")

        # 入库
        duration = TTSEngine.get_duration(str(mp3_path))
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
            "created_at": self._lib._now_cst().strftime("%Y-%m-%d %H:%M"),
        }
        self._lib.add_entry(entry)

        return AddResult(
            success=True,
            name=display_name,
            ascii_name=ascii_name,
            file=str(mp3_path),
            duration=duration,
            tweet_id=tweet_id,
            author=author,
        )

    # ── 音频库操作 ──────────────────────────────────────────────────

    def list_audios(self) -> list[dict]:
        return self._lib.list_all()

    def get_audio(self, identifier: str | int) -> dict:
        r = self._lib.find(identifier)
        # 补上 send_file 兼容
        if "send_file" not in r:
            r["send_file"] = r.get("file", "")
        return r

    def delete_audio(self, identifier: str | int) -> dict:
        return self._lib.remove(identifier)

    # ── 语言 / 时长 工具 ────────────────────────────────────────────

    @staticmethod
    def detect_language(text: str) -> str:
        return TTSEngine.detect_language(text)

    @staticmethod
    def get_duration(file_path: str) -> int:
        return TTSEngine.get_duration(file_path)
