"""
APEX v3 — Master Orchestrator
Coordinates: Planner → Architect → Coder → Reviewer → SelfHealer → DocWriter
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
    ):
        self.dry_run  = dry_run
        self.on_event = on_event or (lambda agent, status, msg: print(f"[{agent}] {status}: {msg}"))
        self.memory   = MemoryStore()

        llm = LLMProvider(model)
        self.planner   = PlannerAgent(llm)
        self.architect = ArchitectAgent(llm)
        self.coder     = CoderAgent(LLMProvider("coding"))
        self.reviewer  = ReviewerAgent(LLMProvider("coding"))
        self.debugger  = DebuggerAgent(LLMProvider("coding"))
        self.healer    = SelfHealerAgent(LLMProvider("coding"))
        self.docwriter = DocWriterAgent(llm)

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

        # 1. Plan
        self._emit("Planner", "running", "Analyzing project requirements...")
        if not self.dry_run:
            plan_result = self.planner.run(ctx)
            mem.plan = plan_result.output
            ctx["plan"] = plan_result.output
            mem.add_event("Planner", "complete", f"{plan_result.duration:.1f}s")
            self._emit("Planner", "done", f"Plan ready ({plan_result.duration:.1f}s)")
        else:
            ctx["plan"] = '{"tech_stack": {"frontend": "Next.js", "backend": "FastAPI"}}'
            self._emit("Planner", "done", "[dry-run]")

        # 2. Architect
        self._emit("Architect", "running", "Designing system architecture...")
        if not self.dry_run:
            arch_result = self.architect.run(ctx)
            ctx["architecture"] = arch_result.output
            self._emit("Architect", "done", f"Architecture ready ({arch_result.duration:.1f}s)")

        # 3. Code generation
        self._emit("Coder", "running", "Generating production code...")
        all_files: dict[str, str] = {}
        if not self.dry_run:
            code_result = self.coder.run(ctx)
            all_files.update(code_result.files)
            self._emit("Coder", "done", f"{len(all_files)} files generated ({code_result.duration:.1f}s)")
        else:
            all_files = {"README.md": f"# {name}\n{request}"}
            self._emit("Coder", "done", "[dry-run] 1 stub file")

        # 4. Review
        if not skip_review and not self.dry_run:
            self._emit("Reviewer", "running", "Reviewing code quality & security...")
            code_dump = "\n\n".join(f"// {p}\n{c}" for p, c in list(all_files.items())[:5])
            review_result = self.reviewer.run({"code": code_dump})
            if review_result.files:
                all_files.update(review_result.files)
                self._emit("Reviewer", "done", f"Fixed issues, score updated")
            else:
                self._emit("Reviewer", "done", f"Review passed ({review_result.duration:.1f}s)")

        # 5. Auto-heal if any issues detected
        if not self.dry_run:
            self._emit("SelfHealer", "running", "Running self-healing pass...")
            heal_result = self.healer.heal(all_files, "proactive check")
            if heal_result.files:
                all_files.update(heal_result.files)
                self._emit("SelfHealer", "done", f"Patched {len(heal_result.files)} files")
            else:
                self._emit("SelfHealer", "done", "No issues found")

        # 6. Documentation
        self._emit("DocWriter", "running", "Writing documentation...")
        if not self.dry_run:
            doc_result = self.docwriter.run(ctx)
            all_files.update(doc_result.files)
            self._emit("DocWriter", "done", "README.md generated")

        # 7. Write to disk
        mem.update_files(all_files)
        self._write_files(out, all_files)
        self.memory.save(mem)

        self._emit("System", "complete", f"Project ready at {out}")
        return str(out)

    # ── Stream generation ──────────────────────────────────────────────────────
    def generate_stream(self, name: str, request: str) -> Iterator[str]:
        """Yields streaming tokens from the coder agent."""
        ctx = {"name": name, "request": request}

        # Quick plan first
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
