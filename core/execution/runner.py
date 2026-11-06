"""
APEX v3 — Code Executor

Runs install / type-check / lint / test / build steps for a generated project
and returns captured output for the SelfHealer.

Safety model (see core/security.py):
  * Disabled unless explicitly approved: ``Executor(..., allow_execution=True)``
    or ``APEX_ALLOW_EXECUTION=1``. Generated code is untrusted.
  * No shell. Commands are argv lists; strings are split with shlex, so
    ``; rm -rf ~`` is passed as literal arguments, not interpreted.
  * Minimal environment: provider API keys and other secrets in the parent
    process are not inherited by children.
  * Timeouts kill the whole process group, not just the direct child.
  * npm lifecycle scripts are skipped by default (``--ignore-scripts``);
    set ``APEX_ALLOW_INSTALL_SCRIPTS=1`` to allow them.

This is NOT an OS sandbox. Run untrusted projects inside a container/VM.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from core.security import (
    ExecutionDisabledError, env_flag, execution_allowed, minimal_env, run_argv, safe_join,
)


@dataclass
class ExecResult:
    stdout: str
    stderr: str
    returncode: int
    duration: float
    timed_out: bool = False

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.timed_out

    @property
    def error_summary(self) -> str:
        if self.timed_out:
            return "Process timed out"
        text = self.stderr or self.stdout or ""
        lines = text.strip().splitlines()
        return "\n".join(lines[-20:]) if lines else ""


def _npm() -> str:
    return "npm.cmd" if sys.platform == "win32" else "npm"


def _npx() -> str:
    return "npx.cmd" if sys.platform == "win32" else "npx"


class Executor:
    """Run install / check / test commands for a generated project."""

    def __init__(self, project_dir: str, timeout: int = 120, allow_execution: bool | None = None):
        self.project_dir = Path(project_dir).resolve()
        self.timeout = timeout
        self.allow_execution = execution_allowed() if allow_execution is None else allow_execution

    # ── helpers ────────────────────────────────────────────────────────────────
    def _scripts(self) -> dict:
        pkg = self.project_dir / "package.json"
        if not pkg.is_file():
            return {}
        try:
            data = json.loads(pkg.read_text(encoding="utf-8"))
            scripts = data.get("scripts", {})
            return scripts if isinstance(scripts, dict) else {}
        except (ValueError, OSError):
            return {}

    # ── Install dependencies ───────────────────────────────────────────────────
    def install_deps(self) -> ExecResult:
        """Auto-detect and install deps (npm / pip / both)."""
        results = []
        if (self.project_dir / "package.json").exists():
            argv = [_npm(), "install", "--prefer-offline", "--no-audit", "--no-fund"]
            if not env_flag("APEX_ALLOW_INSTALL_SCRIPTS"):
                argv.append("--ignore-scripts")
            results.append(self.run(argv))
        if (self.project_dir / "requirements.txt").exists():
            results.append(self.run(
                [sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "-q",
                 "--disable-pip-version-check"]
            ))
        if not results:
            return ExecResult("No deps file found", "", 0, 0)
        for r in results:
            if not r.ok:
                return r
        return results[-1]

    # ── TypeScript check ───────────────────────────────────────────────────────
    def type_check(self) -> ExecResult:
        if not (self.project_dir / "tsconfig.json").exists():
            return ExecResult("No tsconfig.json", "", 0, 0)
        # --no-install: never fetch an arbitrary package just to type-check.
        return self.run([_npx(), "--no-install", "tsc", "--noEmit"])

    # ── Lint ───────────────────────────────────────────────────────────────────
    def lint(self) -> ExecResult:
        if "lint" in self._scripts():
            return self.run([_npm(), "run", "lint"])
        return ExecResult("No lint script", "", 0, 0)

    # ── Run tests ──────────────────────────────────────────────────────────────
    def test(self) -> ExecResult:
        if (self.project_dir / "pytest.ini").exists() or (self.project_dir / "tests").exists():
            return self.run([sys.executable, "-m", "pytest", "-x", "-q"])
        if "test" in self._scripts():
            return self.run([_npm(), "test", "--", "--watchAll=false"])
        return ExecResult("No test runner found", "", 0, 0)

    # ── Build ──────────────────────────────────────────────────────────────────
    def build(self) -> ExecResult:
        if "build" in self._scripts():
            return self.run([_npm(), "run", "build"])
        return ExecResult("No build script", "", 0, 0)

    # ── Generic run ────────────────────────────────────────────────────────────
    def run(self, cmd: str | Sequence[str], env_extra: dict | None = None) -> ExecResult:
        """
        Run ``cmd`` in the project directory. ``cmd`` is an argv list (preferred)
        or a string that is split with shlex — it is never passed to a shell.
        """
        if not self.allow_execution:
            return ExecResult(
                "", str(ExecutionDisabledError(
                    "Executor is disabled. Pass allow_execution=True or set APEX_ALLOW_EXECUTION=1.")),
                -1, 0.0,
            )
        try:
            r = run_argv(cmd, self.project_dir, timeout=self.timeout, env=minimal_env(env_extra))
        except ValueError as e:
            return ExecResult("", str(e), -1, 0.0)
        return ExecResult(
            stdout=r.stdout, stderr=r.error, returncode=r.returncode,
            duration=r.duration, timed_out=r.timed_out,
        )

    # ── Run file directly ──────────────────────────────────────────────────────
    def run_file(self, filename: str) -> ExecResult:
        try:
            fpath = safe_join(self.project_dir, filename)
        except ValueError as e:
            return ExecResult("", str(e), 1, 0)
        if not fpath.is_file():
            return ExecResult("", f"File not found: {filename}", 1, 0)
        if fpath.suffix == ".py":
            return self.run([sys.executable, str(fpath)])
        if fpath.suffix in (".js", ".mjs", ".cjs"):
            return self.run(["node", str(fpath)])
        return ExecResult("", f"Unknown file type: {filename}", 1, 0)
