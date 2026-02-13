from atg_engine.db.session import SessionLocal
from atg_engine.models import TweetCandidate
from datetime import datetime, timedelta

db = SessionLocal()
try:
    # Get tweets from last hour
    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
    tweets = (
        db.query(TweetCandidate)
        .filter(TweetCandidate.created_at >= one_hour_ago)
        .order_by(TweetCandidate.created_at.desc())
        .all()
    )
    
    print(f"\nFound {len(tweets)} tweets from the last hour:\n")
    for i, t in enumerate(tweets, 1):
        score = f"{t.quality_score:.1f}" if t.quality_score else "N/A"
        status = "PUBLISHED" if t.published else "UNPUBLISHED"
        text_preview = t.text[:100] + "..." if len(t.text) > 100 else t.text
        thread_info = f" [Thread seq:{t.thread_sequence}]" if t.thread_sequence is not None else ""
        print(f"{i}. [{status}] [Score: {score}]{thread_info} {text_preview}")
finally:
    db.close()
