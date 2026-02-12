"""Bootstrap: ensure Persona, VoiceGenome, StrategyState exist. Load persona config from file."""
import json
import logging
from pathlib import Path
from typing import Any

from atg_engine.db.session import SessionLocal
from atg_engine.models import Persona, VoiceGenome, StrategyState

logger = logging.getLogger(__name__)


def _get_persona_config_path() -> Path | None:
    """Return path to persona config file if set via env or default file exists."""
    from atg_engine.config.settings import BASE_DIR, PERSONA_CONFIG_PATH

    if PERSONA_CONFIG_PATH:
        p = Path(PERSONA_CONFIG_PATH)
        if p.exists():
            return p
        logger.warning("PERSONA_CONFIG_PATH is set but file not found: %s", PERSONA_CONFIG_PATH)
        return None
    default = BASE_DIR.parent / "persona_mila.json"
    if default.exists():
        return default
    return None


def _persona_is_empty(persona: Persona) -> bool:
    """True if persona has no meaningful content (would yield 'No persona defined yet.')."""
    if getattr(persona, "persona_extended", None) and (persona.persona_extended or "").strip():
        return False
    return not (persona.name or persona.niche or persona.bio)


def ensure_bootstrap():
    """Create default Persona, VoiceGenome, and StrategyState if missing. Call before daily/weekly.
    If the persona is empty and PERSONA_CONFIG_PATH is set (or persona_mila.json exists in project root),
    automatically applies that config so content stays on-brand."""
    config_path_to_apply: Path | None = None
    try:
        db = SessionLocal()
        try:
            persona = db.query(Persona).first()
            if not persona:
                persona = Persona(
                    name="",
                    handle="",
                    niche="",
                    bio="",
                    dos_donts="",
                    style_notes="",
                )
                db.add(persona)
            genome = db.query(VoiceGenome).order_by(VoiceGenome.last_updated.desc()).first()
            if not genome:
                genome = VoiceGenome(
                    tone_traits="[]",
                    language_patterns="[]",
                    taboo_topics="[]",
                    risk_tolerance=0.5,
                    aggressiveness=0.5,
                    humor_level=0.5,
                    controversy_level=0.5,
                )
                db.add(genome)
            strategy = db.query(StrategyState).order_by(StrategyState.last_reviewed.desc()).first()
            if not strategy:
                strategy = StrategyState(
                    wig="Follower growth",
                    daily_post_target=5,
                    thread_ratio=0.2,
                    experimentation_rate=0.25,
                )
                db.add(strategy)
            db.commit()
            if _persona_is_empty(persona):
                config_path_to_apply = _get_persona_config_path()
        finally:
            db.close()
    except Exception as e:
        logger.exception("Bootstrap failed: %s", e)
        raise RuntimeError(f"Bootstrap failed (DB unavailable or schema issue): {e}") from e
    if config_path_to_apply:
        try:
            msg = apply_persona_config(config_path_to_apply)
            logger.info("Persona was empty; auto-applied from config: %s", msg)
        except Exception as e:
            logger.warning("Failed to auto-apply persona config from %s: %s", config_path_to_apply, e)


def load_persona_config(path: str | Path) -> dict[str, Any]:
    """Load persona (and optional voice_genome, strategy) from JSON file."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    data = json.loads(p.read_text(encoding="utf-8"))
    return data


def apply_persona_config(config_path: str | Path) -> str:
    """
    Create or update Persona (and optionally VoiceGenome, StrategyState) from config file.
    Returns a short status message.
    """
    data = load_persona_config(config_path)
    db = SessionLocal()
    try:
        persona_data = data.get("persona", data)
        persona = db.query(Persona).first()
        if not persona:
            persona = Persona()
            db.add(persona)

        is_new_format = (
            "basic_info" in persona_data
            or "backstory" in persona_data
            or "voice_range" in persona_data
            or "content_categories" in persona_data
            or "tweet_formulas" in persona_data
        )
        if is_new_format:
            existing = {}
            if persona.persona_extended:
                try:
                    existing = json.loads(persona.persona_extended)
                except (TypeError, ValueError):
                    pass
            merged = {**existing, **persona_data}
            persona.persona_extended = json.dumps(merged, ensure_ascii=False)
            basic = persona_data.get("basic_info") or existing.get("basic_info") or {}
            persona.name = basic.get("name", persona.name or "")
            persona.handle = basic.get("handle", persona.handle or "")
            persona.niche = basic.get("actual_niche", basic.get("niche", persona.niche or ""))
            persona.bio = persona_data.get("bio", persona.bio or "")
            dd = persona_data.get("dos_donts")
            if isinstance(dd, dict):
                do_list = dd.get("do") or []
                dont_list = dd.get("dont") or []
                do_str = "; ".join(do_list) if do_list and isinstance(do_list[0], str) else (str(do_list) if do_list else "")
                dont_str = "; ".join(dont_list) if dont_list and isinstance(dont_list[0], str) else (str(dont_list) if dont_list else "")
                persona.dos_donts = f"Do: {do_str}. Don't: {dont_str}" if dont_str else (f"Do: {do_str}" if do_str else (persona.dos_donts or ""))
            else:
                persona.dos_donts = str(dd) if dd else (persona.dos_donts or "")
            persona.style_notes = persona_data.get("style_notes", persona.style_notes or "")
        else:
            persona.persona_extended = None
            persona.name = persona_data.get("name", persona.name or "")
            persona.handle = persona_data.get("handle", persona.handle or "")
            persona.niche = persona_data.get("niche", persona.niche or "")
            persona.bio = persona_data.get("bio", persona.bio or "")
            persona.dos_donts = persona_data.get("dos_donts", persona.dos_donts or "")
            persona.style_notes = persona_data.get("style_notes", persona.style_notes or "")

        if "voice_genome" in data:
            vg = data["voice_genome"]
            genome = db.query(VoiceGenome).order_by(VoiceGenome.last_updated.desc()).first()
            if not genome:
                genome = VoiceGenome()
                db.add(genome)
            if "tone_traits" in vg:
                genome.tone_traits = json.dumps(vg["tone_traits"]) if isinstance(vg["tone_traits"], list) else vg["tone_traits"]
            if "risk_tolerance" in vg:
                genome.risk_tolerance = float(vg["risk_tolerance"])
            if "aggressiveness" in vg:
                genome.aggressiveness = float(vg["aggressiveness"])
            if "humor_level" in vg:
                genome.humor_level = float(vg["humor_level"])
            if "controversy_level" in vg:
                genome.controversy_level = float(vg["controversy_level"])

        if "strategy" in data:
            st = data["strategy"]
            strategy = db.query(StrategyState).order_by(StrategyState.last_reviewed.desc()).first()
            if not strategy:
                strategy = StrategyState()
                db.add(strategy)
            if "wig" in st:
                strategy.wig = st["wig"]
            if "daily_post_target" in st:
                strategy.daily_post_target = int(st["daily_post_target"])
            if "thread_ratio" in st:
                strategy.thread_ratio = float(st["thread_ratio"])
            if "experimentation_rate" in st:
                strategy.experimentation_rate = float(st["experimentation_rate"])

        db.commit()
        return f"Persona and config applied from {config_path}."
    finally:
        db.close()
