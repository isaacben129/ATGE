"""Unit tests for ChainedTwitterReadProvider: primary success, primary failure -> fallback."""
import pytest
from unittest.mock import MagicMock

from atg_engine.services.twitter_read_provider import (
    ChainedTwitterReadProvider,
    OfficialTwitterReadProvider,
    XpozReadProvider,
    _read_provider_by_name,
    get_read_provider,
)


def test_chained_read_primary_success_metrics_no_fallback():
    """When primary returns metrics, fallback is not called."""
    primary = MagicMock()
    primary.get_tweet_metrics_batch.return_value = {"tid1": {"impressions": 10, "likes": 1, "retweets": 0, "replies": 0}}
    primary.get_me_follower_count.return_value = 100

    fallback = MagicMock()
    chain = ChainedTwitterReadProvider(primary, fallback)

    out = chain.get_tweet_metrics_batch(["tid1"])
    assert out == {"tid1": {"impressions": 10, "likes": 1, "retweets": 0, "replies": 0}}
    assert primary.get_tweet_metrics_batch.call_count == 1
    fallback.get_tweet_metrics_batch.assert_not_called()

    count = chain.get_me_follower_count()
    assert count == 100
    assert primary.get_me_follower_count.call_count == 1
    fallback.get_me_follower_count.assert_not_called()


def test_chained_read_primary_not_implemented_uses_fallback():
    """When primary raises NotImplementedError, fallback is used."""
    primary = XpozReadProvider()
    fallback = MagicMock()
    fallback.get_tweet_metrics_batch.return_value = {"tid1": {"impressions": 0, "likes": 0, "retweets": 0, "replies": 0}}
    fallback.get_me_follower_count.return_value = 42

    chain = ChainedTwitterReadProvider(primary, fallback)

    out = chain.get_tweet_metrics_batch(["tid1"])
    assert out == {"tid1": {"impressions": 0, "likes": 0, "retweets": 0, "replies": 0}}
    assert fallback.get_tweet_metrics_batch.call_count == 1

    count = chain.get_me_follower_count()
    assert count == 42
    assert fallback.get_me_follower_count.call_count == 1


def test_chained_read_primary_429_uses_fallback():
    """When primary raises with status 429, fallback is used."""
    primary = MagicMock()
    err = Exception("Rate limited")
    err.response = MagicMock(status_code=429)
    primary.get_tweet_metrics_batch.side_effect = err

    fallback = MagicMock()
    fallback.get_tweet_metrics_batch.return_value = {"tid1": {"impressions": 1, "likes": 0, "retweets": 0, "replies": 0}}

    chain = ChainedTwitterReadProvider(primary, fallback)
    out = chain.get_tweet_metrics_batch(["tid1"])
    assert out == {"tid1": {"impressions": 1, "likes": 0, "retweets": 0, "replies": 0}}
    fallback.get_tweet_metrics_batch.assert_called_once_with(["tid1"])


def test_chained_read_primary_runtime_error_xpoz_uses_fallback():
    """When primary raises RuntimeError with 'Xpoz', fallback is used."""
    primary = MagicMock()
    primary.get_tweet_metrics_batch.side_effect = RuntimeError("Xpoz tweet metrics failed: 429")

    fallback = MagicMock()
    fallback.get_tweet_metrics_batch.return_value = {"tid1": {"impressions": 0, "likes": 0, "retweets": 0, "replies": 0}}

    chain = ChainedTwitterReadProvider(primary, fallback)
    out = chain.get_tweet_metrics_batch(["tid1"])
    assert out == {"tid1": {"impressions": 0, "likes": 0, "retweets": 0, "replies": 0}}
    fallback.get_tweet_metrics_batch.assert_called_once_with(["tid1"])


def test_chained_read_primary_non_retryable_raises():
    """When primary raises a non-retryable error, we do not call fallback."""
    primary = MagicMock()
    primary.get_tweet_metrics_batch.side_effect = ValueError("bad request")

    fallback = MagicMock()
    chain = ChainedTwitterReadProvider(primary, fallback)

    with pytest.raises(ValueError, match="bad request"):
        chain.get_tweet_metrics_batch(["tid1"])
    fallback.get_tweet_metrics_batch.assert_not_called()


def test_read_provider_by_name():
    """_read_provider_by_name returns correct provider type."""
    assert isinstance(_read_provider_by_name("official"), OfficialTwitterReadProvider)
    assert isinstance(_read_provider_by_name("xpoz"), XpozReadProvider)
    assert isinstance(_read_provider_by_name(""), OfficialTwitterReadProvider)


def test_get_read_provider_returns_chain_when_primary_differs_from_fallback(monkeypatch):
    """get_read_provider returns ChainedTwitterReadProvider when primary != fallback."""
    monkeypatch.setattr("atg_engine.config.settings.TWITTER_READ_PRIMARY", "xpoz")
    monkeypatch.setattr("atg_engine.config.settings.TWITTER_READ_FALLBACK", "official")
    from atg_engine.services.twitter_read_provider import get_read_provider
    provider = get_read_provider()
    assert isinstance(provider, ChainedTwitterReadProvider)


def test_get_read_provider_returns_single_when_primary_equals_fallback(monkeypatch):
    """get_read_provider returns single provider when primary == fallback (no chain)."""
    monkeypatch.setattr("atg_engine.config.settings.TWITTER_READ_PRIMARY", "official")
    monkeypatch.setattr("atg_engine.config.settings.TWITTER_READ_FALLBACK", "official")
    from atg_engine.services.twitter_read_provider import get_read_provider
    provider = get_read_provider()
    assert isinstance(provider, OfficialTwitterReadProvider)
