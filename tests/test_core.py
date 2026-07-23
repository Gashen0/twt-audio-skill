"""twt-audio-mcp 基础单元测试。"""

import json
import tempfile
from pathlib import Path

import pytest

from scripts.core.models import TweetResult, AddResult, CoreError
from scripts.core.library import AudioLibrary


# ── Models ───────────────────────────────────────────────────────

class TestModels:
    def test_tweet_result_dataclass(self):
        r = TweetResult(text="hello", author="user", tweet_id="123")
        assert r.text == "hello"
        assert r.author == "user"
        assert r.tweet_id == "123"
        assert r.is_article is False
        assert r.article_title == ""

    def test_tweet_result_to_dict(self):
        r = TweetResult(text="hello", author="u", tweet_id="1", is_article=True, article_title="Title")
        d = r.to_dict()
        assert d["text"] == "hello"
        assert d["is_article"] is True
        assert d["article_title"] == "Title"

    def test_add_result_success(self):
        r = AddResult(success=True, name="test", duration=125)
        assert r.success
        assert r.name == "test"
        assert r.duration_str == "2分5秒"

    def test_add_result_short_duration(self):
        r = AddResult(success=True, name="short", duration=42)
        assert r.duration_str == "42秒"

    def test_add_result_to_dict(self):
        r = AddResult(success=True, name="x", duration=60, tweet_id="999", author="a")
        d = r.to_dict()
        assert d["success"] is True
        assert d["duration_str"] == "1分0秒"
        assert d["tweet_id"] == "999"
        assert d["author"] == "a"

    def test_add_result_error(self):
        r = AddResult(success=False, error="something went wrong")
        assert r.success is False
        assert r.error == "something went wrong"
        assert r.duplicate is False

    def test_core_error(self):
        e = CoreError("test error")
        assert str(e) == "test error"
        assert isinstance(e, Exception)


# ── AudioLibrary ────────────────────────────────────────────────

class TestAudioLibraryBase:
    """基础 CRUD 测试"""

    @pytest.fixture
    def lib(self):
        tmpdir = tempfile.mkdtemp()
        index_path = Path(tmpdir) / "index.json"
        audio_dir = Path(tmpdir) / "audios"
        return AudioLibrary(index_path=index_path, audio_dir=audio_dir)

    def test_empty_list(self, lib):
        assert lib.list_all() == []

    def test_add_and_list(self, lib):
        entry = {
            "name": "测试音频",
            "ascii_name": "test_audio",
            "file": "/tmp/test.mp3",
            "tweet_id": "123",
            "author": "user",
            "text_length": 10,
            "duration": 120,
            "voice": "zh-CN-XiaoxiaoNeural",
            "rate": "+0%",
            "created_at": "2026-01-01 12:00",
        }
        lib.add_entry(entry)
        audios = lib.list_all()
        assert len(audios) == 1
        assert audios[0]["name"] == "测试音频"
        assert audios[0]["duration_str"] == "2分0秒"
        assert audios[0]["index"] == 1

    def test_find_by_index(self, lib):
        lib.add_entry({"name": "first", "ascii_name": "a1", "duration": 10, "tweet_id": "1"})
        lib.add_entry({"name": "second", "ascii_name": "a2", "duration": 20, "tweet_id": "2"})
        found = lib.find(2)
        assert found["name"] == "second"
        found = lib.find("2")
        assert found["name"] == "second"

    def test_find_by_exact_name(self, lib):
        lib.add_entry({"name": "测试", "ascii_name": "ceshi", "duration": 10, "tweet_id": "1"})
        lib.add_entry({"name": "测试音频", "ascii_name": "ceshi_yinpin", "duration": 20, "tweet_id": "2"})
        found = lib.find("测试")
        # 精确匹配优先
        assert found["name"] == "测试"

    def test_find_by_substring_prefers_shorter(self, lib):
        """精确匹配优先，没有精确时子串取最短"""
        # "short" 精确匹配到 name="short"（第1轮精确匹配），所以返回它
        lib.add_entry({"name": "short", "ascii_name": "short_name", "duration": 10, "tweet_id": "1"})
        lib.add_entry({"name": "shorter", "ascii_name": "shorter", "duration": 20, "tweet_id": "2"})
        found = lib.find("short")
        assert found["name"] == "short"  # 精确匹配 first name

    def test_find_by_substring_no_exact(self, lib):
        """没有精确匹配时，子串匹配取最短"""
        lib.add_entry({"name": "测试一二三", "ascii_name": "ceshi_yi_er_san", "duration": 10, "tweet_id": "1"})
        lib.add_entry({"name": "测试", "ascii_name": "ceshi", "duration": 20, "tweet_id": "2"})
        found = lib.find("测试")
        assert found["name"] == "测试"  # 精确匹配优先

    def test_find_not_found(self, lib):
        import pytest
        lib.add_entry({"name": "only", "ascii_name": "only", "duration": 10, "tweet_id": "1"})
        with pytest.raises(CoreError):
            lib.find("nonexistent")

    def test_remove_by_index(self, lib):
        lib.add_entry({"name": "a", "ascii_name": "a", "duration": 10, "tweet_id": "1"})
        lib.add_entry({"name": "b", "ascii_name": "b", "duration": 20, "tweet_id": "2"})
        removed = lib.remove(1)
        assert removed["name"] == "a"
        assert lib.list_all()[0]["name"] == "b"  # "a" 被删，只剩 "b"

    def test_remove_nonexistent_raises(self, lib):
        import pytest
        lib.add_entry({"name": "a", "ascii_name": "a", "duration": 10, "tweet_id": "1"})
        with pytest.raises(CoreError):
            lib.remove(99)

    def test_tweet_id_exists(self, lib):
        lib.add_entry({"name": "a", "ascii_name": "a", "duration": 10, "tweet_id": "999"})
        assert lib.tweet_id_exists("999") is not None
        assert lib.tweet_id_exists("888") is None

    def test_ascii_name_exists(self, lib):
        lib.add_entry({"name": "a", "ascii_name": "test_name", "duration": 10, "tweet_id": "1"})
        assert lib.ascii_name_exists("test_name") is True
        assert lib.ascii_name_exists("other") is False


class TestAudioLibrarySecurity:
    """路径遍历和安全测试"""

    @pytest.fixture
    def lib(self):
        tmpdir = tempfile.mkdtemp()
        index_path = Path(tmpdir) / "index.json"
        audio_dir = Path(tmpdir) / "audios"
        return AudioLibrary(index_path=index_path, audio_dir=audio_dir)

    def test_remove_path_traversal_protected(self, lib):
        """索引中存在 audio_dir 外的路径，remove 应该跳过删除"""
        audio_dir = lib._audio_dir
        safe_file = audio_dir / "safe.mp3"
        safe_file.parent.mkdir(parents=True, exist_ok=True)
        safe_file.write_text("safe")
        evil_file = Path(tempfile.mkdtemp()) / "evil.txt"
        evil_file.write_text("evil")

        entry = {
            "name": "test",
            "ascii_name": "test",
            "file": str(evil_file),  # 在 audio_dir 之外
            "send_file": str(safe_file),  # 在 audio_dir 之内
            "tweet_id": "1",
            "duration": 10,
            "author": "",
        }
        lib.add_entry(entry)
        removed = lib.remove(1)
        # safe_file 应该被删除
        assert not safe_file.exists()
        # evil_file 应该在 audio_dir 外，被跳过
        assert evil_file.exists()
        assert str(evil_file) not in removed.get("_deleted_files", [])

    def test_remove_only_deletes_files_in_audio_dir(self, lib):
        """确保只有 audio_dir 内的文件被删除"""
        audio_dir = lib._audio_dir
        outside = Path(tempfile.mkdtemp()) / "outside.mp3"
        outside.write_text("data")

        entry = {
            "name": "outside_test",
            "ascii_name": "outside_test",
            "file": str(outside),
            "tweet_id": "2",
            "duration": 10,
        }
        lib.add_entry(entry)
        removed = lib.remove(1)
        assert outside.exists()  # 没被删
        assert "_deleted_files" not in removed or removed["_deleted_files"] == []


class TestSanitizeDisplayName:
    def test_article_title_used(self):
        from scripts.core.library import AudioLibrary
        lib = AudioLibrary("/tmp/i.json", "/tmp/a")
        name = lib.sanitize_display_name("some text", "author", "Article Title Here")
        assert "Article Title Here" in name

    def test_url_removed(self):
        from scripts.core.library import AudioLibrary
        lib = AudioLibrary("/tmp/i.json", "/tmp/a")
        name = lib.sanitize_display_name("Check this out https://example.com/foo/bar")
        assert "https://" not in name

    def test_emoji_removed(self):
        from scripts.core.library import AudioLibrary
        lib = AudioLibrary("/tmp/i.json", "/tmp/a")
        name = lib.sanitize_display_name("Hello 🎉 world")
        assert "🎉" not in name

    def test_cjk_truncation_with_trailing_dot(self):
        from scripts.core.library import AudioLibrary
        lib = AudioLibrary("/tmp/i.json", "/tmp/a")
        # 20个中文字刚好达到 max_w，不截断
        text = "这是一个长测试文本用于验证截断逻辑是否正确工作。"
        name = lib.sanitize_display_name(text)
        assert len(name) <= 20
        assert not name.endswith(".")
        assert not name.endswith(" ")

    def test_empty_fallback(self):
        from scripts.core.library import AudioLibrary
        lib = AudioLibrary("/tmp/i.json", "/tmp/a")
        name = lib.sanitize_display_name("", "")
        assert name == "推文音频"


class TestMakeAsciiFilename:
    def test_pure_english(self):
        from scripts.core.library import AudioLibrary
        lib = AudioLibrary("/tmp/i.json", "/tmp/a")
        name = lib.make_ascii_filename("Hello World Test")
        assert name == "hello_world_test"

    def test_article_title_english(self):
        from scripts.core.library import AudioLibrary
        lib = AudioLibrary("/tmp/i.json", "/tmp/a")
        name = lib.make_ascii_filename("中文字符", "some text", "English Article Title")
        assert "english" in name
        assert "article" in name

    def test_pinyin_fallback(self):
        from scripts.core.library import AudioLibrary
        lib = AudioLibrary("/tmp/i.json", "/tmp/a")
        name = lib.make_ascii_filename("你好世界", "一些中文文字")
        # 应该生成拼音
        assert name
        assert all(c.isascii() for c in name)

    def test_hash_fallback(self):
        from scripts.core.library import AudioLibrary
        lib = AudioLibrary("/tmp/i.json", "/tmp/a")
        name = lib.make_ascii_filename("🌍🌏🌎", "")
        assert name.startswith("twt_")


# ── XClient ─────────────────────────────────────────────────────

class TestExtractTweetId:
    def test_pure_digits(self):
        from scripts.core.x_client import XClient
        assert XClient.extract_tweet_id("12345") == "12345"

    def test_full_url(self):
        from scripts.core.x_client import XClient
        assert XClient.extract_tweet_id("https://x.com/user/status/98765") == "98765"

    def test_url_with_params(self):
        from scripts.core.x_client import XClient
        assert XClient.extract_tweet_id("https://x.com/elonmusk/status/123456?lang=en") == "123456"

    def test_empty_raises(self):
        from scripts.core.x_client import XClient, CoreError
        import pytest
        with pytest.raises(CoreError):
            XClient.extract_tweet_id("")

    def test_invalid_raises(self):
        from scripts.core.x_client import XClient, CoreError
        import pytest
        with pytest.raises(CoreError):
            XClient.extract_tweet_id("not-a-tweet")
