"""CadenceManagerAgent - runs daily/weekly review, triggers strategy and evolution."""
from crewai import Agent

from atg_engine.services.llm_client import get_llm


def create_agent(settings=None, **kwargs) -> Agent:
    llm = get_llm()
    return Agent(
        role="Execution Cadence Orchestrator",
        goal="Trigger weekly review cycles: summarize current WIG and strategy, then request evolution analysis and strategy update. Do not generate any content—orchestration only.",
        backstory="You orchestrate the 4DX cadence. You run daily and weekly execution reviews and trigger the WIG strategist and evolution agent. You do not create tweets, ideas, or strategy details yourself; you only coordinate the review and hand off to specialists.",
        llm=llm,
        tools=[],
        verbose=kwargs.get("verbose", True),
    )
