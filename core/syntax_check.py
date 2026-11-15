"""Static syntax validation for generated files (no code is executed)."""
from __future__ import annotations

import ast
import logging
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger("apex.syntax")

JS_EXTENSIONS = (".js", ".ts", ".tsx", ".jsx")


@dataclass
class SyntaxReport:
    total: int = 0
    passed: int = 0
    failed: list[str] = field(default_factory=list)
    node_available: bool = True

    @property
    def ok(self) -> bool:
        return not self.failed


def _brackets_balanced(src: str) -> bool:
    return src.count("{") == src.count("}") and src.count("(") == src.count(")")


def _check_js(name: str, src: str, tmpdir: str, report: SyntaxReport) -> str | None:
    """Return an error string, or None when the file passes."""
    if report.node_available:
        path = Path(tmpdir) / name.replace("/", "_").replace("\\", "_")
        path.write_text(src, encoding="utf-8")
        try:
            result = subprocess.run(["node", "--check", str(path)], capture_output=True, timeout=10)
        except FileNotFoundError:
            report.node_available = False
            log.warning("node not found — falling back to a bracket-balance check for JS/TS files")
        except subprocess.TimeoutExpired:
            return f"{name}: syntax check timed out"
        else:
            return None if result.returncode == 0 else f"{name}: {result.stderr.decode(errors='replace')[:100]}"
    return None if _brackets_balanced(src) else f"{name}: unbalanced brackets (basic check)"


def check_syntax(files: dict[str, str]) -> SyntaxReport:
    """Parse every .py file with ``ast`` and every JS/TS file with ``node --check``."""
    report = SyntaxReport()
    with tempfile.TemporaryDirectory() as tmpdir:
        for name, src in files.items():
            if name.endswith(".py"):
                error = None
                try:
                    ast.parse(src)
                except SyntaxError as e:
                    error = f"{name}: {e}"
            elif name.endswith(JS_EXTENSIONS):
                error = _check_js(name, src, tmpdir, report)
            else:
                continue
            report.total += 1
            if error:
                report.failed.append(error)
            else:
                report.passed += 1
    return report
