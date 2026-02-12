"""
End-to-end viral pipeline test with mocked Twitter discovery.
Use when TWITTER_BEARER_TOKEN is missing or search returns no results.
Requires: GROQ_API_KEY in .env (LLM for breakdown, spin, quote, gatekeeper).
"""
import os
import sys

# Ensure project root on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock discovery to return 2 fake viral tweets so the rest of the pipeline runs
FAKE_TWEETS = [
    {
        "tweet_id": "999001",
        "text": "Men confuse my silence for mystery. It's just disinterest with better packaging.",
        "author_username": "someone",
        "likes": 500,
        "retweets": 80,
        "matched_category": "psychological_observations",
    },
    {
        "tweet_id": "999002",
        "text": "You don't miss me. You miss how I made you feel about yourself.",
        "author_username": "other",
        "likes": 1200,
        "retweets": 200,
        "matched_category": "self_awareness_and_contradictions",
    },
]


def main():
    from unittest.mock import patch
    from atg_engine.pipelines.viral_spin_and_quote_pipeline import run as viral_run
    from atg_engine.pipelines.publishing import run as publish_run

    print("=== E2E Viral Pipeline (mocked discovery) ===\n")

    with patch("atg_engine.pipelines.viral_spin_and_quote_pipeline.validate_env"):  # skip Twitter check when discovery is mocked
        with patch("atg_engine.pipelines.viral_spin_and_quote_pipeline.discover_by_categories", return_value=FAKE_TWEETS):
            with patch("atg_engine.pipelines.viral_spin_and_quote_pipeline.discover_trending_tweets", return_value=FAKE_TWEETS):
                result = viral_run(
                    mode="both",
                    categories=None,
                    tweets_per_category=2,
                    min_likes=0,
                    min_retweets=0,
                    dry_run=False,
                    verbose=True,
                )
                print("\nViral pipeline result:", result)

    print("\n=== Publish preview (dry-run, limit 2) ===\n")
    publish_result = publish_run(limit=2, dry_run=True)
    print(publish_result)
    print("\nDone.")


if __name__ == "__main__":
    main()
