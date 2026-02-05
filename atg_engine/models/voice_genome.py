"""VoiceGenome model - brand personality and voice parameters."""
from datetime import datetime
from typing import List

from sqlalchemy import DateTime, Float, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from atg_engine.db.session import Base


class VoiceGenome(Base):
    __tablename__ = "voice_genomes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tone_traits: Mapped[list] = mapped_column(Text, default="[]")  # JSON array stored as text for SQLite compat
    language_patterns: Mapped[list] = mapped_column(Text, default="[]")
    taboo_topics: Mapped[list] = mapped_column(Text, default="[]")
    risk_tolerance: Mapped[float] = mapped_column(Float, default=0.5)
    aggressiveness: Mapped[float] = mapped_column(Float, default=0.5)
    humor_level: Mapped[float] = mapped_column(Float, default=0.5)
    controversy_level: Mapped[float] = mapped_column(Float, default=0.5)
    last_updated: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def get_tone_traits_list(self) -> List[str]:
        import json
        if isinstance(self.tone_traits, list):
            return self.tone_traits
        try:
            return json.loads(self.tone_traits or "[]")
        except (TypeError, ValueError):
            return []

    def get_language_patterns_list(self) -> List[str]:
        import json
        if isinstance(self.language_patterns, list):
            return self.language_patterns
        try:
            return json.loads(self.language_patterns or "[]")
        except (TypeError, ValueError):
            return []

    def get_taboo_topics_list(self) -> List[str]:
        import json
        if isinstance(self.taboo_topics, list):
            return self.taboo_topics
        try:
            return json.loads(self.taboo_topics or "[]")
        except (TypeError, ValueError):
            return []
