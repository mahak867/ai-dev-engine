"""Re-export of the canned demo LLM (lives in core so the server can use it too)."""
from core.demo_llm import _APP, _SINGLE_APP, _TEST, _block, respond  # noqa: F401
