"""Load env and app settings."""
import os
from pathlib import Path

from dotenv import load_dotenv

# Paths (BASE_DIR = atg_engine package root)
BASE_DIR = Path(__file__).resolve().parent.parent
# Load .env from project root so it works regardless of cwd
load_dotenv(BASE_DIR.parent / ".env")

PROMPTS_DIR = BASE_DIR / "config" / "prompts"

# Database (Supabase: set SUPABASE_DATABASE_URL or DATABASE_URL)
DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("SUPABASE_DATABASE_URL") or "sqlite:///./atg_engine.db"
# Supabase project (optional; for client/auth/storage if you add them later)
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
if DATABASE_URL.startswith("sqlite") and not DATABASE_URL.startswith("sqlite:///"):
    # Relative path -> resolve under project
    DATABASE_URL = f"sqlite:///{BASE_DIR.parent / 'atg_engine.db'}"

# LLM (Groq)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "groq/llama-3.3-70b-versatile")

# Twitter / X API v2
# Optional: TWITTER_CLIENT_ID / TWITTER_CLIENT_SECRET are the same as API Key/Secret (OAuth 2.0 names).
# If only Client ID/Secret are set, they are used as API Key/Secret.
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN", "")
TWITTER_API_KEY = os.getenv("TWITTER_API_KEY", "").strip() or os.getenv("TWITTER_CLIENT_ID", "").strip()
TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET", "").strip() or os.getenv("TWITTER_CLIENT_SECRET", "").strip()
TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN", "")
TWITTER_ACCESS_SECRET = os.getenv("TWITTER_ACCESS_SECRET", "")

# Read provider: "official" (batched API) or "xpoz" (when implemented)
TWITTER_READ_PROVIDER = os.getenv("TWITTER_READ_PROVIDER", "official")
# Optional: cap tweet IDs per ingestion run to stay under free tier (e.g. 30 * 30 days = 900/month)
PERFORMANCE_INGESTION_MAX_TWEETS = int(os.getenv("PERFORMANCE_INGESTION_MAX_TWEETS", "50"))

# Persona: optional path to JSON config; if set and DB persona is empty, bootstrap will auto-apply it
PERSONA_CONFIG_PATH = os.getenv("PERSONA_CONFIG_PATH", "").strip()

# Scheduler (cron-like)
DAILY_GENERATION_CRON = os.getenv("DAILY_GENERATION_CRON", "0 8 * * *")  # 08:00 daily
PUBLISHING_INTERVAL_HOURS = int(os.getenv("PUBLISHING_INTERVAL_HOURS", "1"))
PERFORMANCE_INTERVAL_HOURS = int(os.getenv("PERFORMANCE_INTERVAL_HOURS", "3"))
WEEKLY_REVIEW_CRON = os.getenv("WEEKLY_REVIEW_CRON", "0 9 * * 1")  # Monday 09:00
TRENDING_CONTENT_CRON = os.getenv("TRENDING_CONTENT_CRON", "0 */6 * * *")  # Every 6 hours
