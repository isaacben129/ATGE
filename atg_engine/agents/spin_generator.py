"""SpinGeneratorAgent - writes original tweets inspired by viral content in persona voice."""
from crewai import Agent

from atg_engine.services.llm_client import get_llm


def create_agent(settings=None, **kwargs) -> Agent:
    llm = get_llm()
    return Agent(
        role="Original Content Creator (Inspired Mode)",
        goal="Write 1–2 original tweets in the persona's voice that capture the same insight or structure as a viral tweet, using the persona's tweet formulas. Output: TWEET_ID, SPIN_1, optional SPIN_2, FORMULA_USED. Every tweet under 280 characters.",
        backstory="You take viral tweet breakdowns and create fresh, on-brand originals—same psychological punch, different words and angle. You never copy; you adapt structure and insight to the persona's voice and formulas.",
        llm=llm,
        tools=[],
        verbose=kwargs.get("verbose", True),
    )
