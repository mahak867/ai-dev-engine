import os
from typing import Dict, List, Tuple

import requests

from core.ai.groq_provider import generate as groq_generate


OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

ROUTING_PROFILES: Dict[str, Dict[str, List[str] or str]] = {
    "quality_max": {
        "openrouter_models": [
            "anthropic/claude-sonnet-4",
            "openai/gpt-5",
            "google/gemini-2.5-pro",
        ],
        "groq_model": "moonshotai/kimi-k2-instruct",
    },
    "groq_primary": {
        "openrouter_models": [
            "moonshotai/kimi-k2",
            "openai/gpt-4.1",
        ],
        "groq_model": "moonshotai/kimi-k2-instruct",
    },
    "balanced_cost": {
        "openrouter_models": [
            "openai/gpt-4.1-mini",
            "anthropic/claude-3.5-sonnet",
        ],
        "groq_model": "qwen/qwen3-32b",
    },
}


def available_profiles() -> List[str]:
    return list(ROUTING_PROFILES.keys())


def cloud_status(openrouter_key: str, groq_key: str) -> str:
    has_or = bool(openrouter_key.strip())
    has_groq = bool(groq_key.strip())
    if has_or and has_groq:
        return "OpenRouter + Groq ready"
    if has_or:
        return "OpenRouter ready"
    if has_groq:
        return "Groq ready"
    return "No cloud key set"


def _openrouter_generate(
    openrouter_key: str,
    profile: str,
    prompt: str,
    system_prompt: str,
    max_tokens: int = 1200,
) -> Tuple[str, str]:
    models = ROUTING_PROFILES.get(profile, ROUTING_PROFILES["quality_max"])["openrouter_models"]
    payload = {
        "models": models,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "max_tokens": max_tokens,
    }
    resp = requests.post(
        OPENROUTER_URL,
        headers={
            "Authorization": f"Bearer {openrouter_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()
    message = data["choices"][0]["message"]["content"]
    model = data.get("model", models[0])
    return message, model


def _groq_generate(
    groq_key: str,
    profile: str,
    prompt: str,
    system_prompt: str,
) -> Tuple[str, str]:
    model = ROUTING_PROFILES.get(profile, ROUTING_PROFILES["quality_max"])["groq_model"]
    merged = f"{system_prompt}\n\n{prompt}"
    old_value = os.environ.get("GROQ_API_KEY")
    os.environ["GROQ_API_KEY"] = groq_key
    try:
        output = groq_generate(model, merged, use_cache=False)
    finally:
        if old_value is None:
            del os.environ["GROQ_API_KEY"]
        else:
            os.environ["GROQ_API_KEY"] = old_value
    return output, model


def generate_cloud_text(
    prompt: str,
    profile: str = "quality_max",
    provider_preference: str = "auto",
    openrouter_key: str = "",
    groq_key: str = "",
    system_prompt: str = "You are a senior engineering assistant. Be precise and practical.",
) -> Dict[str, str]:
    pref = provider_preference.strip().lower()
    openrouter_key = openrouter_key.strip()
    groq_key = groq_key.strip()

    order = []
    if pref == "openrouter":
        order = ["openrouter", "groq"]
    elif pref == "groq":
        order = ["groq", "openrouter"]
    else:
        order = ["openrouter", "groq"]

    last_error = ""
    for provider in order:
        try:
            if provider == "openrouter" and openrouter_key:
                text, model = _openrouter_generate(openrouter_key, profile, prompt, system_prompt)
                return {"ok": "1", "provider": "OpenRouter", "model": model, "text": text}
            if provider == "groq" and groq_key:
                text, model = _groq_generate(groq_key, profile, prompt, system_prompt)
                return {"ok": "1", "provider": "Groq", "model": model, "text": text}
        except Exception as exc:
            last_error = str(exc)

    return {
        "ok": "0",
        "provider": "",
        "model": "",
        "text": "",
        "error": last_error or "No cloud key configured for selected provider routing.",
    }
