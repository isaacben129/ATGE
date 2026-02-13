"""
Twitter read-provider abstraction: metrics and follower count.
Posting stays in twitter_api; only read operations go through a provider
so we can swap to a free-tier alternative (e.g. Xpoz) when available.
Free-first: use TWITTER_READ_PRIMARY (e.g. xpoz), fallback to TWITTER_READ_FALLBACK (official) on failure.
"""
import logging
from typing import Any, Protocol

logger = logging.getLogger(__name__)


def _is_retryable_read_error(exc: BaseException) -> bool:
    """True if we should try the fallback provider (rate limit, not implemented, etc.)."""
    if isinstance(exc, NotImplementedError):
        return True
    if isinstance(exc, RuntimeError) and ("Xpoz" in str(exc) or "RapidAPI" in str(exc)):
        return True
    resp = getattr(exc, "response", None)
    status = getattr(resp, "status_code", None) if resp is not None else getattr(exc, "status_code", None)
    return status in (429, 503)


class TwitterReadProvider(Protocol):
    """Interface for tweet metrics and follower count (read-only)."""

    def get_tweet_metrics_batch(self, tweet_ids: list[str]) -> dict[str, dict[str, Any]]:
        """Return dict mapping tweet_id -> {impressions, likes, retweets, replies}."""
        ...

    def get_me_follower_count(self) -> int | None:
        """Return authenticated user's follower count or None."""
        ...


class ChainedTwitterReadProvider:
    """Tries primary provider; on NotImplementedError or rate limit (429/503), uses fallback."""

    def __init__(self, primary: "TwitterReadProvider", fallback: "TwitterReadProvider") -> None:
        self._primary = primary
        self._fallback = fallback
        self._fallback_is_official = isinstance(fallback, OfficialTwitterReadProvider)

    def get_tweet_metrics_batch(self, tweet_ids: list[str]) -> dict[str, dict[str, Any]]:
        try:
            return self._primary.get_tweet_metrics_batch(tweet_ids)
        except Exception as e:
            if _is_retryable_read_error(e):
                # Check if fallback to paid API is disabled
                from atg_engine.config.settings import TWITTER_DISABLE_PAID_FALLBACK
                if TWITTER_DISABLE_PAID_FALLBACK and self._fallback_is_official:
                    logger.error(
                        "Read primary failed (%s), but fallback to PAID official Twitter API is disabled. "
                        "Set TWITTER_DISABLE_PAID_FALLBACK=false in .env to allow fallback, or fix the primary provider. "
                        "Error: %s", type(e).__name__, e
                    )
                    raise RuntimeError(
                        f"Primary read provider failed ({type(e).__name__}) and fallback to paid API is disabled. "
                        f"Original error: {e}"
                    ) from e
                logger.warning("Read primary failed (%s), using fallback: %s", type(e).__name__, e)
                return self._fallback.get_tweet_metrics_batch(tweet_ids)
            raise

    def get_me_follower_count(self) -> int | None:
        try:
            return self._primary.get_me_follower_count()
        except Exception as e:
            if _is_retryable_read_error(e):
                # Check if fallback to paid API is disabled
                from atg_engine.config.settings import TWITTER_DISABLE_PAID_FALLBACK
                if TWITTER_DISABLE_PAID_FALLBACK and self._fallback_is_official:
                    logger.error(
                        "Read primary failed (%s), but fallback to PAID official Twitter API is disabled. "
                        "Set TWITTER_DISABLE_PAID_FALLBACK=false in .env to allow fallback, or fix the primary provider. "
                        "Error: %s", type(e).__name__, e
                    )
                    raise RuntimeError(
                        f"Primary read provider failed ({type(e).__name__}) and fallback to paid API is disabled. "
                        f"Original error: {e}"
                    ) from e
                logger.warning("Read primary failed (%s), using fallback: %s", type(e).__name__, e)
                return self._fallback.get_me_follower_count()
            raise


class OfficialTwitterReadProvider:
    """Uses official X API with batched tweet lookup (free-tier friendly)."""

    def get_tweet_metrics_batch(self, tweet_ids: list[str]) -> dict[str, dict[str, Any]]:
        from atg_engine.services import twitter_api
        return twitter_api.get_tweet_metrics_batch(tweet_ids)

    def get_me_follower_count(self) -> int | None:
        from atg_engine.services import twitter_api
        return twitter_api.get_me_follower_count()


class RapidAPIReadProvider:
    """
    RapidAPI Twitter API (free tier): tweet metrics and optional follower count.
    Requires RAPIDAPI_KEY. Set RAPIDAPI_TWITTER_USERNAME for get_me_follower_count; else returns None.
    Optimized with caching to minimize API calls.
    """
    def get_tweet_metrics_batch(self, tweet_ids: list[str]) -> dict[str, dict[str, Any]]:
        from atg_engine.config.settings import RAPIDAPI_KEY
        from atg_engine.services import rapidapi_client
        if not RAPIDAPI_KEY:
            raise NotImplementedError(
                "RapidAPI read provider requires RAPIDAPI_KEY in .env when TWITTER_READ_PRIMARY=rapidapi."
            )
        return rapidapi_client.get_tweet_metrics_batch(tweet_ids)

    def get_me_follower_count(self) -> int | None:
        from atg_engine.config.settings import RAPIDAPI_KEY, RAPIDAPI_TWITTER_USERNAME
        from atg_engine.services import rapidapi_client
        if not RAPIDAPI_KEY:
            raise NotImplementedError(
                "RapidAPI read provider requires RAPIDAPI_KEY in .env when TWITTER_READ_PRIMARY=rapidapi."
            )
        if not RAPIDAPI_TWITTER_USERNAME:
            return None
        return rapidapi_client.get_user_follower_count(RAPIDAPI_TWITTER_USERNAME)


class XpozReadProvider:
    """
    Xpoz MCP (free tier): tweet metrics and optional follower count.
    Requires XPOZ_API_KEY. Set XPOZ_TWITTER_USERNAME for get_me_follower_count; else returns None.
    """
    def get_tweet_metrics_batch(self, tweet_ids: list[str]) -> dict[str, dict[str, Any]]:
        from atg_engine.config.settings import XPOZ_API_KEY
        from atg_engine.services import xpoz_client
        if not XPOZ_API_KEY:
            raise NotImplementedError(
                "Xpoz read provider requires XPOZ_API_KEY in .env when TWITTER_READ_PRIMARY=xpoz."
            )
        return xpoz_client.get_tweet_metrics_batch(tweet_ids)

    def get_me_follower_count(self) -> int | None:
        from atg_engine.config.settings import XPOZ_API_KEY, XPOZ_TWITTER_USERNAME
        from atg_engine.services import xpoz_client
        if not XPOZ_API_KEY:
            raise NotImplementedError(
                "Xpoz read provider requires XPOZ_API_KEY in .env when TWITTER_READ_PRIMARY=xpoz."
            )
        if not XPOZ_TWITTER_USERNAME:
            return None
        return xpoz_client.get_user_follower_count(XPOZ_TWITTER_USERNAME)


def _read_provider_by_name(name: str) -> TwitterReadProvider:
    """Return a read provider instance by name (official, rapidapi, xpoz)."""
    n = (name or "official").strip().lower()
    if n == "rapidapi":
        return RapidAPIReadProvider()
    if n == "xpoz":
        return XpozReadProvider()
    return OfficialTwitterReadProvider()


def get_read_provider() -> TwitterReadProvider:
    """Return the configured read provider: primary with fallback chain (free-first)."""
    from atg_engine.config.settings import TWITTER_READ_PRIMARY, TWITTER_READ_FALLBACK
    primary = _read_provider_by_name(TWITTER_READ_PRIMARY)
    fallback = _read_provider_by_name(TWITTER_READ_FALLBACK)
    if TWITTER_READ_PRIMARY == TWITTER_READ_FALLBACK:
        return primary
    return ChainedTwitterReadProvider(primary, fallback)
