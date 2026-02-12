"""Viral spin & quote pipeline: discover by category -> breakdown -> spin and/or quote -> gatekeeper -> save."""
import logging
import re
from crewai import Crew, Process, Task

logger = logging.getLogger(__name__)

from atg_engine.agents import (
    create_breakdown_agent,
    create_spin_generator,
    create_curation_agent,
    create_misinformation_gatekeeper,
)
from atg_engine.config.env_validation import validate_env
from atg_engine.db.session import SessionLocal
from atg_engine.models import TweetCandidate, Persona
from atg_engine.services.bootstrap import ensure_bootstrap
from atg_engine.services.trending_content_discovery import (
    discover_by_categories,
    discover_trending_tweets,
)


def _fetch_persona_and_viral_context():
    db = SessionLocal()
    try:
        persona = db.query(Persona).first()
        if not persona:
            return None, "No persona defined yet.", {}, {}
        curation_ctx = persona.get_prompt_context("curation")
        writer_ctx = persona.get_prompt_context("writer")
        viral = persona.get_viral_content_context()
        return persona, curation_ctx, writer_ctx, viral
    finally:
        db.close()


def _parse_breakdowns(raw: str) -> list[dict]:
    """Parse breakdown agent output into list of dicts with tweet_id, matched_categories, formula, structure, why_it_works."""
    out = []
    block = re.compile(
        r"TWEET_ID:\s*(\S+)\s*\n"
        r"(?:MATCHED_CATEGORIES?:\s*(.+?)\s*\n)?"
        r"(?:FORMULA:\s*(.+?)\s*\n)?"
        r"(?:STRUCTURE:\s*(.+?)\s*\n)?"
        r"(?:WHY_IT_WORKS:\s*(.+?))(?=\s*TWEET_ID:|\s*\Z)",
        re.DOTALL | re.IGNORECASE,
    )
    for m in block.finditer(raw):
        tweet_id = (m.group(1) or "").strip()
        if not tweet_id:
            continue
        out.append({
            "tweet_id": tweet_id,
            "matched_categories": (m.group(2) or "").strip()[:200],
            "formula": (m.group(3) or "").strip()[:128],
            "structure": (m.group(4) or "").strip()[:500],
            "why_it_works": (m.group(5) or "").strip()[:500],
        })
    return out


def _parse_spins(raw: str) -> list[dict]:
    """Parse spin agent output: list of {tweet_id, spin_1, spin_2 (optional), formula_used}."""
    out = []
    block = re.compile(
        r"TWEET_ID:\s*(\S+)\s*\n"
        r"(?:SPIN_1:\s*(.+?)\s*\n)"
        r"(?:(?:SPIN_2:\s*(.+?)\s*\n)?)?"
        r"(?:FORMULA_USED:\s*(.+?))?(?=\s*TWEET_ID:|\s*\Z)",
        re.DOTALL | re.IGNORECASE,
    )
    for m in block.finditer(raw):
        tweet_id = (m.group(1) or "").strip()
        spin_1 = (m.group(2) or "").strip()
        if not tweet_id or not spin_1:
            continue
        spin_2 = (m.group(3) or "").strip() if m.group(3) else None
        formula = (m.group(4) or "").strip()[:128] if m.group(4) else ""
        out.append({
            "tweet_id": tweet_id,
            "spin_1": spin_1[:280],
            "spin_2": spin_2[:280] if spin_2 else None,
            "formula_used": formula,
        })
    return out


def _parse_quote_recommendations(raw: str) -> list[dict]:
    """Parse curation output: tweet_id, quote_text, reason."""
    out = []
    for m in re.finditer(
        r"TWEET_ID:\s*(\S+)\s*\n.*?QUOTE_TEXT:\s*(.+?)\s*\n.*?REASON:\s*(.+?)(?=\n\nTWEET_ID:|\Z)",
        raw,
        re.DOTALL | re.IGNORECASE,
    ):
        tid = (m.group(1) or "").strip()
        text = (m.group(2) or "").strip()[:280]
        if tid and text:
            out.append({"tweet_id": tid, "quote_text": text, "reason": (m.group(3) or "").strip()})
    return out


def _parse_approved_refs(raw: str) -> set[int]:
    """Parse gatekeeper output: CONTENT_REF: N APPROVED: true -> set of N. Do not match past next CONTENT_REF."""
    refs = set()
    for m in re.finditer(
        r"CONTENT_REF:\s*(\d+)\s*(?:(?!CONTENT_REF).)*?APPROVED:\s*true",
        raw,
        re.DOTALL | re.IGNORECASE,
    ):
        refs.add(int(m.group(1)))
    return refs


def run(**kwargs) -> str:
    mode = (kwargs.get("mode") or "both").lower()
    if mode not in ("spin", "quote", "both"):
        mode = "both"
    category_filter = kwargs.get("categories")
    if isinstance(category_filter, str):
        category_filter = [c.strip() for c in category_filter.split(",") if c.strip()] or None
    tweets_per_category = kwargs.get("tweets_per_category", 5)
    min_likes = kwargs.get("min_likes", 100)
    min_retweets = kwargs.get("min_retweets", 10)
    dry_run = kwargs.get("dry_run", False)
    verbose = kwargs.get("verbose", True)

    validate_env(require_llm=True, require_twitter=True)
    ensure_bootstrap()

    persona, curation_ctx, writer_ctx, viral = _fetch_persona_and_viral_context()
    content_categories = viral.get("content_categories") or {}
    tweet_formulas = viral.get("tweet_formulas") or {}

    if curation_ctx == "No persona defined yet.":
        logger.warning("Persona is empty. Run init-persona with a config that has content_categories and tweet_formulas for best results.")

    if content_categories:
        trending = discover_by_categories(
            content_categories,
            tweets_per_category=tweets_per_category,
            min_likes=min_likes,
            min_retweets=min_retweets,
            category_filter=category_filter,
        )
    else:
        trending = discover_trending_tweets(
            query=kwargs.get("query", ""),
            max_results=kwargs.get("max_results", 15),
            min_likes=min_likes,
            min_retweets=min_retweets,
        )
        for t in trending:
            t["matched_category"] = t.get("matched_category", "viral_content")

    if not trending:
        return "No viral tweets found. Try lower min_likes/min_retweets or add content_categories to persona."

    trending_summary = "\n\n".join([
        f"TWEET_ID: {t['tweet_id']}\n"
        f"Author: @{t.get('author_username', '?')}\n"
        f"Text: {t['text']}\n"
        f"Engagement: {t.get('likes', 0)} likes, {t.get('retweets', 0)} retweets\n"
        f"Matched category: {t.get('matched_category', 'viral_content')}"
        for t in trending
    ])

    categories_str = "\n".join(
        f"- {k}: {', '.join(v[:3]) if isinstance(v, list) else str(v)}..."
        for k, v in list(content_categories.items())[:12]
    ) if content_categories else "None specified."
    formulas_str = "\n".join(
        f"- {k}: {v.get('structure', '')} (e.g. \"{v.get('example', '')[:60]}...\")"
        for k, v in list(tweet_formulas.items())[:10]
    ) if tweet_formulas else "None specified."

    breakdown_agent = create_breakdown_agent()
    breakdown_task = Task(
        description=(
            "Analyze each viral tweet below. For each one, identify:\n"
            "1. Which content categories (from the list) it fits.\n"
            "2. Which tweet formula (from the list) it matches, or 'custom'.\n"
            "3. Structure: hook, tension, payoff in one line.\n"
            "4. Why it works (psychological/engagement reason).\n\n"
            f"Content categories:\n{categories_str}\n\n"
            f"Tweet formulas:\n{formulas_str}\n\n"
            f"Viral tweets:\n{trending_summary}\n\n"
            "Output exactly one block per tweet in this format:\n"
            "TWEET_ID: <id>\n"
            "MATCHED_CATEGORIES: <comma-separated category names>\n"
            "FORMULA: <formula name or custom>\n"
            "STRUCTURE: <one line>\n"
            "WHY_IT_WORKS: <one line>\n"
        ),
        expected_output=(
            "One block per tweet: TWEET_ID, MATCHED_CATEGORIES, FORMULA, STRUCTURE, WHY_IT_WORKS."
        ),
        agent=breakdown_agent,
    )

    crew_tasks = [breakdown_task]
    breakdown_result = None

    breakdown_crew = Crew(
        agents=[breakdown_agent],
        tasks=[breakdown_task],
        verbose=verbose,
    )
    result = breakdown_crew.kickoff()
    raw_breakdown = result.raw if hasattr(result, "raw") else str(result)
    breakdowns = _parse_breakdowns(raw_breakdown)
    if not breakdowns:
        return f"Breakdown agent produced no parseable output. Raw:\n{raw_breakdown}"

    breakdown_by_id = {b["tweet_id"]: b for b in breakdowns}
    for t in trending:
        tid = t.get("tweet_id")
        if tid and tid not in breakdown_by_id:
            breakdown_by_id[tid] = {
                "tweet_id": tid,
                "matched_categories": t.get("matched_category", "viral_content"),
                "formula": "",
                "structure": "",
                "why_it_works": "",
            }

    spin_recs: list[dict] = []
    quote_recs: list[dict] = []

    if mode in ("spin", "both"):
        spin_agent = create_spin_generator()
        breakdown_text = "\n\n".join([
            f"TWEET_ID: {b['tweet_id']}\n"
            f"Original tweet: {next((t['text'] for t in trending if t.get('tweet_id') == b['tweet_id']), '')}\n"
            f"MATCHED_CATEGORIES: {b['matched_categories']}\n"
            f"FORMULA: {b['formula']}\n"
            f"STRUCTURE: {b['structure']}\n"
            f"WHY_IT_WORKS: {b['why_it_works']}"
            for b in breakdowns
        ])
        spin_task = Task(
            description=(
                "Write 1–2 original tweets inspired by each viral tweet below. Use the persona's voice and tweet formulas. "
                "Same insight or structure, your own words. Every tweet under 280 characters.\n\n"
                f"Persona (writer) context:\n{writer_ctx}\n\n"
                f"Tweet formulas:\n{formulas_str}\n\n"
                f"Breakdowns (viral tweet + analysis):\n{breakdown_text}\n\n"
                "For each breakdown output:\n"
                "TWEET_ID: <original viral tweet id>\n"
                "SPIN_1: <your original tweet>\n"
                "SPIN_2: <optional second variant>\n"
                "FORMULA_USED: <which formula you applied>\n"
            ),
            expected_output="One block per tweet: TWEET_ID, SPIN_1, optional SPIN_2, FORMULA_USED. Each tweet under 280 chars.",
            agent=spin_agent,
        )
        spin_crew = Crew(agents=[spin_agent], tasks=[spin_task], verbose=verbose)
        spin_result = spin_crew.kickoff()
        spin_raw = spin_result.raw if hasattr(spin_result, "raw") else str(spin_result)
        spin_recs = _parse_spins(spin_raw)

    if mode in ("quote", "both"):
        curation_agent = create_curation_agent()
        breakdown_text = "\n\n".join([
            f"TWEET_ID: {b['tweet_id']}\n"
            f"Original: {next((t['text'] for t in trending if t.get('tweet_id') == b['tweet_id']), '')}\n"
            f"Categories: {b['matched_categories']}\n"
            f"Formula: {b['formula']}"
            for b in breakdowns
        ])
        quote_task = Task(
            description=(
                "For each viral tweet below, write quote-tweet commentary that adds your perspective. "
                "Use the persona's voice and formulas. Under 280 characters per quote.\n\n"
                f"Persona (curation) context:\n{curation_ctx}\n\n"
                f"Formulas:\n{formulas_str}\n\n"
                f"Viral tweets and breakdowns:\n{breakdown_text}\n\n"
                "For each tweet you recommend, output:\n"
                "TWEET_ID: <id>\n"
                "QUOTE_TEXT: <your commentary>\n"
                "REASON: <why quoting>\n"
            ),
            expected_output="One block per tweet: TWEET_ID, QUOTE_TEXT, REASON.",
            agent=curation_agent,
        )
        quote_crew = Crew(agents=[curation_agent], tasks=[quote_task], verbose=verbose)
        quote_result = quote_crew.kickoff()
        quote_raw = quote_result.raw if hasattr(quote_result, "raw") else str(quote_result)
        quote_recs = _parse_quote_recommendations(quote_raw)

    content_items: list[tuple[str, str, str, str, str]] = []
    for s in spin_recs:
        bid = breakdown_by_id.get(s["tweet_id"], {})
        cat = bid.get("matched_categories", "")
        formula = s.get("formula_used", "")
        content_items.append(("spin", s["tweet_id"], s["spin_1"], cat, formula))
        if s.get("spin_2"):
            content_items.append(("spin", s["tweet_id"], s["spin_2"], cat, formula))
    for q in quote_recs:
        bid = breakdown_by_id.get(q["tweet_id"], {})
        content_items.append(("quote", q["tweet_id"], q["quote_text"], bid.get("matched_categories", ""), "quote_tweet"))

    if not content_items:
        return "No spin or quote recommendations to gatekeep. Check agent outputs."

    gatekeeper_agent = create_misinformation_gatekeeper()
    numbered = "\n\n".join(
        f"CONTENT_REF: {i}\nTYPE: {typ}\nTWEET_ID: {tid}\nTEXT: {text}"
        for i, (typ, tid, text, _cat, _form) in enumerate(content_items, 1)
    )
    gate_task = Task(
        description=(
            "Review each content piece below for factual and policy compliance.\n\n"
            "Rules: Verifiable factual claims allowed only if verifiable; otherwise block. "
            "Opinions, satire, subjective: allow. No hate speech, impersonation, or Twitter ToS violations. "
            "When unsure, block.\n\n"
            f"Content:\n{numbered}\n\n"
            "Output for each CONTENT_REF: CONTENT_REF: N, APPROVED: true or false, REASON: one line."
        ),
        expected_output="For each item: CONTENT_REF: <n> APPROVED: true|false REASON: <line>",
        agent=gatekeeper_agent,
    )
    gate_crew = Crew(agents=[gatekeeper_agent], tasks=[gate_task], verbose=verbose)
    gate_result = gate_crew.kickoff()
    gate_raw = gate_result.raw if hasattr(gate_result, "raw") else str(gate_result)
    approved_refs = _parse_approved_refs(gate_raw)

    saved = 0
    if not dry_run:
        db = SessionLocal()
        try:
            for i, (typ, tweet_id, text, category, formula) in enumerate(content_items, 1):
                if i not in approved_refs:
                    continue
                text = (text or "").strip()
                if not text or len(text) > 280:
                    continue
                topic = category or "viral_content"
                hook_type = formula or ("quote_tweet" if typ == "quote" else "viral_spin")
                quote_tweet_id = tweet_id if typ == "quote" else None
                db.add(TweetCandidate(
                    text=text,
                    topic=topic,
                    hook_type=hook_type,
                    approved=True,
                    published=False,
                    quote_tweet_id=quote_tweet_id,
                ))
                saved += 1
            db.commit()
        finally:
            db.close()

    return (
        f"Viral pipeline: {len(trending)} tweets -> {len(breakdowns)} breakdowns. "
        f"Spins: {len(spin_recs)}, Quotes: {len(quote_recs)}. "
        f"Approved: {len(approved_refs)}. Saved: {saved}."
    )
