"""Test trending discovery with various queries to find ones with engagement.
Run from project root: python scripts/test_trending_queries.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from atg_engine.services.trending_content_discovery import discover_trending_tweets


def _safe(s: str, max_len: int = 70) -> str:
    """Avoid UnicodeEncodeError on Windows console."""
    if not s:
        return ""
    return (s[:max_len] + ("..." if len(s) > max_len else "")).encode("ascii", "replace").decode("ascii")


def main():
    # Popular topics that often have engagement
    test_queries = [
        "AI OR artificial intelligence",
        "viral OR trending",
        "breaking news",
        "tech OR technology",
        "startup OR business",
        "crypto OR bitcoin",
        "politics OR news",
        "gaming OR video games",
        "music OR song",
        "sports OR football",
        "fitness OR workout",
        "food OR recipe",
        "travel OR vacation",
        "fashion OR style",
        "movie OR film",
    ]

    print("Testing queries with min_likes=5, min_retweets=1 (prime-ish content):\n")
    
    results = []
    for q in test_queries:
        try:
            tweets = discover_trending_tweets(
                query=q,
                max_results=10,
                min_likes=5,
                min_retweets=1,
            )
            if tweets:
                results.append((q, tweets))
                print(f"[OK] {q}: {len(tweets)} tweets")
                top = tweets[0]
                print(f"  Top: likes={top.get('likes')} RTs={top.get('retweets')} | {_safe(top.get('text') or '', 60)}")
            else:
                print(f"[0] {q}: 0 tweets")
        except Exception as e:
            err_msg = str(e)
            if "402" in err_msg or "Payment Required" in err_msg:
                print(f"[ERR] {q}: Twitter API account needs credits/billing")
                break  # Stop testing if API is out of credits
            else:
                print(f"[ERR] {q}: {err_msg}")
        print()

    if results:
        print(f"\n=== Best queries (found {sum(len(t) for _, t in results)} total tweets) ===")
        for q, tweets in sorted(results, key=lambda x: len(x[1]), reverse=True)[:5]:
            print(f"{q}: {len(tweets)} tweets")
    else:
        print("\nNo queries returned tweets. Try:")
        print("  1. Lower thresholds: python -m atg_engine run-trending --min-likes 1 --min-retweets 0")
        print("  2. Check Twitter API credits/billing")
        print("  3. Try specific hashtags or trending topics")


if __name__ == "__main__":
    main()
