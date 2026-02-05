"""Environment validation: fail fast with clear messages when required vars are missing."""
import warnings

from atg_engine.config.settings import (
    DATABASE_URL,
    GROQ_API_KEY,
    TWITTER_ACCESS_SECRET,
    TWITTER_ACCESS_TOKEN,
    TWITTER_API_KEY,
    TWITTER_API_SECRET,
    TWITTER_BEARER_TOKEN,
)


def validate_env(*, require_llm: bool = True, require_twitter: bool = False) -> None:
    """
    Validate required env vars. Raises ValueError with a clear message if validation fails.
    - require_llm: require GROQ_API_KEY (for daily, weekly).
    - require_twitter: require Twitter OAuth vars (for publish, analytics).
    Warns if DATABASE_URL is default SQLite.
    """
    missing = []
    if require_llm and not (GROQ_API_KEY and GROQ_API_KEY.strip()):
        missing.append("GROQ_API_KEY (set in .env)")
    if require_twitter:
        twitter_ok = all([
            TWITTER_API_KEY and TWITTER_API_KEY.strip(),
            TWITTER_API_SECRET and TWITTER_API_SECRET.strip(),
            TWITTER_ACCESS_TOKEN and TWITTER_ACCESS_TOKEN.strip(),
            TWITTER_ACCESS_SECRET and TWITTER_ACCESS_SECRET.strip(),
        ])
        if not twitter_ok:
            missing.append("TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET (set in .env)")
        if not (TWITTER_BEARER_TOKEN and TWITTER_BEARER_TOKEN.strip()):
            missing.append("TWITTER_BEARER_TOKEN (set in .env)")

    if missing:
        raise ValueError(
            "Missing required environment variables: " + "; ".join(missing)
        )

    if DATABASE_URL.startswith("sqlite"):
        warnings.warn(
            "Using default SQLite. For production, set DATABASE_URL (e.g. PostgreSQL/Supabase).",
            UserWarning,
            stacklevel=2,
        )
