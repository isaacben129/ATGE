"""StrategyState model - WIG and posting strategy."""
from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from atg_engine.db.session import Base


class StrategyState(Base):
    __tablename__ = "strategy_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    wig: Mapped[str] = mapped_column(String(256), default="Follower growth")
    daily_post_target: Mapped[int] = mapped_column(Integer, default=5)
    thread_ratio: Mapped[float] = mapped_column(Float, default=0.2)
    experimentation_rate: Mapped[float] = mapped_column(Float, default=0.25)
    last_reviewed: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
