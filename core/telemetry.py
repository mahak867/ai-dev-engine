"""
APEX — per-agent token, cost and latency accounting.

Every LLM call made through ``LLMProvider`` is recorded against the agent that
made it and the run (``UsageTracker``) that is active in the current context.

    tracker = UsageTracker()
    with track(tracker):
        orchestrator.generate_fullstack(...)
    print(tracker.summary())

Token counts come from the provider's ``usage`` block when it returns one and
are otherwise estimated at ~4 characters per token (``estimated: true``).

Cost is only computed for models with a known price. Prices change, so none are
hard-coded: set them in ``APEX_PRICES`` (JSON, USD per 1M tokens) or a JSON file
at ``APEX_PRICES_FILE``, e.g. ``{"groq/llama-3.3-70b": {"input": 0.59, "output": 0.79}}``.
Ollama models are always $0. Unknown prices are reported as ``null``, never 0.
"""
from __future__ import annotations

import contextvars
import functools
import json
import os
import threading
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from typing import Callable, Iterator

_tracker: contextvars.ContextVar["UsageTracker | None"] = contextvars.ContextVar("apex_tracker", default=None)
_agent: contextvars.ContextVar[str] = contextvars.ContextVar("apex_agent", default="unattributed")


@dataclass
class CallRecord:
    agent: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    seconds: float
    cost_usd: float | None
    estimated: bool = False
    ok: bool = True
    ts: float = field(default_factory=time.time)


def estimate_tokens(text_or_messages) -> int:
    if isinstance(text_or_messages, list):
        text = "".join(str(m.get("content", "")) for m in text_or_messages)
    else:
        text = str(text_or_messages or "")
    return max(1, len(text) // 4) if text else 0


@functools.lru_cache(maxsize=1)
def _prices() -> dict:
    prices: dict = {}
    path = os.environ.get("APEX_PRICES_FILE")
    if path and os.path.isfile(path):
        try:
            with open(path, encoding="utf-8") as f:
                prices.update(json.load(f))
        except (OSError, ValueError):
            pass
    raw = os.environ.get("APEX_PRICES")
    if raw:
        try:
            prices.update(json.loads(raw))
        except ValueError:
            pass
    return prices


def reload_prices() -> None:
    _prices.cache_clear()


def price_for(model: str, prompt_tokens: int, completion_tokens: int) -> float | None:
    if model.startswith("ollama/") or model.startswith("fake/"):
        return 0.0
    p = _prices().get(model)
    if not p:
        return None
    return round(prompt_tokens / 1e6 * float(p.get("input", 0))
                 + completion_tokens / 1e6 * float(p.get("output", 0)), 6)


class UsageTracker:
    """Thread-safe collection of LLM calls for one run."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.records: list[CallRecord] = []
        self.stage_seconds: dict[str, float] = {}
        self.started = time.time()

    def add(self, rec: CallRecord) -> None:
        with self._lock:
            self.records.append(rec)

    def add_stage_time(self, stage: str, seconds: float) -> None:
        with self._lock:
            self.stage_seconds[stage] = self.stage_seconds.get(stage, 0.0) + seconds

    def summary(self) -> dict:
        with self._lock:
            recs = list(self.records)
            stages = dict(self.stage_seconds)
        by_agent: dict[str, dict] = {}
        for r in recs:
            a = by_agent.setdefault(r.agent, {
                "calls": 0, "prompt_tokens": 0, "completion_tokens": 0,
                "seconds": 0.0, "cost_usd": 0.0, "cost_known": True, "models": set(),
            })
            a["calls"] += 1
            a["prompt_tokens"] += r.prompt_tokens
            a["completion_tokens"] += r.completion_tokens
            a["seconds"] += r.seconds
            a["models"].add(r.model)
            if r.cost_usd is None:
                a["cost_known"] = False
            else:
                a["cost_usd"] += r.cost_usd
        for a in by_agent.values():
            a["models"] = sorted(a["models"])
            a["seconds"] = round(a["seconds"], 2)
            a["cost_usd"] = round(a["cost_usd"], 6) if a.pop("cost_known") else None
            a["total_tokens"] = a["prompt_tokens"] + a["completion_tokens"]
        for stage, secs in stages.items():
            by_agent.setdefault(stage, {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0,
                                        "total_tokens": 0, "seconds": 0.0, "cost_usd": 0.0, "models": []})
            by_agent[stage]["seconds"] = round(by_agent[stage]["seconds"] + secs, 2)
        costs = [r.cost_usd for r in recs]
        return {
            "calls": len(recs),
            "failed_calls": sum(1 for r in recs if not r.ok),
            "prompt_tokens": sum(r.prompt_tokens for r in recs),
            "completion_tokens": sum(r.completion_tokens for r in recs),
            "total_tokens": sum(r.prompt_tokens + r.completion_tokens for r in recs),
            "llm_seconds": round(sum(r.seconds for r in recs), 2),
            "wall_seconds": round(time.time() - self.started, 2),
            "cost_usd": round(sum(costs), 6) if recs and all(c is not None for c in costs) else (0.0 if not recs else None),
            "estimated_tokens": any(r.estimated for r in recs),
            "by_agent": by_agent,
        }

    def to_json(self) -> str:
        return json.dumps({"summary": self.summary(), "calls": [asdict(r) for r in self.records]}, indent=2)


# ── context helpers ────────────────────────────────────────────────────────────
@contextmanager
def track(tracker: UsageTracker) -> Iterator[UsageTracker]:
    token = _tracker.set(tracker)
    try:
        yield tracker
    finally:
        _tracker.reset(token)


@contextmanager
def agent_scope(name: str) -> Iterator[None]:
    token = _agent.set(name)
    try:
        yield
    finally:
        _agent.reset(token)


@contextmanager
def stage(name: str) -> Iterator[None]:
    """Time a non-LLM stage (e.g. Executor sandbox run) into the active tracker."""
    t0 = time.time()
    try:
        yield
    finally:
        t = _tracker.get()
        if t is not None:
            t.add_stage_time(name, time.time() - t0)


def current_agent() -> str:
    return _agent.get()


def current_tracker() -> "UsageTracker | None":
    return _tracker.get()


def record(model: str, prompt_tokens: int, completion_tokens: int, seconds: float,
           *, estimated: bool = False, ok: bool = True) -> None:
    t = _tracker.get()
    if t is None:
        return
    t.add(CallRecord(
        agent=_agent.get(), model=model,
        prompt_tokens=int(prompt_tokens or 0), completion_tokens=int(completion_tokens or 0),
        seconds=round(seconds, 3),
        cost_usd=price_for(model, int(prompt_tokens or 0), int(completion_tokens or 0)) if ok else 0.0,
        estimated=estimated, ok=ok,
    ))


def in_context(fn: Callable, *args, **kwargs) -> Callable[[], object]:
    """Wrap ``fn`` so a new thread runs it with the caller's tracker/agent context."""
    ctx = contextvars.copy_context()
    return lambda: ctx.run(fn, *args, **kwargs)


def agent_run(name: str | None = None):
    """Decorator: attribute every LLM call inside the wrapped method to the agent."""
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(self, *a, **kw):
            with agent_scope(name or getattr(self, "name", type(self).__name__)):
                return fn(self, *a, **kw)
        wrapper.__apex_scoped__ = True
        return wrapper
    return deco
