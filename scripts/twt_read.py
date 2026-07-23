#!/usr/bin/env python3
"""
Read a tweet (or thread) from X/Twitter using cookie authentication.
Extracts full text including long-form articles.

Usage:
 python3 twt_read.py <tweet_url_or_id>
 python3 twt_read.py https://x.com/user/status/1234567890
 python3 twt_read.py 1234567890
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Configuration — loaded from config.yaml, with hardcoded fallbacks
# ---------------------------------------------------------------------------

_PROJECT_DIR = Path(__file__).resolve().parent.parent  # twt-audio-mcp/
_CONFIG_PATH = _PROJECT_DIR / "config.yaml"
_DATA_DIR = _PROJECT_DIR / "data"


def _load_config() -> dict:
    """Load config.yaml; return empty dict on failure."""
    try:
        import yaml
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except (ImportError, FileNotFoundError):
        return {}


_CFG = _load_config()

# Paths — configurable via config.yaml
_tw_cfg = _CFG.get("twitter", {})
_path_cfg = _CFG.get("paths", {})

COOKIE_PATH = str(_DATA_DIR / _path_cfg.get("cookie_file", "secrets/x_cookies.json"))
BEARER = _tw_cfg.get(
    "bearer",
    "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA",
)

# TweetDetail queryId (for reading a single tweet with context)
TWEET_DETAIL_QUERY_ID = _tw_cfg.get("tweet_detail_query_id", "_i0BBmP_dK_ZLFa2Y-ei9Q")

# TweetResultByRestId queryId (for reading article content)
TWEET_RESULT_BY_REST_ID_QUERY_ID = _tw_cfg.get(
    "tweet_result_by_rest_id_query_id", "uEyKTt72BfzaY84WLGC5Dw"
)

# Rate limiting
MIN_INTERVAL = _tw_cfg.get("rate_limit_seconds", 5)
RATE_LIMIT_MARGIN = _tw_cfg.get("rate_limit_margin", 0.1)
LAST_REQUEST_TIME = 0

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
    "responsive_web_edit_tweet_api_enabled": True,
    "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
    "view_counts_everywhere_api_enabled": True,
    "longform_notetweets_consumption_enabled": True,
    "responsive_web_twitter_article_tweet_consumption_enabled": True,
    "content_disclosure_indicator_enabled": True,
    "content_disclosure_ai_generated_indicator_enabled": True,
    "responsive_web_grok_show_grok_translated_post": True,
    "responsive_web_grok_analysis_button_from_backend": True,
    "post_ctas_fetch_enabled": True,
    "freedom_of_speech_not_reach_fetch_enabled": True,
    "standardized_nudges_misinfo": True,
    "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
    "longform_notetweets_rich_text_read_enabled": True,
    "longform_notetweets_inline_media_enabled": True,
    "responsive_web_enhance_cards_enabled": False,
}


def load_cookies() -> dict:
    """Load X/Twitter cookies from JSON file."""
    try:
        with open(COOKIE_PATH) as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: Cookie file not found at {COOKIE_PATH}", file=sys.stderr)
        sys.exit(1)


def rate_limit():
    """Enforce minimum interval between X API requests."""
    global LAST_REQUEST_TIME
    now = time.time()
    elapsed = now - LAST_REQUEST_TIME
    if elapsed < MIN_INTERVAL:
        wait = MIN_INTERVAL - elapsed + RATE_LIMIT_MARGIN
        time.sleep(wait)
    LAST_REQUEST_TIME = time.time()


def extract_tweet_id(input_str: str) -> str:
    """Extract tweet ID from URL or raw numeric ID.

    Args:
        input_str: Tweet URL (https://x.com/user/status/123) or raw ID string.

    Returns:
        Numeric tweet ID as string.

    Raises:
        SystemExit: If input cannot be parsed.
    """
    input_str = input_str.strip()
    if re.match(r'^\d+$', input_str):
        return input_str
    m = re.search(r'/status/(\d+)', input_str)
    if m:
        return m.group(1)
    print(f"Error: Cannot extract tweet ID from: {input_str}", file=sys.stderr)
    sys.exit(1)


def _extract_text_from_tweet_result(tweet_result: dict) -> str:
    """Extract text from a single tweet result object."""
    text_parts = []

    legacy = tweet_result.get("legacy", {})
    full_text = legacy.get("full_text", "")
    if full_text:
        text_parts.append(full_text)

    # Long-form note_tweet takes priority
    note_tweet = tweet_result.get("note_tweet", {})
    if note_tweet:
        note_result = note_tweet.get("note_tweet_results", {}).get("result", {})
        note_text = note_result.get("text", "")
        if note_text:
            text_parts = [note_text]

    return text_parts[0] if text_parts else ""


def _find_tweet_result(data, focal_tweet_id: str = None) -> list:
    """Recursively find tweet result objects in the GraphQL response."""
    results = []

    def _walk(obj):
        if isinstance(obj, dict):
            if "result" in obj and isinstance(obj["result"], dict):
                result = obj["result"]
                if result.get("__typename") == "Tweet":
                    results.append(result)
                elif result.get("__typename") == "TweetWithVisibilityResults":
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


def _extract_article_blocks(data) -> list:
    """Extract article text from Draft.js blocks in the response."""
    blocks = []

    def _walk(obj, depth=0):
        if depth > 20:
            return
        if isinstance(obj, dict):
            if "blocks" in obj and isinstance(obj["blocks"], list):
                candidate = obj["blocks"]
                if len(candidate) > 5:  # Article content has many blocks
                    blocks.extend(candidate)
            for v in obj.values():
                _walk(v, depth + 1)
        elif isinstance(obj, list):
            for item in obj:
                _walk(item, depth + 1)

    _walk(data)
    return blocks


def _blocks_to_text(blocks: list) -> str:
    """Convert Draft.js blocks to plain text.

    Handles: header-two, unordered-list-item, ordered-list-item, blockquote.
    All other block types are rendered as plain text.
    """
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


def _fetch_article_content(session: requests.Session, tweet_id: str, cookies: dict) -> str | None:
    """Fetch article content using TweetResultByRestId endpoint.

    TweetDetail only returns article preview. This endpoint returns
    the full article blocks (Draft.js format).

    Returns:
        Article plain text, or None on failure.
    """
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
        "features": json.dumps(FEATURES),
        "fieldToggles": json.dumps(field_toggles),
    }

    url = f"https://x.com/i/api/graphql/{TWEET_RESULT_BY_REST_ID_QUERY_ID}/TweetResultByRestId"

    rate_limit()
    resp = session.get(url, params=params)

    if resp.status_code != 200:
        return None

    data = resp.json()
    article_blocks = _extract_article_blocks(data)

    if article_blocks:
        return _blocks_to_text(article_blocks)

    return None


def read_tweet(tweet_id: str) -> dict:
    """Read a single tweet and return its full text.

    Args:
        tweet_id: Numeric tweet ID string.

    Returns:
        Dict with keys: text, author, tweet_id, is_article, article_title.

    Raises:
        SystemExit: On HTTP error or no tweet found.
    """
    cookies = load_cookies()

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
        "Authorization": f"Bearer {BEARER}",
        "X-Csrf-Token": cookies["ct0"],
    })

    # Step 1: Fetch tweet details via TweetDetail
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
        "features": json.dumps(FEATURES),
        "fieldToggles": json.dumps(field_toggles),
    }

    url = f"https://x.com/i/api/graphql/{TWEET_DETAIL_QUERY_ID}/TweetDetail"

    rate_limit()
    resp = session.get(url, params=params)

    if resp.status_code != 200:
        print(f"Error: HTTP {resp.status_code}", file=sys.stderr)
        print(resp.text[:500], file=sys.stderr)
        sys.exit(1)

    data = resp.json()

    # Find all tweet results
    all_tweets = _find_tweet_result(data, tweet_id)

    if not all_tweets:
        print("Error: No tweet found in response", file=sys.stderr)
        sys.exit(1)

    # Extract the focal tweet
    focal_text = ""
    author_id = None
    author_name = ""
    is_article = False
    article_title = ""

    for tweet in all_tweets:
        text = _extract_text_from_tweet_result(tweet)
        legacy = tweet.get("legacy", {})
        tweet_id_str = str(legacy.get("id_str", ""))
        uid = str(legacy.get("user_id_str", ""))

        if tweet_id_str == str(tweet_id):
            author_id = uid

            # Check if this is an article tweet
            article = tweet.get("article", {})
            if article:
                is_article = True
                article_result = article.get("article_results", {}).get("result", {})
                article_title = article_result.get("title", "")
                _preview = article_result.get("preview_text", "")

            # Check note_tweet for long-form
            note_tweet = tweet.get("note_tweet", {})
            if note_tweet:
                note_result = note_tweet.get("note_tweet_results", {}).get("result", {})
                note_text = note_result.get("text", "")
                if note_text:
                    focal_text = note_text

            if not focal_text:
                focal_text = text

        # Get author name
        core = tweet.get("core", {})
        user_results = core.get("user_results", {}).get("result", {})
        legacy_user = user_results.get("legacy", {})
        if legacy_user.get("name"):
            author_name = legacy_user["name"]
        elif uid and uid == author_id:
            # Thread reply by same author
            thread_text = _extract_text_from_tweet_result(tweet)
            if thread_text:
                focal_text += "\n\n" + thread_text

    # Step 2: If article, fetch full content via TweetResultByRestId
    if is_article:
        article_content = _fetch_article_content(session, tweet_id, cookies)
        if article_content:
            if article_title:
                focal_text = f"{article_title}\n\n{article_content}"
            else:
                focal_text = article_content

    return {
        "text": focal_text.strip(),
        "author": author_name,
        "tweet_id": str(tweet_id),
        "is_article": is_article,
        "article_title": article_title if is_article else "",
    }


def main():
    parser = argparse.ArgumentParser(description="Read a tweet from X/Twitter")
    parser.add_argument("input", help="Tweet URL or ID")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    tweet_id = extract_tweet_id(args.input)
    result = read_tweet(tweet_id)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if result["author"]:
            print(f"@{result['author']}\n")
        print(result["text"])
        print(f"\n[tweet_id: {result['tweet_id']}]")


if __name__ == "__main__":
    main()
