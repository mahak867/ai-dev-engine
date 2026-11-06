# core/execution/auto_runner.py
# Starts a generated app's backend/frontend for local preview.
#
# This executes AI-generated code on the host, so it requires explicit approval
# (approved=True or APEX_ALLOW_EXECUTION=1). Services bind to localhost, get a
# minimal environment (no provider API keys), and are torn down as whole
# process groups on exit.

from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

from core.security import minimal_env, require_approval


def _spawn(argv: list[str], cwd: Path, env: dict) -> subprocess.Popen:
    kwargs: dict = {}
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    else:
        kwargs["start_new_session"] = True
    return subprocess.Popen(
        argv, cwd=str(cwd), env=env, shell=False,
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", **kwargs,
    )


def _stop(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
        else:
            os.killpg(proc.pid, signal.SIGTERM)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        proc.kill()


def auto_run(project_path: str, on_ready=None, *, approved: bool | None = None,
             open_browser: bool = False) -> None:
    """Start backend (port 5000) and frontend (port 5173) after an explicit approval."""
    require_approval("auto_run (start generated app)", approved)

    path = Path(project_path).resolve()
    backend = path / "backend"
    frontend = path / "frontend"

    print("\n" + "=" * 55)
    print("  AUTO-STARTING YOUR APP (localhost only)")
    print("=" * 55)

    processes: list[tuple[str, subprocess.Popen]] = []

    if (backend / "app.py").is_file():
        print("  Starting backend on http://127.0.0.1:5000 ...")
        env = minimal_env({"FLASK_RUN_HOST": "127.0.0.1", "HOST": "127.0.0.1", "PORT": "5000"})
        processes.append(("backend", _spawn([sys.executable, "app.py"], backend, env)))

    if (frontend / "package.json").is_file():
        print("  Starting frontend on http://127.0.0.1:5173 ...")
        npm = "npm.cmd" if sys.platform == "win32" else "npm"
        env = minimal_env({"HOST": "127.0.0.1"})
        processes.append(("frontend", _spawn([npm, "run", "dev", "--", "--host", "127.0.0.1"], frontend, env)))

    if not processes:
        print("  No runnable app found")
        return

    def wait_and_open():
        time.sleep(4)
        if open_browser:
            print("\n  Opening http://localhost:5173 in browser...")
            webbrowser.open("http://localhost:5173")
        else:
            print("\n  App should be up at http://localhost:5173")
        if on_ready:
            on_ready()

    threading.Thread(target=wait_and_open, daemon=True).start()
    print("\n  Press Ctrl+C to stop all services\n")

    def stream(name, proc):
        for line in proc.stdout:
            line = line.strip()
            if line:
                print(f"  [{name}] {line}")

    for name, proc in processes:
        threading.Thread(target=stream, args=(name, proc), daemon=True).start()

    try:
        for _, proc in processes:
            proc.wait()
    except KeyboardInterrupt:
        print("\n  Stopping all services...")
    finally:
        for _, proc in processes:
            _stop(proc)
