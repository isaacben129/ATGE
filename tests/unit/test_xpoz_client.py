"""Unit tests for xpoz_client parsing helpers (no network)."""
import pytest

from atg_engine.services.xpoz_client import (
    _parse_operation_id,
    _parse_posts_from_status,
    _parse_user_from_status,
    _post_to_metrics,
    _get_tool_text,
)


def test_parse_operation_id():
    """_parse_operation_id extracts operationId or operation_id from JSON."""
    assert _parse_operation_id('{"operationId": "op123"}') == "op123"
    assert _parse_operation_id('{"operation_id": "op456"}') == "op456"
    assert _parse_operation_id("") is None
    assert _parse_operation_id("{}") is None
    assert _parse_operation_id("not json") is None


def test_parse_posts_from_status():
    """_parse_posts_from_status extracts list of posts from result.data or result.posts."""
    assert _parse_posts_from_status("") == []
    assert _parse_posts_from_status('{"result": {"posts": [{"id": "1", "likeCount": 10}]}}') == [
        {"id": "1", "likeCount": 10}
    ]
    assert _parse_posts_from_status('{"result": {"data": [{"id": "2"}]}}') == [{"id": "2"}]
    assert _parse_posts_from_status('{"result": {"id": "3", "likeCount": 5}}') == [
        {"id": "3", "likeCount": 5}
    ]


def test_parse_user_from_status():
    """_parse_user_from_status extracts user with followersCount."""
    assert _parse_user_from_status('{"result": {"followersCount": 100}}') == {"followersCount": 100}
    assert _parse_user_from_status('{"result": {"followers_count": 200}}') == {"followers_count": 200}
    assert _parse_user_from_status("") is None
    assert _parse_user_from_status("{}") is None


def test_post_to_metrics():
    """_post_to_metrics maps Xpoz post fields to impressions, likes, retweets, replies."""
    out = _post_to_metrics({
        "id": "123",
        "impressionCount": 1000,
        "likeCount": 10,
        "retweetCount": 2,
        "replyCount": 1,
    })
    assert out == {"impressions": 1000, "likes": 10, "retweets": 2, "replies": 1}
    assert _post_to_metrics({}) == {}
    assert _post_to_metrics({"id": ""}) == {}


def test_get_tool_text():
    """_get_tool_text extracts text from MCP result content (dict shape)."""
    assert _get_tool_text({"content": [{"text": "hi"}]}) == "hi"
    assert _get_tool_text({"content": []}) == ""
    assert _get_tool_text(None) == ""
