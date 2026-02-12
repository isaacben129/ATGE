"""Unit tests for Persona.get_viral_content_context and curation context with categories/formulas."""
import json
import pytest

from atg_engine.models.persona import Persona


def test_get_viral_content_context_empty():
    """Persona with no persona_extended returns empty categories and formulas."""
    p = Persona(name="Test", persona_extended=None)
    out = p.get_viral_content_context()
    assert out["content_categories"] == {}
    assert out["tweet_formulas"] == {}


def test_get_viral_content_context_with_extended():
    """Persona with persona_extended containing content_categories and tweet_formulas returns them."""
    extended = {
        "content_categories": {
            "psychological_observations": ["Desire and power", "Self-deception"],
            "dating_and_desire": ["Modern dating"],
        },
        "tweet_formulas": {
            "uncomfortable_truth": {"structure": "Say the quiet part", "example": "You don't miss me."},
        },
    }
    p = Persona(name="Test", persona_extended=json.dumps(extended))
    out = p.get_viral_content_context()
    assert "psychological_observations" in out["content_categories"]
    assert len(out["content_categories"]["psychological_observations"]) == 2
    assert "uncomfortable_truth" in out["tweet_formulas"]
    assert out["tweet_formulas"]["uncomfortable_truth"]["structure"] == "Say the quiet part"


def test_get_viral_content_context_partial():
    """Only content_categories or only tweet_formulas is fine."""
    p = Persona(persona_extended=json.dumps({"content_categories": {"a": ["b"]}}))
    out = p.get_viral_content_context()
    assert out["content_categories"] == {"a": ["b"]}
    assert out["tweet_formulas"] == {}

    p2 = Persona(persona_extended=json.dumps({"tweet_formulas": {"f": {"structure": "x"}}}))
    out2 = p2.get_viral_content_context()
    assert out2["tweet_formulas"] == {"f": {"structure": "x"}}
    assert out2["content_categories"] == {}


def test_get_prompt_context_curation_includes_categories_when_present():
    """Curation context includes category and formula hints when in extended."""
    extended = {
        "basic_info": {"actual_niche": "Psychology"},
        "retweet_commentary_style": {"approach": "Add edge"},
        "content_categories": {"cat1": ["t1"]},
        "tweet_formulas": {"f1": {"structure": "hook + payoff"}},
    }
    p = Persona(persona_extended=json.dumps(extended))
    ctx = p.get_prompt_context("curation")
    assert "cat1" in ctx
    assert "f1" in ctx or "hook" in ctx
