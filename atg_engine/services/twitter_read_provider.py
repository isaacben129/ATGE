"""
Twitter read-provider abstraction: metrics and follower count.
Posting stays in twitter_api; only read operations go through a provider
so we can swap to a free-tier alternative (e.g. Xpoz) when available.
"""
from typing import Any, Protocol


class TwitterReadProvider(Protocol):
    """Interface for tweet metrics and follower count (read-only)."""

    def get_tweet_metrics_batch(self, tweet_ids: list[str]) -> dict[str, dict[str, Any]]:
        """Return dict mapping tweet_id -> {impressions, likes, retweets, replies}."""
        ...

    def get_me_follower_count(self) -> int | None:
        """Return authenticated user's follower count or None."""
        ...


class OfficialTwitterReadProvider:
    """Uses official X API with batched tweet lookup (free-tier friendly)."""

    def get_tweet_metrics_batch(self, tweet_ids: list[str]) -> dict[str, dict[str, Any]]:
        from atg_engine.services import twitter_api
        return twitter_api.get_tweet_metrics_batch(tweet_ids)

    def get_me_follower_count(self) -> int | None:
        from atg_engine.services import twitter_api
        return twitter_api.get_me_follower_count()


class XpozReadProvider:
    """
    Placeholder for Xpoz (free 100K results/month).
    When Xpoz exposes a REST API or SDK callable from Python, implement
    get_tweet_metrics_batch and get_me_follower_count here and set
    TWITTER_READ_PROVIDER=xpoz. Until then, raises NotImplementedError.
    """
    def get_tweet_metrics_batch(self, tweet_ids: list[str]) -> dict[str, dict[str, Any]]:
        raise NotImplementedError(
            "Xpoz read provider not implemented yet. "
            "When Xpoz offers a callable REST API, implement it here and set TWITTER_READ_PROVIDER=xpoz."
        )

    def get_me_follower_count(self) -> int | None:
        raise NotImplementedError(
            "Xpoz read provider not implemented yet. "
            "When Xpoz offers a callable REST API, implement it here and set TWITTER_READ_PROVIDER=xpoz."
        )


def get_read_provider() -> TwitterReadProvider:
    """Return the configured read provider (official, xpoz, etc.)."""
    from atg_engine.config.settings import TWITTER_READ_PROVIDER
    if TWITTER_READ_PROVIDER == "xpoz":
        return XpozReadProvider()
    return OfficialTwitterReadProvider()
