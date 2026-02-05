"""AnalyticsAgent - pulls tweet metrics from Twitter API, stores TweetPerformance."""
from crewai import Agent

from atg_engine.services.llm_client import get_llm


def create_agent(settings=None, **kwargs) -> Agent:
    llm = get_llm()
    return Agent(
        role="Social Metrics Ingestion Specialist",
        goal="Pull tweet metrics from the Twitter API, compute engagement rate and growth deltas, and store results consistently in TweetPerformance records for the evolution pipeline.",
        backstory="You focus on data pipeline accuracy. You ingest impressions, likes, retweets, and replies from Twitter, compute engagement rates and deltas, and ensure every record is stored so the evolution agent can interpret performance reliably.",
        llm=llm,
        tools=[],
        verbose=kwargs.get("verbose", True),
    )
