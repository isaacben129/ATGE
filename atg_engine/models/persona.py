"""Persona model - identity definition for the social media personality."""
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from atg_engine.db.session import Base


class Persona(Base):
    __tablename__ = "personas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(256), default="")
    handle: Mapped[str] = mapped_column(String(128), default="")
    niche: Mapped[str] = mapped_column(String(512), default="")
    bio: Mapped[str] = mapped_column(Text, default="")
    dos_donts: Mapped[str] = mapped_column(Text, default="")
    style_notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def to_prompt_context(self) -> str:
        """Summary for injection into agent prompts."""
        parts = []
        if self.name:
            parts.append(f"Name: {self.name}")
        if self.handle:
            parts.append(f"Handle: @{self.handle.lstrip('@')}")
        if self.niche:
            parts.append(f"Niche: {self.niche}")
        if self.bio:
            parts.append(f"Bio: {self.bio}")
        if self.dos_donts:
            parts.append(f"Do's and don'ts: {self.dos_donts}")
        if self.style_notes:
            parts.append(f"Style notes: {self.style_notes}")
        return "\n".join(parts) if parts else "No persona defined yet."
