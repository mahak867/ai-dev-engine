"""
APEX AI Dev Engine v3 — Multi-Provider Router
Free-first: Groq (free tier) + Ollama (local) as primary.
Optional paid providers (OpenRouter, Together, Mistral) only used
if their API keys are explicitly set in .env.
"""
from __future__ import annotations
import os, json, time, logging
from typing import Iterator
import requests

log = logging.getLogger("apex.provider")

# ── Model catalogue ────────────────────────────────────────────────────────────
MODELS = {
    # ── FREE: Groq (fast, free tier) ─────────────────────────────────────────
    "groq/llama-3.3-70b":        {"provider": "groq", "ctx": 128_000, "free": True},
    "groq/llama-3.1-8b":         {"provider": "groq", "ctx": 128_000, "free": True},
    "groq/mixtral-8x7b":         {"provider": "groq", "ctx":  32_768, "free": True},
    "groq/gemma2-9b":            {"provider": "groq", "ctx":   8_192, "free": True},
    "groq/qwen-qwq-32b":         {"provider": "groq", "ctx": 128_000, "free": True},
    # ── FREE: Ollama (local, fully offline) ───────────────────────────────────
    "ollama/llama3.3":           {"provider": "ollama", "ctx": 128_000, "free": True},
    "ollama/qwen2.5-coder:32b":  {"provider": "ollama", "ctx": 128_000, "free": True},
    "ollama/deepseek-coder-v2":  {"provider": "ollama", "ctx": 163_840, "free": True},
    "ollama/codellama:70b":      {"provider": "ollama", "ctx": 100_000, "free": True},
    "ollama/qwen2.5:72b":        {"provider": "ollama", "ctx": 128_000, "free": True},
    # ── OPTIONAL paid (only used if key is set) ───────────────────────────────
    "or/kimi-k2":                {"provider": "openrouter", "ctx": 131_072, "free": False},
    "or/deepseek-r1":            {"provider": "openrouter", "ctx": 163_840, "free": False},
    "or/gemini-2.5-pro":         {"provider": "openrouter", "ctx":1_048_576,"free": False},
    "together/llama-3.3-70b":    {"provider": "together",   "ctx": 128_000, "free": False},
    "together/deepseek-r1":      {"provider": "together",   "ctx": 163_840, "free": False},
    "mistral/codestral":         {"provider": "mistral",    "ctx": 256_000, "free": False},
}

FREE_MODELS  = [m for m, i in MODELS.items() if i["free"]]
PAID_MODELS  = [m for m, i in MODELS.items() if not i["free"]]

# ── Cascades — FREE first, paid only if key exists ────────────────────────────
DEFAULT_CASCADE = [
    "groq/llama-3.3-70b",
    "groq/qwen-qwq-32b",
    "ollama/qwen2.5-coder:32b",
    "ollama/llama3.3",
]
CODING_CASCADE = [
    "groq/qwen-qwq-32b",
    "groq/llama-3.3-70b",
    "ollama/qwen2.5-coder:32b",
    "ollama/deepseek-coder-v2",
]
REASONING_CASCADE = [
    "groq/qwen-qwq-32b",
    "groq/llama-3.3-70b",
    "ollama/qwen2.5:72b",
]


def _paid_fallback(provider: str, model_key: str) -> list[str]:
    """Return paid model only if its key is configured."""
    key_map = {
        "openrouter": "OPENROUTER_API_KEY",
        "together":   "TOGETHER_API_KEY",
        "mistral":    "MISTRAL_API_KEY",
    }
    env_key = key_map.get(provider, "")
    if env_key and os.getenv(env_key):
        return [model_key]
    return []


class LLMProvider:
    """Unified LLM interface — free-first cascade with optional paid fallback."""

    def __init__(self, model: str = "auto", temperature: float = 0.2):
        self.model       = model
        self.temperature = temperature
        self._session    = requests.Session()
        self._session.headers.update({"Content-Type": "application/json"})

    # ── Public API ─────────────────────────────────────────────────────────────
    def complete(self, messages: list[dict], max_tokens: int = 8192) -> str:
        for model in self._resolve_cascade():
            try:
                return self._call(model, messages, max_tokens, stream=False)
            except Exception as e:
                log.warning(f"[{model}] failed: {e}, trying next...")
        raise RuntimeError("All providers exhausted — set GROQ_API_KEY for free access.")

    def stream(self, messages: list[dict], max_tokens: int = 8192) -> Iterator[str]:
        for model in self._resolve_cascade():
            try:
                yield from self._call(model, messages, max_tokens, stream=True)
                return
            except Exception as e:
                log.warning(f"[{model}] stream failed: {e}, trying next...")
        raise RuntimeError("All providers exhausted.")

    # ── Cascade resolution ─────────────────────────────────────────────────────
    def _resolve_cascade(self) -> list[str]:
        if self.model == "auto":      base = DEFAULT_CASCADE
        elif self.model == "coding":  base = CODING_CASCADE
        elif self.model == "reasoning": base = REASONING_CASCADE
        else:                         return [self.model]

        # append optional paid models if keys present
        extras: list[str] = []
        for m, info in MODELS.items():
            if not info["free"]:
                extras += _paid_fallback(info["provider"], m)
        return base + extras

    # ── Internal dispatch ──────────────────────────────────────────────────────
    def _call(self, model: str, messages: list, max_tokens: int, stream: bool):
        provider = MODELS[model]["provider"]
        return {
            "groq":       self._groq,
            "ollama":     self._ollama,
            "openrouter": self._openrouter,
            "together":   self._together,
            "mistral":    self._mistral,
        }[provider](model, messages, max_tokens, stream)

    # ── Groq (FREE) ────────────────────────────────────────────────────────────
    def _groq(self, model, messages, max_tokens, stream):
        key = os.getenv("GROQ_API_KEY", "")
        if not key:
            raise RuntimeError("GROQ_API_KEY not set — free tier, get it at console.groq.com")
        groq_ids = {
            "llama-3.3-70b": "llama-3.3-70b-versatile",
            "llama-3.1-8b":  "llama-3.1-8b-instant",
            "mixtral-8x7b":  "mixtral-8x7b-32768",
            "gemma2-9b":     "gemma2-9b-it",
            "qwen-qwq-32b":  "qwen-qwq-32b",
        }
        model_id = groq_ids.get(model.split("/", 1)[1], model.split("/", 1)[1])
        return self._openai_compat(
            "https://api.groq.com/openai/v1/chat/completions",
            key, model_id, messages, max_tokens, stream,
        )

    # ── Ollama (FREE / local) ──────────────────────────────────────────────────
    def _ollama(self, model, messages, max_tokens, stream):
        host     = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        model_id = model.split("/", 1)[1]
        payload  = {
            "model": model_id, "messages": messages, "stream": stream,
            "options": {"temperature": self.temperature, "num_predict": max_tokens},
        }
        r = self._session.post(f"{host}/api/chat", json=payload, stream=stream, timeout=120)
        r.raise_for_status()
        if not stream:
            return r.json()["message"]["content"]
        def _gen():
            for line in r.iter_lines():
                if line:
                    chunk = json.loads(line)
                    if token := chunk.get("message", {}).get("content", ""):
                        yield token
                    if chunk.get("done"): break
        return _gen()

    # ── OpenRouter (optional paid) ─────────────────────────────────────────────
    def _openrouter(self, model, messages, max_tokens, stream):
        key = os.getenv("OPENROUTER_API_KEY", "")
        if not key: raise RuntimeError("OPENROUTER_API_KEY not set")
        or_ids = {
            "kimi-k2":        "moonshotai/kimi-k2",
            "deepseek-r1":    "deepseek/deepseek-r1",
            "gemini-2.5-pro": "google/gemini-2.5-pro",
        }
        model_id = or_ids.get(model.split("/", 1)[1], model.split("/", 1)[1])
        return self._openai_compat(
            "https://openrouter.ai/api/v1/chat/completions",
            key, model_id, messages, max_tokens, stream,
            extra_headers={"HTTP-Referer": "https://github.com/mahak867/ai-dev-engine"},
        )

    # ── Together AI (optional paid) ────────────────────────────────────────────
    def _together(self, model, messages, max_tokens, stream):
        key = os.getenv("TOGETHER_API_KEY", "")
        if not key: raise RuntimeError("TOGETHER_API_KEY not set")
        together_ids = {
            "llama-3.3-70b": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
            "deepseek-r1":   "deepseek-ai/DeepSeek-R1",
        }
        model_id = together_ids.get(model.split("/", 1)[1], model.split("/", 1)[1])
        return self._openai_compat(
            "https://api.together.xyz/v1/chat/completions",
            key, model_id, messages, max_tokens, stream,
        )

    # ── Mistral (optional paid) ────────────────────────────────────────────────
    def _mistral(self, model, messages, max_tokens, stream):
        key = os.getenv("MISTRAL_API_KEY", "")
        if not key: raise RuntimeError("MISTRAL_API_KEY not set")
        ids = {"codestral": "codestral-latest"}
        model_id = ids.get(model.split("/", 1)[1], model.split("/", 1)[1])
        return self._openai_compat(
            "https://api.mistral.ai/v1/chat/completions",
            key, model_id, messages, max_tokens, stream,
        )

    # ── OpenAI-compat helper ───────────────────────────────────────────────────
    def _openai_compat(self, url, key, model_id, messages, max_tokens, stream,
                       extra_headers: dict | None = None):
        headers = {"Authorization": f"Bearer {key}"}
        if extra_headers: headers.update(extra_headers)
        payload = {
            "model": model_id, "messages": messages,
            "max_tokens": max_tokens, "temperature": self.temperature, "stream": stream,
        }
        r = self._session.post(url, json=payload, headers=headers, stream=stream, timeout=120)
        r.raise_for_status()
        if not stream:
            return r.json()["choices"][0]["message"]["content"]
        def _gen():
            for line in r.iter_lines():
                if line and line.startswith(b"data: "):
                    data = line[6:]
                    if data == b"[DONE]": break
                    try:
                        if token := json.loads(data)["choices"][0].get("delta", {}).get("content", ""):
                            yield token
                    except Exception:
                        pass
        return _gen()
