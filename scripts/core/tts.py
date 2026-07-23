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
        self._run_async(text, output_path, selected_voice, tts_rate)

    def _run_async(self, text: str, output_path: str, voice: str, rate: str):
        """安全地在新事件循环中运行 edge-tts。"""
        import edge_tts
        communicate = edge_tts.Communicate(text, voice, rate=rate)

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # 没有运行中事件循环 → 用 asyncio.run（最简单）
            asyncio.run(communicate.save(output_path))
            return

        # 已有事件循环 → run_until_complete 避免嵌套
        if loop.is_running():
            import threading
            result = [None]
            exc = [None]

            def _run():
                try:
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    new_loop.run_until_complete(communicate.save(output_path))
                    new_loop.close()
                except Exception as e:
                    exc[0] = e

            t = threading.Thread(target=_run, daemon=True)
            t.start()
            t.join()
            if exc[0]:
                raise exc[0]
        else:
            loop.run_until_complete(communicate.save(output_path))

    # ── 时长 ────────────────────────────────────────────────────────

    @staticmethod
    def get_duration(file_path: str) -> int:
        """返回音频时长（秒）。优先 mutagen 解析，fallback 文件大小估。"""
        try:
            import mutagen
            audio = mutagen.File(file_path)
            if audio:
                return int(audio.info.length)
        except (ImportError, Exception):
            pass
        try:
            size = Path(file_path).stat().st_size
            return int(size / 4000)
        except OSError:
            return 0
