"""BreakdownAgent - analyzes viral tweets: structure, formula, why it works."""
from crewai import Agent

from atg_engine.services.llm_client import get_llm


def create_agent(settings=None, **kwargs) -> Agent:
    llm = get_llm()
    return Agent(
        role="Viral Tweet Analyst",
        goal="Analyze viral tweets and identify their structure, which content category and tweet formula they use, and why they work. Output in a strict format: TWEET_ID, MATCHED_CATEGORIES, FORMULA, STRUCTURE, WHY_IT_WORKS.",
        backstory="You are an expert at reverse-engineering why tweets go viral. You understand psychological hooks, tension, and payoff. You map content to categories and named formulas so the same insight can be adapted in a new voice.",
        llm=llm,
        tools=[],
        verbose=kwargs.get("verbose", True),
    )
