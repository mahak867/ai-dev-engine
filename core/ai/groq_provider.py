# core/ai/groq_provider.py
# Groq cloud provider - Kimi K2 + Qwen3-32B + Llama 3.3 70B
# Includes SHA256 response caching (from apex-pro), 413/429 handling

import os
import time
import hashlib
import requests
from pathlib import Path

GROQ_MODELS = {
    "reasoner": "moonshotai/kimi-k2-instruct",
    "coder":    "qwen/qwen3-32b",
    "decoder":  "llama-3.3-70b-versatile",
    "general":  "llama-3.3-70b-versatile",
}

# SHA256 response cache (from apex-pro - avoids repeat API calls)
CACHE_DIR = Path.home() / ".apex_engine" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Per-model rate limit tracker
_last_call: dict = {}

def _cache_key(model: str, prompt: str) -> str:
    return hashlib.sha256(f"{model}:{prompt}".encode()).hexdigest()[:20]

def _get_cached(key: str) -> str:
    f = CACHE_DIR / f"{key}.txt"
    return f.read_text(encoding="utf-8") if f.exists() else ""

def _set_cached(key: str, value: str):
    try:
        (CACHE_DIR / f"{key}.txt").write_text(value, encoding="utf-8")
    except Exception:
        pass

def _rate_limit(model: str):
    """Per-model rate limiting to avoid 429s."""
    gaps = {
        "moonshotai/kimi-k2-instruct": 2.0,
        "qwen/qwen3-32b": 2.0,
        "llama-3.3-70b-versatile": 1.0,
    }
    gap = gaps.get(model, 1.5)
    last = _last_call.get(model, 0)
    wait = gap - (time.time() - last)
    if wait > 0:
        time.sleep(wait)
    _last_call[model] = time.time()

def _get_system_prompt(model: str) -> str:
    if "kimi" in model:
        return "You are a world-class CTO and principal architect. Think deeply. Be exhaustive and precise."
    if "qwen" in model:
        return "You are a senior full-stack engineer. Write complete, production-ready code. No placeholders. No truncation."
    return "You are a senior software engineer. Be accurate and concise."

def generate(model: str, prompt: str, use_cache: bool = True) -> str:
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY not set. Run: setx GROQ_API_KEY your_key_here")

    # Check cache first (apex-pro pattern)
    if use_cache:
        key = _cache_key(model, prompt)
        cached = _get_cached(key)
        if cached:
            print(f"    [Groq] {model.split('/')[-1]}... (cached)")
            return cached

    # Hard cap to prevent 413
    MAX = 80000
    if len(prompt) > MAX:
        print(f"     Trimming prompt {len(prompt):,} -> {MAX:,} chars")
        prompt = prompt[:MAX]

    for attempt in range(4):
        _rate_limit(model)
        try:
            print(f"    [Groq] {model.split('/')[-1]}...")
            resp = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": _get_system_prompt(model)},
                        {"role": "user",   "content": prompt},
                    ],
                    "max_tokens": 8000,
                    "temperature": 0.15,
                },
                timeout=180,
            )
            if resp.status_code == 429:
                wait = 65 * (attempt + 1)
                print(f"     Rate limit — waiting {wait}s...")
                time.sleep(wait)
                continue
            if resp.status_code == 413:
                trim = int(len(prompt) * 0.6)
                print(f"     413 — trimming to {trim:,} chars")
                prompt = prompt[:trim]
                continue
            resp.raise_for_status()
            result = resp.json()["choices"][0]["message"]["content"]
            print(f"    [Groq] v")
            # Save to cache
            if use_cache:
                _set_cached(_cache_key(model, prompt), result)
            return result
        except requests.exceptions.HTTPError as e:
            if attempt == 3:
                raise RuntimeError(f"Groq HTTP error: {e}") from e
            time.sleep(5)
    raise RuntimeError("Groq generation failed after 4 attempts")

def clear_cache():
    """Clear the response cache."""
    for f in CACHE_DIR.glob("*.txt"):
        f.unlink()
    print(f"Cache cleared ({CACHE_DIR})")

def cache_stats() -> dict:
    files = list(CACHE_DIR.glob("*.txt"))
    size = sum(f.stat().st_size for f in files)
    return {"entries": len(files), "size_kb": size // 1024, "path": str(CACHE_DIR)}
