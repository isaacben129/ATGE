"""
RapidAPI Twitter client: tweet search, metrics batch, and user follower count.
Uses RapidAPI twitter-api45 endpoint. Do not log or expose RAPIDAPI_KEY.
Optimized with caching to minimize API calls due to limited monthly quota.
"""
import http.client
import json
import logging
import time
import urllib.parse
from typing import Any

from atg_engine.config.settings import RAPIDAPI_KEY, RAPIDAPI_HOST, RAPIDAPI_CACHE_TTL_SEC

logger = logging.getLogger(__name__)

_DEFAULT_METRICS = {"impressions": 0, "likes": 0, "retweets": 0, "replies": 0}

# Request cache: {cache_key: (response_data, timestamp)}
_request_cache: dict[str, tuple[Any, float]] = {}
# Deduplication: track recent requests in last 60 seconds
_recent_requests: dict[str, float] = {}
DEDUP_WINDOW_SEC = 60.0


def _get_cache_key(endpoint: str, params: dict[str, Any]) -> str:
    """Generate cache key from endpoint and sorted params."""
    sorted_params = sorted(params.items())
    params_str = "&".join(f"{k}={v}" for k, v in sorted_params)
    return f"{endpoint}:{params_str}"


def _is_cache_valid(timestamp: float) -> bool:
    """Check if cached entry is still valid based on TTL."""
    return (time.time() - timestamp) < RAPIDAPI_CACHE_TTL_SEC


def _make_request(endpoint: str, params: dict[str, Any], use_cache: bool = True) -> dict[str, Any]:
    """
    Make RapidAPI request with caching and error handling.
    
    Args:
        endpoint: API endpoint path (e.g., "/search.php")
        params: Query parameters dict
        use_cache: Whether to use cache (default True)
    
    Returns:
        Parsed JSON response as dict
    
    Raises:
        RuntimeError: On API errors or rate limits
    """
    global _recent_requests, _request_cache
    
    if not RAPIDAPI_KEY:
        raise RuntimeError("RAPIDAPI_KEY not configured")
    
    # Check cache
    cache_key = _get_cache_key(endpoint, params)
    if use_cache and cache_key in _request_cache:
        cached_data, cached_time = _request_cache[cache_key]
        if _is_cache_valid(cached_time):
            logger.debug("RapidAPI cache hit for %s", endpoint)
            return cached_data
    
    # Deduplication: prevent duplicate requests within short window
    request_fingerprint = f"{endpoint}:{hash(tuple(sorted(params.items())))}"
    current_time = time.time()
    if request_fingerprint in _recent_requests:
        last_time = _recent_requests[request_fingerprint]
        if (current_time - last_time) < DEDUP_WINDOW_SEC:
            logger.debug("RapidAPI deduplication: skipping duplicate request within %s seconds", DEDUP_WINDOW_SEC)
            # Return cached result if available, otherwise wait
            if cache_key in _request_cache:
                cached_data, _ = _request_cache[cache_key]
                return cached_data
    
    # Build query string
    query_params = urllib.parse.urlencode(params)
    full_path = f"{endpoint}?{query_params}" if query_params else endpoint
    
    headers = {
        'x-rapidapi-key': RAPIDAPI_KEY,
        'x-rapidapi-host': RAPIDAPI_HOST,
    }
    
    try:
        conn = http.client.HTTPSConnection(RAPIDAPI_HOST)
        conn.request("GET", full_path, headers=headers)
        res = conn.getresponse()
        data = res.read()
        
        status_code = res.status
        if status_code == 429:
            raise RuntimeError(f"RapidAPI rate limit exceeded (429)")
        if status_code != 200:
            error_text = data.decode("utf-8", errors="ignore")
            raise RuntimeError(f"RapidAPI request failed: status {status_code}, {error_text[:200]}")
        
        response_text = data.decode("utf-8")
        try:
            response_data = json.loads(response_text)
        except json.JSONDecodeError as e:
            logger.error("RapidAPI response not valid JSON: %s", response_text[:500])
            raise RuntimeError(f"RapidAPI response parse error: {e}")
        
        # Cache successful response
        if use_cache:
            _request_cache[cache_key] = (response_data, current_time)
            # Clean old cache entries (keep last 100)
            if len(_request_cache) > 100:
                oldest_key = min(_request_cache.keys(), key=lambda k: _request_cache[k][1])
                del _request_cache[oldest_key]
        
        # Track recent request
        _recent_requests[request_fingerprint] = current_time
        # Clean old dedup entries (keep last 50)
        if len(_recent_requests) > 50:
            cutoff_time = current_time - DEDUP_WINDOW_SEC
            # Remove old entries in place to avoid UnboundLocalError
            keys_to_remove = [k for k, v in _recent_requests.items() if v <= cutoff_time]
            for k in keys_to_remove:
                del _recent_requests[k]
        
        return response_data
        
    except http.client.HTTPException as e:
        raise RuntimeError(f"RapidAPI HTTP error: {e}") from e
    except Exception as e:
        if isinstance(e, RuntimeError):
            raise
        raise RuntimeError(f"RapidAPI request failed: {e}") from e
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _map_tweet_to_internal(tweet: dict[str, Any]) -> dict[str, Any]:
    """Map RapidAPI tweet object to internal format."""
    return {
        "tweet_id": str(tweet.get("tweet_id", "")),
        "text": tweet.get("text", ""),
        "author_username": tweet.get("screen_name", "unknown"),
        "likes": int(tweet.get("favorites", 0) or 0),
        "retweets": int(tweet.get("retweets", 0) or 0),
        "replies": int(tweet.get("replies", 0) or 0),
        "created_at": tweet.get("created_at"),
        # Impressions not available in RapidAPI response, default to 0
        "impressions": 0,
        # Quotes available but not in standard format
        "quotes": int(tweet.get("quotes", 0) or 0),
    }


def search_tweets_by_keywords(
    keywords: str, 
    limit: int = 100, 
    search_type: str = "Top", 
    cursor: str | None = None
) -> tuple[list[dict[str, Any]], str | None]:
    """
    Search tweets by keywords using RapidAPI.
    
    Args:
        keywords: Search query/keywords
        limit: Maximum number of results (not directly used by API, but for reference)
        search_type: Search type ("Top", "Latest", etc.)
        cursor: Optional cursor for pagination
    
    Returns:
        Tuple of (list of tweet dicts, next_cursor string or None)
    """
    if not keywords or not keywords.strip():
        return [], None
    
    params: dict[str, Any] = {
        "query": keywords.strip(),
        "search_type": search_type,
    }
    if cursor:
        params["cursor"] = cursor
    
    try:
        response = _make_request("/search.php", params)
        
        timeline = response.get("timeline", [])
        if not isinstance(timeline, list):
            logger.warning("RapidAPI search returned invalid timeline format")
            return [], None
        
        tweets = []
        for tweet_obj in timeline:
            if isinstance(tweet_obj, dict) and tweet_obj.get("type") == "tweet":
                mapped_tweet = _map_tweet_to_internal(tweet_obj)
                tweets.append(mapped_tweet)
        
        next_cursor = response.get("next_cursor")
        if next_cursor and not isinstance(next_cursor, str):
            next_cursor = None
        
        logger.debug("RapidAPI search returned %s tweets, next_cursor: %s", len(tweets), bool(next_cursor))
        return tweets, next_cursor
        
    except Exception as e:
        logger.warning("RapidAPI search failed: %s", e)
        raise RuntimeError(f"RapidAPI search failed: {e}") from e


def get_tweet_metrics_batch(tweet_ids: list[str]) -> dict[str, dict[str, Any]]:
    """
    Get tweet metrics for multiple tweets.
    
    Note: RapidAPI search results include metrics, but there's no direct batch endpoint
    for metrics by ID. This function would need to search for tweets by ID if such
    an endpoint exists, or return cached metrics from previous searches.
    
    For now, returns default metrics (0s) since we don't have a metrics-by-ID endpoint.
    If tweets were fetched via search, their metrics are already available.
    
    Args:
        tweet_ids: List of tweet IDs
    
    Returns:
        Dict mapping tweet_id -> {impressions, likes, retweets, replies}
    """
    if not tweet_ids:
        return {}
    
    # RapidAPI doesn't have a direct batch metrics endpoint
    # Metrics come with search results, so this is a placeholder
    # In practice, metrics should be extracted from search results when available
    result: dict[str, dict[str, Any]] = {}
    for tid in tweet_ids:
        result[str(tid)] = dict(_DEFAULT_METRICS)
    
    logger.debug("RapidAPI get_tweet_metrics_batch: returning default metrics for %s tweets", len(tweet_ids))
    return result


def get_user_follower_count(username: str) -> int | None:
    """
    Get follower count for a Twitter username via RapidAPI.
    
    Args:
        username: Twitter username (with or without @)
    
    Returns:
        Follower count or None if unavailable
    """
    if not username or not username.strip():
        return None
    
    # Remove @ if present
    screenname = username.strip().lstrip("@")
    
    params = {
        "screenname": screenname,
        "blue_verified": "0",
    }
    
    try:
        response = _make_request("/followers.php", params)
        
        followers_count = response.get("followers_count")
        if followers_count is None:
            logger.warning("RapidAPI followers response missing followers_count")
            return None
        
        try:
            count = int(followers_count)
            logger.debug("RapidAPI follower count for %s: %s", screenname, count)
            return count
        except (ValueError, TypeError):
            logger.warning("RapidAPI followers_count not a valid integer: %s", followers_count)
            return None
        
    except Exception as e:
        logger.warning("RapidAPI get_user_follower_count failed: %s", e)
        raise RuntimeError(f"RapidAPI follower count failed: {e}") from e
