"""MutationLog model - record of voice genome evolution."""
from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from atg_engine.db.session import Base


class MutationLog(Base):
    __tablename__ = "mutation_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    old_genome_id: Mapped[int] = mapped_column(Integer, nullable=False)
    new_genome_id: Mapped[int] = mapped_column(Integer, nullable=False)
    mutation_reason: Mapped[str] = mapped_column(Text, default="")
    performance_delta: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
