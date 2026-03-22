# core/ai/model_validator.py
# Validates Ollama (local) or Groq (cloud) setup on startup.

import os
import requests
from core.ai.model_router import MODELS, GROQ_MODELS

OLLAMA_URL = "http://localhost:11434"


def check_ollama_running() -> bool:
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        return r.status_code == 200
    except Exception:
        return False


def get_pulled_models() -> list:
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        return [m["name"] for m in r.json().get("models", [])]
    except Exception:
        return []


def resolve_model_name(wanted: str, pulled: list) -> str | None:
    if wanted in pulled:
        return wanted
    wanted_base = wanted.split(":")[0]
    wanted_tag  = wanted.split(":")[1] if ":" in wanted else ""
    for p in pulled:
        p_base = p.split(":")[0]
        p_tag  = p.split(":")[1] if ":" in p else ""
        if p_base == wanted_base and p_tag.startswith(wanted_tag):
            return p
    for p in pulled:
        if p.split(":")[0] == wanted_base:
            return p
    return None


def check_groq() -> dict:
    """Validate Groq API key and return resolved models."""
    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key:
        raise RuntimeError(
            "\n[ERR] GROQ_API_KEY not set.\n"
            "   Get a free key at console.groq.com\n"
            "   Then run:  set GROQ_API_KEY=your_key\n"
        )
    # Quick test call
    try:
        r = requests.get(
            "https://api.groq.com/openai/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10,
        )
        if r.status_code == 401:
            raise RuntimeError("\n[ERR] Invalid Groq API key.")
        r.raise_for_status()
        print("  [OK] Groq API key valid")
        print("  [OK] Groq models:")
        for task, model in GROQ_MODELS.items():
            print(f"     {task:10s} -> {model}")
        return GROQ_MODELS
    except requests.exceptions.ConnectionError:
        raise RuntimeError("\n[ERR] Cannot reach Groq API. Check internet connection.")


def validate_and_resolve_models() -> dict:
    from core.ai.provider import get_provider
    provider = get_provider()
    if provider == "groq" or (provider == "ollama" and os.getenv("GROQ_API_KEY")):
        return check_groq()

    if not check_ollama_running():
        raise RuntimeError(
            "\n[ERR] Ollama is not running.\n"
            "   Start it with:  ollama serve\n"
        )

    pulled   = get_pulled_models()
    resolved = {}
    missing  = []

    for task, wanted in MODELS.items():
        match = resolve_model_name(wanted, pulled)
        if match:
            resolved[task] = match
            if match != wanted:
                print(f"  [i]  Model resolved: '{wanted}' -> '{match}'")
        else:
            missing.append((task, wanted))

    if missing:
        lines = "\n".join(f"   ollama pull {m}" for _, m in missing)
        raise RuntimeError(f"\n[ERR] Missing models:\n{lines}\n")

    return resolved


def startup_check(auto_resolve: bool = True) -> dict | None:
    from core.ai.provider import get_provider
    provider = get_provider()
    print(f"\n[*] Checking {provider.upper()} + models...")
    try:
        resolved = validate_and_resolve_models()
        print(f"  [OK] {provider.upper()} running")
        if provider == "ollama":
            print("  [OK] All models available:")
            for task, name in resolved.items():
                print(f"     {task:10s} -> {name}")
        print()
        return resolved
    except RuntimeError as e:
        print(str(e))
        if not auto_resolve:
            return None
        raise
