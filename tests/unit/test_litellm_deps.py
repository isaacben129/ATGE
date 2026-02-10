"""Tests that guard against the LiteLLM/fastapi_sso import error seen on Railway.

LiteLLM's logging code imports proxy_server -> management_endpoints.types -> fastapi_sso.
If fastapi_sso is not installed, ModuleNotFoundError is raised. These tests ensure the
dependency is present and the full import chain works.
"""

import pytest


def test_fastapi_sso_importable():
    """fastapi_sso must be installed so LiteLLM proxy types can import OpenID."""
    import fastapi_sso  # noqa: F401
    from fastapi_sso.sso.base import OpenID

    assert OpenID is not None


def test_litellm_proxy_types_import():
    """LiteLLM proxy types module imports fastapi_sso; this is the exact path that failed on Railway."""
    from litellm.proxy.management_endpoints import types  # noqa: F401

    # CustomOpenID is defined in that module and uses OpenID from fastapi_sso
    assert hasattr(types, "CustomOpenID")


def test_scheduler_import_chain():
    """Import the same path Railway runs: scheduler -> start_scheduler (no blocking run)."""
    from atg_engine.services.scheduler import start_scheduler

    assert callable(start_scheduler)


def test_llm_client_import():
    """Import LLM factory; CrewAI/LiteLLM may be loaded and can trigger LiteLLM logging setup."""
    from atg_engine.services.llm_client import get_llm

    assert callable(get_llm)
