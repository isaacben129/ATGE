"""Parse gatekeeper output for APPROVED true/false per item. Detects thread tweets by numbered lines (1. 2. 3.)."""
import re


def _normalize_text_and_thread_seq(text: str) -> tuple[str, int | None]:
    """If text starts with 'N.' (thread numbering), return (stripped text, N-1). Else (text, None)."""
    text = text.strip()
    m = re.match(r"^(\d+)\.\s*(.*)$", text, re.DOTALL)
    if m:
        num = int(m.group(1))
        rest = m.group(2).strip()
        if 1 <= num <= 20:
            return rest, num - 1
    return text, None


def _strip_tweet_prefix(text: str) -> str:
    """If text starts with 'TWEET:' (case-insensitive), return the rest. Else return text."""
    t = text.strip()
    if t.upper().startswith("TWEET:"):
        return t[6:].strip()
    return t


def parse_approved_content(gatekeeper_output: str) -> list[dict]:
    """Parse gatekeeper output for TWEET: / APPROVED: / REASON: blocks. Returns list of {text, approved, topic?, hook_type?, thread_sequence?}."""
    approved_list = []
    lines = gatekeeper_output.strip().split("\n")
    current_text = ""
    for line in lines:
        if "APPROVED:" in line.upper():
            approved = "true" in line.lower()
            if current_text.strip():
                raw = _strip_tweet_prefix(current_text)
                text, thread_sequence = _normalize_text_and_thread_seq(raw)
                item = {"text": text, "approved": approved, "topic": "", "hook_type": ""}
                if thread_sequence is not None:
                    item["thread_sequence"] = thread_sequence
                approved_list.append(item)
            current_text = ""
        elif "REASON:" in line.upper():
            # REASON line follows APPROVED; do not add to current_text
            continue
        else:
            current_text += line + "\n"
    if current_text.strip():
        raw = _strip_tweet_prefix(current_text)
        text, thread_sequence = _normalize_text_and_thread_seq(raw)
        item = {"text": text, "approved": True, "topic": "", "hook_type": ""}
        if thread_sequence is not None:
            item["thread_sequence"] = thread_sequence
        approved_list.append(item)
    return approved_list
