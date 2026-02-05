# Autonomous Twitter Growth Engine (ATGE)

CrewAI-based system that grows a Twitter account autonomously using real API data and Darwinian voice evolution, with a strict no-misinformation guardrail.

## Requirements

- Python 3.11+
- Groq API key (for LLM)
- X (Twitter) API v2 credentials

## Setup

1. Clone or copy the project, then install dependencies:

   ```bash
   pip install -e .
   ```

2. Copy environment template and fill in secrets:

   ```bash
   cp .env.example .env
   # Edit .env with GROQ_API_KEY, Twitter API keys, etc.
   ```

3. Initialize the database:

   ```bash
   python -m atg_engine db init
   ```

   If you already had a database from an earlier version, run `python -m atg_engine db init` again to add any missing columns (e.g. after thread support was introduced).

## Environment variables

See `.env.example`. Key variables:

- `GROQ_API_KEY` – Groq API key (LLM)
- `GROQ_MODEL` – Optional; default `groq/llama-3.1-70b-versatile`
- `TWITTER_*` – X API v2 OAuth credentials
- `DATABASE_URL` – SQLite (default) or PostgreSQL. For Supabase, use `SUPABASE_DATABASE_URL` or `DATABASE_URL`.
- `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY` – Optional; for Supabase client (auth/storage) if you add it. See [Using Supabase](#using-supabase).

## Using Supabase

ATGE uses Supabase as PostgreSQL for persistence. You can also set project URL and keys if you add Supabase client features (auth, storage) later.

### Where to get values (Supabase Dashboard)

1. Open [Supabase Dashboard](https://supabase.com/dashboard) → your project.
2. **Settings → API**
   - **Project URL** → `SUPABASE_URL` (e.g. `https://xxxx.supabase.co`)
   - **Project API keys**: **anon public** → `SUPABASE_ANON_KEY`; **service_role** (secret) → `SUPABASE_SERVICE_ROLE_KEY` (server-only, never expose in client).
3. **Settings → Database**
   - **Connection string** → **URI**: copy and replace the password placeholder.
   - For serverless (Railway/Fly), use the **Session pooler** (port **6543**); for direct connection use port **5432**.
   - If the password contains special characters (`[ ] ! / # @ %`), URL-encode them (e.g. `[` → `%5B`, `]` → `%5D`, `!` → `%21`, `/` → `%2F`).
   - Set this as `DATABASE_URL` (or `SUPABASE_DATABASE_URL`) in `.env`; never commit it.

### Required for ATGE

- **Database:** Set `DATABASE_URL` (or `SUPABASE_DATABASE_URL`) to your Supabase Postgres connection string. Then run `python -m atg_engine db init` once to create tables.

### Optional (for future Supabase client use)

- `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY` — see `.env.example`. The app currently uses only the database connection; these are available in config if you add Supabase client (auth, storage, etc.).

## Running pipelines

Run a single pipeline (for cron or manual use):

```bash
python -m atg_engine run-daily      # Daily content generation
python -m atg_engine run-publish    # Publish approved tweets
python -m atg_engine run-analytics  # Ingest tweet performance
python -m atg_engine run-weekly     # Weekly evolution review
```

Run the built-in scheduler (all pipelines on a schedule):

```bash
python -m atg_engine scheduler
```

## CLI dashboard (scoreboard)

View follower growth, engagement, and evolution metrics:

```bash
python -m atg_engine dashboard
```

## Docker

```bash
docker-compose up --build
```

Uses `.env` for secrets. Optional PostgreSQL service; default is SQLite in a volume.

## Deploying (Railway / Fly.io + Supabase)

Deploy the scheduler so it runs 24/7 and picks up code changes when you push to GitHub.

### GitHub

1. Push this repo to GitHub. Ensure `.env` is in `.gitignore` and never commit it.
2. All secrets are set in the deployment platform’s environment, not in the repo.

### Supabase

Use your existing Supabase project as the database:

1. In [Supabase Dashboard](https://supabase.com/dashboard): Project → **Settings** → **Database** → **Connection string** → **URI**.
2. Copy the URI and replace the password placeholder with your database password. For serverless (Railway/Fly), prefer the **Session pooler** (port 6543) over the direct connection (port 5432).
3. If the password contains special characters (`[ ] ! / # @ %`), URL-encode them (e.g. `[` → `%5B`, `]` → `%5D`).
4. Set this URI as `DATABASE_URL` (or `SUPABASE_DATABASE_URL`) in your deployment platform’s environment variables.

### One-time database init

Tables must exist in Supabase before the app runs. Do **one** of the following:

- **Locally:** Set `DATABASE_URL` in `.env` to your Supabase URI, then run:
  ```bash
  python -m atg_engine db init
  ```
- **On the platform:** Run the same command as a one-off (Railway: run a command; Fly: `fly console` then run it).

### Railway

1. Create a project at [railway.app](https://railway.app) and connect your GitHub repo.
2. Deploy from the repo (Railway will use the Dockerfile if present).
3. In the service, set **Variables** to all required env vars (see list below). Do **not** commit these; set them in the Railway dashboard.
4. Start command is already `python -m atg_engine scheduler` in the Dockerfile. If not using Docker, set the start command to that.
5. After first deploy, run `python -m atg_engine db init` once (see One-time database init above).

### Fly.io

1. Install [flyctl](https://fly.io/docs/hub/getting-started-install/) and sign in.
2. From the project root: `fly launch` (or attach an existing app). Use the Dockerfile.
3. Set secrets (env vars) with:
   ```bash
   fly secrets set DATABASE_URL="postgresql://..." GROQ_API_KEY="..." TWITTER_BEARER_TOKEN="..." ...
   ```
   (Use your real values; set each variable. See list below.)
4. Deploy: `fly deploy`. The Dockerfile `CMD` runs the scheduler.
5. Run `python -m atg_engine db init` once (e.g. via `fly console` or locally with `DATABASE_URL` set to your Supabase URI).

### Environment variables to set in production

Set these in the deployment platform (Railway Variables or Fly secrets). Never put real values in the repo.

| Variable | Required | Notes |
|----------|----------|------|
| `DATABASE_URL` | Yes | Your Supabase Postgres connection string (Session pooler URI recommended). |
| `GROQ_API_KEY` | Yes | Groq API key for the LLM. |
| `GROQ_MODEL` | No | Default `groq/llama-3.3-70b-versatile`. |
| `TWITTER_BEARER_TOKEN` | Yes | X API v2 app Bearer token. |
| `TWITTER_API_KEY` | Yes | X API consumer key. |
| `TWITTER_API_SECRET` | Yes | X API consumer secret. |
| `TWITTER_ACCESS_TOKEN` | Yes | X API user access token. |
| `TWITTER_ACCESS_SECRET` | Yes | X API user access secret. |

Optional (scheduler): `DAILY_GENERATION_CRON`, `PUBLISHING_INTERVAL_HOURS`, `PERFORMANCE_INTERVAL_HOURS`, `WEEKLY_REVIEW_CRON` (see `.env.example` or config).

Optional (Supabase client): `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY` (see [Using Supabase](#using-supabase)).

### Persona (optional)

If you use a persona config (e.g. `persona_mila.json`), run **once** after the database is initialized so the deployed app has the persona and strategy:

```bash
python -m atg_engine init-persona --config persona_mila.json
```

Run this locally with `DATABASE_URL` set to your Supabase URI, or as a one-off in the platform (Railway run command / Fly console).

## Project structure

- `atg_engine/agents/` – CrewAI agents (WIG, voice, ideas, hooks, writer, thread, gatekeeper, publisher, analytics, evolution, cadence)
- `atg_engine/models/` – SQLAlchemy models
- `atg_engine/services/` – Twitter API, LLM, scoring, evolution, scheduler
- `atg_engine/pipelines/` – Daily generation, publishing, performance ingestion, weekly review
- `atg_engine/config/` – Settings and prompts (including misinformation gatekeeper)

## Testing

Install dev dependencies and run unit tests (no CrewAI/API required for unit tests):

```bash
pip install -e ".[dev]"
python -m pytest tests/unit -v
```

Integration tests require CrewAI and will run with `python -m pytest tests/ -v` after full install.

## Guardrails

- **No misinformation**: All factual claims must be verifiable; opinions/satire allowed. Gatekeeper has veto over publishing.
- Twitter ToS compliant; no hate speech or impersonation.
