"""CrewAI-compatible LLM factory (Groq)."""
from crewai import LLM

from atg_engine.config.settings import GROQ_API_KEY, GROQ_MODEL

_llm: LLM | None = None


def get_llm(model: str | None = None) -> LLM:
    """Return a CrewAI LLM instance (singleton) using Groq."""
    global _llm
    if _llm is None:
        _llm = LLM(
            model=model or GROQ_MODEL,
            api_key=GROQ_API_KEY,
        )
    return _llm
