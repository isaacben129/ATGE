FROM python:3.11-slim

WORKDIR /app

# Copy full project so pip install -e . can find atg_engine (.dockerignore excludes .env, .git, etc.)
COPY . .
RUN pip install --no-cache-dir -e .

ENV PYTHONUNBUFFERED=1
# DATABASE_URL must be set at runtime (e.g. Supabase URI in Railway/Fly env)

RUN mkdir -p /app/data

# Default: run scheduler (all pipelines on schedule)
CMD ["python", "-m", "atg_engine", "scheduler"]
