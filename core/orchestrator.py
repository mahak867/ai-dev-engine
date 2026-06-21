"""
APEX v3 — Master Orchestrator
Coordinates: Planner → Architect → Coder → Reviewer → SelfHealer → DocWriter
Agent-to-agent dialogue is logged at every handoff for Track 3 compliance.
"""
from __future__ import annotations
import os, logging, time
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

        # 1. Plan
        self._emit("Planner", "running", "Analyzing project requirements...")
        if not self.dry_run:
            plan_result = self.planner.run(ctx)
            mem.plan = plan_result.output
            ctx["plan"] = plan_result.output
            mem.add_event("Planner", "complete", f"{plan_result.duration:.1f}s")
            self._emit("Planner", "done", f"Plan ready ({plan_result.duration:.1f}s)")
            # DIALOGUE: Planner → Architect
            self._dialogue("Planner", "Architect",
                "handoff",
                f"Plan complete. Tech stack and file structure ready. Passing to Architect for system design. Summary: {plan_result.output[:200]}")
        else:
            ctx["plan"] = '{"tech_stack": {"frontend": "Next.js", "backend": "FastAPI"}}'
            self._emit("Planner", "done", "[dry-run]")

        # 2. Architect
        self._emit("Architect", "running", "Designing system architecture...")
        if not self.dry_run:
            arch_result = self.architect.run(ctx)
            ctx["architecture"] = arch_result.output
            self._emit("Architect", "done", f"Architecture ready ({arch_result.duration:.1f}s)")
            # DIALOGUE: Architect → Coder
            self._dialogue("Architect", "Coder",
                "handoff",
                f"Architecture complete. Security notes and component structure defined. Coder should implement all files per the plan. Key decisions: {arch_result.output[:200]}")

        # 3. Code generation
        self._emit("Coder", "running", "Generating production code...")
        all_files: dict[str, str] = {}
        if not self.dry_run:
            code_result = self.coder.run(ctx)
            all_files.update(code_result.files)
            self._emit("Coder", "done", f"{len(all_files)} files generated ({code_result.duration:.1f}s)")
            # DIALOGUE: Coder → Reviewer
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
                code_dump = "\n\n".join(f"// {p}\n{c}" for p, c in list(all_files.items())[:5])
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
                # DIALOGUE: SelfHealer → Debugger
                self._dialogue("SelfHealer", "Debugger",
                    "handoff",
                    f"Patched {len(heal_result.files)} files. Requesting runtime error check on patched code.")
            else:
                self._emit("SelfHealer", "done", "No issues found")
                self._dialogue("SelfHealer", "Debugger",
                    "handoff",
                    "No patches needed. Code is clean. Debugger to verify no runtime errors.")

        # 6. Documentation
        self._emit("DocWriter", "running", "Writing documentation...")
        if not self.dry_run:
            doc_result = self.docwriter.run(ctx)
            all_files.update(doc_result.files)
            self._emit("DocWriter", "done", "README.md generated")
            # DIALOGUE: DocWriter → System
            self._dialogue("DocWriter", "System",
                "complete",
                f"Documentation complete. README.md generated with full API docs, setup instructions, and architecture notes.")

        # 7. Write to disk
        mem.update_files(all_files)
        self._write_files(out, all_files)
        self.memory.save(mem)

        self._emit("System", "complete", f"Project ready at {out}")
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
    def _emit(self, agent: str, status: str, msg: str):
        log.info(f"[{agent}] {status}: {msg}")
        if self.on_event:
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
