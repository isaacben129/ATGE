"""
Twitter search provider abstraction for trending tweet discovery.
Free-first: use TWITTER_SEARCH_PRIMARY, fallback to TWITTER_SEARCH_FALLBACK on failure.
Posting stays in twitter_api; search goes through this provider.
"""
import logging
import time
from typing import Any, Protocol

from atg_engine.config.settings import TWITTER_BEARER_TOKEN

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
INITIAL_BACKOFF = 2.0

# Twitter requires at least one "standalone" term when using lang:/is:/has: (conjunction-required operators).
DEFAULT_SEARCH_TERM = "the"
VALID_DEFAULT_QUERY = f"{DEFAULT_SEARCH_TERM} -is:retweet lang:en"


def _is_retryable_search_error(exc: BaseException) -> bool:
    """True if we should try the fallback provider (rate limit, NotImplemented, connection errors, etc.)."""
    if isinstance(exc, NotImplementedError):
        return True
    # Connection/transport errors: retry (or fallback) often recovers
    if isinstance(exc, (ConnectionError, OSError)):
        return True
    msg = str(exc).lower()
    if "connection" in msg or "remote end closed" in msg or "aborted" in msg:
        return True
    resp = getattr(exc, "response", None)
    status = getattr(resp, "status_code", None) if resp is not None else getattr(exc, "status_code", None)
    return status in (429, 503)


class TwitterSearchProvider(Protocol):
    """Interface for recent tweet search (same list-of-dict shape as discover_trending_tweets)."""

    def search_recent_tweets(
        self,
        query: str = "",
        max_results: int = 10,
        min_likes: int = 100,
        min_retweets: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Search recent tweets. Returns list of dicts with:
        tweet_id, text, author_username, likes, retweets, created_at.
        """
        ...


class OfficialTwitterSearchProvider:
    """Uses official X API v2 search_recent_tweets (tweepy bearer client)."""

    def search_recent_tweets(
        self,
        query: str = "",
        max_results: int = 10,
        min_likes: int = 100,
        min_retweets: int = 10,
    ) -> list[dict[str, Any]]:
        client = _get_tweepy_client()
        if client is None:
            return []

        search_query = query.strip() or VALID_DEFAULT_QUERY
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
                if attempt < MAX_RETRIES - 1 and _is_retryable_search_error(e):
                    time.sleep(INITIAL_BACKOFF * (2**attempt))
                else:
                    raise

        return []


def _get_tweepy_client():
    """Lazy import tweepy Client (v2) with bearer token for search."""
    try:
        import tweepy
    except ImportError:
        return None
    if not TWITTER_BEARER_TOKEN:
        return None
    return tweepy.Client(bearer_token=TWITTER_BEARER_TOKEN)


class ChainedTwitterSearchProvider:
    """Tries primary provider; on failure or rate limit (429/503), uses fallback."""

    def __init__(self, primary: TwitterSearchProvider, fallback: TwitterSearchProvider) -> None:
        self._primary = primary
        self._fallback = fallback

    def search_recent_tweets(
        self,
        query: str = "",
        max_results: int = 10,
        min_likes: int = 100,
        min_retweets: int = 10,
    ) -> list[dict[str, Any]]:
        try:
            return self._primary.search_recent_tweets(
                query=query,
                max_results=max_results,
                min_likes=min_likes,
                min_retweets=min_retweets,
            )
        except Exception as e:
            if _is_retryable_search_error(e):
                logger.warning("Search primary failed (%s), using fallback: %s", type(e).__name__, e)
                return self._fallback.search_recent_tweets(
                    query=query,
                    max_results=max_results,
                    min_likes=min_likes,
                    min_retweets=min_retweets,
                )
            raise


class FreeTwitterSearchProvider:
    """
    Stub for a free search source (e.g. Nitter RSS or third-party free API).
    Set TWITTER_SEARCH_PRIMARY to this provider name when one is implemented.
    Until then, raises NotImplementedError (chain will use fallback).
    """
    def search_recent_tweets(
        self,
        query: str = "",
        max_results: int = 10,
        min_likes: int = 100,
        min_retweets: int = 10,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError(
            "Free search provider not implemented. "
            "Set TWITTER_SEARCH_PRIMARY=official until a free search source is added."
        )


def _search_provider_by_name(name: str) -> TwitterSearchProvider:
    """Return a search provider instance by name (official, free stub)."""
    n = (name or "official").strip().lower()
    if n == "free":
        return FreeTwitterSearchProvider()
    return OfficialTwitterSearchProvider()


def get_search_provider() -> TwitterSearchProvider:
    """Return the configured search provider: primary with fallback chain (free-first)."""
    from atg_engine.config.settings import TWITTER_SEARCH_PRIMARY, TWITTER_SEARCH_FALLBACK
    primary = _search_provider_by_name(TWITTER_SEARCH_PRIMARY)
    fallback = _search_provider_by_name(TWITTER_SEARCH_FALLBACK)
    if TWITTER_SEARCH_PRIMARY == TWITTER_SEARCH_FALLBACK:
        return primary
    return ChainedTwitterSearchProvider(primary, fallback)
