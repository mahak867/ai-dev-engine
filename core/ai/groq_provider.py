# core/ai/groq_provider.py
# Optimized Groq provider with best available models as of March 2026

import os
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from core.ai.response_cleaner import clean

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

# Best models on Groq as of March 2026 (ranked by intelligence score)
# gpt-oss-120b: score 33 — best reasoning, replaces kimi for architecture
# kimi-k2-0905: score 31 — best for frontend coding (improved web outputs)  
# qwen/qwen3-32b: score 28 — best for backend code generation
# llama-3.3-70b: fast, reliable for config/formatting
GROQ_MODELS = {
    "general":  "llama-3.3-70b-versatile",
    "coder":    "qwen/qwen3-32b",           # Best coding model on Groq
    "decoder":  "llama-3.3-70b-versatile",
    "reasoner": "moonshotai/kimi-k2-instruct",  # Best reasoning/architecture
}

# Upgrade mapping — use these if available
GROQ_MODELS_UPGRADED = {
    "general":  "meta-llama/llama-4-scout-17b-16e-instruct",
    "coder":    "qwen/qwen3-32b",
    "decoder":  "llama-3.3-70b-versatile",
    "reasoner": "moonshotai/kimi-k2-instruct",
}

# Try upgraded models, fall back to originals if unavailable
PREFERRED_MODELS = {
    "reasoner": "openai/gpt-oss-120b",      # Best reasoning on Groq
    "coder":    "moonshotai/kimi-k2-0905",  # Best frontend/coding
    "general":  "llama-3.3-70b-versatile",
    "decoder":  "llama-3.3-70b-versatile",
}

MODEL_TOKENS = {
    "openai/gpt-oss-120b":          8192,
    "moonshotai/kimi-k2-0905":      8192,
    "moonshotai/kimi-k2-instruct":  8192,
    "qwen/qwen3-32b":               8192,
    "llama-3.3-70b-versatile":      8192,
}

SYSTEM_PROMPTS = {
    "openai/gpt-oss-120b": (
        "You are a principal engineer and CTO. You design production-grade systems. "
        "You write complete, working code with no placeholders or TODOs. "
        "When returning JSON, return only raw valid JSON with no markdown."
    ),
    "moonshotai/kimi-k2-0905": (
        "You are a senior full-stack engineer specializing in React and Flask. "
        "You write beautiful, complete UI code. You never truncate output. "
        "You always complete every file fully. No TODOs, no placeholders. "
        "When returning JSON, return only raw valid JSON."
    ),
    "moonshotai/kimi-k2-instruct": (
        "You are a principal engineer. You design scalable systems. "
        "You write complete code with no placeholders. "
        "When returning JSON, return only raw valid JSON."
    ),
    "qwen/qwen3-32b": (
        "You are a senior software engineer. You write production-ready code. "
        "You never truncate output. You complete every file fully. "
        "No TODOs, no placeholders, no '# Add logic here' comments. "
        "When returning JSON, return only raw valid JSON with no markdown fences."
    ),
    "llama-3.3-70b-versatile": (
        "You are a senior engineer. Return complete, working output. "
        "When returning JSON, return only raw valid JSON."
    ),
}

_session = None

def _get_session():
    global _session
    if _session is None:
        _session = requests.Session()
        adapter = HTTPAdapter(pool_connections=4, pool_maxsize=4)
        _session.mount("https://", adapter)
    return _session


def get_groq_key() -> str:
    key = os.getenv("GROQ_API_KEY", "")
    if not key:
        raise RuntimeError(
            "GROQ_API_KEY not set.\n"
            "Get a free key at https://console.groq.com\n"
            "Then run: setx GROQ_API_KEY your_key_here"
        )
    return key


def _resolve_model(model: str, use_preferred: bool = True) -> str:
    """Resolve task key to model name, trying preferred first."""
    if model in PREFERRED_MODELS and use_preferred:
        return PREFERRED_MODELS[model]
    if model in GROQ_MODELS:
        return GROQ_MODELS[model]
    return model


def generate(model: str, prompt: str, clean_output: bool = True, retries: int = 3) -> str:
    """Call Groq API with auto-retry and fallback models."""
    resolved = _resolve_model(model)
    fallback = GROQ_MODELS.get(model, resolved)
    api_key = get_groq_key()

    for attempt in range(retries):
        current_model = resolved if attempt < 2 else fallback
        max_tokens = MODEL_TOKENS.get(current_model, 8192)
        system = SYSTEM_PROMPTS.get(current_model, "You are a helpful expert engineer.")
        print(f"    [Groq] {current_model.split('/')[-1]}...", flush=True)

        try:
            resp = _get_session().post(
                GROQ_API_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": current_model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.15,
                    "max_tokens": max_tokens,
                    "top_p": 0.95,
                },
                timeout=180,
            )

            if resp.status_code == 429:
                wait = 65 * (attempt + 1)
                print(f"     Rate limit — waiting {wait}s...", flush=True)
                time.sleep(wait)
                continue

            if resp.status_code == 503:
                wait = 15 * (attempt + 1)
                print(f"     Groq overloaded — waiting {wait}s...", flush=True)
                time.sleep(wait)
                continue

            if resp.status_code == 400 and attempt == 0:
                # Model might not be available, try fallback
                print(f"     {current_model} unavailable, trying fallback...", flush=True)
                resolved = fallback
                continue

            resp.raise_for_status()
            raw = resp.json()["choices"][0]["message"]["content"]
            print(f"    [Groq] ✓", flush=True)
            return clean(raw) if clean_output else raw

        except requests.exceptions.ConnectionError:
            if attempt < retries - 1:
                print(f"     Connection error — retrying...", flush=True)
                time.sleep(5)
                continue
            raise RuntimeError("Cannot reach Groq. Check your internet.")

        except requests.exceptions.Timeout:
            if attempt < retries - 1:
                print(f"     Timeout — retrying...", flush=True)
                time.sleep(5)
                continue
            raise TimeoutError("Groq timed out.")

        except requests.exceptions.HTTPError as e:
            if resp.status_code == 401:
                raise RuntimeError("Invalid GROQ_API_KEY. Check at console.groq.com")
            raise RuntimeError(f"Groq HTTP error: {e}")

        except Exception as e:
            if attempt < retries - 1:
                time.sleep(3)
                continue
            raise RuntimeError(f"Groq error: {e}")

    raise RuntimeError("Groq failed after all retries.")


def check_groq() -> bool:
    try:
        get_groq_key()
        generate("general", "Reply: OK", clean_output=False)
        return True
    except Exception:
        return False
