"""VoiceGenomeAgent - maintains current VoiceGenome, applies mutations from EvolutionAgent."""
from crewai import Agent

from atg_engine.services.llm_client import get_llm


def create_agent(settings=None, **kwargs) -> Agent:
    llm = get_llm()
    return Agent(
        role="Brand Voice Genome Curator",
        goal="Maintain the brand's evolving voice (tone traits, language patterns, risk and humor levels). Apply mutations from the evolution agent and output the current or updated voice parameters so all content agents stay consistent.",
        backstory="You have experience in brand voice systems and incremental updates. You curate the voice genome that defines how the brand sounds. You apply weighted updates from the evolution agent, ensure consistency, and output the resulting parameters in a structured form.",
        llm=llm,
        tools=[],
        verbose=kwargs.get("verbose", True),
    )
