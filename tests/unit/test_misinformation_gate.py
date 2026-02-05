"""Unit tests for misinformation gatekeeper parsing (mock LLM response -> approved/blocked)."""
import pytest
from atg_engine.utils.gatekeeper_parse import parse_approved_content, _strip_tweet_prefix


def test_strip_tweet_prefix():
    """TWEET: prefix is stripped so stored text is content only."""
    assert _strip_tweet_prefix("TWEET: Hello world") == "Hello world"
    assert _strip_tweet_prefix("tweet: lowercase") == "lowercase"
    assert _strip_tweet_prefix("No prefix here") == "No prefix here"


def test_parse_approved_content_tweet_prefix_format():
    """New format with TWEET: / APPROVED: / REASON: per piece."""
    text = (
        "TWEET: This is the actual tweet content.\n"
        "APPROVED: true\n"
        "REASON: opinion only\n\n"
        "TWEET: Unverifiable claim about X.\n"
        "APPROVED: false\n"
        "REASON: unverifiable factual claim"
    )
    out = parse_approved_content(text)
    assert len(out) == 2
    assert out[0]["text"] == "This is the actual tweet content."
    assert out[0]["approved"] is True
    assert out[1]["text"] == "Unverifiable claim about X."
    assert out[1]["approved"] is False


def test_parse_approved_content_single_approved():
    text = "This is a tweet.\nAPPROVED: true\nREASON: opinion only"
    out = parse_approved_content(text)
    assert len(out) >= 1
    assert any(item["approved"] for item in out)


def test_parse_approved_content_single_rejected():
    text = "Claim: The earth is flat.\nAPPROVED: false\nREASON: unverifiable claim"
    out = parse_approved_content(text)
    assert len(out) >= 1
    assert any(not item["approved"] for item in out)


def test_parse_approved_content_multiple():
    text = (
        "Tweet one.\nAPPROVED: true\nREASON: ok\n"
        "Tweet two.\nAPPROVED: false\nREASON: factual"
    )
    out = parse_approved_content(text)
    assert len(out) >= 2
