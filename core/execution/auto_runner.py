# core/execution/auto_runner.py
# Auto-runs generated apps after generation

import subprocess
import threading
import time
import os
import sys
import webbrowser
from pathlib import Path


def auto_run(project_path: str, on_ready=None):
    """Auto-start backend and frontend after generation."""
    path = Path(project_path)
    backend = path / "backend"
    frontend = path / "frontend"
    
    print("\n" + "="*55)
    print("  AUTO-STARTING YOUR APP")
    print("="*55)
    
    processes = []
    
    # Start backend
    if (backend / "app.py").exists():
        print("  Starting backend on port 5000...")
        env = os.environ.copy()
        env["FLASK_ENV"] = "development"
        backend_proc = subprocess.Popen(
            [sys.executable, "app.py"],
            cwd=str(backend),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        processes.append(("backend", backend_proc))
    
    # Start frontend
    if (frontend / "package.json").exists():
        print("  Starting frontend on port 5173...")
        npm = "npm.cmd" if sys.platform == "win32" else "npm"
        frontend_proc = subprocess.Popen(
            [npm, "run", "dev"],
            cwd=str(frontend),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        processes.append(("frontend", frontend_proc))
    
    if not processes:
        print("  No runnable app found")
        return
    
    # Wait for services to start then open browser
    def wait_and_open():
        time.sleep(4)
        print("\n  Opening http://localhost:5173 in browser...")
        webbrowser.open("http://localhost:5173")
        if on_ready:
            on_ready()
    
    threading.Thread(target=wait_and_open, daemon=True).start()
    
    print("\n  Press Ctrl+C to stop all services\n")
    
    # Stream output
    def stream(name, proc):
        for line in proc.stdout:
            line = line.strip()
            if line:
                print(f"  [{name}] {line}")
    
    threads = []
    for name, proc in processes:
        t = threading.Thread(target=stream, args=(name, proc), daemon=True)
        t.start()
        threads.append(t)
    
    try:
        for _, proc in processes:
            proc.wait()
    except KeyboardInterrupt:
        print("\n  Stopping all services...")
        for _, proc in processes:
            proc.terminate()
