"""Unit tests for XpozReadProvider: no key -> NotImplementedError; with key and mocked client -> returns data."""
import pytest
from unittest.mock import patch

from atg_engine.services.twitter_read_provider import XpozReadProvider


def test_validate_env_requires_xpoz_api_key_when_primary_is_xpoz(monkeypatch):
    """When TWITTER_READ_PRIMARY=xpoz and require_twitter True, validate_env requires XPOZ_API_KEY."""
    import atg_engine.config.env_validation as env_validation
    monkeypatch.setattr(env_validation, "TWITTER_READ_PRIMARY", "xpoz")
    monkeypatch.setattr(env_validation, "XPOZ_API_KEY", "")
    monkeypatch.setattr(env_validation, "TWITTER_API_KEY", "k")
    monkeypatch.setattr(env_validation, "TWITTER_API_SECRET", "s")
    monkeypatch.setattr(env_validation, "TWITTER_ACCESS_TOKEN", "t")
    monkeypatch.setattr(env_validation, "TWITTER_ACCESS_SECRET", "ts")
    monkeypatch.setattr(env_validation, "TWITTER_BEARER_TOKEN", "b")
    with pytest.raises(ValueError, match="XPOZ_API_KEY"):
        env_validation.validate_env(require_llm=False, require_twitter=True)


def test_xpoz_read_provider_no_api_key_raises_not_implemented(monkeypatch):
    """When XPOZ_API_KEY is missing, get_tweet_metrics_batch and get_me_follower_count raise NotImplementedError."""
    monkeypatch.setattr("atg_engine.config.settings.XPOZ_API_KEY", "")
    provider = XpozReadProvider()
    with pytest.raises(NotImplementedError, match="XPOZ_API_KEY"):
        provider.get_tweet_metrics_batch(["tid1"])
    with pytest.raises(NotImplementedError, match="XPOZ_API_KEY"):
        provider.get_me_follower_count()


def test_xpoz_read_provider_with_key_calls_xpoz_client_metrics(monkeypatch):
    """When XPOZ_API_KEY is set, get_tweet_metrics_batch delegates to xpoz_client and returns result."""
    monkeypatch.setattr("atg_engine.config.settings.XPOZ_API_KEY", "fake-key")
    fake_metrics = {"tid1": {"impressions": 100, "likes": 5, "retweets": 1, "replies": 0}}
    with patch("atg_engine.services.xpoz_client.get_tweet_metrics_batch", return_value=fake_metrics):
        provider = XpozReadProvider()
        out = provider.get_tweet_metrics_batch(["tid1"])
    assert out == fake_metrics


def test_xpoz_read_provider_with_key_no_username_returns_none(monkeypatch):
    """When XPOZ_TWITTER_USERNAME is not set, get_me_follower_count returns None (no exception)."""
    monkeypatch.setattr("atg_engine.config.settings.XPOZ_API_KEY", "fake-key")
    monkeypatch.setattr("atg_engine.config.settings.XPOZ_TWITTER_USERNAME", "")
    provider = XpozReadProvider()
    assert provider.get_me_follower_count() is None


def test_xpoz_read_provider_with_username_calls_xpoz_client_follower_count(monkeypatch):
    """When XPOZ_TWITTER_USERNAME is set, get_me_follower_count delegates to xpoz_client."""
    monkeypatch.setattr("atg_engine.config.settings.XPOZ_API_KEY", "fake-key")
    monkeypatch.setattr("atg_engine.config.settings.XPOZ_TWITTER_USERNAME", "myhandle")
    with patch("atg_engine.services.xpoz_client.get_user_follower_count", return_value=1234) as mock_fn:
        provider = XpozReadProvider()
        out = provider.get_me_follower_count()
    assert out == 1234
    mock_fn.assert_called_once_with("myhandle")
