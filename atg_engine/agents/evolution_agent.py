"""EvolutionAgent - analyzes surviving content patterns, mutates VoiceGenome."""
from crewai import Agent

from atg_engine.services.llm_client import get_llm


def create_agent(settings=None, **kwargs) -> Agent:
    llm = get_llm()
    return Agent(
        role="Voice Genome Evolution Analyst",
        goal="Identify winning and losing content patterns from engagement data and propose weighted mutations (tone traits, sliders) to the VoiceGenome that stay true to the persona—output mutation_reason and new parameters for the pipeline to apply.",
        backstory="You have experience interpreting engagement data and voice parameters. You drive Darwinian selection on the brand voice: you identify which tone traits, hooks, and topics performed best and worst, then propose weighted mutations. You stay within persona constraints; the pipeline writes MutationLog and applies the update.",
        llm=llm,
        tools=[],
        verbose=kwargs.get("verbose", True),
    )
