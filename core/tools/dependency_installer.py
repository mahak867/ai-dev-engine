# core/tools/dependency_installer.py
# Handles Python (pip) and Node.js (npm) dependency installation.

import subprocess
import re
import os
from pathlib import Path


class DependencyInstaller:

    # ── Python ────────────────────────────────────────────────────
    def extract_missing_module(self, error: str) -> str | None:
        """Extract missing Python module name from a ModuleNotFoundError."""
        match = re.search(r"No module named '([^']+)'", error)
        if match:
            return match.group(1).split(".")[0]
        return None

    def install(self, package: str) -> bool:
        """pip install a Python package."""
        try:
            result = subprocess.run(
                ["pip", "install", package],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode == 0:
                print(f"  ✅ Installed: {package}")
                return True
            print(f"  ❌ pip install {package} failed:\n{result.stderr}")
            return False
        except Exception as e:
            print(f"  ❌ pip install error: {e}")
            return False

    def install_requirements(self, project_path: str) -> bool:
        """Install all deps from requirements.txt if present."""
        req = Path(project_path) / "requirements.txt"
        if not req.exists():
            req = Path(project_path) / "backend" / "requirements.txt"
        if not req.exists():
            return True
        try:
            result = subprocess.run(
                ["pip", "install", "-r", str(req)],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode == 0:
                print("  ✅ requirements.txt installed.")
                return True
            print(f"  ❌ requirements.txt install failed:\n{result.stderr}")
            return False
        except Exception as e:
            print(f"  ❌ requirements install error: {e}")
            return False

    # ── Node.js ───────────────────────────────────────────────────
    def npm_install(self, frontend_path: str) -> bool:
        """Run npm install in the frontend directory."""
        pkg = Path(frontend_path) / "package.json"
        if not pkg.exists():
            return True  # Nothing to install
        try:
            result = subprocess.run(
                ["npm", "install"],
                cwd=frontend_path,
                capture_output=True,
                text=True,
                timeout=180,
            )
            if result.returncode == 0:
                print("  ✅ npm install completed.")
                return True
            print(f"  ❌ npm install failed:\n{result.stderr}")
            return False
        except FileNotFoundError:
            print("  ⚠️  npm not found — install Node.js: https://nodejs.org")
            return False
        except Exception as e:
            print(f"  ❌ npm install error: {e}")
            return False

    def install_all(self, project_path: str) -> bool:
        """Install both Python and Node deps for a full-stack project."""
        py_ok = self.install_requirements(project_path)
        node_ok = True

        frontend_dirs = [
            Path(project_path) / "frontend",
            Path(project_path),
        ]
        for d in frontend_dirs:
            if (d / "package.json").exists():
                node_ok = self.npm_install(str(d))
                break

        return py_ok and node_ok
