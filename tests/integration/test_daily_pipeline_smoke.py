"""Smoke test: daily_generation pipeline with mocked DB (no real LLM/Twitter)."""
import pytest


@pytest.fixture(autouse=True)
def _init_db():
    from atg_engine.db.init_db import init_db
    from atg_engine.db.session import SessionLocal
    from atg_engine.models import VoiceGenome, StrategyState
    init_db()
    db = SessionLocal()
    try:
        g = VoiceGenome(
            tone_traits='["direct"]',
            language_patterns="[]",
            taboo_topics="[]",
            risk_tolerance=0.5,
            aggressiveness=0.5,
            humor_level=0.5,
            controversy_level=0.5,
        )
        db.add(g)
        s = StrategyState(wig="Follower growth", daily_post_target=3, thread_ratio=0.2, experimentation_rate=0.25)
        db.add(s)
        db.commit()
    finally:
        db.close()
    yield
    # Teardown not required for in-memory DB


def test_daily_pipeline_imports_and_context_fetch():
    """Verify pipeline can be imported and context fetch runs without error."""
    from atg_engine.pipelines.daily_generation import _fetch_context
    genome_json, strategy_json, persona = _fetch_context()
    assert isinstance(genome_json, str)
    assert isinstance(strategy_json, str)
    assert persona is None or hasattr(persona, "get_prompt_context")
    if persona:
        assert isinstance(persona.get_prompt_context("writer"), str)
        assert isinstance(persona.get_prompt_context("full"), str)


def test_save_approved_only():
    """Verify only approved items are saved to DB."""
    from atg_engine.pipelines.daily_generation import _save_approved_only
    from atg_engine.db.session import SessionLocal
    from atg_engine.models import TweetCandidate
    _save_approved_only([
        {"text": "Approved tweet one", "approved": True},
        {"text": "Rejected tweet", "approved": False},
        {"text": "Approved tweet two", "approved": True},
    ])
    db = SessionLocal()
    try:
        count = db.query(TweetCandidate).filter(TweetCandidate.approved == True).count()
        assert count == 2
    finally:
        db.close()
