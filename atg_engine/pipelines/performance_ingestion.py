"""Performance ingestion pipeline: pull tweet metrics via read provider, update TweetPerformance; poll account follower count."""
from atg_engine.config.env_validation import validate_env
from atg_engine.config.settings import PERFORMANCE_INGESTION_MAX_TWEETS
from atg_engine.db.session import SessionLocal
from atg_engine.models import AccountSnapshot, TweetPerformance
from atg_engine.services import scoring
from atg_engine.services.twitter_read_provider import get_read_provider

_DEFAULT_METRICS = {"impressions": 0, "likes": 0, "retweets": 0, "replies": 0}


def run(**kwargs) -> str:
    validate_env(require_llm=False, require_twitter=True)
    db = SessionLocal()
    try:
        limit = PERFORMANCE_INGESTION_MAX_TWEETS
        perf_list = db.query(TweetPerformance).limit(limit).all()
        provider = get_read_provider()
        tweet_ids = [p.tweet_id for p in perf_list]
        metrics_map = provider.get_tweet_metrics_batch(tweet_ids) if tweet_ids else {}
        updated = 0
        for p in perf_list:
            metrics = metrics_map.get(p.tweet_id, _DEFAULT_METRICS)
            p.impressions = metrics.get("impressions", 0)
            p.likes = metrics.get("likes", 0)
            p.retweets = metrics.get("retweets", 0)
            p.replies = metrics.get("replies", 0)
            p.engagement_rate = scoring.engagement_rate(
                p.impressions, p.likes, p.retweets, p.replies
            )
            updated += 1
        follower_count = provider.get_me_follower_count()
        if follower_count is not None:
            prev = db.query(AccountSnapshot).order_by(AccountSnapshot.recorded_at.desc()).first()
            db.add(AccountSnapshot(follower_count=follower_count))
        db.commit()
        msg = f"Updated {updated} TweetPerformance records."
        if follower_count is not None:
            delta = follower_count - (prev.follower_count if prev else follower_count)
            msg += f" Follower count: {follower_count} (delta: {delta:+d})."
        return msg
    finally:
        db.close()
