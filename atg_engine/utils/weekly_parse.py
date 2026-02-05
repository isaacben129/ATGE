"""Parse weekly review Crew output for genome and strategy parameters."""
import json
import re
from typing import Any


def _extract_json_block(text: str, start_pattern: str = r"\{") -> dict | None:
    """Find a JSON-like block (starts with {, ends with }) and parse it. Handles trailing commas."""
    start = re.search(start_pattern, text)
    if not start:
        return None
    i = start.start()
    depth = 0
    for j in range(i, len(text)):
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0:
                raw = text[i : j + 1]
                raw = re.sub(r",\s*}", "}", raw)
                raw = re.sub(r",\s*]", "]", raw)
                try:
                    return json.loads(raw)
                except json.JSONDecodeError:
                    return None
    return None


def parse_genome_from_raw(raw: str) -> dict[str, Any] | None:
    """
    Extract voice genome params from Crew raw output.
    Looks for tone_traits (list or JSON array), risk_tolerance, aggressiveness, humor_level, controversy_level.
    """
    # Try to find a block containing "tone_traits" or "risk_tolerance"
    for pattern in [r"tone_traits", r"risk_tolerance", r"voice genome", r"genome"]:
        idx = raw.lower().find(pattern)
        if idx == -1:
            continue
        snippet = raw[max(0, idx - 100) : idx + 600]
        obj = _extract_json_block(snippet, r"\{")
        if not obj:
            continue
        result = {}
        if "tone_traits" in obj:
            v = obj["tone_traits"]
            result["tone_traits"] = json.dumps(v) if isinstance(v, list) else str(v)
        if "risk_tolerance" in obj:
            try:
                result["risk_tolerance"] = float(obj["risk_tolerance"])
            except (TypeError, ValueError):
                pass
        if "aggressiveness" in obj:
            try:
                result["aggressiveness"] = float(obj["aggressiveness"])
            except (TypeError, ValueError):
                pass
        if "humor_level" in obj:
            try:
                result["humor_level"] = float(obj["humor_level"])
            except (TypeError, ValueError):
                pass
        if "controversy_level" in obj:
            try:
                result["controversy_level"] = float(obj["controversy_level"])
            except (TypeError, ValueError):
                pass
        if result:
            return result
    # Fallback: key: value lines
    result = {}
    for key in ["risk_tolerance", "aggressiveness", "humor_level", "controversy_level"]:
        m = re.search(rf"{key}\s*[:=]\s*([0-9.]+)", raw, re.IGNORECASE)
        if m:
            try:
                result[key] = float(m.group(1))
            except ValueError:
                pass
    tone_m = re.search(r"tone_traits?\s*[:=]\s*\[([^\]]+)\]", raw, re.IGNORECASE)
    if tone_m:
        result["tone_traits"] = "[" + tone_m.group(1) + "]"
    return result if result else None


def parse_strategy_from_raw(raw: str) -> dict[str, Any] | None:
    """
    Extract strategy params from Crew raw output.
    Looks for daily_post_target, thread_ratio, experimentation_rate, wig.
    """
    result = {}
    m = re.search(r"daily_post_target\s*[:=]\s*(\d+)", raw, re.IGNORECASE)
    if m:
        result["daily_post_target"] = int(m.group(1))
    m = re.search(r"thread_ratio\s*[:=]\s*([0-9.]+)", raw, re.IGNORECASE)
    if m:
        try:
            result["thread_ratio"] = float(m.group(1))
        except ValueError:
            pass
    m = re.search(r"experimentation_rate\s*[:=]\s*([0-9.]+)", raw, re.IGNORECASE)
    if m:
        try:
            result["experimentation_rate"] = float(m.group(1))
        except ValueError:
            pass
    m = re.search(r"wig\s*[:=]\s*[\"']?([^\"'\n,}]+)[\"']?", raw, re.IGNORECASE)
    if m:
        result["wig"] = m.group(1).strip()
    obj = _extract_json_block(raw, r"\{")
    if obj:
        if "daily_post_target" in obj:
            result["daily_post_target"] = int(obj["daily_post_target"])
        if "thread_ratio" in obj:
            result["thread_ratio"] = float(obj["thread_ratio"])
        if "experimentation_rate" in obj:
            result["experimentation_rate"] = float(obj["experimentation_rate"])
        if "wig" in obj:
            result["wig"] = str(obj["wig"])
    return result if result else None
