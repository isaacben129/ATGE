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
POLL_INTERVAL_SEC = 5.0  # Xpoz recommends 5 seconds
POLL_TIMEOUT_SEC = 300.0  # 5 minutes - Xpoz operations can take time
BATCH_SIZE = 100

_DEFAULT_METRICS = {"impressions": 0, "likes": 0, "retweets": 0, "replies": 0}


def _get_tool_text(result: Any) -> str:
    """Extract text from MCP CallToolResult (content list with text)."""
    if result is None:
        return ""
    # Try result.content (object attribute)
    content = getattr(result, "content", None)
    # If not found, try result.get("content") (dict access)
    if content is None and isinstance(result, dict):
        content = result.get("content")
    # If still not found, try result.result.content (nested)
    if content is None:
        result_obj = getattr(result, "result", None) or (result.get("result") if isinstance(result, dict) else None)
        if result_obj:
            content = getattr(result_obj, "content", None) or (result_obj.get("content") if isinstance(result_obj, dict) else None)
    if not content:
        return ""
    if isinstance(content, list) and len(content) > 0:
        first = content[0]
        text = getattr(first, "text", None) if not isinstance(first, dict) else first.get("text")
        return text or ""
    return ""


def _parse_operation_id(text: str) -> str | None:
    """Parse operation ID from Xpoz tool response (text format: 'operationId: op_...' or JSON)."""
    if not text or not text.strip():
        logger.debug("_parse_operation_id: empty text")
        return None
    # Try text format first: "operationId: op_..."
    import re
    match = re.search(r'operationId:\s*([^\s\n]+)', text, re.IGNORECASE)
    if match:
        op_id = match.group(1).strip()
        logger.debug("_parse_operation_id: found operationId (text format): %s", op_id)
        return op_id
    # Try JSON format
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            op_id = data.get("operationId") or data.get("operation_id") or data.get("result", {}).get("operationId")
            if op_id:
                logger.debug("_parse_operation_id: found operationId (JSON format): %s", op_id)
                return op_id
    except json.JSONDecodeError:
        pass
    logger.debug("_parse_operation_id: no operationId found in text (first 200 chars): %s", text[:200])
    return None


def _parse_posts_from_status(text: str) -> list[dict[str, Any]]:
    """Parse list of posts from checkOperationStatus result (YAML or JSON format)."""
    logger.debug("_parse_posts_from_status called with text length: %s", len(text) if text else 0)
    if not text or not text.strip():
        logger.debug("_parse_posts_from_status: empty text")
        return []
    # Try YAML first (Xpoz returns YAML format)
    # Xpoz returns YAML with keys like "results[138]" which PyYAML can handle
    try:
        import yaml
        # Try full text first
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError:
            # If that fails, try parsing just the data section
            if "data:" in text:
                data_part = text.split("data:", 1)[1].strip()
                data = yaml.safe_load(f"data:\n{data_part}")
            else:
                raise
        logger.debug("YAML parsed successfully, type: %s, keys: %s", type(data), list(data.keys()) if isinstance(data, dict) else "not dict")
        if isinstance(data, dict):
            # Check data.results (YAML format)
            data_obj = data.get("data", {})
            logger.debug("data_obj type: %s, keys: %s", type(data_obj), list(data_obj.keys()) if isinstance(data_obj, dict) else "not dict")
            if isinstance(data_obj, dict):
                # Results can be under results[0], results[153], etc. (keys like "results[153]")
                # Or just "results" as a list
                all_posts = []
                for key, value in data_obj.items():
                    logger.debug("Checking key: %s, value type: %s", key, type(value))
                    if key.startswith("results") and isinstance(value, list):
                        logger.debug("Found results list with %s items", len(value))
                        all_posts.extend(value)
                    elif key == "results" and isinstance(value, list):
                        logger.debug("Found results list with %s items", len(value))
                        all_posts.extend(value)
                if all_posts:
                    logger.debug("Returning %s posts from YAML", len(all_posts))
                    return all_posts
            # Also check top-level results
            if isinstance(data.get("results"), list):
                logger.debug("Found top-level results with %s items", len(data.get("results")))
                return data.get("results")
    except ImportError:
        logger.debug("PyYAML not available, skipping YAML parsing")
    except yaml.YAMLError as e:
        logger.debug("YAML parse error: %s, trying regex extraction", e)
        # Fallback: extract the results section and parse it as YAML
        import re
        # Find the results[XXX]: section and extract everything until the next top-level key or end
        results_match = re.search(r'results\[\d+\]:\s*\n((?:\s+-\s+.*(?:\n|$))+)', text, re.MULTILINE | re.DOTALL)
        if results_match:
            results_yaml = results_match.group(1)
            try:
                # Parse the YAML list (indented items)
                posts_list = yaml.safe_load(results_yaml)
                if isinstance(posts_list, list):
                    logger.debug("Extracted %s posts via regex+YAML", len(posts_list))
                    return posts_list
            except Exception as e2:
                logger.debug("Regex+YAML parsing failed: %s", e2)
                # Last resort: try to parse each item individually
                # Match each "- id: ..." block with all its properties
                item_pattern = r'^\s+-\s+id:\s+"([^"]+)"\s*\n((?:\s+\w+:\s+.*\n?)*)'
                items = re.findall(item_pattern, text, re.MULTILINE)
                if items:
                    posts_list = []
                    for item_id, item_content in items:
                        post = {"id": item_id}
                        # Parse the rest of the fields
                        for line in item_content.split('\n'):
                            if ':' in line:
                                key, value = line.split(':', 1)
                                key = key.strip()
                                value = value.strip().strip('"').strip("'")
                                post[key] = value
                        posts_list.append(post)
                    if posts_list:
                        logger.debug("Extracted %s posts via manual parsing", len(posts_list))
                        return posts_list
    except Exception as e:
        logger.debug("YAML parsing exception: %s", e, exc_info=True)
    
    # Try JSON format
    try:
        data = json.loads(text)
        if not isinstance(data, dict):
            return []
        # Try common shapes: result.data, result.posts, result.results, data, posts, results
        result = data.get("result", data)
        if isinstance(result, dict):
            posts = result.get("posts") or result.get("data") or result.get("content") or result.get("results")
            # Also check for nested result.data or result.result
            if not posts:
                nested_result = result.get("result")
                if isinstance(nested_result, dict):
                    posts = nested_result.get("posts") or nested_result.get("data") or nested_result.get("results")
            # Check pagination object
            if not posts:
                pagination = result.get("pagination")
                if isinstance(pagination, dict):
                    posts = pagination.get("results") or pagination.get("data")
        else:
            posts = None
        if isinstance(posts, list):
            return posts
        # Single post
        if isinstance(result, dict) and "id" in result:
            return [result]
        return []
    except json.JSONDecodeError:
        pass
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
    logger.debug("_call_tool_and_poll: got text (first 300 chars): %s", (text or "")[:300])
    op_id = _parse_operation_id(text)
    if not op_id:
        logger.debug("No operationId found in response, returning text as-is (length: %s)", len(text) if text else 0)
        return text
    logger.debug("Found operationId: %s, starting polling", op_id)
    deadline = time.monotonic() + poll_timeout
    last_text = text
    poll_count = 0
    while time.monotonic() < deadline:
        await asyncio.sleep(poll_interval)
        poll_count += 1
        try:
            status_result = await session.call_tool(poll_tool, {"operationId": op_id})
            status_text = _get_tool_text(status_result)
            if status_text:
                last_text = status_text  # Always update last_text with new response
                logger.debug("Poll %s: status_text length=%s, first 200 chars: %s", poll_count, len(status_text), status_text[:200])
            else:
                logger.debug("Poll %s: empty status_text", poll_count)
                continue
            # Try parsing as JSON first
            try:
                data = json.loads(status_text)
                result_obj = data.get("result", data) if isinstance(data, dict) else data
                if isinstance(result_obj, dict):
                    status = result_obj.get("status")
                    if status == "completed" or status == "succeeded":
                        logger.debug("Operation completed after %s polls", poll_count)
                        return status_text
                    # Check if we have data/posts even if status isn't "completed"
                    if result_obj.get("data") or result_obj.get("posts"):
                        logger.debug("Found data in response after %s polls", poll_count)
                        return status_text
            except json.JSONDecodeError:
                # Not JSON, might be text format - check for "status: completed" or "success: true"
                if "status: completed" in status_text.lower() or "status: succeeded" in status_text.lower():
                    logger.debug("Operation completed (text format) after %s polls", poll_count)
                    return status_text
                # Check if it contains actual data (posts array or similar)
                if '"posts"' in status_text or '"data"' in status_text or 'tableName:' in status_text:
                    logger.debug("Found data indicators in text format after %s polls", poll_count)
                    return status_text
        except Exception as e:
            logger.debug("Poll %s failed: %s", poll_count, e, exc_info=True)
            if poll_count >= 3:  # After a few failures, return what we have
                break
    logger.debug("Polling timeout after %s polls, returning last_text (length=%s)", poll_count, len(last_text))
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


async def _search_tweets_by_keywords_async(keywords: str, limit: int = 100) -> list[dict[str, Any]]:
    """Search tweets by keywords using Xpoz getTwitterPostsByKeywords."""
    if not keywords or not XPOZ_API_KEY:
        return []
    headers = {"Authorization": f"Bearer {XPOZ_API_KEY}"}
    try:
        async with streamablehttp_client(
            XPOZ_MCP_URL, headers=headers, timeout=60.0
        ) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                args: dict[str, Any] = {
                    "query": keywords,  # Xpoz uses "query" parameter name
                    "limit": min(limit, 100),  # Xpoz max is 100 per page
                }
                result_text = await _call_tool_and_poll(
                    session, "getTwitterPostsByKeywords", args
                )
                logger.debug("Xpoz search result_text length: %s", len(result_text) if result_text else 0)
                logger.debug("Xpoz search result_text (first 2000 chars): %s", (result_text or "")[:2000])
                if not result_text:
                    logger.warning("Xpoz search returned empty result_text")
                    return []
                # Try to parse as JSON to see structure
                try:
                    import json
                    data = json.loads(result_text)
                    logger.debug("Result is valid JSON, keys: %s", list(data.keys()) if isinstance(data, dict) else "not dict")
                    if isinstance(data, dict):
                        result_obj = data.get("result", data)
                        if isinstance(result_obj, dict):
                            logger.debug("Result object keys: %s", list(result_obj.keys()))
                except json.JSONDecodeError:
                    logger.debug("Result is not JSON, checking for text patterns")
                posts = _parse_posts_from_status(result_text)
                logger.debug("Parsed posts count: %s", len(posts) if posts else 0)
                if posts and len(posts) > 0:
                    logger.debug("Sample post keys: %s", list(posts[0].keys()))
                return posts if posts is not None else []
    except Exception as e:
        logger.warning("Xpoz getTwitterPostsByKeywords failed: %s", e, exc_info=True)
        raise


def search_tweets_by_keywords(keywords: str, limit: int = 100) -> list[dict[str, Any]]:
    """Sync wrapper: search tweets by keywords via Xpoz (getTwitterPostsByKeywords)."""
    try:
        result = asyncio.run(_search_tweets_by_keywords_async(keywords, limit))
        return result if result is not None else []
    except Exception as e:
        raise RuntimeError(f"Xpoz search failed: {e}") from e
