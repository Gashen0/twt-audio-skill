"""Twitter/X API 客户端 — 负责 GraphQL 请求、推文解析、Article 全文抓取。

纯函数风格：接收配置，返回结构化数据，不持有全局状态（rate_limit 除外）。"""

import json
import re
import time
from typing import Optional

import requests

from .models import TweetResult, CoreError


# ── FEATURES 固定字典（X GraphQL API 必需）───────────────────────────

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

FIELD_TOGGLES = {
    "withArticleRichContentState": True,
    "withArticlePlainText": True,
    "withArticleSummaryText": True,
    "withArticleVoiceOver": False,
    "withGrokAnalyze": False,
    "withDisallowedReplyControls": False,
}


class XClient:
    """X GraphQL API 封装。维护实例级 session 复用 TCP 连接。"""

    def __init__(self, bearer: str, tweet_detail_qid: str, tweet_result_qid: str,
                 rate_limit_seconds: int = 5, rate_limit_margin: float = 0.1):
        self._bearer = bearer
        self._detail_qid = tweet_detail_qid
        self._result_qid = tweet_result_qid
        self._min_interval = rate_limit_seconds
        self._rate_margin = rate_limit_margin
        self._last_request_time = 0.0
        self._session: Optional[requests.Session] = None

    # ── Session 管理 ───────────────────────────────────────────────

    def _make_session(self, cookies: dict) -> requests.Session:
        if self._session is None:
            self._session = requests.Session()
            self._session.headers.update({
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/136.0.0.0 Safari/537.36"
                ),
                "Accept": "*/*",
                "Accept-Language": "en-US,en;q=0.9",
                "Authorization": f"Bearer {self._bearer}",
            })
        # Cookie 按需更新（可能每次都不同）
        self._session.cookies.set("auth_token", cookies["auth_token"], domain=".x.com")
        self._session.cookies.set("ct0", cookies["ct0"], domain=".x.com")
        self._session.cookies.set("twid", cookies["twid"], domain=".x.com")
        self._session.headers["X-Csrf-Token"] = cookies["ct0"]
        return self._session

    def _rate_limit(self):
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self._min_interval:
            wait = self._min_interval - elapsed + self._rate_margin
            time.sleep(wait)
        self._last_request_time = time.time()

    # ── HTTP 请求 + 429 处理 ─────────────────────────────────────────

    def _request(self, method: str, url: str, **kwargs) -> requests.Response:
        """带 rate limit 和 429 重试的 HTTP 请求。"""
        session = self._session or requests
        self._rate_limit()
        resp = session.request(method, url, **kwargs)

        if resp.status_code == 429:
            retry_after = resp.headers.get("Retry-After")
            if retry_after and retry_after.isdigit():
                wait = int(retry_after)
            else:
                wait = 60  # 默认等60秒
            raise CoreError(f"HTTP 429 Rate Limited — 请在 {wait} 秒后重试")

        if resp.status_code != 200:
            raise CoreError(f"HTTP {resp.status_code}: {resp.text[:200]}")

        return resp

    # ── 推文 ID 提取 ────────────────────────────────────────────────

    @staticmethod
    def extract_tweet_id(input_str: str) -> str:
        """从 URL 或纯数字 ID 提取推文 ID。"""
        s = input_str.strip()
        if re.match(r"^\d+$", s):
            return s
        m = re.search(r"/status/(\d+)", s)
        if m:
            return m.group(1)
        raise CoreError(f"无法从输入中提取推文 ID: {input_str}")

    # ── GraphQL 响应解析（显式栈，避免递归深度）───────────────────

    @staticmethod
    def _find_tweet_results(data) -> list:
        """用显式栈遍历 JSON，收集所有 __typename == 'Tweet' 的 result。"""
        results = []
        stack = [data]
        while stack:
            obj = stack.pop()
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
                    stack.append(v)
            elif isinstance(obj, list):
                stack.extend(reversed(obj))  # 保持原顺序
        return results

    @staticmethod
    def _extract_text_from_tweet(tweet_result: dict) -> str:
        """从单条 Tweet result 提取文字（平推文 + note_tweet）。"""
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

    # ── Article 解析（显式栈，避免递归深度）────────────────────────

    @staticmethod
    def _extract_article_blocks(data) -> list:
        """用显式栈遍历，收集 Article 的 blocks。"""
        blocks = []
        stack = [data]
        while stack:
            obj = stack.pop()
            if isinstance(obj, dict):
                if "blocks" in obj and isinstance(obj["blocks"], list):
                    if len(obj["blocks"]) > 5:  # heuristic: 真正的 Article 至少6段
                        blocks.extend(obj["blocks"])
                for v in obj.values():
                    stack.append(v)
            elif isinstance(obj, list):
                stack.extend(reversed(obj))
        return blocks

    @staticmethod
    def _blocks_to_text(blocks: list) -> str:
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

    # ── Article 全文 ────────────────────────────────────────────────

    def _fetch_article_content(self, session: requests.Session, tweet_id: str) -> Optional[str]:
        params = {
            "variables": json.dumps({
                "tweetId": str(tweet_id),
                "includePromotedContent": False,
                "withCommunity": False,
                "withVoice": False,
            }),
            "features": json.dumps(FEATURES),
            "fieldToggles": json.dumps(FIELD_TOGGLES),
        }
        url = f"https://x.com/i/api/graphql/{self._result_qid}/TweetResultByRestId"
        try:
            resp = self._request("GET", url, params=params, timeout=30)
        except CoreError:
            return None
        data = resp.json()
        # 检查 API 错误响应
        if "errors" in data and data.get("errors"):
            return None
        article_blocks = self._extract_article_blocks(data)
        if article_blocks:
            return self._blocks_to_text(article_blocks)
        return None

    # ── 主调 ────────────────────────────────────────────────────────

    def fetch_tweet(self, tweet_id: str, cookies: dict) -> TweetResult:
        """抓取一条推文（含 Article 全文）。"""
        session = self._make_session(cookies)

        # ── Step 1: TweetDetail ──
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
        params = {
            "variables": json.dumps(variables),
            "features": json.dumps(FEATURES),
            "fieldToggles": json.dumps(FIELD_TOGGLES),
        }
        url = f"https://x.com/i/api/graphql/{self._detail_qid}/TweetDetail"
        resp = self._request("GET", url, params=params, timeout=30)

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

        # ── Step 2: Article 全文 ──
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
