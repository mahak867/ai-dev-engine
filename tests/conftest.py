"""
Hermetic test environment.

Every test gets a throwaway HOME and APEX_MEMORY_DIR, no provider API keys,
and fresh server settings — so running the suite never writes to the real
~/.apex/memory and never reaches a paid model.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_SECRET_VARS = [
    "QWEN_API_KEY", "DASHSCOPE_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY",
    "TOGETHER_API_KEY", "MISTRAL_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
    "APEX_API_TOKEN", "APEX_ALLOW_EXECUTION", "APEX_HOST", "APEX_ALLOWED_HOSTS",
    "APEX_ALLOWED_ORIGINS",
]


@pytest.fixture(autouse=True)
def _hermetic_env(tmp_path_factory, monkeypatch):
    home = tmp_path_factory.mktemp("home")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("APEX_MEMORY_DIR", str(home / ".apex" / "memory"))
    for var in _SECRET_VARS:
        monkeypatch.delenv(var, raising=False)
    from core.web_security import get_settings
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
