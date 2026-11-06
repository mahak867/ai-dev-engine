"""
APEX AI Dev Engine v3 — Multi-Provider Router
Qwen Cloud (primary/hackathon) + Groq (free fallback) + Ollama (local) + optional paid.
"""
from __future__ import annotations
import os, json, time, logging, threading, contextvars
from contextlib import contextmanager
from typing import Callable, Iterator
import requests

from core import telemetry

log = logging.getLogger("apex.provider")

# ── Model catalogue ────────────────────────────────────────────────────────────
MODELS = {
    # ── PRIMARY: Qwen Cloud (hackathon requirement) ───────────────────────────
    # Qwen 3.7 (launched May 20, 2026) — agent-tuned flagship, 1M context, no
    # free tier; billed against hackathon DashScope credits. Plus adds vision
    # (used for the wireframe-screenshot -> frontend code feature).
    "qwen/qwen3.7-max":           {"provider": "qwen",  "ctx": 1_000_000, "free": True},
    "qwen/qwen3.7-plus":          {"provider": "qwen",  "ctx": 1_000_000, "free": True, "vision": True},
    # Legacy/cheaper Qwen tier — kept as same-provider fallback if 3.7 errors
    # or credits run low, so the cascade never fully drops out of Qwen Cloud.
    "qwen/qwen-plus":             {"provider": "qwen",  "ctx": 131_072, "free": True},
    "qwen/qwen-turbo":            {"provider": "qwen",  "ctx": 131_072, "free": True},
    "qwen/qwen-max":              {"provider": "qwen",  "ctx":  32_768, "free": True},
    "qwen/qwen-long":             {"provider": "qwen",  "ctx": 10_000_000, "free": True},
    # ── FREE: Groq (fast fallback) ────────────────────────────────────────────
    "groq/llama-3.3-70b":        {"provider": "groq",  "ctx": 128_000, "free": True},
    "groq/llama-3.1-8b":         {"provider": "groq",  "ctx": 128_000, "free": True},
    "groq/mixtral-8x7b":         {"provider": "groq",  "ctx":  32_768, "free": True},
    "groq/gemma2-9b":            {"provider": "groq",  "ctx":   8_192, "free": True},
    "groq/qwen-qwq-32b":         {"provider": "groq",  "ctx": 128_000, "free": True},
    # ── FREE: Ollama (local, fully offline) ───────────────────────────────────
    "ollama/llama3.3":           {"provider": "ollama", "ctx": 128_000, "free": True},
    "ollama/qwen2.5-coder:32b":  {"provider": "ollama", "ctx": 128_000, "free": True},
    "ollama/deepseek-coder-v2":  {"provider": "ollama", "ctx": 163_840, "free": True},
    "ollama/codellama:70b":      {"provider": "ollama", "ctx": 100_000, "free": True},
    "ollama/qwen2.5:72b":        {"provider": "ollama", "ctx": 128_000, "free": True},
    # ── OPTIONAL paid (only used if key is set) ───────────────────────────────
    "or/kimi-k2":                {"provider": "openrouter", "ctx": 131_072, "free": False},
    "or/deepseek-r1":            {"provider": "openrouter", "ctx": 163_840, "free": False},
    "or/gemini-2.5-pro":         {"provider": "openrouter", "ctx": 1_048_576, "free": False},
    "together/llama-3.3-70b":    {"provider": "together",   "ctx": 128_000, "free": False},
    "together/deepseek-r1":      {"provider": "together",   "ctx": 163_840, "free": False},
    "mistral/codestral":         {"provider": "mistral",    "ctx": 256_000, "free": False},
    # ── Deterministic fake (tests / eval self-check only; never in a cascade) ──
    "fake/canned":               {"provider": "fake",       "ctx": 1_000_000, "free": True},
}

# ── Per-request API keys (bring-your-own-key) ──────────────────────────────────
# The hosted demo lets a visitor paste their own key. It is held in a context
# variable for that one run only — never written to os.environ, disk or logs.
_key_overrides: contextvars.ContextVar[dict] = contextvars.ContextVar("apex_key_overrides", default={})


_model_override: contextvars.ContextVar[str] = contextvars.ContextVar("apex_model_override", default="")


@contextmanager
def api_keys(model: str | None = None, **keys: str):
    """
    ``with api_keys(GROQ_API_KEY="gsk_...", model="groq/llama-3.3-70b")``: use
    these keys (and optionally pin one model) for every call in this context.
    """
    clean = {k: v.strip() for k, v in keys.items() if isinstance(v, str) and v.strip()}
    token = _key_overrides.set({**_key_overrides.get(), **clean})
    mtoken = _model_override.set(model) if model else None
    try:
        yield
    finally:
        _key_overrides.reset(token)
        if mtoken is not None:
            _model_override.reset(mtoken)


def _key(name: str) -> str:
    return _key_overrides.get().get(name) or os.getenv(name, "")


def byok_active() -> bool:
    return bool(_key_overrides.get())


# ── Fake provider hook (tests / `eval --self-test`) ───────────────────────────
_fake_responder: Callable[[list[dict]], str] | None = None


def set_fake_responder(fn: Callable[[list[dict]], str] | None) -> None:
    """Install a function that answers ``fake/canned`` calls (None to remove)."""
    global _fake_responder
    _fake_responder = fn

FREE_MODELS = [m for m, i in MODELS.items() if i["free"]]
PAID_MODELS = [m for m, i in MODELS.items() if not i["free"]]
VISION_MODELS = [m for m, i in MODELS.items() if i.get("vision")]

# ── Cascades — Qwen 3.7 first, legacy Qwen second, Groq fallback ──────────────
# FREE quota cascades — qwen3.7-plus is primary (999,597 free tokens remaining
# on Token Plan, same Qwen 3.7 family, vision-capable).
# qwen3.7-max exhausted free quota — now pay-as-you-go only, kept as fallback.
DEFAULT_CASCADE = [
    "qwen/qwen3.7-plus",
    "qwen/qwen-plus",
    "qwen/qwen-turbo",
    "groq/llama-3.3-70b",
    "groq/qwen-qwq-32b",
]
CODING_CASCADE = [
    "qwen/qwen3.7-plus",
    "qwen/qwen-plus",
    "qwen/qwen-turbo",
    "groq/qwen-qwq-32b",
    "groq/llama-3.3-70b",
    "ollama/qwen2.5-coder:32b",
    "ollama/deepseek-coder-v2",
]
REASONING_CASCADE = [
    "qwen/qwen3.7-plus",
    "qwen/qwen3.7-max",
    "qwen/qwen-plus",
    "qwen/qwen-max",
    "groq/qwen-qwq-32b",
    "groq/llama-3.3-70b",
    "ollama/qwen2.5:72b",
]
# Vision-capable cascade — for the wireframe-screenshot -> frontend code feature.
VISION_CASCADE = [
    "qwen/qwen3.7-plus",
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
    """Unified LLM interface — Qwen-first cascade with Groq fallback."""

    def __init__(self, model: str = "auto", temperature: float = 0.2):
        self.model       = model
        self.temperature = temperature
        self._session    = requests.Session()
        self._session.headers.update({"Content-Type": "application/json"})
        self._usage      = threading.local()

    # ── Public API ─────────────────────────────────────────────────────────────
    def complete(self, messages: list[dict], max_tokens: int = 8192) -> str:
        for model in self._resolve_cascade():
            self._usage.value = None
            t0 = time.time()
            try:
                out = self._call(model, messages, max_tokens, stream=False)
            except Exception as e:
                log.warning(f"[{model}] failed: {e}, trying next...")
                if not isinstance(e, KeyError) and "not set" not in str(e):
                    telemetry.record(model, 0, 0, time.time() - t0, ok=False)
                continue
            usage = self._usage.value or {}
            pt, ct = usage.get("prompt_tokens"), usage.get("completion_tokens")
            estimated = pt is None or ct is None
            telemetry.record(
                model,
                pt if pt is not None else telemetry.estimate_tokens(messages),
                ct if ct is not None else telemetry.estimate_tokens(out),
                time.time() - t0, estimated=estimated,
            )
            return out
        raise RuntimeError("All providers exhausted — set QWEN_API_KEY, GROQ_API_KEY or OLLAMA_HOST.")

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
        # APEX_MODEL pins every agent to one model (used by the eval harness so
        # single-agent and society runs are compared on the same model).
        pinned = _model_override.get() or os.getenv("APEX_MODEL", "").strip()
        if pinned:
            return [pinned]
        if self.model == "auto":
            base = DEFAULT_CASCADE
        elif self.model == "coding":
            base = CODING_CASCADE
        elif self.model == "reasoning":
            base = REASONING_CASCADE
        else:
            return [self.model]

        extras: list[str] = []
        for m, info in MODELS.items():
            if not info["free"]:
                extras += _paid_fallback(info["provider"], m)
        return base + extras

    # ── Internal dispatch ──────────────────────────────────────────────────────
    def _call(self, model: str, messages: list, max_tokens: int, stream: bool):
        provider = MODELS[model]["provider"]
        return {
            "qwen":       self._qwen,
            "groq":       self._groq,
            "ollama":     self._ollama,
            "openrouter": self._openrouter,
            "together":   self._together,
            "mistral":    self._mistral,
            "fake":       self._fake,
        }[provider](model, messages, max_tokens, stream)

    def _fake(self, model, messages, max_tokens, stream):
        if _fake_responder is None:
            raise RuntimeError("fake provider has no responder installed")
        out = _fake_responder(messages)
        return iter([out]) if stream else out

    # ── Qwen Cloud (PRIMARY — hackathon requirement) ───────────────────────────
    def _qwen(self, model, messages, max_tokens, stream):
        key = _key("QWEN_API_KEY")
        if not key:
            raise RuntimeError("QWEN_API_KEY not set — get it from home.qwencloud.com/api-keys")
        model_id = model.split("/", 1)[1]
        return self._openai_compat(
            "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions",
            key, model_id, messages, max_tokens, stream,
        )

    # ── Groq (FREE fallback) ───────────────────────────────────────────────────
    def _groq(self, model, messages, max_tokens, stream):
        key = _key("GROQ_API_KEY")
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
            data = r.json()
            self._usage.value = {"prompt_tokens": data.get("prompt_eval_count"),
                                 "completion_tokens": data.get("eval_count")}
            return data["message"]["content"]
        def _gen():
            for line in r.iter_lines():
                if line:
                    chunk = json.loads(line)
                    if token := chunk.get("message", {}).get("content", ""):
                        yield token
                    if chunk.get("done"):
                        break
        return _gen()

    # ── OpenRouter (optional paid) ─────────────────────────────────────────────
    def _openrouter(self, model, messages, max_tokens, stream):
        key = _key("OPENROUTER_API_KEY")
        if not key:
            raise RuntimeError("OPENROUTER_API_KEY not set")
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
        key = _key("TOGETHER_API_KEY")
        if not key:
            raise RuntimeError("TOGETHER_API_KEY not set")
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
        key = _key("MISTRAL_API_KEY")
        if not key:
            raise RuntimeError("MISTRAL_API_KEY not set")
        ids = {"codestral": "codestral-latest"}
        model_id = ids.get(model.split("/", 1)[1], model.split("/", 1)[1])
        return self._openai_compat(
            "https://api.mistral.ai/v1/chat/completions",
            key, model_id, messages, max_tokens, stream,
        )

    # ── OpenAI-compat helper ───────────────────────────────────────────────────
    def _openai_compat(self, url, key, model_id, messages, max_tokens, stream,
                       extra_headers: dict | None = None):
        import time as _time
        headers = {"Authorization": f"Bearer {key}"}
        if extra_headers:
            headers.update(extra_headers)
        payload = {
            "model": model_id, "messages": messages,
            "max_tokens": max_tokens, "temperature": self.temperature, "stream": stream,
        }
        last_err = None
        for attempt in range(3):
            try:
                r = self._session.post(url, json=payload, headers=headers,
                                       stream=stream, timeout=180)
                if r.status_code == 429 or r.status_code >= 500:
                    wait = (2 ** attempt) * 4  # 4s, 8s, 16s
                    log.warning(f"HTTP {r.status_code} from {model_id}, retry in {wait}s ({attempt+1}/3)")
                    _time.sleep(wait)
                    last_err = f"HTTP {r.status_code}"
                    continue
                r.raise_for_status()
                if not stream:
                    data = r.json()
                    self._usage.value = data.get("usage") or None
                    return data["choices"][0]["message"]["content"]
                def _gen():
                    for line in r.iter_lines():
                        if line and line.startswith(b"data: "):
                            data = line[6:]
                            if data == b"[DONE]":
                                break
                            try:
                                if token := json.loads(data)["choices"][0].get("delta", {}).get("content", ""):
                                    yield token
                            except Exception:
                                pass
                return _gen()
            except Exception as e:
                last_err = str(e)
                if attempt < 2:
                    _time.sleep(4 * (attempt + 1))
                continue
        raise RuntimeError(f"{model_id} failed after 3 attempts: {last_err}")
