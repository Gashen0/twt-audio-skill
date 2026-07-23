"""TTS 生成 — 语言检测、Edge-TTS 异步同步化、时长探测。"""

import asyncio
import re
from pathlib import Path
from typing import Optional


class TTSEngine:
    """文本转语音引擎。同步接口，内部 asyncio。"""

    def __init__(self, voices: dict, default_rate: str):
        self._voices = voices
        self._default_rate = default_rate

    # ── 语言检测 ─────────────────────────────────────────────────────

    @staticmethod
    def detect_language(text: str) -> str:
        """检测文本语言：中文字符数 > 英文字符数 → zh，否则 en。"""
        cn = len(re.findall(r"[\u4e00-\u9fff]", text))
        en = len(re.findall(r"[a-zA-Z]", text))
        return "zh" if cn > en else "en"

    # ── TTS 生成 ────────────────────────────────────────────────────

    def generate(self, text: str, output_path: str,
                 voice: Optional[str] = None, rate: Optional[str] = None):
        """同步 TTS 生成。自动选语音 + 语速。"""
        selected_voice = voice or self._voices.get(
            self.detect_language(text), self._voices.get("en", "en-US-JennyNeural"),
        )
        tts_rate = rate or self._default_rate
        asyncio.run(self._generate_async(text, output_path, selected_voice, tts_rate))

    @staticmethod
    async def _generate_async(text: str, output_path: str, voice: str, rate: str):
        """纯异步 TTS 实现。"""
        import edge_tts
        communicate = edge_tts.Communicate(text, voice, rate=rate)
        await communicate.save(output_path)

    # ── 时长 ────────────────────────────────────────────────────────

    @staticmethod
    def get_duration(file_path: str) -> int:
        """返回音频时长（秒）。mutagen 解析，失败返回 0。"""
        try:
            import mutagen
            audio = mutagen.File(file_path)
            if audio:
                return int(audio.info.length)
        except (ImportError, Exception):
            pass
        return 0
