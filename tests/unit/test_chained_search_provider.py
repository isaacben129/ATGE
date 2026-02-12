"""Unit tests for ChainedTwitterSearchProvider: primary success, primary failure -> fallback."""
import pytest
from unittest.mock import MagicMock

from atg_engine.services.twitter_search_provider import (
    ChainedTwitterSearchProvider,
    OfficialTwitterSearchProvider,
    FreeTwitterSearchProvider,
    _search_provider_by_name,
    get_search_provider,
)


def test_chained_search_primary_success_no_fallback():
    """When primary returns results, fallback is not called."""
    primary = MagicMock()
    primary.search_recent_tweets.return_value = [
        {"tweet_id": "1", "text": "hi", "author_username": "u", "likes": 100, "retweets": 10, "created_at": None},
    ]
    fallback = MagicMock()
    chain = ChainedTwitterSearchProvider(primary, fallback)

    out = chain.search_recent_tweets(query="test", max_results=10)
    assert len(out) == 1
    assert out[0]["tweet_id"] == "1"
    assert primary.search_recent_tweets.call_count == 1
    fallback.search_recent_tweets.assert_not_called()


def test_chained_search_primary_not_implemented_uses_fallback():
    """When primary raises NotImplementedError (e.g. Free stub), fallback is used."""
    primary = FreeTwitterSearchProvider()
    fallback = MagicMock()
    fallback.search_recent_tweets.return_value = [
        {"tweet_id": "2", "text": "fallback", "author_username": "u2", "likes": 50, "retweets": 5, "created_at": None},
    ]

    chain = ChainedTwitterSearchProvider(primary, fallback)
    out = chain.search_recent_tweets(query="x", max_results=5)
    assert len(out) == 1
    assert out[0]["tweet_id"] == "2"
    fallback.search_recent_tweets.assert_called_once_with(query="x", max_results=5, min_likes=100, min_retweets=10)


def test_chained_search_primary_429_uses_fallback():
    """When primary raises with status 429, fallback is used."""
    primary = MagicMock()
    err = Exception("Rate limited")
    err.response = MagicMock(status_code=429)
    primary.search_recent_tweets.side_effect = err

    fallback = MagicMock()
    fallback.search_recent_tweets.return_value = []

    chain = ChainedTwitterSearchProvider(primary, fallback)
    out = chain.search_recent_tweets(query="q", max_results=10, min_likes=50, min_retweets=5)
    assert out == []
    fallback.search_recent_tweets.assert_called_once_with(query="q", max_results=10, min_likes=50, min_retweets=5)


def test_chained_search_primary_non_retryable_raises():
    """When primary raises a non-retryable error, we do not call fallback."""
    primary = MagicMock()
    primary.search_recent_tweets.side_effect = ValueError("invalid query")

    fallback = MagicMock()
    chain = ChainedTwitterSearchProvider(primary, fallback)

    with pytest.raises(ValueError, match="invalid query"):
        chain.search_recent_tweets(query="x")
    fallback.search_recent_tweets.assert_not_called()


def test_search_provider_by_name():
    """_search_provider_by_name returns correct provider type."""
    assert isinstance(_search_provider_by_name("official"), OfficialTwitterSearchProvider)
    assert isinstance(_search_provider_by_name("free"), FreeTwitterSearchProvider)
    assert isinstance(_search_provider_by_name(""), OfficialTwitterSearchProvider)


def test_get_search_provider_returns_chain_when_primary_differs_from_fallback(monkeypatch):
    """get_search_provider returns ChainedTwitterSearchProvider when primary != fallback."""
    monkeypatch.setattr("atg_engine.config.settings.TWITTER_SEARCH_PRIMARY", "free")
    monkeypatch.setattr("atg_engine.config.settings.TWITTER_SEARCH_FALLBACK", "official")
    provider = get_search_provider()
    assert isinstance(provider, ChainedTwitterSearchProvider)


def test_get_search_provider_returns_single_when_primary_equals_fallback(monkeypatch):
    """get_search_provider returns single provider when primary == fallback (no chain)."""
    monkeypatch.setattr("atg_engine.config.settings.TWITTER_SEARCH_PRIMARY", "official")
    monkeypatch.setattr("atg_engine.config.settings.TWITTER_SEARCH_FALLBACK", "official")
    provider = get_search_provider()
    assert isinstance(provider, OfficialTwitterSearchProvider)
