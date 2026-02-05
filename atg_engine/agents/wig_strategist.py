"""WIGStrategistAgent - owns WIG, daily targets, experimentation budget."""
from crewai import Agent

from atg_engine.services.llm_client import get_llm


def create_agent(settings=None, **kwargs) -> Agent:
    llm = get_llm()
    return Agent(
        role="Growth Strategy Lead (WIG and posting cadence)",
        goal="Set daily_post_target, thread_ratio, and experimentation_rate from performance data and the Wildly Important Goal (WIG), and output updated strategy parameters for the pipeline.",
        backstory="You are the strategist for an autonomous Twitter growth system with a 4DX-style cadence focus. You set daily post targets, thread ratio, and experimentation rate based on historical follower growth and current strategy state. You own the WIG and output clear, actionable strategy parameters.",
        llm=llm,
        tools=[],
        verbose=kwargs.get("verbose", True),
    )
