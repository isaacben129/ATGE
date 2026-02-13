from atg_engine.db.session import SessionLocal
from atg_engine.models import TweetCandidate

db = SessionLocal()
try:
    # Query newest first by id (highest id = last generated)
    # We want to show newest tweets first, but in generation order within the batch
    # So we query desc, then reverse to get generation order for the newest batch
    tweets = (
        db.query(TweetCandidate)
        .filter(TweetCandidate.approved == True)
        .order_by(TweetCandidate.id.desc())
        .limit(20)
        .all()
    )
    # Reverse to show in generation order (first generated in batch appears first)
    # This matches the terminal output order for the most recent generation
    tweets = list(reversed(tweets))
    
    print(f"\nFound {len(tweets)} approved tweets (all time):\n")
    for i, t in enumerate(tweets, 1):
        score = f"{t.quality_score:.1f}" if t.quality_score else "N/A"
        status = "PUBLISHED" if t.published else "UNPUBLISHED"
        text_preview = t.text[:120] + "..." if len(t.text) > 120 else t.text
        thread_info = f" [Thread seq:{t.thread_sequence}]" if t.thread_sequence is not None else ""
        print(f"{i}. [{status}] [Score: {score}]{thread_info} {text_preview}")
        print(f"   Created: {t.created_at}")
finally:
    db.close()
