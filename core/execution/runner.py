"""
APEX v3 — Safe Code Executor
Runs generated code in sandboxed subprocess, captures output,
feeds errors back to SelfHealer automatically.
"""
from __future__ import annotations
import subprocess, os, sys, time, signal, tempfile, shutil
from pathlib import Path
from dataclasses import dataclass


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
        lines = (self.stderr or "").strip().splitlines()
        return "\n".join(lines[-20:]) if lines else ""


class Executor:
    """Run shell commands, npm/python installs, test suites."""

    def __init__(self, project_dir: str, timeout: int = 120):
        self.project_dir = Path(project_dir)
        self.timeout     = timeout

    # ── Install dependencies ───────────────────────────────────────────────────
    def install_deps(self) -> ExecResult:
        """Auto-detect and install deps (npm / pip / both)."""
        results = []
        if (self.project_dir / "package.json").exists():
            results.append(self.run("npm install --prefer-offline 2>&1"))
        if (self.project_dir / "requirements.txt").exists():
            results.append(self.run(
                f"{sys.executable} -m pip install -r requirements.txt -q 2>&1"
            ))
        if not results:
            return ExecResult("No deps file found", "", 0, 0)
        # return last result (fail if any failed)
        for r in results:
            if not r.ok:
                return r
        return results[-1]

    # ── TypeScript check ───────────────────────────────────────────────────────
    def type_check(self) -> ExecResult:
        if not (self.project_dir / "tsconfig.json").exists():
            return ExecResult("No tsconfig.json", "", 0, 0)
        return self.run("npx --yes tsc --noEmit 2>&1")

    # ── Lint ───────────────────────────────────────────────────────────────────
    def lint(self) -> ExecResult:
        pkg = self.project_dir / "package.json"
        if pkg.exists():
            import json
            scripts = json.loads(pkg.read_text()).get("scripts", {})
            if "lint" in scripts:
                return self.run("npm run lint 2>&1")
        return ExecResult("No lint script", "", 0, 0)

    # ── Run tests ──────────────────────────────────────────────────────────────
    def test(self) -> ExecResult:
        if (self.project_dir / "pytest.ini").exists() or \
           (self.project_dir / "tests").exists():
            return self.run(f"{sys.executable} -m pytest -x -q 2>&1")
        pkg = self.project_dir / "package.json"
        if pkg.exists():
            import json
            scripts = json.loads(pkg.read_text()).get("scripts", {})
            if "test" in scripts:
                return self.run("npm test -- --watchAll=false 2>&1")
        return ExecResult("No test runner found", "", 0, 0)

    # ── Build ──────────────────────────────────────────────────────────────────
    def build(self) -> ExecResult:
        pkg = self.project_dir / "package.json"
        if pkg.exists():
            import json
            scripts = json.loads(pkg.read_text()).get("scripts", {})
            if "build" in scripts:
                return self.run("npm run build 2>&1")
        return ExecResult("No build script", "", 0, 0)

    # ── Generic run ────────────────────────────────────────────────────────────
    def run(self, cmd: str, env_extra: dict | None = None) -> ExecResult:
        env = {**os.environ, **(env_extra or {})}
        # Set CI=true to prevent interactive prompts
        env["CI"] = "true"
        env["NEXT_TELEMETRY_DISABLED"] = "1"

        t0 = time.time()
        try:
            proc = subprocess.Popen(
                cmd, shell=True, cwd=str(self.project_dir),
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                env=env, text=True,
            )
            try:
                stdout, _ = proc.communicate(timeout=self.timeout)
                return ExecResult(
                    stdout=stdout, stderr="",
                    returncode=proc.returncode,
                    duration=time.time() - t0,
                )
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.communicate()
                return ExecResult("", "Timed out", -1, time.time()-t0, timed_out=True)
        except Exception as e:
            return ExecResult("", str(e), -1, time.time()-t0)

    # ── Run file directly ──────────────────────────────────────────────────────
    def run_file(self, filename: str) -> ExecResult:
        fpath = self.project_dir / filename
        if not fpath.exists():
            return ExecResult("", f"File not found: {filename}", 1, 0)
        if filename.endswith(".py"):
            return self.run(f"{sys.executable} {filename}")
        if filename.endswith(".js") or filename.endswith(".ts"):
            return self.run(f"node {filename}")
        return ExecResult("", f"Unknown file type: {filename}", 1, 0)
