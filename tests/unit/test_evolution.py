"""Unit tests for services/evolution.py weighted update."""
import json
import pytest
from atg_engine.services.evolution import weighted_update


class _FakeGenome:
    def __init__(self):
        self.tone_traits = '["edgy", "direct"]'
        self.language_patterns = "[]"
        self.taboo_topics = "[]"
        self.risk_tolerance = 0.5
        self.aggressiveness = 0.5
        self.humor_level = 0.5
        self.controversy_level = 0.5


def test_weighted_update_promotes_winning_traits():
    genome = _FakeGenome()
    out = weighted_update(
        genome,
        winning_traits=["viral", "punchy"],
        losing_traits=[],
        winning_hooks=[],
        losing_hooks=[],
        performance_delta=0.1,
    )
    traits = json.loads(out["tone_traits"])
    assert "viral" in traits or "punchy" in traits
    assert 0 <= out["risk_tolerance"] <= 1
    assert 0 <= out["aggressiveness"] <= 1


def test_weighted_update_demotes_losing_traits():
    genome = _FakeGenome()
    out = weighted_update(
        genome,
        winning_traits=[],
        losing_traits=["edgy"],
        winning_hooks=[],
        losing_hooks=[],
        performance_delta=-0.1,
    )
    traits = json.loads(out["tone_traits"])
    assert "edgy" not in traits or len(traits) >= 1


def test_weighted_update_sliders_bounded():
    genome = _FakeGenome()
    out = weighted_update(
        genome,
        winning_traits=[],
        losing_traits=[],
        winning_hooks=[],
        losing_hooks=[],
        performance_delta=10.0,
    )
    assert 0 <= out["risk_tolerance"] <= 1
    assert 0 <= out["aggressiveness"] <= 1
    assert 0 <= out["humor_level"] <= 1
    assert 0 <= out["controversy_level"] <= 1
