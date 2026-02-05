"""Unit tests for services/scoring.py."""
import pytest
from atg_engine.services.scoring import engagement_rate, followers_gained_delta


def test_engagement_rate_zero_impressions():
    assert engagement_rate(0, 10, 5, 2) == 0.0


def test_engagement_rate_positive():
    # (likes + retweets + replies) / impressions = 17/100
    assert engagement_rate(100, 10, 5, 2) == 0.17


def test_followers_gained_delta_empty():
    assert followers_gained_delta([]) == 0


def test_followers_gained_delta_sum():
    perf = [{"followers_gained": 5}, {"followers_gained": 3}, {"followers_gained": 0}]
    assert followers_gained_delta(perf) == 8
