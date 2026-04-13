import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List


def _cmd_ok(command: List[str], cwd: Path | None = None) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            command,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
        )
        out = (result.stdout or "").strip() or (result.stderr or "").strip()
        return result.returncode == 0, out
    except Exception as exc:
        return False, str(exc)


def run_doctor(project_path: Path, openrouter_key: str, groq_key: str) -> Dict[str, object]:
    checks: List[Dict[str, str]] = []

    checks.append(
        {
            "name": "python",
            "ok": "yes" if shutil.which("py") or shutil.which("python") else "no",
            "detail": sys.version.split()[0],
        }
    )
    checks.append(
        {
            "name": "git",
            "ok": "yes" if shutil.which("git") else "no",
            "detail": "available" if shutil.which("git") else "missing",
        }
    )

    writable = "yes"
    try:
        test = project_path / ".doctor-write.tmp"
        test.write_text("ok", encoding="utf-8")
        test.unlink(missing_ok=True)
    except Exception as exc:
        writable = f"no ({exc})"
    checks.append({"name": "workspace_write", "ok": "yes" if writable == "yes" else "no", "detail": writable})

    checks.append(
        {
            "name": "openrouter_key",
            "ok": "yes" if openrouter_key.strip() else "no",
            "detail": "configured" if openrouter_key.strip() else "missing",
        }
    )
    checks.append(
        {
            "name": "groq_key",
            "ok": "yes" if groq_key.strip() else "no",
            "detail": "configured" if groq_key.strip() else "missing",
        }
    )

    py_ok, py_out = _cmd_ok(["py", "--version"])
    checks.append({"name": "py_command", "ok": "yes" if py_ok else "no", "detail": py_out[:120]})

    git_ok, git_out = _cmd_ok(["git", "rev-parse", "--is-inside-work-tree"], cwd=project_path)
    checks.append({"name": "git_repo", "ok": "yes" if git_ok else "no", "detail": git_out[:120]})

    compile_ok = True
    compile_note = "no python files found"
    py_files = list(project_path.rglob("*.py"))
    if py_files:
        cmd = ["py", "-m", "py_compile"] + [str(p) for p in py_files[:80]]
        c_ok, c_out = _cmd_ok(cmd, cwd=project_path)
        compile_ok = c_ok
        compile_note = "py_compile ok" if c_ok else c_out[:220]
    checks.append({"name": "syntax_compile", "ok": "yes" if compile_ok else "no", "detail": compile_note})

    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "platform": f"{platform.system()} {platform.release()}",
        "project_path": str(project_path),
        "checks": checks,
    }
    summary["score"] = round(100 * sum(1 for c in checks if c["ok"] == "yes") / len(checks), 1)
    return summary


def doctor_markdown(report: Dict[str, object]) -> str:
    lines = [
        "# Elite Doctor Report",
        "",
        f"- Generated: {report.get('generated_at')}",
        f"- Platform: {report.get('platform')}",
        f"- Project: {report.get('project_path')}",
        f"- Health Score: {report.get('score')}/100",
        "",
        "## Checks",
    ]
    for check in report.get("checks", []):
        status = "PASS" if check.get("ok") == "yes" else "FAIL"
        lines.append(f"- `{check.get('name')}`: {status} - {check.get('detail')}")
    lines.append("")
    lines.append("## Raw JSON")
    lines.append("```json")
    lines.append(json.dumps(report, indent=2))
    lines.append("```")
    lines.append("")
    return "\n".join(lines)
