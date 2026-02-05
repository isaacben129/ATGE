"""ThreadBuilderAgent - builds long-form threads from top ideas."""
from crewai import Agent

from atg_engine.services.llm_client import get_llm


def create_agent(settings=None, **kwargs) -> Agent:
    llm = get_llm()
    return Agent(
        role="Twitter Thread Architect specializing in narrative structure",
        goal="Build 2–4 tweet threads from the top ideas using problem → insight → takeaway structure, with each tweet numbered and under 280 characters.",
        backstory="You have extensive experience turning single ideas into engaging multi-tweet threads. You prioritize clarity and narrative flow: problem, insight, takeaway. You number every tweet and never exceed 280 characters per tweet.",
        llm=llm,
        tools=[],
        verbose=kwargs.get("verbose", True),
    )
