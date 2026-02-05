"""PublisherAgent - publishes approved tweets via Twitter API."""
from crewai import Agent

from atg_engine.services.llm_client import get_llm


def create_agent(settings=None, **kwargs) -> Agent:
    llm = get_llm()
    return Agent(
        role="Approved Content Publisher (Twitter API executor only)",
        goal="Publish only approved tweet candidates via the Twitter API, handle rate limits, and log tweet IDs for analytics—no content creation or approval decisions.",
        backstory="You are the executor of approved content only. You post to Twitter only what has passed the misinformation gatekeeper and log tweet IDs so the system can track performance. You do not create or approve content.",
        llm=llm,
        tools=[],
        verbose=kwargs.get("verbose", True),
    )
