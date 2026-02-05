"""Weekly review pipeline: CadenceManager -> EvolutionAgent -> VoiceGenomeAgent; update StrategyState and MutationLog."""
from crewai import Crew, Process, Task

from atg_engine.agents import (
    create_cadence_manager,
    create_evolution_agent,
    create_voice_genome,
    create_wig_strategist,
)
from atg_engine.db.session import SessionLocal
from atg_engine.models import (
    Persona,
    VoiceGenome,
    StrategyState,
    MutationLog,
    TweetPerformance,
)
from atg_engine.config.env_validation import validate_env
from atg_engine.services.bootstrap import ensure_bootstrap
from atg_engine.services.evolution import weighted_update
from atg_engine.utils.weekly_parse import parse_genome_from_raw, parse_strategy_from_raw


def _get_performance_signals(db):
    """Aggregate winning/losing traits and hooks from TweetPerformance and related candidates."""
    # Simplified: get top and bottom by engagement_rate
    perfs = (
        db.query(TweetPerformance)
        .order_by(TweetPerformance.engagement_rate.desc())
        .limit(20)
        .all()
    )
    winning_traits = []
    losing_traits = []
    winning_hooks = []
    losing_hooks = []
    if len(perfs) >= 2:
        top = perfs[: len(perfs) // 2]
        bottom = perfs[len(perfs) // 2 :]
        for p in top:
            winning_hooks.append("high_engagement")
        for p in bottom:
            losing_hooks.append("low_engagement")
    return winning_traits, losing_traits, winning_hooks, losing_hooks


def run(**kwargs) -> str:
    validate_env(require_llm=True, require_twitter=False)
    ensure_bootstrap()
    db = SessionLocal()
    try:
        persona = db.query(Persona).first()
        persona_context = persona.to_prompt_context() if persona else "No persona defined."
        genome = db.query(VoiceGenome).order_by(VoiceGenome.last_updated.desc()).first()
        strategy = db.query(StrategyState).order_by(StrategyState.last_reviewed.desc()).first()
        if not genome:
            genome = VoiceGenome(
                tone_traits="[]",
                language_patterns="[]",
                taboo_topics="[]",
                risk_tolerance=0.5,
                aggressiveness=0.5,
                humor_level=0.5,
                controversy_level=0.5,
            )
            db.add(genome)
            db.commit()
            db.refresh(genome)
        if not strategy:
            strategy = StrategyState(
                wig="Follower growth",
                daily_post_target=5,
                thread_ratio=0.2,
                experimentation_rate=0.25,
            )
            db.add(strategy)
            db.commit()
            db.refresh(strategy)

        cadence_agent = create_cadence_manager()
        evolution_agent = create_evolution_agent()
        voice_agent = create_voice_genome()
        wig_agent = create_wig_strategist()

        win_t, lose_t, win_h, lose_h = _get_performance_signals(db)
        performance_delta = 0.1

        review_task = Task(
            description=(
                "Trigger the weekly review. Summarize the current WIG and strategy state, then state that evolution analysis and strategy update should run.\n\n"
                "Inputs: Persona (voice should stay aligned): "
                + persona_context
                + "; current WIG and strategy (daily_post_target, thread_ratio, experimentation_rate).\n\n"
                "Steps:\n"
                "1. Summarize current WIG and strategy in 2–4 sentences.\n"
                "2. Explicitly request evolution analysis and strategy update."
            ),
            expected_output=(
                "A brief summary (2–4 sentences) of current WIG and strategy state, "
                "and an explicit request for evolution analysis and strategy update."
            ),
            agent=cadence_agent,
        )
        evolution_task = Task(
            description=(
                "Analyze performance signals and propose a weighted mutation to the voice genome that stays true to the persona.\n\n"
                "Inputs: Persona: "
                + persona_context
                + "; winning signals (traits/hooks): "
                + str(win_t)
                + ", "
                + str(win_h)
                + "; losing signals: "
                + str(lose_t)
                + ", "
                + str(lose_h)
                + ".\n\n"
                "Steps:\n"
                "1. Identify which content patterns (tone traits, hooks) align with winning vs losing performance.\n"
                "2. Propose a weighted mutation: adjust tone_traits, risk_tolerance, aggressiveness, humor_level, controversy_level (and language_patterns/taboo_topics if applicable) so the genome evolves toward what worked while staying within persona.\n"
                "3. Output mutation_reason (1–2 sentences) and new parameters in a JSON-like block."
            ),
            expected_output=(
                "Two parts: (1) mutation_reason: 1–2 sentences explaining the proposed change. "
                "(2) New parameters as a JSON-like block with keys: tone_traits, risk_tolerance, aggressiveness, humor_level, controversy_level (and language_patterns, taboo_topics if applicable)."
            ),
            agent=evolution_agent,
            context=[review_task],
        )
        voice_task = Task(
            description=(
                "Apply the mutation from the previous task to the current voice genome and output the resulting state.\n\n"
                "Inputs: The evolution task output (mutation_reason and new params); current voice genome.\n\n"
                "Steps:\n"
                "1. Apply the proposed mutation to the current genome.\n"
                "2. Output the updated voice genome as a JSON-like block with the same keys as the evolution output."
            ),
            expected_output=(
                "Updated voice genome as a JSON-like block with keys: tone_traits, risk_tolerance, aggressiveness, humor_level, controversy_level "
                "(and language_patterns, taboo_topics if present in the mutation)."
            ),
            agent=voice_agent,
            context=[evolution_task],
        )
        wig_task = Task(
            description=(
                "Propose updated strategy parameters based on the review summary and current strategy.\n\n"
                "Inputs: Review summary from the cadence task; current strategy (daily_post_target, thread_ratio, experimentation_rate, wig).\n\n"
                "Steps:\n"
                "1. Consider the current WIG and performance context.\n"
                "2. Propose updated daily_post_target, thread_ratio, experimentation_rate (and wig if applicable).\n"
                "3. Output in the format specified in expected_output."
            ),
            expected_output=(
                "Updated strategy parameters as a JSON-like block with keys: daily_post_target, thread_ratio, experimentation_rate (and wig if applicable)."
            ),
            agent=wig_agent,
            context=[review_task],
        )

        crew = Crew(
            agents=[cadence_agent, evolution_agent, voice_agent, wig_agent],
            tasks=[review_task, evolution_task, voice_task, wig_task],
            process=Process.sequential,
            verbose=kwargs.get("verbose", True),
        )
        result = crew.kickoff()
        raw = result.raw if hasattr(result, "raw") else str(result)

        # Code-based weighted update (fallback)
        new_params = weighted_update(
            genome,
            winning_traits=win_t,
            losing_traits=lose_t,
            winning_hooks=win_h,
            losing_hooks=lose_h,
            performance_delta=performance_delta,
        )
        # Parse LLM output for genome; merge into new_params when present
        genome_parsed = parse_genome_from_raw(raw)
        if genome_parsed:
            for k, v in genome_parsed.items():
                new_params[k] = v
        mutation_reason = "Weekly evolution (LLM + signals)" if genome_parsed else "Weekly evolution from performance signals"

        new_genome = VoiceGenome(
            tone_traits=new_params.get("tone_traits", genome.tone_traits),
            language_patterns=new_params.get("language_patterns", genome.language_patterns),
            taboo_topics=new_params.get("taboo_topics", genome.taboo_topics),
            risk_tolerance=new_params.get("risk_tolerance", genome.risk_tolerance),
            aggressiveness=new_params.get("aggressiveness", genome.aggressiveness),
            humor_level=new_params.get("humor_level", genome.humor_level),
            controversy_level=new_params.get("controversy_level", genome.controversy_level),
        )
        db.add(new_genome)
        db.commit()
        db.refresh(new_genome)
        mutation_log = MutationLog(
            old_genome_id=genome.id,
            new_genome_id=new_genome.id,
            mutation_reason=mutation_reason,
            performance_delta=performance_delta,
        )
        db.add(mutation_log)

        # Parse LLM output for strategy; update StrategyState when present
        strategy_parsed = parse_strategy_from_raw(raw)
        if strategy and strategy_parsed:
            from datetime import datetime, timezone
            if "wig" in strategy_parsed:
                strategy.wig = strategy_parsed["wig"]
            if "daily_post_target" in strategy_parsed:
                strategy.daily_post_target = strategy_parsed["daily_post_target"]
            if "thread_ratio" in strategy_parsed:
                strategy.thread_ratio = strategy_parsed["thread_ratio"]
            if "experimentation_rate" in strategy_parsed:
                strategy.experimentation_rate = strategy_parsed["experimentation_rate"]
            strategy.last_reviewed = datetime.now(timezone.utc)
        elif strategy:
            from datetime import datetime, timezone
            strategy.last_reviewed = datetime.now(timezone.utc)
        db.commit()
        return raw
    finally:
        db.close()
