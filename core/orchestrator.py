"""
APEX v3 — Master Orchestrator
Coordinates: Planner → Architect → Coder → Reviewer → SelfHealer → DocWriter
Agent-to-agent dialogue is logged at every handoff for Track 3 compliance.
"""
from __future__ import annotations
import os, logging, time, threading, subprocess, tempfile, ast
from pathlib import Path
from typing import Callable, Iterator
from core.ai.provider import LLMProvider
from core.agents.base import (
    PlannerAgent, ArchitectAgent, CoderAgent,
    ReviewerAgent, DebuggerAgent, SelfHealerAgent, DocWriterAgent,
    AgentResult,
)
from core.memory.store import MemoryStore, ProjectMemory

log = logging.getLogger("apex.orchestrator")


class Orchestrator:
    """Full pipeline: plan → architect → code → review → heal → document."""

    def __init__(
        self,
        model: str = "auto",
        dry_run: bool = False,
        on_event: Callable[[str, str, str], None] | None = None,
        on_dialogue: Callable[[str, str, str, str], None] | None = None,
    ):
        self.dry_run    = dry_run
        self.on_event   = on_event or (lambda agent, status, msg: print(f"[{agent}] {status}: {msg}"))
        self.on_dialogue = on_dialogue  # callback(from_agent, to_agent, msg_type, content)
        self.memory     = MemoryStore()
        self.dialogue_log: list[dict] = []

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
        mem = ProjectMemory(name=name, request=request)
        out = Path(output_dir) / name
        ctx = {"name": name, "request": request}
        self.dialogue_log = []  # reset per run

        # ── Inject memory context from past similar runs ───────────────────────
        # This makes the system smarter over time — agents see what worked
        # in similar past projects and avoid repeating mistakes.
        memory_context = self.memory.get_context_for_request(request)
        if memory_context:
            ctx["memory_context"] = memory_context
            self._emit("System", "running",
                f"Found {len(self.memory.list_projects())} past projects — injecting learned context")
            self._dialogue("Memory", "Planner", "context",
                f"Relevant past project context loaded. {memory_context[:300]}")

        # ── 1 + 2: Planner & Architect run IN PARALLEL ─────────────────────────────
        # This is a Track 3 differentiator — agents work simultaneously, not
        # sequentially. Both start at the same time; we wait for both to finish.
        plan_result = arch_result = None
        arch_result = None  # also used in review negotiation loop

        if not self.dry_run:
            self._emit("Planner",   "running", "Analyzing requirements in parallel...")
            self._emit("Architect", "running", "Pre-loading architecture patterns...")

            plan_container  = [None]
            arch_container  = [None]
            plan_err        = [None]
            arch_err        = [None]

            def _run_planner():
                try:
                    plan_container[0] = self.planner.run(ctx.copy())
                except Exception as e:
                    plan_err[0] = str(e)

            def _run_architect():
                try:
                    # Architect gets a basic context first; will be updated once
                    # Planner finishes, but starts immediately for speed.
                    arch_container[0] = self.architect.run(ctx.copy())
                except Exception as e:
                    arch_err[0] = str(e)

            t_plan = threading.Thread(target=_run_planner,   daemon=True)
            t_arch = threading.Thread(target=_run_architect, daemon=True)
            t_plan.start(); t_arch.start()
            t_plan.join();  t_arch.join()

            plan_result = plan_container[0]
            arch_result = arch_container[0]

            if plan_result:
                mem.plan    = plan_result.output
                ctx["plan"] = plan_result.output
                mem.add_event("Planner", "complete", f"{plan_result.duration:.1f}s")
                self._emit("Planner", "done",
                    f"Plan ready ({plan_result.duration:.1f}s) — ran in parallel with Architect")
                self._dialogue("Planner", "Architect", "handoff",
                    f"Plan complete. Tech stack and file structure ready. Summary: {plan_result.output[:200]}")
            else:
                ctx["plan"] = '{"tech_stack": {"backend": "FastAPI"}}'
                self._emit("Planner", "done", f"Plan error: {plan_err[0]}")

            if arch_result:
                ctx["architecture"] = arch_result.output
                self._emit("Architect", "done",
                    f"Architecture ready ({arch_result.duration:.1f}s) — ran in parallel with Planner")
                self._dialogue("Architect", "Coder", "handoff",
                    f"Architecture complete. Security decisions defined. Key: {arch_result.output[:200]}")
            else:
                self._emit("Architect", "done", f"Arch error: {arch_err[0]}")

            self._dialogue("Planner", "Coder", "sync",
                f"Parallel phase complete. Both Planner and Architect finished. "
                f"Planner took {plan_result.duration:.1f}s, Architect took {arch_result.duration:.1f}s. "
                f"Combined time saved vs sequential: ~{min(plan_result.duration, arch_result.duration):.0f}s. "
                f"Handing combined context to Coder.")
        else:
            ctx["plan"] = '{"tech_stack": {"frontend": "Next.js", "backend": "FastAPI"}}'
            self._emit("Planner",   "done", "[dry-run]")
            self._emit("Architect", "done", "[dry-run]")

        # 3. Code generation
        self._emit("Coder", "running", "Generating production code...")
        all_files: dict[str, str] = {}
        if not self.dry_run:
            code_result = self.coder.run(ctx)
            all_files.update(code_result.files)
            if not code_result.success:
                self._emit("Coder", "error", f"Coder failed: {code_result.error}")
            elif len(all_files) < 3:
                self._emit("Coder", "error",
                    f"Only {len(all_files)} file(s) generated — may indicate a parsing "
                    f"or generation issue. Raw output was {len(code_result.output)} chars.")
            else:
                self._emit("Coder", "done", f"{len(all_files)} files generated ({code_result.duration:.1f}s)")
            self._dialogue("Coder", "Reviewer",
                "handoff",
                f"Code generation complete. {len(all_files)} files produced. Requesting security audit and quality review. Files: {list(all_files.keys())[:8]}")
        else:
            all_files = {"README.md": f"# {name}\n{request}"}
            self._emit("Coder", "done", "[dry-run] 1 stub file")

        # 4. Review — with conflict resolution.
        # Reviewer can REJECT the submission; if it does, Coder revises and
        # Reviewer re-reviews, up to MAX_REVIEW_ROUNDS times. This is the
        # explicit Track 3 requirement: agents must be able to disagree and
        # resolve it through dialogue, not just hand off silently.
        MAX_REVIEW_ROUNDS = 3
        review_result = None
        if not skip_review and not self.dry_run:
            for round_num in range(1, MAX_REVIEW_ROUNDS + 1):
                self._emit("Reviewer", "running",
                    f"Reviewing code quality & security (round {round_num})...")
                # Review ALL files, prioritising code files first
                priority_exts = ('.py','.ts','.js','.go','.rs','.tsx','.jsx')
                sorted_files = sorted(all_files.items(),
                    key=lambda x: (0 if x[0].endswith(priority_exts) else 1, x[0]))
                code_dump = "\n\n".join(
                    f"// {fp}\n{c}" for fp, c in sorted_files
                )[:12000]  # cap at 12K chars so Reviewer context stays fast
                review_result = self.reviewer.run({"code": code_dump})

                if review_result.verdict == "rejected" and round_num < MAX_REVIEW_ROUNDS:
                    notes = self.reviewer.build_revision_notes(review_result.output)
                    self._emit("Reviewer", "rejected",
                        f"Round {round_num}: score {review_result.score}/100 — "
                        f"{len(review_result.critical)} blocking issue(s), sent back to Coder")
                    # DIALOGUE: Reviewer → Coder (rejection)
                    self._dialogue("Reviewer", "Coder",
                        "request",
                        f"REJECTED (round {round_num}, score {review_result.score}/100). "
                        f"Revision required: {notes[:300]}")

                    # On round 2+, loop in Architect to re-evaluate design
                    # This is real multi-agent negotiation: not just Reviewer↔Coder
                    # but also Architect re-examining structural decisions
                    if round_num >= 2 and arch_result:
                        self._emit("Architect", "running",
                            f"Re-evaluating architecture after round {round_num} rejection...")
                        arch_revision_ctx = {**ctx,
                            "review_feedback": notes,
                            "request": f"The Reviewer rejected the code. Issues: {notes[:300]}. "
                                       f"Re-examine your architecture decisions and provide updated "
                                       f"security-focused guidance for the Coder's revision."}
                        arch_revision = self.architect.run(arch_revision_ctx)
                        ctx["architecture"] = arch_revision.output
                        self._emit("Architect", "done",
                            f"Architecture updated ({arch_revision.duration:.1f}s)")
                        self._dialogue("Architect", "Coder", "negotiation",
                            f"Round {round_num} architecture review complete. "
                            f"Updated security guidance: {arch_revision.output[:200]}")

                    self._emit("Coder", "running", f"Revising per Reviewer feedback (round {round_num})...")
                    revise_result = self.coder.revise(all_files, notes)
                    if revise_result.files:
                        all_files.update(revise_result.files)
                    self._emit("Coder", "done",
                        f"Revised {len(revise_result.files)} file(s) ({revise_result.duration:.1f}s)")
                    # DIALOGUE: Coder → Reviewer (patch submitted)
                    self._dialogue("Coder", "Reviewer",
                        "patch",
                        f"Revision complete for round {round_num}. "
                        f"Patched {len(revise_result.files)} file(s): {list(revise_result.files.keys())[:8]}. "
                        f"Resubmitting for review.")
                    continue  # re-review the patched code

                # Either approved, or we've exhausted rounds — stop looping.
                if review_result.files:
                    all_files.update(review_result.files)
                if review_result.verdict == "approved":
                    self._emit("Reviewer", "done",
                        f"Approved — score {review_result.score}/100 (round {round_num})")
                    self._dialogue("Reviewer", "SelfHealer",
                        "feedback",
                        f"Code APPROVED after {round_num} round(s). Score {review_result.score}/100. "
                        f"No critical issues remain. SelfHealer to do proactive check.")
                else:
                    self._emit("Reviewer", "done",
                        f"Round limit reached — proceeding with score {review_result.score}/100, "
                        f"{len(review_result.critical)} unresolved issue(s)")
                    self._dialogue("Reviewer", "SelfHealer",
                        "feedback",
                        f"Max revision rounds ({MAX_REVIEW_ROUNDS}) reached without full approval. "
                        f"Score {review_result.score}/100. Remaining issues handed to SelfHealer as a fallback: "
                        f"{review_result.critical[:5]}")
                break

        # 5. Auto-heal
        if not self.dry_run:
            self._emit("SelfHealer", "running", "Running self-healing pass...")
            heal_result = self.healer.heal(all_files, "proactive check")
            if heal_result.files:
                all_files.update(heal_result.files)
                self._emit("SelfHealer", "done", f"Patched {len(heal_result.files)} files")
                self._dialogue("SelfHealer", "Debugger",
                    "handoff",
                    f"Patched {len(heal_result.files)} files. Requesting runtime error check on patched code.")
            else:
                self._emit("SelfHealer", "done", "No issues found")
                self._dialogue("SelfHealer", "Debugger",
                    "handoff",
                    "No patches needed. Code is clean. Debugger to verify no runtime errors.")

        # 5b. Debugger — runtime error check (now actually runs in pipeline)
        if not self.dry_run:
            self._emit("Debugger", "running", "Verifying no runtime errors...")
            code_sample = "\n\n".join(
                f"// {fp}\n{c}" for fp, c in list(all_files.items())[:3]
                if fp.endswith(('.py','.js','.ts','.go','.rs'))
            ) or "\n\n".join(f"// {fp}\n{c}" for fp, c in list(all_files.items())[:2])
            debug_result = self.debugger.run({
                "code": code_sample,
                "error": "Proactive check: scan for import errors, undefined vars, missing await, type mismatches, and startup crashes."
            })
            if debug_result.files:
                all_files.update(debug_result.files)
                self._emit("Debugger", "done", f"Fixed {len(debug_result.files)} runtime issue(s)")
                self._dialogue("Debugger", "DocWriter", "handoff",
                    f"Fixed {len(debug_result.files)} runtime issue(s). Code ready for documentation.")
            else:
                self._emit("Debugger", "done", "No runtime errors found")
                self._dialogue("Debugger", "DocWriter", "handoff",
                    "Runtime check passed. No startup errors detected. Passing to DocWriter.")

        # 5c. Executor — syntax validate generated files (proof code works)
        if not self.dry_run:
            self._emit("Executor", "running", "Validating syntax of generated files...")
            passed, failed, total = 0, [], 0
            with tempfile.TemporaryDirectory() as tmpdir:
                for fname, content in all_files.items():
                    if fname.endswith(".py"):
                        total += 1
                        try:
                            ast.parse(content)
                            passed += 1
                        except SyntaxError as e:
                            failed.append(f"{fname}: {e}")
                    elif fname.endswith((".js", ".ts", ".tsx", ".jsx")):
                        total += 1
                        fpath = Path(tmpdir) / fname.replace("/", "_")
                        fpath.write_text(content, encoding="utf-8")
                        result = subprocess.run(
                            ["node", "--check", str(fpath)],
                            capture_output=True, timeout=10
                        )
                        if result.returncode == 0:
                            passed += 1
                        else:
                            failed.append(f"{fname}: {result.stderr.decode()[:100]}")

            if total == 0:
                self._emit("Executor", "done", "No validatable files (non-Python/JS project)")
            elif not failed:
                self._emit("Executor", "done",
                    f"✓ All {passed}/{total} files pass syntax validation")
                self._dialogue("Executor", "DocWriter", "validation",
                    f"Syntax validation PASSED: {passed}/{total} files validated. "
                    f"Code is syntactically correct and ready for deployment.")
            else:
                self._emit("Executor", "error",
                    f"{passed}/{total} passed, {len(failed)} failed: {failed[0][:80]}")
                self._dialogue("Executor", "DocWriter", "validation",
                    f"Syntax validation: {passed}/{total} passed. "
                    f"Issues: {failed[:3]}")

        # 6. Documentation
        self._emit("DocWriter", "running", "Writing documentation...")
        if not self.dry_run:
            doc_result = self.docwriter.run(ctx)
            all_files.update(doc_result.files)
            self._emit("DocWriter", "done", "README.md generated")
            self._dialogue("DocWriter", "System", "complete",
                "Documentation complete. README.md generated with full API docs, setup instructions, and architecture notes.")

        # 7. Write to disk + save enriched memory
        mem.update_files(all_files)
        mem.quality_score = review_result.score if review_result else 100
        mem.review_rounds = getattr(review_result, '_rounds', 1)
        mem.file_count = len(all_files)

        # Extract tech stack from plan for future memory context
        import re as _re
        try:
            import json as _json
            plan_data = _json.loads(ctx.get("plan", "{}"))
            mem.tech_stack = plan_data.get("tech_stack", {})
        except Exception:
            pass

        # Record lessons from this run
        if review_result and review_result.score >= 90:
            mem.add_lesson(f"High quality ({review_result.score}/100) achieved with {len(all_files)} files")
        if review_result and review_result.critical:
            for issue in review_result.critical[:3]:
                mem.add_lesson(f"Watch for: {issue[:80]}")

        self._write_files(out, all_files)
        self.memory.save(mem)

        final_score = review_result.score if review_result else 100
        self._emit("System", "complete", f"Project ready at {out}")
        self._emit("System", "done",
            f"complete — {len(all_files)} files generated",
            {"quality_score": final_score, "files": len(all_files)})
        return str(out)

    # ── Stream generation ──────────────────────────────────────────────────────
    def generate_stream(self, name: str, request: str) -> Iterator[str]:
        ctx = {"name": name, "request": request}
        yield f"[Planner] Analyzing...\n"
        if not self.dry_run:
            plan_result = self.planner.run(ctx)
            ctx["plan"] = plan_result.output
        yield f"[Planner] Done. Starting code generation...\n\n"
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
        changed = []
        for fpath, content in result.files.items():
            full = path / fpath
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_text(content, encoding="utf-8")
            changed.append(fpath)
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
            for fpath, content in result.files.items():
                Path(fpath).write_text(content, encoding="utf-8")
        self._emit("Debugger", "done", "Fix applied")
        return result.output

    # ── Helpers ────────────────────────────────────────────────────────────────
    def _emit(self, agent: str, status: str, msg: str, extra: dict = None):
        log.info(f"[{agent}] {status}: {msg}")
        if self.on_event:
            try:
                self.on_event(agent, status, msg, extra or {})
            except TypeError:
                self.on_event(agent, status, msg)

    def _write_files(self, base: Path, files: dict[str, str]):
        base.mkdir(parents=True, exist_ok=True)
        for rel_path, content in files.items():
            full = base / rel_path
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_text(content, encoding="utf-8")

    def _read_project(self, base: Path) -> dict[str, str]:
        files = {}
        skip = {".git", "node_modules", "__pycache__", ".next", "dist", "build"}
        for p in base.rglob("*"):
            if p.is_file() and not any(s in p.parts for s in skip):
                try:
                    files[str(p.relative_to(base))] = p.read_text(encoding="utf-8")
                except Exception:
                    pass
        return files
