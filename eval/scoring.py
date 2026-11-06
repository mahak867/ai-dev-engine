"""
Independent scoring for generated projects.

Nothing here asks an LLM. Every number comes from a standard tool or a
deterministic check, so single-agent and society output are judged the same way:

  * syntax       — ``ast.parse`` on every .py file
  * ruff         — ``ruff check --select E9,F,B,S`` (errors, bugbear, flake8-bandit)
  * bandit       — issue counts by severity (HIGH / MEDIUM / LOW)
  * secrets      — known token formats + ``getenv("X", "<literal>")`` fallbacks
  * structure    — has tests / requirements / README
  * sandbox      — (optional) deps install, compile, import, pytest pass rate,
                   run in the Docker sandbox with no network
"""
from __future__ import annotations

import ast
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

SKIP_DIRS = {"node_modules", ".git", "__pycache__", ".venv", "venv", ".apex-deps"}

SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"gsk_[A-Za-z0-9]{20,}"),
    re.compile(r"(?:ghp|gho|ghs|github_pat)_[A-Za-z0-9_]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    # os.getenv("SECRET_KEY", "literal") / os.environ.get(..., "literal") — the
    # "fallback default secret" bug the Reviewer is meant to catch.
    re.compile(r"""(?:getenv|environ\.get)\(\s*['"][A-Z0-9_]*(?:SECRET|KEY|TOKEN|PASSWORD)[A-Z0-9_]*['"]\s*,\s*['"][^'"]{6,}['"]"""),
    # SECRET_KEY = "literal"
    re.compile(r"""^\s*[A-Z0-9_]*(?:SECRET|PASSWORD|API_KEY|TOKEN)[A-Z0-9_]*\s*=\s*['"][^'"]{8,}['"]""", re.M),
]


def _py_files(root: Path) -> list[Path]:
    return [p for p in root.rglob("*.py")
            if not any(s in p.parts for s in SKIP_DIRS) and not p.is_symlink()]


def _is_test(p: Path) -> bool:
    return p.name.startswith("test_") or p.name.endswith("_test.py") or "tests" in p.parts


def _run_json(argv: list[str], cwd: Path) -> object | None:
    try:
        r = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=300)
    except (OSError, subprocess.TimeoutExpired):
        return None
    out = r.stdout.strip()
    if not out:
        return None
    try:
        return json.loads(out)
    except ValueError:
        return None


def tool_versions() -> dict:
    from importlib import metadata
    v = {}
    for name in ("ruff", "bandit"):
        try:
            v[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            v[name] = None
    return v


def ruff_counts(root: Path) -> dict:
    data = _run_json([sys.executable, "-m", "ruff", "check", "--isolated", "--no-cache",
                      "--select", "E9,F,B,S", "--output-format", "json",
                      "--exclude", ",".join(SKIP_DIRS), "."], root)
    if data is None:
        return {"ruff_ok": shutil.which("ruff") is not None or _has_module("ruff"), "ruff_errors": 0,
                "ruff_security": 0, "ruff_codes": {}}
    codes: dict[str, int] = {}
    sec = 0
    for item in data:
        path = Path(item.get("filename", ""))
        code = item.get("code") or "?"
        # S101 (assert) is expected in tests; don't penalise test files for it.
        if code == "S101" and _is_test(path):
            continue
        codes[code] = codes.get(code, 0) + 1
        if code.startswith("S"):
            sec += 1
    return {"ruff_ok": True, "ruff_errors": sum(codes.values()), "ruff_security": sec,
            "ruff_codes": dict(sorted(codes.items(), key=lambda kv: -kv[1])[:15])}


def bandit_counts(root: Path) -> dict:
    data = _run_json([sys.executable, "-m", "bandit", "-r", ".", "-f", "json", "-q",
                      "-x", ",".join(f"./{d}" for d in SKIP_DIRS) + ",./tests"], root)
    if not isinstance(data, dict):
        return {"bandit_ok": False, "bandit_high": 0, "bandit_medium": 0, "bandit_low": 0, "bandit_ids": {}}
    sev = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    ids: dict[str, int] = {}
    for r in data.get("results", []):
        if _is_test(Path(r.get("filename", ""))):
            continue
        sev[r.get("issue_severity", "LOW")] = sev.get(r.get("issue_severity", "LOW"), 0) + 1
        ids[r.get("test_id", "?")] = ids.get(r.get("test_id", "?"), 0) + 1
    return {"bandit_ok": True, "bandit_high": sev["HIGH"], "bandit_medium": sev["MEDIUM"],
            "bandit_low": sev["LOW"], "bandit_ids": ids}


def _has_module(name: str) -> bool:
    import importlib.util
    return importlib.util.find_spec(name) is not None


def secret_hits(root: Path) -> int:
    n = 0
    for p in root.rglob("*"):
        if not p.is_file() or p.is_symlink() or any(s in p.parts for s in SKIP_DIRS):
            continue
        if p.suffix not in {".py", ".js", ".ts", ".env", ".json", ".yml", ".yaml", ".toml", ".cfg", ".ini", ""}:
            continue
        if p.name in {".env.example", "env.example"}:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        n += sum(len(pat.findall(text)) for pat in SECRET_PATTERNS)
    return n


def score_project(root: str | Path, *, sandbox: bool = False) -> dict:
    root = Path(root)
    if not root.is_dir():
        return {"generated": False}
    files = [p for p in root.rglob("*") if p.is_file() and not any(s in p.parts for s in SKIP_DIRS)]
    py = _py_files(root)
    syntax_bad, loc = 0, 0
    for p in py:
        try:
            src = p.read_text(encoding="utf-8", errors="replace")
            loc += sum(1 for line in src.splitlines() if line.strip() and not line.strip().startswith("#"))
            ast.parse(src)
        except SyntaxError:
            syntax_bad += 1
    tests = [p for p in py if _is_test(p)]
    out = {
        "generated": len(files) > 0,
        "files": len(files),
        "py_files": len(py),
        "py_loc": loc,
        "syntax_error_files": syntax_bad,
        "has_tests": bool(tests),
        "test_files": len(tests),
        "has_requirements": any(p.name in ("requirements.txt", "pyproject.toml") for p in files),
        "has_readme": any(p.name.lower() == "readme.md" for p in files),
        "secrets": secret_hits(root),
    }
    out.update(ruff_counts(root))
    out.update(bandit_counts(root))
    if sandbox:
        from core.execution.sandbox import DockerSandbox
        rep = DockerSandbox().smoke_test(root)
        out["sandbox"] = {
            "ran": rep.ran, "ok": rep.ok, "reason": rep.reason,
            "deps_ok": rep.deps_ok, "compile_ok": rep.compile_ok, "import_ok": rep.import_ok,
            "tests_found": rep.tests_found, "tests_passed": rep.tests_passed,
            "tests_failed": rep.tests_failed, "seconds": rep.seconds,
        }
    return out
