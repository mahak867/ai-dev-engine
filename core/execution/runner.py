# core/execution/runner.py
# Smart execution engine — detects app type and picks the right run command.
# Handles Python (Flask/FastAPI/script), Node.js (React/Vue), static HTML.

import subprocess
import sys
import os
import json
from pathlib import Path

# Use the same Python that's running this script — avoids python vs python3 issues
PYTHON = sys.executable


class CodeRunner:

    def __init__(self, project_path: str, app_type: str = "auto"):
        self.project_path = Path(project_path)
        self.app_type = app_type

    # ── App type detection ────────────────────────────────────────
    def detect_app_type(self) -> str:
        has_backend = (
            any(self.project_path.glob("backend/**/*.py")) or
            any(self.project_path.glob("*.py"))
        )
        has_node = (
            (self.project_path / "frontend" / "package.json").exists() or
            (self.project_path / "package.json").exists()
        )
        has_html = (
            (self.project_path / "frontend" / "index.html").exists() or
            (self.project_path / "index.html").exists()
        )

        if has_backend and has_node:
            return "fullstack_node"
        if has_backend and has_html:
            return "fullstack_static"
        if has_backend:
            return self._detect_python_type()
        if has_node:
            return "node"
        if has_html:
            return "static"
        return "unknown"

    def _detect_python_type(self) -> str:
        server_keywords = ["Flask", "FastAPI", "uvicorn", "app.run", "create_app"]
        for f in list(self.project_path.rglob("*.py"))[:15]:
            try:
                content = f.read_text(encoding="utf-8", errors="ignore")
                if any(kw in content for kw in server_keywords):
                    return "python_server"
            except Exception:
                pass
        return "python_script"

    # ── Entry point finders ───────────────────────────────────────
    def _find_python_entry(self) -> str | None:
        candidates = ["run.py", "app.py", "main.py", "server.py", "cli.py"]
        # Check backend/ first
        for name in candidates:
            p = self.project_path / "backend" / name
            if p.exists():
                return str(p.relative_to(self.project_path))
        # Then root
        for name in candidates:
            p = self.project_path / name
            if p.exists():
                return name
        # Fallback: any .py
        for f in self.project_path.rglob("*.py"):
            if "__pycache__" not in str(f):
                return str(f.relative_to(self.project_path))
        return None

    def _find_package_json_dir(self) -> Path | None:
        for p in [
            self.project_path / "frontend",
            self.project_path,
        ]:
            if (p / "package.json").exists():
                return p
        return None

    # ── Runners ───────────────────────────────────────────────────
    def _run_python(self, entry: str) -> dict:
        # If entry is inside backend/, run from backend/ dir with just the filename
        # This fixes "from backend.xxx import" errors caused by wrong cwd
        if entry.startswith("backend" + os.sep) or entry.startswith("backend/"):
            run_cwd = self.project_path / "backend"
            run_entry = os.path.basename(entry)
        else:
            run_cwd = self.project_path
            run_entry = entry
        print(f"  ▶  {PYTHON} {run_entry}  (cwd: {run_cwd.name}/)")
        try:
            result = subprocess.run(
                [PYTHON, run_entry],
                cwd=run_cwd,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                return {"success": True, "output": result.stdout, "type": "python"}
            return {"success": False, "error": result.stderr or result.stdout, "type": "python"}

        except subprocess.TimeoutExpired:
            # A server running past timeout means it started successfully
            return {"success": True, "output": "Server started (still running).", "type": "python_server"}
        except FileNotFoundError:
            return {"success": False, "error": f"Python not found at: {PYTHON}", "type": "python"}
        except Exception as e:
            return {"success": False, "error": str(e), "type": "python"}

    def _run_node(self, pkg_dir: Path) -> dict:
        print(f"  ▶  npm install && npm run dev  (in {pkg_dir.name}/)")
        try:
            # npm install
            inst = subprocess.run(
                ["npm", "install"],
                cwd=pkg_dir,
                capture_output=True,
                text=True,
                timeout=180,
            )
            if inst.returncode != 0:
                return {"success": False, "error": f"npm install failed:\n{inst.stderr}", "type": "node"}

            # Pick dev or start script
            pkg  = json.loads((pkg_dir / "package.json").read_text())
            scripts = pkg.get("scripts", {})
            run_cmd = "dev" if "dev" in scripts else "start" if "start" in scripts else None

            if not run_cmd:
                return {"success": True, "output": "npm install OK. No dev/start script found — run manually.", "type": "node"}

            subprocess.run(
                ["npm", "run", run_cmd],
                cwd=pkg_dir,
                capture_output=True,
                text=True,
                timeout=25,
            )
            return {"success": True, "output": f"npm run {run_cmd} started.", "type": "node"}

        except subprocess.TimeoutExpired:
            return {"success": True, "output": "Frontend dev server started.", "type": "node"}
        except FileNotFoundError:
            return {
                "success": True, "output": "npm not found - install Node.js. Frontend files are ready.",
                "type": "node",
            }
        except Exception as e:
            return {"success": False, "error": str(e), "type": "node"}

    def _run_static(self) -> dict:
        for candidate in [
            self.project_path / "frontend" / "index.html",
            self.project_path / "index.html",
        ]:
            if candidate.exists():
                return {
                    "success": True,
                    "output": f"Static site ready.\nOpen in browser: {candidate.resolve()}",
                    "type": "static",
                }
        return {"success": False, "error": "index.html not found.", "type": "static"}

    # ── Public run() ─────────────────────────────────────────────
    def run(self) -> dict:
        app_type = self.app_type if self.app_type != "auto" else self.detect_app_type()
        print(f"  🔍 App type: {app_type}")

        if app_type in ("python_script", "python_server"):
            entry = self._find_python_entry()
            if not entry:
                return {"success": False, "error": "No Python entry point found.", "type": "python"}
            return self._run_python(entry)

        if app_type == "node":
            pkg_dir = self._find_package_json_dir()
            if not pkg_dir:
                return {"success": False, "error": "package.json not found.", "type": "node"}
            return self._run_node(pkg_dir)

        if app_type == "static":
            return self._run_static()

        if app_type in ("fullstack_node", "fullstack_react"):
            print("  🔗 Running backend + frontend...")
            entry   = self._find_python_entry()
            py_res  = self._run_python(entry) if entry else {"success": True, "output": "no backend entry"}
            pkg_dir = self._find_package_json_dir()
            nd_res  = self._run_node(pkg_dir) if pkg_dir else {"success": True, "output": "no package.json"}
            return {
                "success": py_res.get("success") and nd_res.get("success"),
                "output":  f"Backend: {py_res.get('output','')}\nFrontend: {nd_res.get('output','')}",
                "error":   f"{py_res.get('error','')}\n{nd_res.get('error','')}".strip(),
                "type":    "fullstack",
            }

        if app_type == "fullstack_static":
            entry  = self._find_python_entry()
            py_res = self._run_python(entry) if entry else {"success": True}
            st_res = self._run_static()
            return {
                "success": py_res.get("success") and st_res.get("success"),
                "output":  f"Backend: {py_res.get('output','')}\nFrontend: {st_res.get('output','')}",
                "error":   f"{py_res.get('error','')}\n{st_res.get('error','')}".strip(),
                "type":    "fullstack_static",
            }

        return {"success": False, "error": f"Unknown app type: {app_type}", "type": "unknown"}

