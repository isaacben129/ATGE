"""Test trending search with lowest parameters to verify API returns data.
Run from project root: python scripts/test_trending_search.py
"""
import sys
from pathlib import Path

# Ensure atg_engine is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from atg_engine.services.trending_content_discovery import discover_trending_tweets


def _safe(s: str, max_len: int = 80) -> str:
    """Avoid UnicodeEncodeError on Windows console."""
    if not s:
        return ""
    return (s[:max_len] + ("..." if len(s) > max_len else "")).encode("ascii", "replace").decode("ascii")


def main():
    print("=== Raw search (min_likes=0, min_retweets=0, max_results=20) ===")
    raw = discover_trending_tweets(
        query="",
        max_results=20,
        min_likes=0,
        min_retweets=0,
    )
    print(f"Count: {len(raw)}")
    if raw:
        t = raw[0]
        print(f"First: id={t.get('tweet_id')} @{t.get('author_username')} likes={t.get('likes')} RTs={t.get('retweets')}")
        print(f"  Text: {_safe(t.get('text') or '')}")
    else:
        print("No tweets returned. Check API permissions and TWITTER_BEARER_TOKEN.")

    print("\n=== With prime defaults (min_likes=50, min_retweets=5) ===")
    filtered = discover_trending_tweets(
        query="",
        max_results=20,
        min_likes=50,
        min_retweets=5,
    )
    print(f"Count: {len(filtered)}")
    if filtered:
        t = filtered[0]
        print(f"First: id={t.get('tweet_id')} likes={t.get('likes')} RTs={t.get('retweets')} | {_safe(t.get('text') or '', 50)}")


if __name__ == "__main__":
    main()
