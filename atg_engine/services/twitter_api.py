"""Thin wrapper for X (Twitter) API v2: post tweet, get metrics. Uses OAuth 1.0a for posting (Bearer for read). Retries on 429/503."""
import logging
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

logger = logging.getLogger(__name__)


def _get_client():
    """Lazy import tweepy Client (v2) with OAuth 1.0a user context for posting tweets."""
    try:
        import tweepy
    except ImportError:
        logger.error("tweepy not installed")
        return None
    if not all([TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET]):
        logger.error("Missing Twitter API credentials (API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_SECRET)")
        return None
    # OAuth 1.0a User Context - required for create_tweet (posting)
    # Pass bearer_token for read operations if available
    return tweepy.Client(
        bearer_token=TWITTER_BEARER_TOKEN if TWITTER_BEARER_TOKEN else None,
        consumer_key=TWITTER_API_KEY,
        consumer_secret=TWITTER_API_SECRET,
        access_token=TWITTER_ACCESS_TOKEN,
        access_token_secret=TWITTER_ACCESS_SECRET,
    )


def _is_retryable(status_code: int | None) -> bool:
    return status_code in (429, 503)


def post_tweet(text: str, reply_to_tweet_id: str | None = None, quote_tweet_id: str | None = None) -> str | None:
    """
    Post a tweet via API v2. Returns tweet_id or None on failure.
    If reply_to_tweet_id is set, the tweet is posted as a reply (for threads).
    If quote_tweet_id is set, the tweet is posted as a quote of the given tweet.
    Retries with exponential backoff on 429 (rate limit) and 503 (server error).
    """
    client = _get_client()
    if client is None:
        logger.error("Cannot post tweet: Twitter client not available (missing credentials or tweepy)")
        return None
    kwargs = {"text": text}
    if reply_to_tweet_id:
        kwargs["in_reply_to_tweet_id"] = reply_to_tweet_id
    if quote_tweet_id:
        kwargs["quote_tweet_id"] = quote_tweet_id
    last_status = None
    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            response = client.create_tweet(**kwargs)
            if response and response.data:
                tweet_id = response.data.get("id")
                logger.info("Successfully posted tweet: %s", tweet_id)
                return tweet_id
            else:
                logger.warning("Tweet posted but response.data is missing")
        except Exception as e:
            resp = getattr(e, "response", None)
            last_status = getattr(resp, "status_code", None) if resp is not None else getattr(e, "status_code", None)
            last_error = e
            error_msg = str(e)
            if resp and hasattr(resp, "json"):
                try:
                    error_data = resp.json()
                    if isinstance(error_data, dict):
                        error_msg = error_data.get("detail", error_data.get("title", str(e)))
                except Exception:
                    pass
            
            if attempt < MAX_RETRIES - 1 and _is_retryable(last_status):
                sleep_secs = INITIAL_BACKOFF * (2**attempt)
                logger.warning("Twitter API error (status %s): %s. Retrying in %s seconds (attempt %s/%s)", 
                             last_status, error_msg, sleep_secs, attempt + 1, MAX_RETRIES)
                time.sleep(sleep_secs)
            else:
                logger.error("Failed to post tweet after %s attempts. Status: %s, Error: %s", 
                           attempt + 1, last_status, error_msg)
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
