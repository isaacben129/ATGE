"""Create all tables (MVP). Run via: python -m atg_engine db init."""
from sqlalchemy import inspect, text

from atg_engine.db.session import Base, engine
from atg_engine.models import (
    Persona,
    VoiceGenome,
    TweetCandidate,
    TweetPerformance,
    StrategyState,
    MutationLog,
    AccountSnapshot,
)


def _add_missing_tweet_candidate_columns():
    """Add thread_id, thread_sequence, and quote_tweet_id to tweet_candidates if missing (existing DBs)."""
    insp = inspect(engine)
    if "tweet_candidates" not in insp.get_table_names():
        return
    existing = [c["name"] for c in insp.get_columns("tweet_candidates")]
    with engine.connect() as conn:
        if "thread_id" not in existing:
            conn.execute(text("ALTER TABLE tweet_candidates ADD COLUMN thread_id VARCHAR(64)"))
        if "thread_sequence" not in existing:
            conn.execute(text("ALTER TABLE tweet_candidates ADD COLUMN thread_sequence INTEGER"))
        if "quote_tweet_id" not in existing:
            conn.execute(text("ALTER TABLE tweet_candidates ADD COLUMN quote_tweet_id VARCHAR(64)"))
        conn.commit()


def init_db():
    Base.metadata.create_all(bind=engine)
    _add_missing_tweet_candidate_columns()
