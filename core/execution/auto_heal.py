"""
APEX v3 — Auto-Heal Pipeline
Runs → detects errors → heals → retries automatically.
"""
from __future__ import annotations
import logging, time
from pathlib import Path
from core.execution.runner import Executor, ExecResult
from core.agents.base import SelfHealerAgent
from core.ai.provider import LLMProvider

log = logging.getLogger("apex.healer")

MAX_RETRIES = 3


class AutoHealPipeline:
    """
    Full cycle:
    1. Install deps
    2. Type-check
    3. Lint
    4. Test
    If any step fails → send to SelfHealer → patch files → retry.
    """

    def __init__(self, project_dir: str, on_event=None):
        self.project_dir = Path(project_dir)
        self.executor    = Executor(project_dir)
        self.healer      = SelfHealerAgent(LLMProvider("coding"))
        self.on_event    = on_event or (lambda stage, status, msg: print(f"[{stage}] {status}: {msg}"))

    def run(self) -> dict:
        results = {}

        # 1. Install
        self._emit("Install", "running", "Installing dependencies...")
        r = self.executor.install_deps()
        results["install"] = r.ok
        if not r.ok:
            self._emit("Install", "error", r.error_summary[:200])
            self._heal_and_retry("install", r.error_summary, "install dependencies")
        else:
            self._emit("Install", "done", f"Done ({r.duration:.1f}s)")

        # 2. Type check
        self._emit("TypeCheck", "running", "Running TypeScript type check...")
        r = self.executor.type_check()
        results["typecheck"] = r.ok
        if not r.ok and r.stdout.strip():
            self._emit("TypeCheck", "error", r.stdout[:300])
            fixed = self._heal_ts_errors(r.stdout)
            results["typecheck_fixed"] = fixed
        else:
            self._emit("TypeCheck", "done", "No type errors")

        # 3. Lint
        self._emit("Lint", "running", "Running linter...")
        r = self.executor.lint()
        results["lint"] = r.ok
        if r.ok:
            self._emit("Lint", "done", "Clean")
        else:
            self._emit("Lint", "error", r.stdout[:200])

        # 4. Tests
        self._emit("Test", "running", "Running test suite...")
        r = self.executor.test()
        results["test"] = r.ok
        if r.ok:
            self._emit("Test", "done", f"All tests passed ({r.duration:.1f}s)")
        else:
            self._emit("Test", "error", r.error_summary[:200])

        # Summary
        passed = sum(1 for v in results.values() if v is True)
        total  = len([k for k in results if not k.endswith("_fixed")])
        self._emit("Pipeline", "complete", f"{passed}/{total} checks passed")
        return results

    def _heal_ts_errors(self, ts_output: str) -> bool:
        """Extract files with TS errors and patch them."""
        import re
        # parse: src/app/page.tsx(12,5): error TS2345: ...
        file_errors: dict[str, list[str]] = {}
        for m in re.finditer(r"([\w./\-]+\.tsx?)\((\d+),(\d+)\):\s+error\s+(TS\d+:[^\n]+)", ts_output):
            fpath = m.group(1)
            err   = m.group(4)
            file_errors.setdefault(fpath, []).append(err)

        if not file_errors:
            return False

        files = {}
        for fpath in file_errors:
            full = self.project_dir / fpath
            if full.exists():
                files[fpath] = full.read_text(encoding="utf-8")

        error_msg = "\n".join(
            f"{f}: {', '.join(errs)}" for f, errs in file_errors.items()
        )
        self._emit("SelfHealer", "running", f"Fixing {len(files)} files with TS errors...")
        result = self.healer.heal(files, f"TypeScript errors:\n{error_msg}")

        patched = 0
        for fpath, content in result.files.items():
            full = self.project_dir / fpath
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_text(content, encoding="utf-8")
            patched += 1

        self._emit("SelfHealer", "done", f"Patched {patched} files")
        return patched > 0

    def _heal_and_retry(self, stage: str, error: str, action: str) -> bool:
        for attempt in range(1, MAX_RETRIES + 1):
            self._emit("SelfHealer", "running", f"Attempt {attempt}/{MAX_RETRIES}: {action}")
            files = self._read_relevant_files(error)
            result = self.healer.heal(files, error)
            if result.files:
                for fpath, content in result.files.items():
                    full = self.project_dir / fpath
                    full.parent.mkdir(parents=True, exist_ok=True)
                    full.write_text(content, encoding="utf-8")
                # retry
                r = getattr(self.executor, stage, self.executor.install_deps)()
                if r.ok:
                    self._emit("SelfHealer", "done", f"Fixed on attempt {attempt}")
                    return True
        self._emit("SelfHealer", "error", "Could not auto-fix")
        return False

    def _read_relevant_files(self, error: str) -> dict[str, str]:
        """Read files mentioned in the error message."""
        import re
        files = {}
        for m in re.finditer(r"([\w./\-]+\.\w+)", error):
            fpath = self.project_dir / m.group(1)
            if fpath.exists() and fpath.is_file():
                try:
                    files[m.group(1)] = fpath.read_text(encoding="utf-8")
                except Exception:
                    pass
        return files

    def _emit(self, stage: str, status: str, msg: str):
        log.info(f"[{stage}] {status}: {msg}")
        self.on_event(stage, status, msg)
