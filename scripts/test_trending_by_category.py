"""Test trending discovery using one or more categories (topic-based search).
Run from project root: python scripts/test_trending_by_category.py
Uses low thresholds by default so the API returns results.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from atg_engine.services.trending_content_discovery import discover_by_categories


# One or more categories: name -> list of topic strings (used as search terms)
SAMPLE_CATEGORIES = {
    "dating": ["dating", "ghost", "relationships"],
    "tech": ["AI", "machine learning", "coding"],
}


def main():
    import argparse
    p = argparse.ArgumentParser(description="Test trending by category")
    p.add_argument("--min-likes", type=int, default=0, help="Min likes (default 0)")
    p.add_argument("--min-retweets", type=int, default=0, help="Min retweets (default 0)")
    p.add_argument("--per-category", type=int, default=5, help="Max tweets per category (default 5)")
    p.add_argument("--category", type=str, default=None, help="Single category to run (default: all in SAMPLE_CATEGORIES)")
    args = p.parse_args()

    categories = SAMPLE_CATEGORIES
    if args.category:
        if args.category not in categories:
            print("Unknown category. Choose from:", list(categories.keys()))
            return
        categories = {args.category: categories[args.category]}

    print(f"=== Categories: {list(categories.keys())} (min_likes={args.min_likes}, min_retweets={args.min_retweets}) ===")
    tweets = discover_by_categories(
        categories,
        tweets_per_category=args.per_category,
        min_likes=args.min_likes,
        min_retweets=args.min_retweets,
    )
    print(f"Count: {len(tweets)}")
    for i, t in enumerate(tweets[:8]):
        author = t.get("author_username") or "unknown"
        print(f"  {i+1}. id={t.get('tweet_id')} @{author} likes={t.get('likes')} RTs={t.get('retweets')} [{t.get('matched_category')}]")
        text = (t.get("text") or "")[:75]
        print(f"      {text}..." if len((t.get("text") or "")) > 75 else f"      {text}")
    if len(tweets) > 8:
        print(f"  ... and {len(tweets) - 8} more")


if __name__ == "__main__":
    main()
