from atg_engine.db.session import SessionLocal
from atg_engine.models import TweetCandidate

db = SessionLocal()
try:
    tweets = (
        db.query(TweetCandidate)
        .filter(TweetCandidate.approved == True, TweetCandidate.published == False)
        .order_by(TweetCandidate.created_at.desc())
        .limit(10)
        .all()
    )
    
    print(f"\nFound {len(tweets)} approved unpublished tweets:\n")
    for i, t in enumerate(tweets, 1):
        score = f"{t.quality_score:.1f}" if t.quality_score else "N/A"
        text_preview = t.text[:120] + "..." if len(t.text) > 120 else t.text
        thread_info = f" [Thread {t.thread_sequence}]" if t.thread_sequence is not None else ""
        print(f"{i}. [Score: {score}]{thread_info} {text_preview}")
finally:
    db.close()
