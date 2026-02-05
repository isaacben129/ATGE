"""TweetCandidate model - generated tweet content before approval and publishing."""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from atg_engine.db.session import Base


class TweetCandidate(Base):
    __tablename__ = "tweet_candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    tone_traits: Mapped[str] = mapped_column(Text, default="[]")  # JSON array as text
    topic: Mapped[str] = mapped_column(String(512), default="")
    hook_type: Mapped[str] = mapped_column(String(128), default="")
    risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    published: Mapped[bool] = mapped_column(Boolean, default=False)
    tweet_id: Mapped[str] = mapped_column(String(64), nullable=True)
    thread_id: Mapped[str] = mapped_column(String(64), nullable=True, index=True)
    thread_sequence: Mapped[int] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
