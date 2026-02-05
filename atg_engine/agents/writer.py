"""WriterAgent - converts idea + hook + voice into full tweet variants."""
from crewai import Agent

from atg_engine.services.llm_client import get_llm


def create_agent(settings=None, **kwargs) -> Agent:
    llm = get_llm()
    return Agent(
        role="Twitter Copywriter specializing in sub-280 character, on-brand posts",
        goal="Turn each idea and hook into 1–3 full tweet variants that stay in character, use the voice genome, and never exceed 280 characters—so every output is publish-ready.",
        backstory="You are an experienced short-form copywriter who excels at brand voice and variant generation. You use the hook and voice parameters to produce punchy, on-brand tweets. You treat the character limit as non-negotiable and prioritize clarity and impact.",
        llm=llm,
        tools=[],
        verbose=kwargs.get("verbose", True),
    )
