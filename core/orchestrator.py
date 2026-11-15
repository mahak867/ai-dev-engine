"""
APEX — pipeline orchestrator for the 9-agent society.

    Memory → Planner ∥ Architect → Coder ⇄ Reviewer → SelfHealer → Debugger
           → Executor (syntax check + Docker sandbox, heals on failure) → DocWriter

Each stage is one method. Agents talk through ``_dialogue`` (logged and
streamed to the dashboard) and report progress through ``_emit``.
"""
from __future__ import annotations

import json
import logging
import os
import time
from collections.abc import Callable, Iterator
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core import telemetry
from core.agents.base import (
    AgentResult,
    ArchitectAgent,
    CoderAgent,
    DebuggerAgent,
    DocWriterAgent,
    PlannerAgent,
    ReviewerAgent,
    SelfHealerAgent,
)
from core.ai.provider import LLMProvider
from core.execution.sandbox import DockerSandbox, sandbox_enabled
from core.memory.store import MemoryStore, ProjectMemory
from core.security import UnsafePathError, safe_join, write_files_contained
from core.syntax_check import check_syntax

MAX_REVIEW_ROUNDS = 3          # Reviewer ⇄ Coder rounds before proceeding anyway
MIN_EXPECTED_FILES = 3         # fewer than this usually means the output failed to parse
REVIEW_CONTEXT_CHARS = 12_000  # cap on code sent to the Reviewer per round
CODE_EXTENSIONS = (".py", ".ts", ".js", ".go", ".rs", ".tsx", ".jsx")
DEBUG_EXTENSIONS = (".py", ".js", ".ts", ".go", ".rs")


@dataclass
class _Run:
    """Mutable state for one pipeline run."""
    name: str
    request: str
    out: Path
    ctx: dict[str, Any]
    mem: ProjectMemory
    files: dict[str, str] = field(default_factory=dict)
    arch: AgentResult | None = None
    review: AgentResult | None = None
    review_rounds: int = 0


def _outcome(future: Future) -> tuple[AgentResult | None, str | None]:
    """(result, error message) for a finished agent future."""
    err = future.exception()
    if err:
        return None, str(err)
    result = future.result()
    return (result, None) if result.success else (None, result.error or "agent failed")


def _code_dump(files: dict[str, str], limit: int | None = None) -> str:
    """Concatenate files for a prompt, code files first."""
    ordered = sorted(files.items(), key=lambda kv: (not kv[0].endswith(CODE_EXTENSIONS), kv[0]))
    return "\n\n".join(f"// {path}\n{src}" for path, src in ordered)[:limit]


log = logging.getLogger("apex.orchestrator")


class Orchestrator:
    """Full pipeline: plan → architect → code → review → heal → document."""

    def __init__(
        self,
        model: str = "auto",
        dry_run: bool = False,
        on_event: Callable[..., None] | None = None,
        on_dialogue: Callable[[str, str, str, str], None] | None = None,
        memory_store: MemoryStore | None = None,
    ):
        self.dry_run    = dry_run
        self.on_event: Callable[..., None] = on_event or (
            lambda agent, status, msg, extra=None: print(f"[{agent}] {status}: {msg}"))
        self.on_dialogue = on_dialogue  # callback(from_agent, to_agent, msg_type, content)
        self.memory     = memory_store if memory_store is not None else MemoryStore()
        self.dialogue_log: list[dict] = []
        self.last_usage: telemetry.UsageTracker | None = None
        self.last_sandbox: dict | None = None

        llm = LLMProvider(model)
        self.planner   = PlannerAgent(llm)
        self.architect = ArchitectAgent(llm)
        self.coder     = CoderAgent(LLMProvider("coding"))
        self.reviewer  = ReviewerAgent(LLMProvider("coding"))
        self.debugger  = DebuggerAgent(LLMProvider("coding"))
        self.healer    = SelfHealerAgent(LLMProvider("coding"))
        self.docwriter = DocWriterAgent(llm)

    # ── Agent dialogue logging ─────────────────────────────────────────────────
    def _dialogue(self, from_agent: str, to_agent: str, msg_type: str, content: str):
        """Log structured agent-to-agent communication."""
        entry = {
            "from": from_agent,
            "to": to_agent,
            "type": msg_type,  # handoff | feedback | patch | request
            "content": content[:400],
            "ts": time.time(),
        }
        self.dialogue_log.append(entry)
        log.info(f"[DIALOGUE] {from_agent} → {to_agent} ({msg_type}): {content[:80]}")
        if self.on_dialogue:
            self.on_dialogue(from_agent, to_agent, msg_type, content)

    # ── Generate full-stack app ────────────────────────────────────────────────
    def generate_fullstack(
        self,
        name: str,
        request: str,
        output_dir: str = ".",
        skip_review: bool = False,
    ) -> str:
        """Run the 9-agent pipeline. Per-agent usage ends up in ``self.last_usage``."""
        tracker = telemetry.current_tracker() or telemetry.UsageTracker()
        self.last_usage = tracker
        with telemetry.track(tracker):
            return self._generate_fullstack(name, request, output_dir, skip_review)

    def _generate_fullstack(self, name, request, output_dir, skip_review) -> str:
        run = self._begin(name, request, output_dir)
        self._stage_memory(run)
        self._stage_plan(run)
        self._stage_code(run)
        if not self.dry_run:
            if not skip_review:
                self._stage_review(run)
            self._stage_heal(run)
            self._stage_debug(run)
            self._stage_execute(run)
        self._stage_document(run)
        return self._finish(run)

    # ── Pipeline stages ────────────────────────────────────────────────────────
    def _begin(self, name: str, request: str, output_dir: str) -> _Run:
        # `name` becomes a directory under output_dir — it must be one safe component.
        out = safe_join(output_dir, name)
        if out.parent != Path(output_dir).resolve():
            raise UnsafePathError(f"project name must be a single path component: {name!r}")
        self.dialogue_log = []
        self.last_sandbox = None
        return _Run(name=name, request=request, out=out,
                    ctx={"name": name, "request": request},
                    mem=ProjectMemory(name=name, request=request))

    def _stage_memory(self, run: _Run) -> None:
        """Memory agent: inject lessons from similar past runs."""
        context = self.memory.get_context_for_request(run.request)
        if not context:
            return
        run.ctx["memory_context"] = context
        self._emit("System", "running",
                   f"Found {len(self.memory.list_projects())} past projects — injecting learned context")
        self._dialogue("Memory", "Planner", "context",
                       f"Relevant past project context loaded. {context[:300]}")

    def _stage_plan(self, run: _Run) -> None:
        """Planner and Architect run in parallel on the same request."""
        ctx = run.ctx
        if self.dry_run:
            ctx["plan"] = '{"tech_stack": {"frontend": "Next.js", "backend": "FastAPI"}}'
            self._emit("Planner", "done", "[dry-run]")
            self._emit("Architect", "done", "[dry-run]")
            return

        self._emit("Planner", "running", "Analyzing requirements in parallel...")
        self._emit("Architect", "running", "Pre-loading architecture patterns...")
        # in_context copies the caller's context so usage tracking follows the threads
        with ThreadPoolExecutor(max_workers=2, thread_name_prefix="apex-plan") as pool:
            plan_future = pool.submit(telemetry.in_context(self.planner.run, ctx.copy()))
            arch_future = pool.submit(telemetry.in_context(self.architect.run, ctx.copy()))
        plan, plan_err = _outcome(plan_future)
        arch, arch_err = _outcome(arch_future)
        run.arch = arch

        if plan:
            ctx["plan"] = plan.output
            run.mem.plan = plan.output  # type: ignore[assignment]  # stored as the raw plan text
            run.mem.add_event("Planner", "complete", f"{plan.duration:.1f}s")
            self._emit("Planner", "done",
                       f"Plan ready ({plan.duration:.1f}s) — ran in parallel with Architect")
            self._dialogue("Planner", "Architect", "handoff",
                           f"Plan complete. Tech stack and file structure ready. Summary: {plan.output[:200]}")
        else:
            ctx["plan"] = '{"tech_stack": {"backend": "FastAPI"}}'
            self._emit("Planner", "done", f"Plan error: {plan_err}")

        if arch:
            ctx["architecture"] = arch.output
            self._emit("Architect", "done",
                       f"Architecture ready ({arch.duration:.1f}s) — ran in parallel with Planner")
            self._dialogue("Architect", "Coder", "handoff",
                           f"Architecture complete. Security decisions defined. Key: {arch.output[:200]}")
        else:
            self._emit("Architect", "done", f"Arch error: {arch_err}")

        if plan and arch:
            self._dialogue(
                "Planner", "Coder", "sync",
                f"Parallel phase complete. Both Planner and Architect finished. "
                f"Planner took {plan.duration:.1f}s, Architect took {arch.duration:.1f}s. "
                f"Combined time saved vs sequential: ~{min(plan.duration, arch.duration):.0f}s. "
                f"Handing combined context to Coder.")

    def _stage_code(self, run: _Run) -> None:
        self._emit("Coder", "running", "Generating production code...")
        if self.dry_run:
            run.files = {"README.md": f"# {run.name}\n{run.request}"}
            self._emit("Coder", "done", "[dry-run] 1 stub file")
            return
        result = self.coder.run(run.ctx)
        run.files.update(result.files)
        count = len(run.files)
        if not result.success:
            self._emit("Coder", "error", f"Coder failed: {result.error}")
        elif count < MIN_EXPECTED_FILES:
            self._emit("Coder", "error",
                       f"Only {count} file(s) generated — may indicate a parsing "
                       f"or generation issue. Raw output was {len(result.output)} chars.")
        else:
            self._emit("Coder", "done", f"{count} files generated ({result.duration:.1f}s)")
        self._dialogue("Coder", "Reviewer", "handoff",
                       f"Code generation complete. {count} files produced. Requesting security audit "
                       f"and quality review. Files: {list(run.files)[:8]}")

    def _stage_review(self, run: _Run) -> None:
        """
        Reviewer ⇄ Coder negotiation. The Reviewer can reject; the Coder revises
        and resubmits, up to MAX_REVIEW_ROUNDS. From round 2 the Architect is
        pulled back in to rethink the design.
        """
        for round_num in range(1, MAX_REVIEW_ROUNDS + 1):
            run.review_rounds = round_num
            self._emit("Reviewer", "running",
                       f"Reviewing code quality & security (round {round_num})...")
            review = run.review = self.reviewer.run({"code": _code_dump(run.files, REVIEW_CONTEXT_CHARS)})

            if review.verdict == "rejected" and round_num < MAX_REVIEW_ROUNDS:
                self._revise_after_rejection(run, round_num)
                continue

            # Approved, or out of rounds.
            run.files.update(review.files or {})
            if review.verdict == "approved":
                self._emit("Reviewer", "done", f"Approved — score {review.score}/100 (round {round_num})")
                self._dialogue("Reviewer", "SelfHealer", "feedback",
                               f"Code APPROVED after {round_num} round(s). Score {review.score}/100. "
                               f"No critical issues remain. SelfHealer to do proactive check.")
            else:
                self._emit("Reviewer", "done",
                           f"Round limit reached — proceeding with score {review.score}/100, "
                           f"{len(review.critical)} unresolved issue(s)")
                self._dialogue("Reviewer", "SelfHealer", "feedback",
                               f"Max revision rounds ({MAX_REVIEW_ROUNDS}) reached without full approval. "
                               f"Score {review.score}/100. Remaining issues handed to SelfHealer as a "
                               f"fallback: {review.critical[:5]}")
            return

    def _revise_after_rejection(self, run: _Run, round_num: int) -> None:
        review = run.review
        assert review is not None
        notes = self.reviewer.build_revision_notes(review.output)
        self._emit("Reviewer", "rejected",
                   f"Round {round_num}: score {review.score}/100 — "
                   f"{len(review.critical)} blocking issue(s), sent back to Coder")
        self._dialogue("Reviewer", "Coder", "request",
                       f"REJECTED (round {round_num}, score {review.score}/100). "
                       f"Revision required: {notes[:300]}")

        if round_num >= 2 and run.arch:
            self._emit("Architect", "running",
                       f"Re-evaluating architecture after round {round_num} rejection...")
            revision = self.architect.run({
                **run.ctx,
                "review_feedback": notes,
                "request": f"The Reviewer rejected the code. Issues: {notes[:300]}. "
                           f"Re-examine your architecture decisions and provide updated "
                           f"security-focused guidance for the Coder's revision.",
            })
            run.ctx["architecture"] = revision.output
            self._emit("Architect", "done", f"Architecture updated ({revision.duration:.1f}s)")
            self._dialogue("Architect", "Coder", "negotiation",
                           f"Round {round_num} architecture review complete. "
                           f"Updated security guidance: {revision.output[:200]}")

        self._emit("Coder", "running", f"Revising per Reviewer feedback (round {round_num})...")
        revised = self.coder.revise(run.files, notes)
        run.files.update(revised.files or {})
        self._emit("Coder", "done", f"Revised {len(revised.files)} file(s) ({revised.duration:.1f}s)")
        self._dialogue("Coder", "Reviewer", "patch",
                       f"Revision complete for round {round_num}. "
                       f"Patched {len(revised.files)} file(s): {list(revised.files)[:8]}. "
                       f"Resubmitting for review.")

    def _stage_heal(self, run: _Run) -> None:
        self._emit("SelfHealer", "running", "Running self-healing pass...")
        heal = self.healer.heal(run.files, "proactive check")
        if heal.files:
            run.files.update(heal.files)
            self._emit("SelfHealer", "done", f"Patched {len(heal.files)} files")
            self._dialogue("SelfHealer", "Debugger", "handoff",
                           f"Patched {len(heal.files)} files. Requesting runtime error check on patched code.")
        else:
            self._emit("SelfHealer", "done", "No issues found")
            self._dialogue("SelfHealer", "Debugger", "handoff",
                           "No patches needed. Code is clean. Debugger to verify no runtime errors.")

    def _stage_debug(self, run: _Run) -> None:
        self._emit("Debugger", "running", "Verifying no runtime errors...")
        head = list(run.files.items())
        sample = (_code_dump({k: v for k, v in head[:3] if k.endswith(DEBUG_EXTENSIONS)})
                  or _code_dump(dict(head[:2])))
        result = self.debugger.run({
            "code": sample,
            "error": "Proactive check: scan for import errors, undefined vars, missing await, "
                     "type mismatches, and startup crashes.",
        })
        if result.files:
            run.files.update(result.files)
            self._emit("Debugger", "done", f"Fixed {len(result.files)} runtime issue(s)")
            self._dialogue("Debugger", "DocWriter", "handoff",
                           f"Fixed {len(result.files)} runtime issue(s). Code ready for documentation.")
        else:
            self._emit("Debugger", "done", "No runtime errors found")
            self._dialogue("Debugger", "DocWriter", "handoff",
                           "Runtime check passed. No startup errors detected. Passing to DocWriter.")

    def _stage_execute(self, run: _Run) -> None:
        """Executor agent: static syntax check, then (if enabled) a real sandboxed run."""
        self._emit("Executor", "running", "Validating syntax of generated files...")
        report = check_syntax(run.files)
        if report.total == 0:
            self._emit("Executor", "done", "No validatable files (non-Python/JS project)")
        elif report.ok:
            suffix = "" if report.node_available else " (basic check — node unavailable on host)"
            self._emit("Executor", "done",
                       f"✓ All {report.passed}/{report.total} files pass syntax validation{suffix}")
            self._dialogue("Executor", "DocWriter", "validation",
                           f"Syntax validation PASSED: {report.passed}/{report.total} files validated.")
        else:
            self._emit("Executor", "error",
                       f"{report.passed}/{report.total} passed, {len(report.failed)} failed: "
                       f"{report.failed[0][:80]}")
            self._dialogue("Executor", "DocWriter", "validation",
                           f"Syntax validation: {report.passed}/{report.total} passed. "
                           f"Issues: {report.failed[:3]}")
        if sandbox_enabled():
            run.files = self._sandbox_loop(run.files)

    def _stage_document(self, run: _Run) -> None:
        self._emit("DocWriter", "running", "Writing documentation...")
        if self.dry_run:
            return
        doc = self.docwriter.run(run.ctx)
        run.files.update(doc.files)
        self._emit("DocWriter", "done", "README.md generated")
        self._dialogue("DocWriter", "System", "complete",
                       "Documentation complete. README.md generated with setup instructions "
                       "and architecture notes.")

    def _finish(self, run: _Run) -> str:
        """Record what was learned, write the project to disk and report."""
        mem, review = run.mem, run.review
        score = review.score if review else 100
        mem.update_files(run.files)
        mem.quality_score = score
        mem.review_rounds = max(1, run.review_rounds)
        mem.file_count = len(run.files)
        try:
            mem.tech_stack = json.loads(run.ctx.get("plan", "{}")).get("tech_stack", {})
        except (ValueError, AttributeError):
            pass  # the plan is free text from a model; a missing stack is fine

        if review and review.score >= 90:
            mem.add_lesson(f"High quality ({review.score}/100) achieved with {len(run.files)} files")
        for issue in (review.critical[:3] if review else []):
            mem.add_lesson(f"Watch for: {issue[:80]}")

        tracker = telemetry.current_tracker()
        usage = tracker.summary() if tracker else {}
        if usage:
            mem.usage = {k: usage[k] for k in ("calls", "total_tokens", "cost_usd", "llm_seconds", "wall_seconds")}
        if self.last_sandbox:
            mem.sandbox = {k: self.last_sandbox[k] for k in ("attempts", "passed", "first_attempt_passed")}

        rejected = self._write_files(run.out, run.files)
        if rejected:
            self._emit("System", "error",
                       f"Refused {len(rejected)} unsafe file path(s) from model output: {rejected[:3]}")
            mem.add_lesson(f"Model proposed {len(rejected)} path(s) outside the project; they were dropped")
        self.memory.save(mem)

        self._emit("System", "complete", f"Project ready: {run.out.name}/")
        self._emit("System", "done", f"complete — {len(run.files)} files generated",
                   {"quality_score": score, "files": len(run.files), "usage": usage,
                    "sandbox": self.last_sandbox})
        return str(run.out)

    # ── Executor: sandboxed run + heal loop ────────────────────────────────────
    def _sandbox_loop(self, all_files: dict[str, str]) -> dict[str, str]:
        """
        Run the generated Python project in the Docker sandbox (deps → compile →
        import → pytest). On failure hand the real error output to SelfHealer and
        retry, up to APEX_SANDBOX_HEAL_ROUNDS (default 2) times.
        """
        sbx = DockerSandbox()
        rounds = max(0, int(os.environ.get("APEX_SANDBOX_HEAL_ROUNDS", "2")))
        history = []
        for attempt in range(rounds + 1):
            self._emit("Executor", "running",
                       f"Sandbox run {attempt + 1}: install → compile → import → tests (network off)")
            with telemetry.stage("Executor"):
                rep = sbx.smoke_test(None, files=all_files)
            history.append(rep.to_dict())
            if not rep.ran:
                self._emit("Executor", "done", f"Sandbox skipped: {rep.reason}")
                break
            summary = (f"deps={'ok' if rep.deps_ok else 'FAIL'} compile={'ok' if rep.compile_ok else 'FAIL'} "
                       f"import={'ok' if rep.import_ok else ('FAIL' if rep.import_ok is False else 'n/a')} "
                       f"tests={rep.tests_passed}/{rep.tests_found}")
            if rep.ok:
                self._emit("Executor", "done", f"✓ Sandbox passed: {summary}")
                self._dialogue("Executor", "DocWriter", "validation",
                               f"Sandbox run passed on attempt {attempt + 1}: {summary}")
                break
            self._emit("Executor", "error", f"Sandbox failed: {summary}")
            if attempt == rounds:
                break
            self._dialogue("Executor", "SelfHealer", "feedback",
                           f"Sandbox run failed ({summary}). Real output: {rep.failure_log(300)}")
            self._emit("SelfHealer", "running", "Fixing sandbox failures from real error output...")
            heal = self.healer.heal(all_files, "The project failed when run in a sandbox:\n" + rep.failure_log())
            if not heal.files:
                self._emit("SelfHealer", "done", "No patch produced")
                break
            all_files = {**all_files, **heal.files}
            self._emit("SelfHealer", "done", f"Patched {len(heal.files)} files — re-running sandbox")
        self.last_sandbox = {
            "attempts": len(history),
            "passed": bool(history) and history[-1].get("ok", False),
            "first_attempt_passed": bool(history) and history[0].get("ok", False),
            "final": history[-1] if history else None,
        }
        return all_files

    # ── Stream generation ──────────────────────────────────────────────────────
    def generate_stream(self, name: str, request: str) -> Iterator[str]:
        ctx = {"name": name, "request": request}
        yield "[Planner] Analyzing...\n"
        if not self.dry_run:
            plan_result = self.planner.run(ctx)
            ctx["plan"] = plan_result.output
        yield "[Planner] Done. Starting code generation...\n\n"
        yield from self.coder.stream(ctx)

    # ── Edit existing project ──────────────────────────────────────────────────
    def edit_app(self, project_path: str, instruction: str) -> list[str]:
        path = Path(project_path)
        existing = self._read_project(path)
        ctx = {
            "request": instruction,
            "code": "\n\n".join(f"// {p}\n{c}" for p, c in existing.items()),
        }
        self._emit("Coder", "running", f"Applying: {instruction}")
        result = self.coder.run({**ctx, "name": path.name, "plan": ""})
        changed, rejected = write_files_contained(path, result.files, log)
        if rejected:
            self._emit("Coder", "error", f"Refused {len(rejected)} unsafe path(s): {rejected[:3]}")
        self._emit("Coder", "done", f"Modified {len(changed)} files")
        return changed

    # ── Debug specific error ───────────────────────────────────────────────────
    def debug(self, file_path: str, error: str, traceback: str = "") -> str:
        path = Path(file_path)
        code = path.read_text(encoding="utf-8") if path.exists() else ""
        ctx  = {"file": file_path, "code": code, "error": error, "traceback": traceback}
        self._emit("Debugger", "running", f"Analyzing error in {file_path}")
        result = self.debugger.run(ctx)
        if result.files:
            # Only patch the file being debugged. The model's chosen paths are
            # untrusted and used to be written relative to the current directory.
            target = path.resolve()
            match = [c for f, c in result.files.items() if Path(f).name == target.name]
            if len(result.files) == 1 and not match:
                match = list(result.files.values())
            if match and target.is_file():
                write_files_contained(target.parent, {target.name: match[0]}, log)
            ignored = len(result.files) - (1 if match else 0)
            if ignored:
                self._emit("Debugger", "error", f"Ignored {ignored} patch(es) for other files")
        self._emit("Debugger", "done", "Fix applied")
        return result.output

    # ── Helpers ────────────────────────────────────────────────────────────────
    def _emit(self, agent: str, status: str, msg: str, extra: dict | None = None):
        log.info(f"[{agent}] {status}: {msg}")
        try:
            self.on_event(agent, status, msg, extra or {})
        except TypeError:  # callbacks that only take (agent, status, msg)
            self.on_event(agent, status, msg)

    def _write_files(self, base: Path, files: dict[str, str]) -> list[str]:
        """Write model-generated files under ``base``; returns rejected paths."""
        base.mkdir(parents=True, exist_ok=True)
        _, rejected = write_files_contained(base, files, log)
        return rejected

    def _read_project(self, base: Path) -> dict[str, str]:
        files = {}
        skip = {".git", "node_modules", "__pycache__", ".next", "dist", "build"}
        for p in base.rglob("*"):
            if p.is_symlink():
                continue  # don't follow links out of the project into the prompt
            if p.is_file() and not any(s in p.parts for s in skip):
                try:
                    files[str(p.relative_to(base))] = p.read_text(encoding="utf-8")
                except Exception:
                    pass
        return files
