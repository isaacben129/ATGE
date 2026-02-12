"""
Xpoz MCP client: tweet metrics batch and user follower count.
Uses MCP at https://mcp.xpoz.ai/mcp with Bearer token. Do not log or expose XPOZ_API_KEY.
"""
import asyncio
import json
import logging
import time
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from atg_engine.config.settings import XPOZ_API_KEY

logger = logging.getLogger(__name__)

XPOZ_MCP_URL = "https://mcp.xpoz.ai/mcp"
POLL_INTERVAL_SEC = 2.0
POLL_TIMEOUT_SEC = 60.0
BATCH_SIZE = 100

_DEFAULT_METRICS = {"impressions": 0, "likes": 0, "retweets": 0, "replies": 0}


def _get_tool_text(result: Any) -> str:
    """Extract text from MCP CallToolResult (content list with text)."""
    if result is None:
        return ""
    content = getattr(result, "content", None) or result.get("content") if isinstance(result, dict) else None
    if not content:
        return ""
    if isinstance(content, list) and len(content) > 0:
        first = content[0]
        text = getattr(first, "text", None) if not isinstance(first, dict) else first.get("text")
        return text or ""
    return ""


def _parse_operation_id(text: str) -> str | None:
    """Parse operation ID from Xpoz tool response (JSON with operationId or similar)."""
    if not text or not text.strip():
        return None
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data.get("operationId") or data.get("operation_id")
        return None
    except json.JSONDecodeError:
        return None


def _parse_posts_from_status(text: str) -> list[dict[str, Any]]:
    """Parse list of posts from checkOperationStatus result (e.g. data.posts or content array)."""
    if not text or not text.strip():
        return []
    try:
        data = json.loads(text)
        if not isinstance(data, dict):
            return []
        # Try common shapes: result.data, result.posts, data, posts
        result = data.get("result", data)
        if isinstance(result, dict):
            posts = result.get("posts") or result.get("data") or result.get("content")
        else:
            posts = None
        if isinstance(posts, list):
            return posts
        # Single post
        if isinstance(result, dict) and "id" in result:
            return [result]
        return []
    except json.JSONDecodeError:
        return []


def _parse_user_from_status(text: str) -> dict[str, Any] | None:
    """Parse user object from checkOperationStatus (e.g. followersCount)."""
    if not text or not text.strip():
        return None
    try:
        data = json.loads(text)
        if not isinstance(data, dict):
            return None
        result = data.get("result", data)
        if isinstance(result, dict) and ("followersCount" in result or "followers_count" in result):
            return result
        return None
    except json.JSONDecodeError:
        return None


def _post_to_metrics(post: dict[str, Any]) -> dict[str, Any]:
    """Map Xpoz post (retweetCount, replyCount, likeCount, impressionCount) to our shape."""
    tid = str(post.get("id", ""))
    if not tid:
        return {}
    return dict(
        impressions=int(post.get("impressionCount", post.get("impression_count", 0)) or 0),
        likes=int(post.get("likeCount", post.get("like_count", 0)) or 0),
        retweets=int(post.get("retweetCount", post.get("retweet_count", 0)) or 0),
        replies=int(post.get("replyCount", post.get("reply_count", 0)) or 0),
    )


async def _call_tool_and_poll(
    session: ClientSession,
    tool_name: str,
    arguments: dict[str, Any],
    poll_tool: str = "checkOperationStatus",
    poll_timeout: float = POLL_TIMEOUT_SEC,
    poll_interval: float = POLL_INTERVAL_SEC,
) -> str:
    """Call tool that returns operation ID, then poll checkOperationStatus until done; return final result text."""
    result = await session.call_tool(tool_name, arguments)
    text = _get_tool_text(result)
    op_id = _parse_operation_id(text)
    if not op_id:
        return text
    deadline = time.monotonic() + poll_timeout
    last_text = ""
    while time.monotonic() < deadline:
        await asyncio.sleep(poll_interval)
        status_result = await session.call_tool(poll_tool, {"operationId": op_id})
        status_text = _get_tool_text(status_result)
        last_text = status_text or last_text
        if not status_text:
            continue
        try:
            data = json.loads(status_text)
            result = data.get("result", data) if isinstance(data, dict) else None
            status = result.get("status") if isinstance(result, dict) else None
            if status == "completed" or status == "succeeded":
                return status_text
            if isinstance(result, dict) and (result.get("data") or result.get("posts") is not None):
                return status_text
        except json.JSONDecodeError:
            pass
    return last_text


async def _get_tweet_metrics_batch_async(tweet_ids: list[str]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    if not tweet_ids or not XPOZ_API_KEY:
        return out
    headers = {"Authorization": f"Bearer {XPOZ_API_KEY}"}
    try:
        async with streamablehttp_client(
            XPOZ_MCP_URL, headers=headers, timeout=60.0
        ) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                for i in range(0, len(tweet_ids), BATCH_SIZE):
                    chunk = tweet_ids[i : i + BATCH_SIZE]
                    args: dict[str, Any] = {
                        "postIds": chunk,
                        "fields": ["id", "retweetCount", "replyCount", "likeCount", "impressionCount"],
                    }
                    try:
                        result_text = await _call_tool_and_poll(
                            session, "getTwitterPostsByIds", args
                        )
                        posts = _parse_posts_from_status(result_text)
                        for post in posts:
                            m = _post_to_metrics(post)
                            if m:
                                tid = str(post.get("id", ""))
                                out[tid] = m
                    except Exception as e:
                        logger.warning("Xpoz getTwitterPostsByIds failed for chunk: %s", e)
                        raise
    except Exception as e:
        if hasattr(e, "response") and e.response is not None:
            status = getattr(e.response, "status_code", None)
            if status in (401, 403, 429):
                raise
        logger.warning("Xpoz MCP request failed: %s", type(e).__name__)
        raise
    return out


async def _get_user_follower_count_async(username: str) -> int | None:
    if not username or not XPOZ_API_KEY:
        return None
    headers = {"Authorization": f"Bearer {XPOZ_API_KEY}"}
    try:
        async with streamablehttp_client(
            XPOZ_MCP_URL, headers=headers, timeout=60.0
        ) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result_text = await _call_tool_and_poll(
                    session,
                    "getTwitterUserByUsername",
                    {"username": username.lstrip("@")},
                )
                user = _parse_user_from_status(result_text)
                if user is None:
                    return None
                return int(
                    user.get("followersCount", user.get("followers_count", 0)) or 0
                )
    except Exception as e:
        logger.warning("Xpoz getTwitterUserByUsername failed: %s", type(e).__name__)
        raise
    return None


def get_tweet_metrics_batch(tweet_ids: list[str]) -> dict[str, dict[str, Any]]:
    """Sync wrapper: get tweet metrics from Xpoz MCP (getTwitterPostsByIds + checkOperationStatus)."""
    try:
        return asyncio.run(_get_tweet_metrics_batch_async(tweet_ids))
    except Exception as e:
        raise RuntimeError(f"Xpoz tweet metrics failed: {e}") from e


def get_user_follower_count(username: str) -> int | None:
    """Sync wrapper: get follower count for a Twitter username via Xpoz (getTwitterUserByUsername)."""
    try:
        return asyncio.run(_get_user_follower_count_async(username))
    except Exception as e:
        raise RuntimeError(f"Xpoz user lookup failed: {e}") from e
