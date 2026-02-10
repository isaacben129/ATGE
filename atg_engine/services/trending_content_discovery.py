"""Service to discover trending tweets for quote/repost."""
import time
from typing import Any

from atg_engine.config.settings import TWITTER_BEARER_TOKEN

MAX_RETRIES = 3
INITIAL_BACKOFF = 2.0


def _get_client():
    """Lazy import tweepy Client (v2) with bearer token for search."""
    try:
        import tweepy
    except ImportError:
        return None
    if not TWITTER_BEARER_TOKEN:
        return None
    return tweepy.Client(bearer_token=TWITTER_BEARER_TOKEN)


def _is_retryable(status_code: int | None) -> bool:
    return status_code in (429, 503)


def discover_trending_tweets(
    query: str = "",
    max_results: int = 10,
    min_likes: int = 100,
    min_retweets: int = 10,
) -> list[dict[str, Any]]:
    """
    Discover trending tweets using Twitter API v2 search.

    Args:
        query: Search query (empty string uses default: recent non-retweet English tweets).
        max_results: Maximum number of tweets to return.
        min_likes: Minimum likes threshold.
        min_retweets: Minimum retweets threshold.

    Returns:
        List of tweet dicts with: tweet_id, text, author_username, likes, retweets, created_at.
    """
    client = _get_client()
    if client is None:
        return []

    search_query = query if query.strip() else "-is:retweet lang:en"
    cap = min(max(max_results, 10), 100)

    for attempt in range(MAX_RETRIES):
        try:
            response = client.search_recent_tweets(
                query=search_query,
                max_results=cap,
                tweet_fields=["public_metrics", "created_at", "author_id"],
                expansions=["author_id"],
                user_fields=["username"],
            )

            if not response or not response.data:
                return []

            authors: dict[str, str] = {}
            if response.includes and hasattr(response.includes, "users"):
                for user in response.includes.users:
                    authors[str(user.id)] = getattr(user, "username", "unknown")

            trending: list[dict[str, Any]] = []
            for tweet in response.data:
                pm = getattr(tweet, "public_metrics", None)
                if not pm:
                    continue

                likes = getattr(pm, "like_count", 0) or 0
                retweets = getattr(pm, "retweet_count", 0) or 0

                if likes < min_likes or retweets < min_retweets:
                    continue

                tweet_id = str(tweet.id)
                author_id = str(getattr(tweet, "author_id", ""))
                author_username = authors.get(author_id, "unknown")

                trending.append({
                    "tweet_id": tweet_id,
                    "text": getattr(tweet, "text", ""),
                    "author_username": author_username,
                    "likes": likes,
                    "retweets": retweets,
                    "created_at": getattr(tweet, "created_at", None),
                })

            trending.sort(key=lambda x: x["likes"] + x["retweets"], reverse=True)
            return trending[:max_results]

        except Exception as e:
            resp = getattr(e, "response", None)
            status = getattr(resp, "status_code", None) if resp is not None else getattr(e, "status_code", None)
            if attempt < MAX_RETRIES - 1 and _is_retryable(status):
                time.sleep(INITIAL_BACKOFF * (2**attempt))
            else:
                return []

    return []
