"""数据模型 — 零依赖，纯结构。"""


class TweetResult:
    """推文抓取结果"""

    def __init__(self, text: str, author: str, tweet_id: str,
                 is_article: bool = False, article_title: str = ""):
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

    def __init__(self, success: bool, name: str = "", ascii_name: str = "",
                 file: str = "", duration: int = 0, tweet_id: str = "",
                 author: str = "", duplicate: bool = False, error: str = ""):
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
            "duration_str": self.duration_str,
            "tweet_id": self.tweet_id,
            "author": self.author,
            "duplicate": self.duplicate,
            "error": self.error,
        }

    @property
    def duration_str(self) -> str:
        m, s = divmod(self.duration, 60)
        return f"{m}分{s}秒" if m else f"{s}秒"


class AudioEntry:
    """音频库条目（序列化用）"""

    __slots__ = ("name", "ascii_name", "file", "tweet_id", "author",
                 "text_length", "duration", "voice", "rate", "created_at")

    def __init__(self, name: str, ascii_name: str, file: str, tweet_id: str,
                 author: str, text_length: int, duration: int,
                 voice: str, rate: str, created_at: str):
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
        return {s: getattr(self, s) for s in self.__slots__}


class CoreError(Exception):
    """Core 层错误"""
    pass
