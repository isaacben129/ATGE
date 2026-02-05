"""Weighted voice evolution: update genome from performance signals. No DB writes; caller persists."""
import json
import random
from typing import Any

# Mutation rate for random exploration (0.0–1.0)
RANDOM_MUTATION_RATE = 0.1
# Step size for slider nudges
SLIDER_STEP = 0.1


def _parse_list(val: Any) -> list:
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        try:
            return json.loads(val or "[]")
        except (TypeError, ValueError):
            return []
    return []


def _get_genome_val(genome: Any, key: str, default: Any) -> Any:
    """Get attribute from object or key from dict."""
    if hasattr(genome, key):
        return getattr(genome, key)
    if hasattr(genome, "get"):
        return genome.get(key, default)
    return default


def weighted_update(
    current_genome: Any,
    winning_traits: list[str],
    losing_traits: list[str],
    winning_hooks: list[str],
    losing_hooks: list[str],
    performance_delta: float,
) -> dict[str, Any]:
    """
    Produce updated genome dict from current genome and performance signals.
    - Increase weight on winning tone_traits; drop or reduce underperforming.
    - Nudge aggressiveness/controversy/humor_level from performance_delta.
    - Apply small random mutation with probability RANDOM_MUTATION_RATE.
    """
    tone_traits = _parse_list(_get_genome_val(current_genome, "tone_traits", "[]"))
    language_patterns = _parse_list(_get_genome_val(current_genome, "language_patterns", "[]"))
    taboo_topics = _parse_list(_get_genome_val(current_genome, "taboo_topics", "[]"))
    risk_tolerance = float(_get_genome_val(current_genome, "risk_tolerance", 0.5))
    aggressiveness = float(_get_genome_val(current_genome, "aggressiveness", 0.5))
    humor_level = float(_get_genome_val(current_genome, "humor_level", 0.5))
    controversy_level = float(_get_genome_val(current_genome, "controversy_level", 0.5))

    # Promote winning traits (ensure they exist; add if new)
    for t in winning_traits:
        if t and t not in tone_traits:
            tone_traits.append(t)
    # Demote losing traits (remove or leave; we don't have weights, so remove if present)
    for t in losing_traits:
        if t in tone_traits:
            tone_traits.remove(t)
    if not tone_traits:
        tone_traits = ["direct", "clear"]

    # Nudge sliders by performance_delta (positive delta -> slightly more aggressive/humor/controversy)
    nudge = performance_delta * SLIDER_STEP
    aggressiveness = max(0.0, min(1.0, aggressiveness + nudge))
    humor_level = max(0.0, min(1.0, humor_level + nudge * 0.5))
    controversy_level = max(0.0, min(1.0, controversy_level + nudge * 0.5))
    risk_tolerance = max(0.0, min(1.0, risk_tolerance + nudge * 0.3))

    # Random mutation
    if random.random() < RANDOM_MUTATION_RATE:
        which = random.choice(["aggressiveness", "humor_level", "controversy_level", "risk_tolerance"])
        delta = (random.random() - 0.5) * 2 * SLIDER_STEP
        if which == "aggressiveness":
            aggressiveness = max(0.0, min(1.0, aggressiveness + delta))
        elif which == "humor_level":
            humor_level = max(0.0, min(1.0, humor_level + delta))
        elif which == "controversy_level":
            controversy_level = max(0.0, min(1.0, controversy_level + delta))
        else:
            risk_tolerance = max(0.0, min(1.0, risk_tolerance + delta))

    return {
        "tone_traits": json.dumps(tone_traits) if isinstance(tone_traits, list) else tone_traits,
        "language_patterns": json.dumps(language_patterns) if isinstance(language_patterns, list) else language_patterns,
        "taboo_topics": json.dumps(taboo_topics) if isinstance(taboo_topics, list) else taboo_topics,
        "risk_tolerance": risk_tolerance,
        "aggressiveness": aggressiveness,
        "humor_level": humor_level,
        "controversy_level": controversy_level,
    }
