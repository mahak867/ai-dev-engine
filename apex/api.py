"""
Public Python API.

    import apex

    result = apex.generate("todo API with auth and tests", name="todo", sandbox=True)
    print(result.path, result.quality_score, result.usage["total_tokens"])
"""
from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class GenerationResult:
    """What a pipeline run produced."""
    path: str                                  # project directory on disk
    files: list[str]                           # relative paths written
    quality_score: int | None                  # Reviewer's 0-100 score (None if review was skipped)
    review_rounds: int                         # Reviewer ⇄ Coder rounds used
    sandbox: dict[str, Any] | None             # {"attempts", "passed", "first_attempt_passed", "final"} or None
    usage: dict[str, Any] = field(default_factory=dict)   # tokens / cost / seconds, total and per agent

    @property
    def passed_sandbox(self) -> bool | None:
        return None if self.sandbox is None else bool(self.sandbox.get("passed"))


def generate(
    request: str,
    name: str = "app",
    output_dir: str | os.PathLike = ".",
    *,
    model: str = "auto",
    review: bool = True,
    sandbox: bool | None = None,
    on_event: Callable[..., None] | None = None,
    memory_dir: str | os.PathLike | None = None,
) -> GenerationResult:
    """
    Run the 9-agent pipeline and write the project to ``output_dir/name``.

    model       "auto" (provider cascade) or one model id, e.g. "groq/llama-3.3-70b"
                or "openai/gpt-4o-mini" (any OpenAI-compatible endpoint via OPENAI_BASE_URL).
    review      False skips the Reviewer ⇄ Coder loop.
    sandbox     True runs the result in the Docker sandbox and heals on failure;
                None follows the APEX_SANDBOX environment variable.
    on_event    callback(agent, status, message, extra) for live progress.
    memory_dir  where cross-run lessons are stored (default ~/.apex/memory).
    """
    from apex import telemetry
    from apex.ai.provider import api_keys
    from apex.memory.store import MemoryStore
    from apex.orchestrator import Orchestrator

    tracker = telemetry.UsageTracker()
    orch = Orchestrator(
        on_event=on_event or (lambda *a, **k: None),
        sandbox=sandbox,
        memory_store=MemoryStore(str(memory_dir)) if memory_dir else None,
    )
    pinned = None if model in ("auto", "coding", "reasoning") else model
    with telemetry.track(tracker), api_keys(model=pinned):
        path = orch.generate_fullstack(name=name, request=request, output_dir=str(output_dir),
                                       skip_review=not review)
    run = orch.last_run
    return GenerationResult(
        path=path,
        files=sorted(run.files) if run else [],
        quality_score=run.review.score if run and run.review else None,
        review_rounds=run.review_rounds if run else 0,
        sandbox=orch.last_sandbox,
        usage=tracker.summary(),
    )
