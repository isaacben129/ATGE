"""MisinformationGatekeeperAgent - checks factual claims, veto power over publishing."""
from pathlib import Path

from crewai import Agent

from atg_engine.config.settings import PROMPTS_DIR
from atg_engine.services.llm_client import get_llm


def create_agent(settings=None, **kwargs) -> Agent:
    llm = get_llm()
    prompt_path = PROMPTS_DIR / "misinformation_check.txt"
    prompt_template = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else ""
    return Agent(
        role="Content Integrity Reviewer for factual and policy compliance",
        goal="Approve or block each piece of content using a clear rule: verifiable facts are allowed; unverifiable factual claims, hate speech, and ToS violations are blocked; opinions and satire are allowed. Output a strict TWEET / APPROVED / REASON format per piece. When unsure, block.",
        backstory="You have experience in fact-checking and platform policy. You enforce the no-misinformation guardrail: any factual claim in science, health, finance, or news must be verifiable. You are conservative when unsure and have veto power—only content you approve may be published.",
        llm=llm,
        tools=[],
        verbose=kwargs.get("verbose", True),
    )
