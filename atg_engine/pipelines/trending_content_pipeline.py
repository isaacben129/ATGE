"""Trending content pipeline: discover trending tweets, curate, gatekeeper, save for approval."""
import logging
import re
from crewai import Crew, Process, Task

logger = logging.getLogger(__name__)

from atg_engine.agents import create_curation_agent, create_misinformation_gatekeeper
from atg_engine.config.env_validation import validate_env
from atg_engine.db.session import SessionLocal
from atg_engine.models import TweetCandidate, Persona
from atg_engine.services.bootstrap import ensure_bootstrap
from atg_engine.services.trending_content_discovery import discover_trending_tweets


def _fetch_persona_context() -> str:
    db = SessionLocal()
    try:
        persona = db.query(Persona).first()
        return persona.to_prompt_context() if persona else "No persona defined yet."
    finally:
        db.close()


def _parse_curation_output(raw_output: str) -> list[dict]:
    """Parse curation agent output into structured recommendations."""
    recommendations = []
    # Match blocks: TWEET_ID: <id> ... QUOTE_TEXT: <text> ... REASON: <reason>
    block_pattern = re.compile(
        r"TWEET_ID:\s*(\S+)\s+.*?QUOTE_TEXT:\s*(.+?)(?=TWEET_ID:|REASON:|\Z)"
        r".*?REASON:\s*(.+?)(?=TWEET_ID:|\Z)",
        re.DOTALL | re.IGNORECASE,
    )
    for m in block_pattern.finditer(raw_output):
        tweet_id = m.group(1).strip()
        quote_text = m.group(2).strip()
        reason = m.group(3).strip()
        if tweet_id and quote_text:
            recommendations.append({
                "tweet_id": tweet_id,
                "quote_text": quote_text[:280],
                "reason": reason,
            })
    # Fallback: simpler pattern if above misses
    if not recommendations:
        simple = re.findall(
            r"TWEET_ID:\s*(\S+)\s*\n.*?QUOTE_TEXT:\s*(.+?)\s*\n.*?REASON:\s*(.+?)(?=\n\n|TWEET_ID:|\Z)",
            raw_output,
            re.DOTALL | re.IGNORECASE,
        )
        for tweet_id, quote_text, reason in simple:
            if tweet_id and quote_text:
                recommendations.append({
                    "tweet_id": tweet_id.strip(),
                    "quote_text": quote_text.strip()[:280],
                    "reason": reason.strip(),
                })
    return recommendations


def _parse_approved_ids(raw_output: str) -> set[str]:
    """Extract tweet IDs that were approved by the gatekeeper."""
    approved = set()
    for m in re.finditer(r"TWEET_ID:\s*(\S+).*?APPROVED:\s*true", raw_output, re.DOTALL | re.IGNORECASE):
        approved.add(m.group(1).strip())
    return approved


def run(**kwargs) -> str:
    validate_env(require_llm=True, require_twitter=True)
    ensure_bootstrap()
    persona_context = _fetch_persona_context()
    if persona_context == "No persona defined yet.":
        logger.warning(
            "Persona is empty. Curation may be off-brand. Set PERSONA_CONFIG_PATH or run: python -m atg_engine init-persona --config <path>"
        )

    trending = discover_trending_tweets(
        query=kwargs.get("query", ""),
        max_results=kwargs.get("max_results", 10),
        min_likes=kwargs.get("min_likes", 100),
        min_retweets=kwargs.get("min_retweets", 10),
    )

    if not trending:
        return "No trending tweets found matching criteria."

    curation_agent = create_curation_agent()
    gatekeeper_agent = create_misinformation_gatekeeper()

    trending_summary = "\n\n".join([
        f"Tweet ID: {t['tweet_id']}\n"
        f"Author: @{t['author_username']}\n"
        f"Text: {t['text']}\n"
        f"Engagement: {t['likes']} likes, {t['retweets']} retweets"
        for t in trending
    ])

    curation_task = Task(
        description=(
            f"Review the following trending tweets and recommend which ones to quote or repost.\n\n"
            f"Persona context: {persona_context}\n\n"
            f"Trending tweets:\n{trending_summary}\n\n"
            f"Evaluate each tweet based on:\n"
            f"1. Relevance to the persona and audience\n"
            f"2. Quality and engagement potential\n"
            f"3. Alignment with brand voice\n"
            f"4. Potential for adding value through your quote\n\n"
            f"For each tweet you recommend, provide:\n"
            f"- TWEET_ID: <original tweet ID>\n"
            f"- QUOTE_TEXT: <your quote text to add, under 280 characters>\n"
            f"- REASON: <why this is worth quoting>\n"
        ),
        expected_output=(
            "For each recommended tweet, output exactly:\n"
            "TWEET_ID: <id>\n"
            "QUOTE_TEXT: <your quote text>\n"
            "REASON: <reason>\n\n"
            "Only recommend tweets that align with the persona and would benefit from your commentary."
        ),
        agent=curation_agent,
    )

    gatekeeper_task = Task(
        description=(
            "Review the curation recommendations for factual and policy compliance.\n\n"
            "Input: Recommendations from the curation agent (TWEET_ID, QUOTE_TEXT, REASON for each).\n\n"
            "Rules:\n"
            "- Verifiable factual claims are allowed only if verifiable; otherwise block.\n"
            "- Opinions, satire, and clearly subjective statements: allow.\n"
            "- If unsure whether something is factual or verifiable: block.\n"
            "- No hate speech, impersonation, or Twitter ToS violations.\n\n"
            "Output APPROVED: true or false for each recommendation."
        ),
        expected_output=(
            "For each recommendation, output:\n"
            "TWEET_ID: <id>\n"
            "APPROVED: true\n"
            "REASON: <reason>\n"
            "or\n"
            "TWEET_ID: <id>\n"
            "APPROVED: false\n"
            "REASON: <reason>\n"
        ),
        agent=gatekeeper_agent,
        context=[curation_task],
    )

    crew = Crew(
        agents=[curation_agent, gatekeeper_agent],
        tasks=[curation_task, gatekeeper_task],
        process=Process.sequential,
        verbose=kwargs.get("verbose", True),
    )

    result = crew.kickoff()
    raw = result.raw if hasattr(result, "raw") else str(result)

    recommendations = _parse_curation_output(raw)
    approved_ids = _parse_approved_ids(raw)

    if not kwargs.get("dry_run", False):
        db = SessionLocal()
        try:
            for rec in recommendations:
                if rec["tweet_id"] not in approved_ids:
                    continue
                quote_text = (rec["quote_text"] or "").strip()
                if not quote_text or len(quote_text) > 280:
                    continue
                candidate = TweetCandidate(
                    text=quote_text,
                    topic="trending_content",
                    hook_type="quote_tweet",
                    approved=True,
                    published=False,
                    quote_tweet_id=rec["tweet_id"],
                )
                db.add(candidate)
            db.commit()
        finally:
            db.close()

    return (
        f"Found {len(trending)} trending tweets. Recommended {len(recommendations)} for quoting. "
        f"Approved {len(approved_ids)}.\n\nRaw output:\n{raw}"
    )
