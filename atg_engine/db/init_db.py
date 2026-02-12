"""Create all tables (MVP). Run via: python -m atg_engine db init."""
import logging

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

logger = logging.getLogger(__name__)


def _add_missing_tweet_candidate_columns():
    """Add thread_id, thread_sequence, and quote_tweet_id to tweet_candidates if missing (existing DBs)."""
    insp = inspect(engine)
    if "tweet_candidates" not in insp.get_table_names():
        return
    existing = [c["name"] for c in insp.get_columns("tweet_candidates")]
    with engine.connect() as conn:
        if "thread_id" not in existing:
            try:
                conn.execute(text("ALTER TABLE tweet_candidates ADD COLUMN thread_id VARCHAR(64)"))
                conn.commit()
            except Exception as e:
                logger.warning("Could not add thread_id to tweet_candidates: %s", e)
        if "thread_sequence" not in existing:
            try:
                conn.execute(text("ALTER TABLE tweet_candidates ADD COLUMN thread_sequence INTEGER"))
                conn.commit()
            except Exception as e:
                logger.warning("Could not add thread_sequence to tweet_candidates: %s", e)
        if "quote_tweet_id" not in existing:
            try:
                conn.execute(text("ALTER TABLE tweet_candidates ADD COLUMN quote_tweet_id VARCHAR(64)"))
                conn.commit()
            except Exception as e:
                logger.warning("Could not add quote_tweet_id to tweet_candidates: %s", e)
        try:
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_tweet_candidates_quote_tweet_id ON tweet_candidates (quote_tweet_id)"))
            conn.commit()
        except Exception as e:
            logger.warning("Could not create index on quote_tweet_id: %s", e)


def _add_missing_persona_extended_column():
    """Add persona_extended to personas if missing (existing DBs)."""
    insp = inspect(engine)
    if "personas" not in insp.get_table_names():
        return
    existing = [c["name"] for c in insp.get_columns("personas")]
    if "persona_extended" not in existing:
        with engine.connect() as conn:
            try:
                conn.execute(text("ALTER TABLE personas ADD COLUMN persona_extended TEXT"))
                conn.commit()
            except Exception as e:
                logger.warning("Could not add persona_extended to personas: %s", e)


def init_db():
    """Create all tables and run migrations. Raises on DB/schema failure after logging."""
    try:
        Base.metadata.create_all(bind=engine)
        _add_missing_tweet_candidate_columns()
        _add_missing_persona_extended_column()
    except Exception as e:
        logger.warning("DB init failed: %s", e, exc_info=True)
        raise
