"""Service to discover trending tweets for quote/repost. Uses search provider (free-first with fallback)."""
from typing import Any

from atg_engine.services.twitter_search_provider import VALID_DEFAULT_QUERY, get_search_provider


def discover_trending_tweets(
    query: str = "",
    max_results: int = 50,
    min_likes: int = 50,
    min_retweets: int = 5,
) -> list[dict[str, Any]]:
    """
    Discover trending tweets using the configured search provider (official or free-first chain).

    Args:
        query: Search query (empty string uses default: recent non-retweet English tweets).
        max_results: Maximum number of tweets to return.
        min_likes: Minimum likes threshold.
        min_retweets: Minimum retweets threshold.

    Returns:
        List of tweet dicts with: tweet_id, text, author_username, likes, retweets, created_at.
    """
    provider = get_search_provider()
    return provider.search_recent_tweets(
        query=query,
        max_results=max_results,
        min_likes=min_likes,
        min_retweets=min_retweets,
    )


def _topic_to_search_terms(topic: str, max_terms: int = 3) -> list[str]:
    """Turn a topic string into search terms (words or short phrases)."""
    stop = {"and", "the", "of", "in", "on", "vs", "or", "to", "for", "what", "why", "how"}
    words = []
    for part in topic.replace(",", " ").split():
        w = part.strip().strip("()[]").lower()
        if w and w not in stop and len(w) > 1:
            words.append(w)
    if not words:
        return []
    out = []
    for w in words[:max_terms]:
        if len(w) > 3:
            out.append(w)
    return out[:max_terms] if out else words[:max_terms]


def discover_by_categories(
    categories: dict[str, list[str]],
    tweets_per_category: int = 5,
    min_likes: int = 50,
    min_retweets: int = 5,
    category_filter: list[str] | None = None,
) -> list[dict[str, Any]]:
    """
    Run multiple searches (one per category) using topic keywords from category lists.
    Each returned tweet has an extra key: matched_category (str).

    Args:
        categories: Dict mapping category name -> list of topic strings.
        tweets_per_category: Max tweets to fetch per category.
        min_likes: Minimum likes.
        min_retweets: Minimum retweets.
        category_filter: If set, only search these category names; else all keys.

    Returns:
        List of tweet dicts with tweet_id, text, author_username, likes, retweets, created_at, matched_category.
        Deduplicated by tweet_id (first category wins).
    """
    seen_ids: set[str] = set()
    result: list[dict[str, Any]] = []
    names = category_filter if category_filter else list(categories.keys())

    for cat_name in names:
        topics = categories.get(cat_name)
        if not topics or not isinstance(topics, list):
            continue
        terms = []
        for t in topics[:3]:
            if isinstance(t, str) and t.strip():
                terms.extend(_topic_to_search_terms(t.strip(), max_terms=2))
        if not terms:
            query = VALID_DEFAULT_QUERY
        else:
            or_part = " OR ".join(f'"{t}"' if " " in t else t for t in terms[:4])
            query = f"({or_part}) -is:retweet lang:en"
        batch = discover_trending_tweets(
            query=query,
            max_results=tweets_per_category,
            min_likes=min_likes,
            min_retweets=min_retweets,
        )
        for t in batch:
            tid = t.get("tweet_id")
            if tid and tid not in seen_ids:
                seen_ids.add(tid)
                t = {**t, "matched_category": cat_name}
                result.append(t)
    result.sort(key=lambda x: (x.get("likes") or 0) + (x.get("retweets") or 0), reverse=True)
    return result
