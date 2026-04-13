# core/ai/tool_registry.py
# 19 permission-gated tools for the APEX agent
# Pattern from claw-code: independently sandboxed tools with configurable access controls

import os
import subprocess
import json
import re
from pathlib import Path
from typing import Optional


class PermissionError(Exception):
    pass


class ToolRegistry:
    """
    19 permission-gated tools. Each tool declares required permissions.
    Tools are sandboxed - file I/O restricted to project path.
    """

    TOOLS = {
        # File I/O (read-only by default)
        "read_file":     {"permission": "file.read",  "desc": "Read a file"},
        "write_file":    {"permission": "file.write", "desc": "Write/create a file"},
        "list_dir":      {"permission": "file.read",  "desc": "List directory contents"},
        "search_files":  {"permission": "file.read",  "desc": "Search files by pattern"},
        "delete_file":   {"permission": "file.write", "desc": "Delete a file"},

        # Shell (requires explicit permission)
        "bash":          {"permission": "shell",      "desc": "Run a shell command"},
        "python_eval":   {"permission": "shell",      "desc": "Evaluate Python code"},

        # Git operations
        "git_status":    {"permission": "git",        "desc": "Git status"},
        "git_diff":      {"permission": "git",        "desc": "Git diff"},
        "git_commit":    {"permission": "git.write",  "desc": "Git commit"},
        "git_push":      {"permission": "git.write",  "desc": "Git push"},

        # Web
        "web_search":    {"permission": "web",        "desc": "Search the web"},
        "web_fetch":     {"permission": "web",        "desc": "Fetch a URL"},

        # Code analysis
        "find_imports":  {"permission": "file.read",  "desc": "Find all imports in file"},
        "count_lines":   {"permission": "file.read",  "desc": "Count lines in file"},
        "find_todos":    {"permission": "file.read",  "desc": "Find TODO comments"},
        "syntax_check":  {"permission": "file.read",  "desc": "Check Python/JSX syntax"},

        # Project
        "run_tests":     {"permission": "shell",      "desc": "Run project tests"},
        "install_deps":  {"permission": "shell",      "desc": "Install dependencies"},
    }

    def __init__(self, project_path: str, granted_permissions: Optional[set] = None):
        self.project_path = Path(project_path)
        self.permissions = granted_permissions or {"file.read", "git", "web"}
        self._call_log = []

    def grant(self, permission: str):
        self.permissions.add(permission)

    def revoke(self, permission: str):
        self.permissions.discard(permission)

    def _check_permission(self, tool_name: str):
        tool = self.TOOLS.get(tool_name, {})
        required = tool.get("permission", "")
        if required and required not in self.permissions:
            raise PermissionError(
                f"Tool '{tool_name}' requires permission '{required}'. "
                f"Granted: {self.permissions}"
            )

    def _safe_path(self, path: str) -> Path:
        """Ensure path is within project directory."""
        p = (self.project_path / path).resolve()
        if not str(p).startswith(str(self.project_path.resolve())):
            raise PermissionError(f"Path '{path}' is outside project directory")
        return p

    def call(self, tool_name: str, **kwargs) -> str:
        """Execute a tool and return result as string."""
        self._check_permission(tool_name)
        self._call_log.append({"tool": tool_name, "kwargs": kwargs})

        fn = getattr(self, f"_tool_{tool_name}", None)
        if not fn:
            return f"Error: Tool '{tool_name}' not implemented"

        try:
            return fn(**kwargs)
        except PermissionError:
            raise
        except Exception as e:
            return f"Error: {e}"

    # ── TOOL IMPLEMENTATIONS ─────────────────────────────────────────────────

    def _tool_read_file(self, path: str, max_lines: int = 200) -> str:
        p = self._safe_path(path)
        if not p.exists():
            return f"Error: File not found: {path}"
        lines = p.read_text(encoding="utf-8", errors="ignore").split("\n")
        if len(lines) > max_lines:
            return "\n".join(lines[:max_lines]) + f"\n... ({len(lines)-max_lines} more lines)"
        return "\n".join(lines)

    def _tool_write_file(self, path: str, content: str) -> str:
        p = self._safe_path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"Written: {path} ({len(content)} chars)"

    def _tool_list_dir(self, path: str = ".") -> str:
        p = self._safe_path(path)
        if not p.exists():
            return f"Error: Directory not found: {path}"
        items = []
        for item in sorted(p.iterdir()):
            if item.name.startswith("."):
                continue
            kind = "d" if item.is_dir() else "f"
            size = f" ({item.stat().st_size:,}b)" if item.is_file() else ""
            items.append(f"  [{kind}] {item.name}{size}")
        return "\n".join(items) or "(empty)"

    def _tool_search_files(self, pattern: str, path: str = ".") -> str:
        p = self._safe_path(path)
        results = []
        for f in p.rglob("*"):
            if any(skip in str(f) for skip in ["node_modules", "__pycache__", ".git"]):
                continue
            if re.search(pattern, f.name, re.IGNORECASE):
                results.append(str(f.relative_to(self.project_path)))
        return "\n".join(results[:50]) or "No files found"

    def _tool_delete_file(self, path: str) -> str:
        p = self._safe_path(path)
        if p.exists():
            p.unlink()
            return f"Deleted: {path}"
        return f"File not found: {path}"

    def _tool_bash(self, command: str, cwd: str = ".") -> str:
        work_dir = self._safe_path(cwd)
        result = subprocess.run(
            command, shell=True, cwd=str(work_dir),
            capture_output=True, text=True, timeout=60,
            encoding="utf-8", errors="replace"
        )
        output = result.stdout + result.stderr
        return output[:2000] if output else "(no output)"

    def _tool_python_eval(self, code: str) -> str:
        # Restricted eval - only safe operations
        restricted = ["import os", "import sys", "subprocess", "open(", "__import__"]
        if any(r in code for r in restricted):
            return "Error: Restricted operation"
        try:
            result = eval(code)
            return str(result)
        except Exception as e:
            return f"Error: {e}"

    def _tool_git_status(self) -> str:
        return self._tool_bash("git status --short")

    def _tool_git_diff(self, file: str = "") -> str:
        return self._tool_bash(f"git diff {file}")

    def _tool_git_commit(self, message: str) -> str:
        self._tool_bash("git add -A")
        return self._tool_bash(f'git commit -m "{message}"')

    def _tool_git_push(self) -> str:
        return self._tool_bash("git push")

    def _tool_web_search(self, query: str) -> str:
        # Simple DuckDuckGo instant answer
        import urllib.request, urllib.parse
        url = f"https://api.duckduckgo.com/?q={urllib.parse.quote(query)}&format=json&no_html=1"
        try:
            with urllib.request.urlopen(url, timeout=10) as r:
                data = json.loads(r.read())
                abstract = data.get("AbstractText", "")
                return abstract[:500] or "No results"
        except Exception as e:
            return f"Search error: {e}"

    def _tool_web_fetch(self, url: str) -> str:
        import urllib.request
        try:
            with urllib.request.urlopen(url, timeout=10) as r:
                content = r.read().decode("utf-8", errors="ignore")
                # Strip HTML tags
                content = re.sub(r"<[^>]+>", "", content)
                return content[:2000]
        except Exception as e:
            return f"Fetch error: {e}"

    def _tool_find_imports(self, path: str) -> str:
        content = self._tool_read_file(path)
        imports = re.findall(r"^(?:import|from)\s+\S+", content, re.MULTILINE)
        return "\n".join(imports) or "No imports found"

    def _tool_count_lines(self, path: str) -> str:
        content = self._tool_read_file(path, max_lines=99999)
        return f"{len(content.splitlines())} lines in {path}"

    def _tool_find_todos(self, path: str = ".") -> str:
        p = self._safe_path(path)
        todos = []
        for f in p.rglob("*.py"):
            if "__pycache__" in str(f): continue
            for i, line in enumerate(f.read_text(errors="ignore").splitlines(), 1):
                if "TODO" in line or "FIXME" in line or "HACK" in line:
                    todos.append(f"{f.name}:{i}: {line.strip()}")
        return "\n".join(todos[:20]) or "No TODOs found"

    def _tool_syntax_check(self, path: str) -> str:
        import ast
        p = self._safe_path(path)
        content = p.read_text(encoding="utf-8", errors="ignore")
        if path.endswith(".py"):
            try:
                ast.parse(content)
                return f"OK: {path} - valid Python"
            except SyntaxError as e:
                return f"ERROR: {path} line {e.lineno}: {e.msg}"
        return f"OK: {path} - not a Python file"

    def _tool_run_tests(self, path: str = "backend") -> str:
        return self._tool_bash("python -m pytest tests/ -v --tb=short 2>&1 | head -50", cwd=path)

    def _tool_install_deps(self, path: str = "backend") -> str:
        return self._tool_bash("pip install -r requirements.txt -q", cwd=path)

    def available_tools(self) -> list:
        """Return tools the current permissions allow."""
        return [
            name for name, info in self.TOOLS.items()
            if info["permission"] in self.permissions
        ]

    def call_log(self) -> list:
        return self._call_log
