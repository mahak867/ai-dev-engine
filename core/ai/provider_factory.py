# core/ai/provider_factory.py
# Selects between Ollama (local) and Groq (cloud) at runtime.
# Priority: explicit --provider flag > GROQ_API_KEY env var > Ollama

import os

_PROVIDER = "ollama"  # default


def set_provider(provider: str):
    """Set provider: 'ollama' or 'groq'"""
    global _PROVIDER
    if provider not in ("ollama", "groq"):
        raise ValueError(f"Unknown provider '{provider}'. Use 'ollama' or 'groq'.")
    _PROVIDER = provider
    print(f"  [Provider] Using: {provider.upper()}")


def get_provider() -> str:
    return _PROVIDER


def auto_detect():
    """
    Auto-detect best provider:
    - If GROQ_API_KEY is set → use Groq
    - Otherwise → use Ollama
    """
    global _PROVIDER
    if os.getenv("GROQ_API_KEY", "").strip():
        _PROVIDER = "groq"
        print("  [Provider] GROQ_API_KEY detected — using Groq.")
    else:
        _PROVIDER = "ollama"


def generate(model: str, prompt: str, clean_output: bool = True) -> str:
    """
    Universal generate() — routes to correct provider automatically.
    This replaces direct calls to ollama_provider.generate().
    """
    if _PROVIDER == "groq":
        from core.ai.groq_provider import generate as groq_generate
        return groq_generate(model, prompt, clean_output)
    else:
        from core.ai.ollama_provider import generate as ollama_generate
        return ollama_generate(model, prompt, clean_output)
