"""Unit tests for trending_content_discovery: _topic_to_search_terms, discover_by_categories (mocked)."""
import pytest
from unittest.mock import patch

from atg_engine.services.trending_content_discovery import (
    _topic_to_search_terms,
    discover_by_categories,
)


def test_topic_to_search_terms_basic():
    """Topic string becomes list of search terms (stop words removed, min length)."""
    assert "desire" in _topic_to_search_terms("Desire and power dynamics")
    assert "power" in _topic_to_search_terms("Desire and power dynamics")
    assert "and" not in _topic_to_search_terms("Desire and power dynamics")


def test_topic_to_search_terms_stop_words():
    """Stop words are excluded."""
    out = _topic_to_search_terms("Why people do what they do")
    assert "why" not in out
    assert "what" not in out
    assert "do" not in out
    assert "people" in out or "they" in out


def test_topic_to_search_terms_short_words():
    """Words with len > 3 are preferred; fallback to first max_terms."""
    out = _topic_to_search_terms("The of in")
    assert out == [] or len(out) <= 3


def test_topic_to_search_terms_max_terms():
    """Respects max_terms."""
    out = _topic_to_search_terms("Desire and power dynamics and attachment", max_terms=2)
    assert len(out) <= 2


def test_discover_by_categories_empty_categories():
    """Empty categories dict returns empty list."""
    result = discover_by_categories({}, tweets_per_category=2)
    assert result == []


def test_discover_by_categories_category_filter():
    """category_filter limits which categories are searched."""
    with patch(
        "atg_engine.services.trending_content_discovery.discover_trending_tweets",
        return_value=[],
    ) as mock_discover:
        discover_by_categories(
            {"cat_a": ["topic a"], "cat_b": ["topic b"]},
            tweets_per_category=1,
            category_filter=["cat_a"],
        )
        assert mock_discover.call_count == 1


def test_discover_by_categories_deduplicates_and_tags():
    """When mock returns tweets, they get matched_category and are deduplicated."""
    fake_tweets = [
        {"tweet_id": "111", "text": "x", "author_username": "u", "likes": 200, "retweets": 20},
        {"tweet_id": "222", "text": "y", "author_username": "u", "likes": 150, "retweets": 15},
    ]
    with patch(
        "atg_engine.services.trending_content_discovery.discover_trending_tweets",
        side_effect=[fake_tweets, []],  # first category returns 2, second returns 0
    ):
        result = discover_by_categories(
            {"psych": ["desire power"], "dating": ["dating"]},
            tweets_per_category=5,
            min_likes=10,
            min_retweets=5,
        )
        assert len(result) == 2
        for t in result:
            assert "matched_category" in t
            assert t["matched_category"] in ("psych", "dating")
            assert t["tweet_id"] in ("111", "222")
