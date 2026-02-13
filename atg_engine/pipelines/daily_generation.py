"""Daily generation pipeline: ideas -> hooks -> writer -> thread -> gatekeeper -> save approved."""
import json
import logging
import re
import uuid
from crewai import Crew, Process, Task

logger = logging.getLogger(__name__)

from atg_engine.agents import (
    create_idea_generator,
    create_hook_generator,
    create_writer,
    create_thread_builder,
    create_misinformation_gatekeeper,
    create_quality_scorer,
)
from atg_engine.db.session import SessionLocal
from atg_engine.config.env_validation import validate_env
from atg_engine.config.settings import MIN_QUALITY_SCORE
from atg_engine.models import TweetCandidate, VoiceGenome, StrategyState, Persona, TweetPerformance
from atg_engine.services.bootstrap import ensure_bootstrap
from atg_engine.services.trending_content_discovery import discover_by_categories, discover_trending_tweets
from atg_engine.utils.gatekeeper_parse import (
    _normalize_text_and_thread_seq,
    _strip_tweet_prefix,
    parse_approved_content,
)
from atg_engine.utils.quality_parse import parse_quality_scores, _normalize_tweet_text


def _fetch_context():
    ensure_bootstrap()
    db = SessionLocal()
    try:
        persona = db.query(Persona).first()
        genome = db.query(VoiceGenome).order_by(VoiceGenome.last_updated.desc()).first()
        strategy = db.query(StrategyState).order_by(StrategyState.last_reviewed.desc()).first()
        genome_json = "{}"
        if genome:
            genome_json = json.dumps({
                "tone_traits": genome.get_tone_traits_list(),
                "risk_tolerance": genome.risk_tolerance,
                "aggressiveness": genome.aggressiveness,
                "humor_level": genome.humor_level,
            })
        strategy_json = "{}"
        if strategy:
            strategy_json = json.dumps({
                "daily_post_target": strategy.daily_post_target,
                "thread_ratio": strategy.thread_ratio,
                "experimentation_rate": strategy.experimentation_rate,
            })
        no_persona_msg = "No persona defined yet."
        if not persona or persona.get_prompt_context("full") == no_persona_msg:
            logger.warning(
                "Persona is empty. Content may be off-brand. Set PERSONA_CONFIG_PATH or add persona_mila.json and re-run, or run: python -m atg_engine init-persona --config <path>"
            )
        return genome_json, strategy_json, persona
    finally:
        db.close()


def _fetch_performance_insights(persona: Persona | None, limit: int = 5) -> str:
    """Fetch insights from top-performing tweets to guide idea generation."""
    if not persona:
        return ""
    db = SessionLocal()
    try:
        # Get top performing tweets with their candidate data
        top_perfs = (
            db.query(TweetPerformance)
            .join(TweetCandidate, TweetPerformance.candidate_id == TweetCandidate.id)
            .filter(
                TweetPerformance.engagement_rate > 0,
                TweetCandidate.text.is_not(None),
            )
            .order_by(TweetPerformance.engagement_rate.desc())
            .limit(limit)
            .all()
        )
        
        if not top_perfs:
            return ""
        
        insights = []
        insights.append(f"Top {len(top_perfs)} performing tweets (use these patterns):")
        for perf in top_perfs:
            candidate = db.query(TweetCandidate).filter(TweetCandidate.id == perf.candidate_id).first()
            if candidate:
                topic = candidate.topic or "general"
                hook_type = candidate.hook_type or "unknown"
                text_preview = candidate.text[:100] + "..." if len(candidate.text) > 100 else candidate.text
                insights.append(
                    f"  Engagement: {perf.engagement_rate:.2f}% | Topic: {topic} | Hook: {hook_type} | Text: \"{text_preview}\""
                )
        return "\n".join(insights)
    except Exception as e:
        logger.warning(f"Failed to fetch performance insights: {e}")
        return ""
    finally:
        db.close()


def _fetch_trending_content(persona: Persona | None, max_results: int = 5) -> str:
    """Fetch trending content relevant to persona categories."""
    if not persona:
        return ""
    try:
        viral_context = persona.get_viral_content_context()
        content_categories = viral_context.get("content_categories") or {}
        
        if content_categories:
            trending = discover_by_categories(
                content_categories,
                tweets_per_category=2,
                min_likes=50,
                min_retweets=5,
            )
        else:
            trending = discover_trending_tweets(
                max_results=max_results,
                min_likes=50,
                min_retweets=5,
            )
        
        if not trending:
            return ""
        
        trending_summary = []
        trending_summary.append(f"Trending topics (consider these angles):")
        for t in trending[:max_results]:
            text_preview = t.get("text", "")[:80] + "..." if len(t.get("text", "")) > 80 else t.get("text", "")
            engagement = t.get("likes", 0) + t.get("retweets", 0)
            category = t.get("matched_category", "general")
            trending_summary.append(
                f"  Category: {category} | Engagement: {engagement} | \"{text_preview}\""
            )
        return "\n".join(trending_summary)
    except Exception as e:
        logger.warning(f"Failed to fetch trending content: {e}")
        return ""


def _save_approved_only(approved_list: list[dict], quality_scores: dict[str, float] | None = None, dry_run: bool = False):
    if dry_run:
        return
    db = SessionLocal()
    try:
        # Group consecutive items with thread_sequence 0,1,2,... into one thread_id
        i = 0
        while i < len(approved_list):
            item = approved_list[i]
            if not item.get("approved"):
                i += 1
                continue
            text = item.get("text", "").strip()
            if not text or len(text) > 280:
                i += 1
                continue
            
            # Check quality score threshold
            quality_score = None
            if quality_scores:
                # Normalize text for matching (strip quotes, normalize whitespace)
                normalized_text = _normalize_tweet_text(text)
                # Try exact match first
                quality_score = quality_scores.get(text)
                # Try normalized match (without quotes)
                if quality_score is None:
                    quality_score = quality_scores.get(normalized_text)
                # Try thread-normalized match
                if quality_score is None:
                    norm_text, _ = _normalize_text_and_thread_seq(text)
                    if norm_text:
                        quality_score = quality_scores.get(_normalize_tweet_text(norm_text))
                # Try stripped match
                if quality_score is None:
                    quality_score = quality_scores.get(text.strip())
                    if quality_score is None:
                        quality_score = quality_scores.get(normalized_text.strip())
            
            # Filter by minimum quality score
            if quality_score is not None and quality_score < MIN_QUALITY_SCORE:
                logger.info(f"Skipping low-quality content (score {quality_score:.1f} < {MIN_QUALITY_SCORE}): {text[:50]}...")
                i += 1
                continue
            
            seq = item.get("thread_sequence")
            if seq is not None and seq == 0:
                thread_id = str(uuid.uuid4())
                j = i + 1
                while j < len(approved_list) and approved_list[j].get("approved") and approved_list[j].get("thread_sequence") == (j - i):
                    j += 1
                for k in range(i, j):
                    t = approved_list[k].get("text", "").strip()
                    if not t or len(t) > 280:
                        continue
                    # Get quality score for this thread tweet
                    thread_quality = None
                    if quality_scores:
                        normalized_t = _normalize_tweet_text(t)
                        thread_quality = quality_scores.get(t)
                        if thread_quality is None:
                            thread_quality = quality_scores.get(normalized_t)
                        if thread_quality is None:
                            norm_t, _ = _normalize_text_and_thread_seq(t)
                            if norm_t:
                                thread_quality = quality_scores.get(_normalize_tweet_text(norm_t))
                            if thread_quality is None:
                                thread_quality = quality_scores.get(t.strip())
                                if thread_quality is None:
                                    thread_quality = quality_scores.get(normalized_t.strip())
                    cand = TweetCandidate(
                        text=t,
                        tone_traits="[]",
                        topic=approved_list[k].get("topic", ""),
                        hook_type=approved_list[k].get("hook_type", ""),
                        risk_score=0.0,
                        quality_score=thread_quality,
                        approved=True,
                        published=False,
                        thread_id=thread_id,
                        thread_sequence=approved_list[k].get("thread_sequence"),
                    )
                    db.add(cand)
                i = j
                continue
            if seq is not None and seq > 0:
                i += 1
                continue
            candidate = TweetCandidate(
                text=text,
                tone_traits="[]",
                topic=item.get("topic", ""),
                hook_type=item.get("hook_type", ""),
                risk_score=0.0,
                quality_score=quality_score,
                approved=True,
                published=False,
                thread_id=None,
                thread_sequence=None,
            )
            db.add(candidate)
            i += 1
        db.commit()
    finally:
        db.close()


def run(**kwargs) -> str:
    validate_env(require_llm=True, require_twitter=False)
    genome_json, strategy_json, persona = _fetch_context()
    no_persona_msg = "No persona defined yet."
    idea_context = persona.get_prompt_context("full") if persona else no_persona_msg
    writer_context = persona.get_prompt_context("writer") if persona else no_persona_msg
    n_ideas = kwargs.get("n_ideas", 3)
    
    # Fetch performance insights and trending content
    performance_insights = _fetch_performance_insights(persona, limit=5)
    trending_content = _fetch_trending_content(persona, max_results=5)
    
    # Build enhanced context strings
    idea_context_enhanced = idea_context
    if performance_insights:
        idea_context_enhanced += "\n\n" + performance_insights
    if trending_content:
        idea_context_enhanced += "\n\n" + trending_content
    
    writer_context_enhanced = writer_context
    if performance_insights:
        writer_context_enhanced += "\n\n" + performance_insights

    idea_agent = create_idea_generator()
    hook_agent = create_hook_generator()
    writer_agent = create_writer()
    thread_agent = create_thread_builder()
    gatekeeper_agent = create_misinformation_gatekeeper()
    quality_scorer_agent = create_quality_scorer()

    idea_task = Task(
        description=(
            "Use the following context to generate exactly "
            + str(n_ideas)
            + " tweet ideas (topic + angle). These ideas will be used for hooks and full tweets.\n\n"
            "Inputs:\n"
            "- Persona (stay in character): "
            + idea_context_enhanced
            + "\n- Voice/strategy: genome="
            + genome_json
            + ", strategy="
            + strategy_json
            + "\n\n"
            "Steps:\n"
            "1. Use the persona and voice/strategy to stay on-brand.\n"
            "2. Consider the performance insights and trending content to inform your ideas—what's working and what's hot.\n"
            "3. Produce exactly "
            + str(n_ideas)
            + " ideas; each idea must have one clear topic and one clear angle.\n"
            "4. Output in the exact format specified in expected_output."
        ),
        expected_output=(
            "A markdown list of exactly "
            + str(n_ideas)
            + " ideas. For each idea use this format:\n"
            "## Idea K\n- Topic: <topic>\n- Angle: <angle>\n"
            "(K = 1 to "
            + str(n_ideas)
            + "). No other sections."
        ),
        agent=idea_agent,
    )
    hook_task = Task(
        description=(
            "For each idea from the previous task (use the exact topic and angle for each), generate one high-impact hook and tag its type.\n\n"
            "Inputs: The list of ideas from the previous task; persona (for voice): "
            + writer_context_enhanced
            + "\n\n"
            "Steps:\n"
            "1. Take each idea in order (Idea 1, Idea 2, ...).\n"
            "2. For each idea, write one scroll-stopping hook that fits the topic and angle.\n"
            "3. Tag each hook with exactly one type: shock, curiosity, authority, contrarian, or other.\n"
            "4. Output in the exact format specified in expected_output."
        ),
        expected_output=(
            "For each idea, one block in this format:\n"
            "## Idea K\nHook: <hook text>\nType: <one of shock|curiosity|authority|contrarian|other>\n"
            "Use the same K numbering as the ideas from the previous task."
        ),
        agent=hook_agent,
        context=[idea_task],
    )
    writer_task = Task(
        description=(
            "Using the ideas and hooks from the previous tasks, write 1–3 full tweet variants per idea. Every tweet must stay in character and be under 280 characters.\n\n"
            "Inputs: Ideas and hooks from the previous tasks; persona: "
            + writer_context_enhanced
            + "; voice: "
            + genome_json
            + "\n\n"
            "Steps:\n"
            "1. Use the example tweets in her voice as style anchors. Every tweet should work on two levels—surface and psychological undercurrent.\n"
            "2. Use the tweet formulas provided in the persona context—apply these structures when writing.\n"
            "3. Consider performance insights—what patterns worked well in past high-performing tweets.\n"
            "4. For each idea, use its hook and the voice parameters to write 1–3 full tweet variants.\n"
            "5. Stay in character for the persona. Vary sentence length: short and sharp for impact, longer for seduction. No emojis, no hashtags, no exclamation points unless ironic. Every tweet must be under 280 characters.\n"
            "6. Output in the exact format specified in expected_output."
        ),
        expected_output=(
            "For each idea, one block in this format:\n"
            "## Idea K\nVariant 1: <full tweet>\nVariant 2: <full tweet>\n(optional Variant 3)\n"
            "Each variant on its own line or clearly separated. Every tweet must be under 280 characters."
        ),
        agent=writer_agent,
        context=[idea_task, hook_task],
    )
    thread_task = Task(
        description=(
            "Pick the top 1–2 ideas from the ideas and writer output, then build a short thread with narrative structure. Stay in character; each tweet under 280 characters.\n\n"
            "Inputs: Ideas and writer output from previous tasks; persona: "
            + writer_context
            + "\n\n"
            "Steps:\n"
            "1. Choose the top 1–2 ideas to turn into a thread.\n"
            "2. Structure the thread as: problem → insight → takeaway (2–4 tweets total).\n"
            "3. Number each tweet. Keep each tweet under 280 characters.\n"
            "4. Output in the exact format specified in expected_output."
        ),
        expected_output=(
            "A thread of 2–4 tweets in this format:\n"
            "1. <tweet>\n2. <tweet>\n...\n"
            "Clear numbering. Each tweet under 280 characters."
        ),
        agent=thread_agent,
        context=[idea_task, writer_task],
    )
    gatekeeper_task = Task(
        description=(
            "Review each tweet or thread piece from the writer and thread tasks for factual and policy compliance. Content should align with the persona voice; your job is only to approve or block based on facts and policy.\n\n"
            "Inputs: All tweet content from the writer and thread tasks; persona (for voice alignment): "
            + writer_context
            + "\n\n"
            "Rules:\n"
            "- Verifiable factual claims (science, health, finance, news) are allowed only if verifiable; otherwise block.\n"
            "- Opinions, satire, and clearly subjective statements: allow.\n"
            "- If unsure whether something is factual or whether a fact is verifiable: block (APPROVED: false).\n"
            "- No hate speech, impersonation, or Twitter ToS violations.\n\n"
            "Output exactly one TWEET / APPROVED / REASON block per piece of content, in the format specified in expected_output."
        ),
        expected_output=(
            "For each piece of content (each tweet or thread tweet), output exactly:\n"
            "TWEET: <quoted or exact text>\nAPPROVED: true\nREASON: <one line>\n"
            "or\n"
            "TWEET: <quoted or exact text>\nAPPROVED: false\nREASON: <one line>\n"
            "One block per piece. Use APPROVED: true only when the content has no unverifiable factual claims and complies with policy."
        ),
        agent=gatekeeper_agent,
        context=[writer_task, thread_task],
    )
    
    quality_task = Task(
        description=(
            "Score each approved tweet or thread piece from the gatekeeper for quality and engagement potential.\n\n"
            "Inputs: All approved content from the gatekeeper task; persona (for alignment): "
            + writer_context
            + "\n\n"
            "Evaluate each piece on:\n"
            "- Clarity (0-10): Is the message clear and easy to understand?\n"
            "- Hook Strength (0-10): Does it grab attention effectively?\n"
            "- Engagement Potential (0-10): Likely to get likes, retweets, replies?\n"
            "- Persona Alignment (0-10): Matches the defined persona voice?\n"
            "- Overall Quality Score (0-10): Composite score\n\n"
            "Output exactly one TWEET / QUALITY_SCORE block per piece of approved content."
        ),
        expected_output=(
            "For each approved piece of content, output exactly:\n"
            "TWEET: <quoted or exact text>\n"
            "CLARITY: <0-10>\n"
            "HOOK_STRENGTH: <0-10>\n"
            "ENGAGEMENT_POTENTIAL: <0-10>\n"
            "PERSONA_ALIGNMENT: <0-10>\n"
            "QUALITY_SCORE: <0-10>\n\n"
            "Or simplified format:\n"
            "TWEET: <text>\n"
            "QUALITY_SCORE: <0-10>\n\n"
            "Only score content that was approved by the gatekeeper. Be strict—only truly high-quality content (score >= 7.0) should pass."
        ),
        agent=quality_scorer_agent,
        context=[gatekeeper_task],
    )

    crew = Crew(
        agents=[idea_agent, hook_agent, writer_agent, thread_agent, gatekeeper_agent, quality_scorer_agent],
        tasks=[idea_task, hook_task, writer_task, thread_task, gatekeeper_task, quality_task],
        process=Process.sequential,
        verbose=kwargs.get("verbose", True),
    )
    result = crew.kickoff()
    raw = result.raw if hasattr(result, "raw") else str(result)
    approved_list = parse_approved_content(raw)
    # Also extract individual tweet texts from raw for approved items (simplified: treat each block ending with APPROVED: true as one tweet)
    texts_found = re.findall(r"([^\n]+(?:\n[^\n]+)*?)\s*APPROVED:\s*true", raw, re.IGNORECASE | re.DOTALL)
    for idx, text in enumerate(texts_found):
        text = _strip_tweet_prefix(text.strip())
        if text and len(text) <= 280 and "REASON:" not in text.upper():
            norm_text, thread_seq = _normalize_text_and_thread_seq(text)
            item = {"text": (norm_text if norm_text else text), "approved": True, "topic": "", "hook_type": ""}
            if thread_seq is not None:
                item["thread_sequence"] = thread_seq
            approved_list.append(item)
    
    # Parse quality scores from quality scorer output
    quality_scores = parse_quality_scores(raw)
    if quality_scores:
        logger.info(f"Parsed {len(quality_scores)} quality scores from quality scorer output")
    
    # Extract tweets from quality scorer output (quality scorer only scores approved content)
    # This is a fallback if gatekeeper output isn't parsed correctly
    # Also add any tweets that have quality scores but weren't in approved_list
    # Parse raw output sequentially to preserve order
    if quality_scores:
        approved_texts = {_normalize_tweet_text(item.get("text", "")) for item in approved_list}
        # Parse raw output sequentially to preserve order
        lines = raw.strip().split("\n")
        current_text = ""
        current_score = None
        score_dimensions = ["CLARITY:", "HOOK_STRENGTH:", "ENGAGEMENT_POTENTIAL:", "PERSONA_ALIGNMENT:"]
        for line in lines:
            line_upper = line.upper().strip()
            # Skip empty lines
            if not line_upper:
                continue
            # Check for TWEET: marker
            if line_upper.startswith("TWEET:"):
                # Save previous entry if exists
                if current_text.strip() and current_score is not None:
                    normalized_tweet = _normalize_tweet_text(current_text)
                    if normalized_tweet not in approved_texts and current_score >= MIN_QUALITY_SCORE:
                        norm_text, thread_seq = _normalize_text_and_thread_seq(normalized_tweet)
                        item = {"text": (norm_text if norm_text else normalized_tweet), "approved": True, "topic": "", "hook_type": ""}
                        if thread_seq is not None:
                            item["thread_sequence"] = thread_seq
                        approved_list.append(item)
                        approved_texts.add(normalized_tweet)
                        logger.info(f"Added tweet from quality scorer output: {normalized_tweet[:50]}... (score: {current_score:.1f})")
                # Start new tweet
                current_text = line[6:].strip()  # Remove "TWEET:" prefix
                current_score = None
            # Check for QUALITY_SCORE: marker
            elif "QUALITY_SCORE:" in line_upper:
                match = re.search(r"QUALITY_SCORE:\s*([\d.]+)", line_upper)
                if match:
                    try:
                        current_score = float(match.group(1))
                        current_score = max(0.0, min(10.0, current_score))
                    except ValueError:
                        pass
            # Skip score dimension lines (CLARITY, HOOK_STRENGTH, etc.)
            elif any(dim in line_upper for dim in score_dimensions):
                continue
            # Accumulate multi-line tweet text (only if we have a current tweet and it's not a marker line)
            elif current_text and not any(marker in line_upper for marker in ["TWEET:", "QUALITY_SCORE:", "APPROVED:", "REASON:"]):
                current_text += "\n" + line.strip()
        # Handle last entry
        if current_text.strip() and current_score is not None:
            normalized_tweet = _normalize_tweet_text(current_text)
            if normalized_tweet not in approved_texts and current_score >= MIN_QUALITY_SCORE:
                norm_text, thread_seq = _normalize_text_and_thread_seq(normalized_tweet)
                item = {"text": (norm_text if norm_text else normalized_tweet), "approved": True, "topic": "", "hook_type": ""}
                if thread_seq is not None:
                    item["thread_sequence"] = thread_seq
                approved_list.append(item)
                approved_texts.add(normalized_tweet)
                logger.info(f"Added tweet from quality scorer output: {normalized_tweet[:50]}... (score: {current_score:.1f})")
    
    _save_approved_only(approved_list, quality_scores=quality_scores, dry_run=kwargs.get("dry_run", False))
    return raw
