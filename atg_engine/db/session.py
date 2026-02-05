"""Database engine, session, and base for ATGE."""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from atg_engine.config.settings import DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
    echo=False,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Yield a DB session (for use as dependency or context)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
