"""Persona model - identity definition for the social media personality."""
import json
from datetime import datetime
from typing import Any

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
    persona_extended: Mapped[str | None] = mapped_column(Text, default=None, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def to_prompt_context(self) -> str:
        """Summary for injection into agent prompts. Uses legacy columns or rich context when persona_extended is set."""
        if self.persona_extended:
            return self.get_prompt_context("full")
        return self._legacy_context()

    def _get_extended_data(self) -> dict[str, Any] | None:
        """Parse persona_extended JSON; return None if missing or invalid."""
        if not self.persona_extended or not self.persona_extended.strip():
            return None
        try:
            return json.loads(self.persona_extended)
        except (TypeError, ValueError):
            return None

    def get_prompt_context(self, kind: str = "full") -> str:
        """Stage-specific context: full (ideas, weekly), writer (hooks, writer, thread, gatekeeper), curation (trending)."""
        data = self._get_extended_data()
        if not data:
            return self._legacy_context()

        basic = data.get("basic_info") or {}
        backstory = data.get("backstory") or {}
        personality = data.get("personality_layers") or {}
        discourse = data.get("discourse_positions") or {}
        voice_range = data.get("voice_range") or {}
        retweet_style = data.get("retweet_commentary_style") or {}
        dos_donts = data.get("dos_donts") or {}
        style_notes = data.get("style_notes") or ""

        if kind == "full":
            return self._build_full_context(
                basic, backstory, personality, discourse, style_notes
            )
        if kind == "writer":
            return self._build_writer_context(
                basic, personality, voice_range, dos_donts, style_notes, data.get("cultural_references"), data.get("tweet_formulas")
            )
        if kind == "curation":
            return self._build_curation_context(
                basic, retweet_style, discourse, data.get("content_categories"), data.get("tweet_formulas")
            )
        return self._legacy_context()

    def get_viral_content_context(self) -> dict[str, Any]:
        """Content categories and tweet formulas for viral spin/quote pipeline. From persona_extended."""
        data = self._get_extended_data()
        if not data:
            return {"content_categories": {}, "tweet_formulas": {}}
        return {
            "content_categories": data.get("content_categories") or {},
            "tweet_formulas": data.get("tweet_formulas") or {},
        }

    def _legacy_context(self) -> str:
        """Build context from the six legacy columns only (no persona_extended)."""
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

    def _build_full_context(
        self,
        basic: dict,
        backstory: dict,
        personality: dict,
        discourse: dict,
        style_notes: str,
    ) -> str:
        """Ideas, weekly review: basic_info, backstory (condensed), personality layers, discourse, style."""
        parts = []
        name = basic.get("name") or self.name
        handle = basic.get("handle") or self.handle
        actual_niche = basic.get("actual_niche") or self.niche
        if name:
            parts.append(f"Name: {name}")
        if handle:
            parts.append(f"Handle: @{str(handle).lstrip('@')}")
        if actual_niche:
            parts.append(f"Niche: {actual_niche}")
        if basic.get("location"):
            parts.append(f"Location: {basic['location']}")
        if basic.get("university") or basic.get("degree"):
            parts.append(f"Background: {basic.get('university', '')} – {basic.get('degree', '')}".strip(" –"))

        if backstory:
            condensed = []
            for k, v in backstory.items():
                if isinstance(v, str) and v.strip():
                    condensed.append(f"{k.replace('_', ' ').title()}: {v[:200]}{'...' if len(v) > 200 else ''}")
            if condensed:
                parts.append("Backstory (condensed): " + " | ".join(condensed[:5]))

        annoys = personality.get("what_actually_annoys_her") or []
        funny = personality.get("what_she_finds_funny") or []
        cares = personality.get("what_she_cares_about_more_than_she_admits") or []
        if annoys:
            parts.append("What annoys her: " + ", ".join(annoys[:6]) if isinstance(annoys[0], str) else str(annoys)[:300])
        if funny:
            parts.append("What she finds funny: " + ", ".join(funny[:6]) if isinstance(funny[0], str) else str(funny)[:300])
        if cares:
            parts.append("What she cares about (more than she admits): " + ", ".join(cares[:5]) if isinstance(cares[0], str) else str(cares)[:300])

        if discourse:
            items = []
            for k, v in list(discourse.items())[:8]:
                sv = str(v)
                items.append(f"{k.replace('_', ' ').title()}: {sv[:80]}..." if len(sv) > 80 else f"{k.replace('_', ' ').title()}: {sv}")
            parts.append("Discourse positions: " + " | ".join(items))

        if style_notes:
            parts.append(f"Style notes: {style_notes[:500]}{'...' if len(style_notes) > 500 else ''}")

        return "\n".join(parts) if parts else "No persona defined yet."

    def _build_writer_context(
        self,
        basic: dict,
        personality: dict,
        voice_range: dict,
        dos_donts: dict,
        style_notes: str,
        cultural_refs: dict | None,
        tweet_formulas: dict | None = None,
    ) -> str:
        """Hooks, writer, thread, gatekeeper: voice_range examples, style_notes, do/dont, contradictions, guardrails, tweet formulas."""
        parts = []

        parts.append("Example tweets in her voice:")
        for label, example in voice_range.items():
            if isinstance(example, str) and example.strip():
                parts.append(f"  {label.replace('_', ' ').title()}: \"{example}\"")

        if style_notes:
            parts.append(f"Style notes: {style_notes}")

        do_list = dos_donts.get("do") if isinstance(dos_donts, dict) else []
        dont_list = dos_donts.get("dont") if isinstance(dos_donts, dict) else []
        if do_list:
            parts.append("Do: " + "; ".join(do_list) if isinstance(do_list[0], str) else str(do_list))
        if dont_list:
            parts.append("Don't: " + "; ".join(dont_list) if isinstance(dont_list[0], str) else str(dont_list))

        contradictions = personality.get("contradictions") if isinstance(personality.get("contradictions"), dict) else {}
        if contradictions:
            parts.append(f"Contradictions: appears {contradictions.get('appears', '')} | actually {contradictions.get('actually', '')}")

        annoys = personality.get("what_actually_annoys_her") or []
        funny = personality.get("what_she_finds_funny") or []
        if annoys and isinstance(annoys[0], str):
            parts.append("What to avoid (annoys her): " + ", ".join(annoys[:5]))
        if funny and isinstance(funny[0], str):
            parts.append("What fits her humor: " + ", ".join(funny[:5]))

        if cultural_refs:
            ref_parts = []
            if cultural_refs.get("books_shes_actually_read"):
                books = cultural_refs["books_shes_actually_read"]
                ref_parts.append("Books: " + ", ".join(books[:4]) if isinstance(books[0], str) else "")
            if cultural_refs.get("london_spots"):
                spots = cultural_refs["london_spots"]
                ref_parts.append("London: " + ", ".join(spots[:3]) if isinstance(spots[0], str) else "")
            if ref_parts:
                parts.append("References: " + " | ".join(r for r in ref_parts if r))

        if tweet_formulas and isinstance(tweet_formulas, dict):
            parts.append("\nTweet formulas (use these structures when writing):")
            for name, info in list(tweet_formulas.items())[:8]:
                if isinstance(info, dict):
                    structure = info.get("structure", "")
                    example = info.get("example", "")
                    if structure:
                        formula_line = f"  {name.replace('_', ' ').title()}: {structure}"
                        if example:
                            formula_line += f" (e.g. \"{example[:80]}{'...' if len(example) > 80 else ''}\")"
                        parts.append(formula_line)

        return "\n".join(parts) if parts else "No persona defined yet."

    def _build_curation_context(
        self,
        basic: dict,
        retweet_style: dict,
        discourse: dict,
        content_categories: dict | None = None,
        tweet_formulas: dict | None = None,
    ) -> str:
        """Trending: retweet_commentary_style (approach + examples), discourse, niche, optional categories/formulas."""
        parts = []
        actual_niche = basic.get("actual_niche") or self.niche
        if actual_niche:
            parts.append(f"Niche: {actual_niche}")

        approach = retweet_style.get("approach") if isinstance(retweet_style, dict) else ""
        if approach:
            parts.append(f"Quote/retweet approach: {approach}")
        examples = retweet_style.get("examples") if isinstance(retweet_style, dict) else []
        if examples and isinstance(examples, list):
            for ex in examples[:2]:
                if isinstance(ex, dict) and ex.get("original") and ex.get("vera_spin"):
                    parts.append(f"  Original: \"{ex['original'][:80]}...\" -> Her spin: \"{ex['vera_spin'][:80]}...\"")

        if content_categories and isinstance(content_categories, dict):
            cat_names = list(content_categories.keys())[:8]
            parts.append("Content categories (use for alignment): " + ", ".join(cat_names))
        if tweet_formulas and isinstance(tweet_formulas, dict):
            formula_lines = []
            for name, info in list(tweet_formulas.items())[:5]:
                if isinstance(info, dict) and info.get("structure"):
                    formula_lines.append(f"{name}: {info['structure'][:60]}...")
            if formula_lines:
                parts.append("Tweet formulas: " + " | ".join(formula_lines))

        if discourse:
            items = [f"{k.replace('_', ' ')}: {str(v)[:60]}" for k, v in list(discourse.items())[:5]]
            parts.append("Discourse positions (brief): " + " | ".join(items))

        return "\n".join(parts) if parts else "No persona defined yet."
