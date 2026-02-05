"""Thin wrapper for X (Twitter) API v2: post tweet, get metrics. OAuth 2.0 / Bearer. Retries on 429/503."""
import time
from typing import Any

MAX_RETRIES = 3
INITIAL_BACKOFF = 2.0

from atg_engine.config.settings import (
    TWITTER_ACCESS_SECRET,
    TWITTER_ACCESS_TOKEN,
    TWITTER_API_KEY,
    TWITTER_API_SECRET,
    TWITTER_BEARER_TOKEN,
)


def _get_client():
    """Lazy import tweepy Client (v2)."""
    try:
        import tweepy
    except ImportError:
        return None
    if not all([TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET]):
        return None
    auth = tweepy.OAuth1UserHandler(
        TWITTER_API_KEY, TWITTER_API_SECRET,
        TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET,
    )
    api = tweepy.API(auth)
    # Tweepy v2 uses Client with bearer token for most v2 endpoints
    if TWITTER_BEARER_TOKEN:
        return tweepy.Client(
            bearer_token=TWITTER_BEARER_TOKEN,
            consumer_key=TWITTER_API_KEY,
            consumer_secret=TWITTER_API_SECRET,
            access_token=TWITTER_ACCESS_TOKEN,
            access_token_secret=TWITTER_ACCESS_SECRET,
        )
    return None


def _is_retryable(status_code: int | None) -> bool:
    return status_code in (429, 503)


def post_tweet(text: str, reply_to_tweet_id: str | None = None) -> str | None:
    """
    Post a tweet via API v2. Returns tweet_id or None on failure.
    If reply_to_tweet_id is set, the tweet is posted as a reply (for threads).
    Retries with exponential backoff on 429 (rate limit) and 503 (server error).
    """
    client = _get_client()
    if client is None:
        return None
    kwargs = {"text": text}
    if reply_to_tweet_id:
        kwargs["in_reply_to_tweet_id"] = reply_to_tweet_id
    last_status = None
    for attempt in range(MAX_RETRIES):
        try:
            response = client.create_tweet(**kwargs)
            if response and response.data:
                return response.data.get("id")
        except Exception as e:
            resp = getattr(e, "response", None)
            last_status = getattr(resp, "status_code", None) if resp is not None else getattr(e, "status_code", None)
            if attempt < MAX_RETRIES - 1 and _is_retryable(last_status):
                sleep_secs = INITIAL_BACKOFF * (2**attempt)
                time.sleep(sleep_secs)
            else:
                break
    return None


def get_me_follower_count() -> int | None:
    """
    Get the authenticated user's current follower count via GET /2/users/me.
    Returns follower_count or None if unavailable.
    """
    client = _get_client()
    if client is None:
        return None
    try:
        response = client.get_me(user_fields=["public_metrics"])
        if not response or not response.data:
            return None
        pm = getattr(response.data, "public_metrics", None)
        if pm is None:
            return None
        if hasattr(pm, "followers_count"):
            return int(pm.followers_count)
        if isinstance(pm, dict):
            return int(pm.get("followers_count", 0))
    except Exception:
        pass
    return None


def get_tweet_metrics(tweet_id: str) -> dict[str, Any]:
    """
    Get tweet metrics (impressions, likes, retweets, replies).
    Returns dict with keys: impressions, likes, retweets, replies; 0 if unavailable.
    """
    result = get_tweet_metrics_batch([tweet_id])
    return result.get(tweet_id, {"impressions": 0, "likes": 0, "retweets": 0, "replies": 0})


# Max tweet IDs per request (X API v2 limit)
GET_TWEETS_BATCH_SIZE = 100


def get_tweet_metrics_batch(tweet_ids: list[str]) -> dict[str, dict[str, Any]]:
    """
    Get metrics for multiple tweets in batch (one or few API calls).
    Returns dict mapping tweet_id -> {impressions, likes, retweets, replies}.
    Missing or failed tweets are omitted; callers can use .get(tweet_id, default).
    """
    out: dict[str, dict[str, Any]] = {}
    if not tweet_ids:
        return out
    client = _get_client()
    if client is None:
        return out
    default_metrics = {"impressions": 0, "likes": 0, "retweets": 0, "replies": 0}

    for i in range(0, len(tweet_ids), GET_TWEETS_BATCH_SIZE):
        chunk = tweet_ids[i : i + GET_TWEETS_BATCH_SIZE]
        last_status = None
        for attempt in range(MAX_RETRIES):
            try:
                response = client.get_tweets(
                    ids=chunk,
                    tweet_fields=["public_metrics"],
                    expansions=[],
                )
                if response and response.data:
                    for tweet in response.data:
                        tid = str(tweet.id) if hasattr(tweet, "id") else getattr(tweet, "id", None)
                        if tid is None:
                            continue
                        pm = getattr(tweet, "public_metrics", None)
                        if pm is None:
                            out[tid] = dict(default_metrics)
                            continue
                        out[tid] = {
                            "impressions": getattr(pm, "impression_count", 0) or 0,
                            "likes": getattr(pm, "like_count", 0) or 0,
                            "retweets": getattr(pm, "retweet_count", 0) or 0,
                            "replies": getattr(pm, "reply_count", 0) or 0,
                        }
                break
            except Exception as e:
                resp = getattr(e, "response", None)
                last_status = getattr(resp, "status_code", None) if resp is not None else getattr(e, "status_code", None)
                if attempt < MAX_RETRIES - 1 and _is_retryable(last_status):
                    time.sleep(INITIAL_BACKOFF * (2**attempt))
                else:
                    for tid in chunk:
                        out[tid] = dict(default_metrics)
                    break

    return out
