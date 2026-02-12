"""Smoke tests for viral_spin_and_quote_pipeline: imports, context fetch, early exit when no tweets."""
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture(autouse=True)
def _init_db():
    from atg_engine.db.init_db import init_db
    from atg_engine.db.session import SessionLocal
    from atg_engine.models import Persona
    init_db()
    db = SessionLocal()
    try:
        p = db.query(Persona).first()
        if not p:
            p = Persona(name="", handle="", niche="")
            db.add(p)
        p.name = "Vera"
        p.handle = "vera"
        p.niche = "Psychology"
        p.persona_extended = '{"content_categories":{"psych":["desire"]},"tweet_formulas":{"f1":{"structure":"x"}}}'
        db.commit()
    finally:
        db.close()
    yield


def test_viral_pipeline_imports():
    """Pipeline and helpers import without error."""
    from atg_engine.pipelines.viral_spin_and_quote_pipeline import (
        run,
        _fetch_persona_and_viral_context,
        _parse_breakdowns,
        _parse_spins,
        _parse_quote_recommendations,
        _parse_approved_refs,
    )
    assert callable(run)
    assert callable(_fetch_persona_and_viral_context)


def test_fetch_persona_and_viral_context():
    """Fetch returns persona, curation ctx, writer ctx, and viral dict with categories/formulas."""
    from atg_engine.pipelines.viral_spin_and_quote_pipeline import _fetch_persona_and_viral_context
    persona, curation_ctx, writer_ctx, viral = _fetch_persona_and_viral_context()
    assert persona is not None
    assert "No persona" not in curation_ctx or "psych" in str(viral)
    assert "content_categories" in viral
    assert "tweet_formulas" in viral
    assert "psych" in viral.get("content_categories", {})


def test_run_returns_early_when_no_tweets():
    """When discovery returns no tweets, run returns without calling LLM (mocked discovery)."""
    from atg_engine.pipelines.viral_spin_and_quote_pipeline import run
    with patch("atg_engine.pipelines.viral_spin_and_quote_pipeline.validate_env"):
        with patch("atg_engine.pipelines.viral_spin_and_quote_pipeline.ensure_bootstrap"):
            with patch(
                "atg_engine.pipelines.viral_spin_and_quote_pipeline.discover_by_categories",
                return_value=[],
            ):
                with patch(
                    "atg_engine.pipelines.viral_spin_and_quote_pipeline.discover_trending_tweets",
                    return_value=[],
                ):
                    result = run(
                        mode="both",
                        categories=None,
                        tweets_per_category=2,
                        min_likes=100,
                        min_retweets=10,
                        dry_run=True,
                        verbose=False,
                    )
                    assert "No viral tweets" in result or "No trending" in result
