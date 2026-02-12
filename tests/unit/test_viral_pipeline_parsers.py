"""Unit tests for viral_spin_and_quote_pipeline parsers."""
import pytest

from atg_engine.pipelines.viral_spin_and_quote_pipeline import (
    _parse_breakdowns,
    _parse_spins,
    _parse_quote_recommendations,
    _parse_approved_refs,
)


def test_parse_breakdowns_single():
    raw = (
        "TWEET_ID: 12345\n"
        "MATCHED_CATEGORIES: psychological_observations, dating_and_desire\n"
        "FORMULA: uncomfortable_truth\n"
        "STRUCTURE: Hook then payoff.\n"
        "WHY_IT_WORKS: Relatable tension.\n"
    )
    out = _parse_breakdowns(raw)
    assert len(out) == 1
    assert out[0]["tweet_id"] == "12345"
    assert "psychological" in out[0]["matched_categories"]
    assert out[0]["formula"] == "uncomfortable_truth"
    assert "Hook" in out[0]["structure"]
    assert "Relatable" in out[0]["why_it_works"]


def test_parse_breakdowns_multiple():
    raw = (
        "TWEET_ID: 111\n"
        "MATCHED_CATEGORIES: cat_a\n"
        "FORMULA: formula_a\n"
        "STRUCTURE: s1\n"
        "WHY_IT_WORKS: w1\n\n"
        "TWEET_ID: 222\n"
        "MATCHED_CATEGORIES: cat_b\n"
        "FORMULA: formula_b\n"
        "STRUCTURE: s2\n"
        "WHY_IT_WORKS: w2\n"
    )
    out = _parse_breakdowns(raw)
    assert len(out) == 2
    assert out[0]["tweet_id"] == "111"
    assert out[1]["tweet_id"] == "222"
    assert out[1]["formula"] == "formula_b"


def test_parse_breakdowns_empty():
    assert _parse_breakdowns("") == []
    assert _parse_breakdowns("No TWEET_ID here") == []


def test_parse_spins_single():
    raw = (
        "TWEET_ID: 999\n"
        "SPIN_1: My original take on this in under 280 chars.\n"
        "FORMULA_USED: philosophy_meets_life\n"
    )
    out = _parse_spins(raw)
    assert len(out) == 1
    assert out[0]["tweet_id"] == "999"
    assert "My original take" in out[0]["spin_1"]
    assert out[0]["formula_used"] == "philosophy_meets_life"
    assert out[0]["spin_2"] is None


def test_parse_spins_with_optional_spin_2():
    raw = (
        "TWEET_ID: 888\n"
        "SPIN_1: First variant.\n"
        "SPIN_2: Second variant.\n"
        "FORMULA_USED: desire_game_theory\n"
    )
    out = _parse_spins(raw)
    assert len(out) == 1
    assert out[0]["spin_1"] == "First variant."
    assert out[0]["spin_2"] == "Second variant."


def test_parse_spins_empty():
    assert _parse_spins("") == []
    assert _parse_spins("TWEET_ID: 1\nNo SPIN_1") == []


def test_parse_quote_recommendations_single():
    raw = (
        "TWEET_ID: 555\n"
        "QUOTE_TEXT: This is my quote commentary.\n"
        "REASON: Adds perspective.\n"
    )
    out = _parse_quote_recommendations(raw)
    assert len(out) == 1
    assert out[0]["tweet_id"] == "555"
    assert out[0]["quote_text"] == "This is my quote commentary."
    assert "perspective" in out[0]["reason"]


def test_parse_quote_recommendations_multiple():
    raw = (
        "TWEET_ID: 1\nQUOTE_TEXT: Quote one.\nREASON: R1\n\n"
        "TWEET_ID: 2\nQUOTE_TEXT: Quote two.\nREASON: R2\n"
    )
    out = _parse_quote_recommendations(raw)
    assert len(out) == 2
    assert out[0]["quote_text"] == "Quote one."
    assert out[1]["tweet_id"] == "2"


def test_parse_approved_refs():
    raw = (
        "CONTENT_REF: 1\nAPPROVED: true\nREASON: ok\n"
        "CONTENT_REF: 2\nAPPROVED: false\nREASON: no\n"
        "CONTENT_REF: 3\nAPPROVED: true\nREASON: yes\n"
    )
    out = _parse_approved_refs(raw)
    assert out == {1, 3}


def test_parse_approved_refs_empty():
    assert _parse_approved_refs("") == set()
    assert _parse_approved_refs("CONTENT_REF: 1 APPROVED: false") == set()
