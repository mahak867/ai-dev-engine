# core/ai/harness.py
# APEX Agent Harness - inspired by claw-code's architectural patterns
# Clean-room implementation for the APEX AI Dev Engine
# Patterns: tool loop, context compaction, hook pipeline, session state, task graph

import json
import time
from typing import Callable, Any, Optional
from dataclasses import dataclass, field
from enum import Enum


# ── HOOK PIPELINE ─────────────────────────────────────────────────────────────
# Pre/Post hooks on every generation step (from claw-code hooks/ architecture)

class HookResult(Enum):
    CONTINUE = "continue"
    SKIP     = "skip"
    RETRY    = "retry"
    ABORT    = "abort"


@dataclass
class HookContext:
    step_name: str
    model: str
    prompt: str
    response: str = ""
    attempt: int = 0
    metadata: dict = field(default_factory=dict)


class HookPipeline:
    """Pre/PostToolUse hook pipeline. Runs hooks before and after each step."""

    def __init__(self):
        self._pre_hooks:  list[Callable] = []
        self._post_hooks: list[Callable] = []

    def add_pre(self, fn: Callable):
        self._pre_hooks.append(fn)

    def add_post(self, fn: Callable):
        self._post_hooks.append(fn)

    def run_pre(self, ctx: HookContext) -> HookResult:
        for hook in self._pre_hooks:
            try:
                result = hook(ctx)
                if result in (HookResult.SKIP, HookResult.ABORT):
                    return result
            except Exception as e:
                print(f"  [Hook] Pre-hook error: {e}")
        return HookResult.CONTINUE

    def run_post(self, ctx: HookContext) -> HookResult:
        for hook in self._post_hooks:
            try:
                result = hook(ctx)
                if result == HookResult.RETRY:
                    return result
            except Exception as e:
                print(f"  [Hook] Post-hook error: {e}")
        return HookResult.CONTINUE


# Built-in hooks for APEX engine
def _hook_size_check(ctx: HookContext) -> HookResult:
    """Pre-hook: abort if prompt is too large for Groq."""
    MAX = 80000
    if len(ctx.prompt) > MAX:
        ctx.prompt = ctx.prompt[:MAX]
        print(f"  [Hook] Prompt trimmed {len(ctx.prompt)} -> {MAX} chars")
    return HookResult.CONTINUE


def _hook_validate_json(ctx: HookContext) -> HookResult:
    """Post-hook: validate JSON response for file-generating steps."""
    if ctx.step_name in ("backend_files", "frontend_files", "config_files"):
        text = ctx.response.strip()
        if not text:
            return HookResult.RETRY
        # Try to find JSON
        start = text.find("{")
        end = text.rfind("}") + 1
        if start < 0 or end <= start:
            print(f"  [Hook] No JSON found in {ctx.step_name} response - will retry")
            return HookResult.RETRY
    return HookResult.CONTINUE


def _hook_log_step(ctx: HookContext) -> HookResult:
    """Post-hook: log step completion to memory."""
    try:
        from core.ai.memory_system import learn_fix
        if ctx.response and "error" in ctx.response.lower()[:100]:
            learn_fix(
                issue=f"Step {ctx.step_name} returned error",
                fix="Check model output format",
                file_type=ctx.step_name
            )
    except Exception:
        pass
    return HookResult.CONTINUE


# ── CONTEXT COMPACTOR ─────────────────────────────────────────────────────────
# Compress accumulated context to stay under token limits (claw-code pattern)

class ContextCompactor:
    """Compresses pipeline context to prevent 413 errors."""

    MAX_CHARS = {
        "api_contract":  1000,   # Architecture output -> backend
        "db_schema":     600,    # Schema -> backend
        "backend_files": 0,      # Don't pass raw files forward
        "memory_hint":   200,    # Memory context
    }

    @classmethod
    def compact(cls, ctx: dict) -> dict:
        """Compact context dict, summarising large fields."""
        compacted = dict(ctx)

        for key, max_chars in cls.MAX_CHARS.items():
            if key in compacted and isinstance(compacted[key], str):
                value = compacted[key]
                if max_chars == 0:
                    # Strip entirely - too large to pass forward
                    compacted[key] = ""
                elif len(value) > max_chars:
                    compacted[key] = value[:max_chars] + "..."
                    print(f"  [Compact] {key}: {len(value)} -> {max_chars} chars")

        return compacted

    @classmethod
    def extract_key_facts(cls, architecture: str) -> str:
        """Extract only key facts from architecture output."""
        if len(architecture) <= 1000:
            return architecture

        lines = architecture.split("\n")
        key_lines = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # Keep lines with endpoints, models, or key decisions
            if any(kw in line.lower() for kw in [
                "get ", "post ", "put ", "delete ", "patch ",
                "model:", "table:", "class ", "endpoint",
                "auth", "route", "blueprint", "schema"
            ]):
                key_lines.append(line)
                if len("\n".join(key_lines)) > 900:
                    break

        result = "\n".join(key_lines[:30])
        return result if result else architecture[:1000]


# ── TOOL LOOP ─────────────────────────────────────────────────────────────────
# Retry loop with backoff - agent keeps trying until success (claw-code pattern)

class ToolLoop:
    """Retry loop for a single generation step. Retries on failure with backoff."""

    def __init__(self, max_attempts: int = 3, hooks: Optional[HookPipeline] = None):
        self.max_attempts = max_attempts
        self.hooks = hooks or HookPipeline()

    def run(self, step_name: str, model: str, prompt: str,
            generate_fn: Callable) -> str:
        """Run a generation step with retry loop and hooks."""

        ctx = HookContext(step_name=step_name, model=model, prompt=prompt)

        for attempt in range(self.max_attempts):
            ctx.attempt = attempt

            # Pre-hooks (size check, validation)
            pre_result = self.hooks.run_pre(ctx)
            if pre_result == HookResult.SKIP:
                return ""
            if pre_result == HookResult.ABORT:
                raise RuntimeError(f"Step {step_name} aborted by pre-hook")

            try:
                response = generate_fn(ctx.prompt)
                ctx.response = response

                # Post-hooks (JSON validation, logging)
                post_result = self.hooks.run_post(ctx)
                if post_result == HookResult.RETRY and attempt < self.max_attempts - 1:
                    print(f"  [ToolLoop] Retrying {step_name} (attempt {attempt+2}/{self.max_attempts})")
                    time.sleep(2)
                    continue

                return response

            except Exception as e:
                err = str(e)
                if "413" in err or "Payload Too Large" in err:
                    # Aggressively trim and retry
                    trim = int(len(ctx.prompt) * 0.7)
                    print(f"  [ToolLoop] 413 - trimming prompt to {trim} chars")
                    ctx.prompt = ctx.prompt[:trim]
                    if attempt < self.max_attempts - 1:
                        time.sleep(2)
                        continue
                elif "429" in err or "rate limit" in err.lower():
                    wait = 65 * (attempt + 1)
                    print(f"  [ToolLoop] Rate limit - waiting {wait}s")
                    time.sleep(wait)
                    if attempt < self.max_attempts - 1:
                        continue
                raise

        raise RuntimeError(f"Step {step_name} failed after {self.max_attempts} attempts")


# ── SESSION STATE ─────────────────────────────────────────────────────────────
# Persistent context across all pipeline steps (claw-code session pattern)

class SessionState:
    """Tracks state across the entire generation session."""

    def __init__(self, request: str, spec: dict):
        self.request = request
        self.spec = spec
        self.started_at = time.time()
        self.steps_completed: list[str] = []
        self.steps_failed: list[str] = []
        self.files_generated: int = 0
        self.total_tokens_used: int = 0
        self.ctx: dict = {"request": request, "spec": spec}

    def record_step(self, name: str, success: bool, output_size: int = 0):
        if success:
            self.steps_completed.append(name)
        else:
            self.steps_failed.append(name)
        self.total_tokens_used += output_size // 4

    def compact(self):
        """Compact context using auto-compactor."""
        try:
            from core.ai.auto_compactor import compact
            self.ctx = compact(self.ctx)
        except ImportError:
            self.ctx = ContextCompactor.compact(self.ctx)

    def elapsed(self) -> float:
        return time.time() - self.started_at

    def summary(self) -> str:
        return (
            f"Session: {len(self.steps_completed)} steps done, "
            f"{self.files_generated} files, "
            f"{self.elapsed():.0f}s elapsed"
        )


# ── TASK DEPENDENCY GRAPH ─────────────────────────────────────────────────────
# Steps can declare dependencies (claw-code Task* pattern)

@dataclass
class Task:
    name: str
    fn: Callable
    depends_on: list[str] = field(default_factory=list)
    output_key: str = ""
    required: bool = True


class TaskGraph:
    """Execute tasks in dependency order, skip failed optional tasks."""

    def __init__(self, tasks: list[Task]):
        self.tasks = {t.name: t for t in tasks}
        self.completed: dict[str, Any] = {}
        self.failed: set[str] = set()

    def _can_run(self, task: Task) -> bool:
        for dep in task.depends_on:
            if dep in self.failed:
                return False
            if dep not in self.completed:
                return False
        return True

    def run(self, initial_ctx: dict) -> dict:
        ctx = dict(initial_ctx)
        pending = list(self.tasks.values())
        max_iters = len(pending) * 2

        for _ in range(max_iters):
            if not pending:
                break

            made_progress = False
            still_pending = []

            for task in pending:
                if not self._can_run(task):
                    still_pending.append(task)
                    continue

                try:
                    result = task.fn(ctx)
                    if task.output_key:
                        ctx[task.output_key] = result
                    self.completed[task.name] = result
                    made_progress = True
                except Exception as e:
                    print(f"  [TaskGraph] Task '{task.name}' failed: {e}")
                    self.failed.add(task.name)
                    if task.required:
                        raise
                    made_progress = True

            pending = still_pending
            if not made_progress:
                # Circular dependency or all blocked
                for t in pending:
                    print(f"  [TaskGraph] Skipping blocked task: {t.name}")
                break

        return ctx


# ── APEX HARNESS ──────────────────────────────────────────────────────────────
# Main harness that wires everything together

class ApexHarness:
    """
    The APEX generation harness.
    Wires: ToolLoop + HookPipeline + ContextCompactor + SessionState + TaskGraph
    """

    def __init__(self, session: SessionState):
        self.session = session
        self.hooks = HookPipeline()
        self.tool_loop = ToolLoop(max_attempts=3, hooks=self.hooks)

        # Register built-in hooks
        self.hooks.add_pre(_hook_size_check)
        self.hooks.add_post(_hook_validate_json)
        self.hooks.add_post(_hook_log_step)

    def run_step(self, step_name: str, model: str,
                 prompt: str, generate_fn: Callable) -> str:
        """Run a single generation step through the harness."""

        # Compact context before each step
        self.session.compact()

        result = self.tool_loop.run(
            step_name=step_name,
            model=model,
            prompt=prompt,
            generate_fn=generate_fn
        )

        self.session.record_step(step_name, success=True, output_size=len(result))
        return result

    def get_ctx(self) -> dict:
        return self.session.ctx

    def update_ctx(self, updates: dict):
        self.session.ctx.update(updates)
        # Compact immediately after architecture (largest output)
        if "api_contract" in updates:
            raw = updates["api_contract"]
            compacted = ContextCompactor.extract_key_facts(raw)
            self.session.ctx["api_contract"] = compacted
            if len(raw) != len(compacted):
                print(f"  [Harness] Architecture compacted: {len(raw)} -> {len(compacted)} chars")
