"""Pytest configuration: use in-memory SQLite for all tests."""
import os

# Set before any atg_engine imports so db session uses in-memory DB
# Force in-memory DB for tests (override .env if present)
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
