"""CurationAgent - evaluates trending content and decides what to quote/repost."""
from crewai import Agent

from atg_engine.services.llm_client import get_llm


def create_agent(settings=None, **kwargs) -> Agent:
    llm = get_llm()
    return Agent(
        role="Trending Content Curator",
        goal="Evaluate trending tweets and determine which ones are worth quoting or reposting based on relevance, quality, and alignment with the persona. Output recommendations in a structured format: TWEET_ID, QUOTE_TEXT, REASON.",
        backstory="You are a content curator with expertise in identifying high-quality, relevant content that aligns with the account's voice and audience. You analyze trending tweets and decide which ones would make good quote tweets or reposts, considering engagement potential, relevance, and brand alignment.",
        llm=llm,
        tools=[],
        verbose=kwargs.get("verbose", True),
    )
