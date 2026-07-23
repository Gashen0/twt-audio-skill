"""数据模型 — 纯结构。"""

from dataclasses import dataclass, field, asdict


@dataclass
class TweetResult:
    """推文抓取结果"""
    text: str = ""
    author: str = ""
    tweet_id: str = ""
    is_article: bool = False
    article_title: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AddResult:
    """添加音频的结果"""
    success: bool = False
    name: str = ""
    ascii_name: str = ""
    file: str = ""
    duration: int = 0
    tweet_id: str = ""
    author: str = ""
    duplicate: bool = False
    error: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["duration_str"] = self.duration_str
        return d

    @property
    def duration_str(self) -> str:
        m, s = divmod(self.duration, 60)
        return f"{m}分{s}秒" if m else f"{s}秒"


class CoreError(Exception):
    """Core 层错误"""
    pass
