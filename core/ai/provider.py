"""
APEX AI Dev Engine v3 — Multi-Provider Router
Supports: Groq, OpenRouter, Together AI, Ollama, Mistral, Cohere
"""
from __future__ import annotations
import os, json, time, logging
from typing import Iterator, Optional
import requests

log = logging.getLogger("apex.provider")

# ── Model catalogue ────────────────────────────────────────────────────────────
MODELS = {
    # Groq (free, ultra-fast)
    "groq/llama-3.3-70b":        {"provider": "groq",       "ctx": 128_000},
    "groq/llama-3.1-8b":         {"provider": "groq",       "ctx": 128_000},
    "groq/mixtral-8x7b":         {"provider": "groq",       "ctx":  32_768},
    "groq/gemma2-9b":            {"provider": "groq",       "ctx":   8_192},
    "groq/qwen-qwq-32b":         {"provider": "groq",       "ctx": 128_000},
    # Together AI
    "together/llama-3.3-70b":    {"provider": "together",   "ctx": 128_000},
    "together/qwen2.5-72b":      {"provider": "together",   "ctx": 128_000},
    "together/deepseek-r1":      {"provider": "together",   "ctx": 163_840},
    # OpenRouter (access to many models including Kimi, Gemini, etc.)
    "or/kimi-k2":                {"provider": "openrouter", "ctx": 131_072},
    "or/gemini-2.5-pro":         {"provider": "openrouter", "ctx":1_048_576},
    "or/deepseek-r1":            {"provider": "openrouter", "ctx": 163_840},
    "or/qwen3-235b":             {"provider": "openrouter", "ctx":  40_960},
    "or/codex-mini":             {"provider": "openrouter", "ctx":  32_000},
    # Ollama (local, free)
    "ollama/llama3.3":           {"provider": "ollama",     "ctx": 128_000},
    "ollama/qwen2.5-coder:32b":  {"provider": "ollama",     "ctx": 128_000},
    "ollama/deepseek-coder-v2":  {"provider": "ollama",     "ctx": 163_840},
    "ollama/codellama:70b":      {"provider": "ollama",     "ctx": 100_000},
    # Mistral
    "mistral/codestral":         {"provider": "mistral",    "ctx": 256_000},
    "mistral/mistral-large":     {"provider": "mistral",    "ctx": 128_000},
}

# ── Default cascade (tries in order until one works) ──────────────────────────
DEFAULT_CASCADE = [
    "groq/llama-3.3-70b",
    "groq/qwen-qwq-32b",
    "ollama/qwen2.5-coder:32b",
    "together/qwen2.5-72b",
]
CODING_CASCADE = [
    "groq/qwen-qwq-32b",
    "groq/llama-3.3-70b",
    "mistral/codestral",
    "ollama/qwen2.5-coder:32b",
    "together/deepseek-r1",
    "or/deepseek-r1",
]
REASONING_CASCADE = [
    "groq/qwen-qwq-32b",
    "together/deepseek-r1",
    "or/deepseek-r1",
    "or/gemini-2.5-pro",
]


class LLMProvider:
    """Unified LLM interface with cascade fallback and streaming."""

    def __init__(self, model: str = "auto", temperature: float = 0.2):
        self.model = model
        self.temperature = temperature
        self._session = requests.Session()
        self._session.headers.update({"Content-Type": "application/json"})

    # ── public API ─────────────────────────────────────────────────────────────
    def complete(self, messages: list[dict], max_tokens: int = 8192) -> str:
        """Blocking completion with cascade fallback."""
        cascade = self._resolve_cascade()
        for model in cascade:
            try:
                return self._call(model, messages, max_tokens, stream=False)
            except Exception as e:
                log.warning(f"[{model}] failed: {e}, trying next...")
        raise RuntimeError("All providers exhausted.")

    def stream(self, messages: list[dict], max_tokens: int = 8192) -> Iterator[str]:
        """Streaming completion with cascade fallback."""
        cascade = self._resolve_cascade()
        for model in cascade:
            try:
                yield from self._call(model, messages, max_tokens, stream=True)
                return
            except Exception as e:
                log.warning(f"[{model}] stream failed: {e}, trying next...")
        raise RuntimeError("All providers exhausted.")

    # ── internals ──────────────────────────────────────────────────────────────
    def _resolve_cascade(self) -> list[str]:
        if self.model == "auto":      return DEFAULT_CASCADE
        if self.model == "coding":    return CODING_CASCADE
        if self.model == "reasoning": return REASONING_CASCADE
        return [self.model]

    def _call(self, model: str, messages: list, max_tokens: int, stream: bool):
        info     = MODELS[model]
        provider = info["provider"]
        dispatch = {
            "groq":       self._groq,
            "together":   self._together,
            "openrouter": self._openrouter,
            "ollama":     self._ollama,
            "mistral":    self._mistral,
        }
        return dispatch[provider](model, messages, max_tokens, stream)

    # ── Groq ───────────────────────────────────────────────────────────────────
    def _groq(self, model, messages, max_tokens, stream):
        key = os.getenv("GROQ_API_KEY", "")
        if not key: raise RuntimeError("GROQ_API_KEY not set")
        model_id = model.split("/", 1)[1]
        # map display names → groq IDs
        groq_ids = {
            "llama-3.3-70b": "llama-3.3-70b-versatile",
            "llama-3.1-8b":  "llama-3.1-8b-instant",
            "mixtral-8x7b":  "mixtral-8x7b-32768",
            "gemma2-9b":     "gemma2-9b-it",
            "qwen-qwq-32b":  "qwen-qwq-32b",
        }
        real_id = groq_ids.get(model_id, model_id)
        return self._openai_compat(
            "https://api.groq.com/openai/v1/chat/completions",
            key, real_id, messages, max_tokens, stream,
        )

    # ── Together AI ────────────────────────────────────────────────────────────
    def _together(self, model, messages, max_tokens, stream):
        key = os.getenv("TOGETHER_API_KEY", "")
        if not key: raise RuntimeError("TOGETHER_API_KEY not set")
        together_ids = {
            "llama-3.3-70b": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
            "qwen2.5-72b":   "Qwen/Qwen2.5-72B-Instruct-Turbo",
            "deepseek-r1":   "deepseek-ai/DeepSeek-R1",
        }
        model_id = model.split("/", 1)[1]
        real_id  = together_ids.get(model_id, model_id)
        return self._openai_compat(
            "https://api.together.xyz/v1/chat/completions",
            key, real_id, messages, max_tokens, stream,
        )

    # ── OpenRouter ─────────────────────────────────────────────────────────────
    def _openrouter(self, model, messages, max_tokens, stream):
        key = os.getenv("OPENROUTER_API_KEY", "")
        if not key: raise RuntimeError("OPENROUTER_API_KEY not set")
        or_ids = {
            "kimi-k2":       "moonshotai/kimi-k2",
            "gemini-2.5-pro":"google/gemini-2.5-pro",
            "deepseek-r1":   "deepseek/deepseek-r1",
            "qwen3-235b":    "qwen/qwen3-235b-a22b",
            "codex-mini":    "openai/codex-mini",
        }
        model_id = model.split("/", 1)[1]
        real_id  = or_ids.get(model_id, model_id)
        return self._openai_compat(
            "https://openrouter.ai/api/v1/chat/completions",
            key, real_id, messages, max_tokens, stream,
            extra_headers={"HTTP-Referer": "https://github.com/mahak867/ai-dev-engine"},
        )

    # ── Ollama (local) ─────────────────────────────────────────────────────────
    def _ollama(self, model, messages, max_tokens, stream):
        host     = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        model_id = model.split("/", 1)[1]
        payload  = {"model": model_id, "messages": messages, "stream": stream,
                    "options": {"temperature": self.temperature, "num_predict": max_tokens}}
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

    # ── Mistral ────────────────────────────────────────────────────────────────
    def _mistral(self, model, messages, max_tokens, stream):
        key = os.getenv("MISTRAL_API_KEY", "")
        if not key: raise RuntimeError("MISTRAL_API_KEY not set")
        mistral_ids = {"codestral": "codestral-latest", "mistral-large": "mistral-large-latest"}
        model_id = model.split("/", 1)[1]
        real_id  = mistral_ids.get(model_id, model_id)
        return self._openai_compat(
            "https://api.mistral.ai/v1/chat/completions",
            key, real_id, messages, max_tokens, stream,
        )

    # ── OpenAI-compatible helper ───────────────────────────────────────────────
    def _openai_compat(self, url, key, model_id, messages, max_tokens, stream,
                       extra_headers: dict | None = None):
        headers = {"Authorization": f"Bearer {key}"}
        if extra_headers: headers.update(extra_headers)
        payload = {
            "model":       model_id,
            "messages":    messages,
            "max_tokens":  max_tokens,
            "temperature": self.temperature,
            "stream":      stream,
        }
        r = self._session.post(url, json=payload, headers=headers,
                               stream=stream, timeout=120)
        r.raise_for_status()
        if not stream:
            return r.json()["choices"][0]["message"]["content"]
        def _gen():
            for line in r.iter_lines():
                if line and line.startswith(b"data: "):
                    data = line[6:]
                    if data == b"[DONE]": break
                    try:
                        chunk = json.loads(data)
                        if token := chunk["choices"][0].get("delta", {}).get("content", ""):
                            yield token
                    except Exception:
                        pass
        return _gen()
