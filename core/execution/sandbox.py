"""
APEX — Docker sandbox for running generated code.

The Executor agent uses this to *actually run* what the Coder wrote: install
its Python dependencies, byte-compile it, import its entry point and run its
test suite — inside a throwaway container with:

  * no network (``--network none``)
  * memory / CPU / PID limits and a hard wall-clock timeout (container killed)
  * read-only root filesystem, ``--cap-drop ALL``, ``no-new-privileges``
  * a non-root user and only the project copy mounted (no host home, no
    Docker socket, no secrets in the environment)

Dependencies are installed on the host as **wheels only** into
``.apex-deps`` (``pip install --only-binary=:all: --target``). Wheels are
unpacked, never executed, so no ``setup.py`` from a model-written
requirements file runs on the host; the code that imports them only ever runs
inside the container. Option lines (``--index-url``, ``-e``…) are stripped
from generated requirements files.

Configuration:
  APEX_SANDBOX                 "docker" to enable in the pipeline (default off)
  APEX_SANDBOX_IMAGE           image with python3 (default python:3.12-slim)
  APEX_SANDBOX_PYVER           python version of that image (default 3.12)
  APEX_SANDBOX_MEMORY / _CPUS / _PIDS / _TIMEOUT
"""
from __future__ import annotations

import os
import re
import shutil
import tempfile
import uuid
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Mapping, Sequence

from core.security import ProcResult, minimal_env, run_argv, to_argv, write_files_contained

DEFAULT_IMAGE = "python:3.12-slim"
DEPS_DIR = ".apex-deps"
_PROXY_VARS = ("HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "http_proxy", "https_proxy", "no_proxy",
               "PIP_INDEX_URL", "PIP_EXTRA_INDEX_URL", "PIP_CERT", "REQUESTS_CA_BUNDLE",
               "SSL_CERT_FILE", "SSL_CERT_DIR")
_DOCKER_VARS = ("DOCKER_HOST", "DOCKER_CONFIG", "DOCKER_CONTEXT", "DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH")
_SKIP_DIRS = {"node_modules", ".git", "__pycache__", ".venv", "venv", DEPS_DIR}


@lru_cache(maxsize=1)
def docker_available() -> bool:
    if not shutil.which("docker"):
        return False
    r = run_argv(["docker", "info", "--format", "{{.ServerVersion}}"], ".", timeout=15,
                 env=minimal_env(passthrough=_DOCKER_VARS))
    return r.returncode == 0 and bool(r.stdout.strip())


def sandbox_enabled() -> bool:
    return os.environ.get("APEX_SANDBOX", "").strip().lower() == "docker" and docker_available()


@dataclass
class SandboxReport:
    ran: bool = False
    reason: str = ""
    python_root: str = ""
    deps_ok: bool | None = None
    compile_ok: bool | None = None
    import_ok: bool | None = None
    tests_found: int = 0
    tests_passed: int = 0
    tests_failed: int = 0
    tests_ok: bool | None = None
    seconds: float = 0.0
    steps: list[dict] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        checks = [self.deps_ok, self.compile_ok, self.import_ok, self.tests_ok]
        return self.ran and all(c is not False for c in checks)

    def failure_log(self, limit: int = 6000) -> str:
        bad = [s for s in self.steps if not s.get("ok")]
        text = "\n\n".join(f"$ {s['step']}\n{s['output']}" for s in bad)
        return text[-limit:]

    def to_dict(self) -> dict:
        d = asdict(self)
        d["ok"] = self.ok
        for s in d["steps"]:
            s["output"] = s["output"][-2000:]
        return d


_PYTEST_COUNTS = re.compile(r"(\d+) (passed|failed|error|errors)")


class DockerSandbox:
    def __init__(self, image: str | None = None, *, memory: str | None = None, cpus: str | None = None,
                 pids: int | None = None, timeout: int | None = None, pyver: str | None = None):
        env = os.environ
        self.image = image or env.get("APEX_SANDBOX_IMAGE", DEFAULT_IMAGE)
        self.memory = memory or env.get("APEX_SANDBOX_MEMORY", "512m")
        self.cpus = cpus or env.get("APEX_SANDBOX_CPUS", "1")
        self.pids = int(pids or env.get("APEX_SANDBOX_PIDS", "128"))
        self.timeout = int(timeout or env.get("APEX_SANDBOX_TIMEOUT", "120"))
        self.pyver = pyver or env.get("APEX_SANDBOX_PYVER", "3.12")

    # ── low level ─────────────────────────────────────────────────────────────
    def _user(self, workdir: Path) -> str:
        uid = os.getuid() if hasattr(os, "getuid") else 0
        if uid != 0:
            return f"{uid}:{os.getgid()}"
        # Running as root on the host: drop to nobody inside and make the
        # (throwaway) workdir writable for it.
        for p in [workdir, *workdir.rglob("*")]:
            try:
                if not p.is_symlink():
                    p.chmod(0o777 if p.is_dir() else 0o666)
            except OSError:
                pass
        return "65534:65534"

    def docker_argv(self, workdir: Path, argv: Sequence[str], name: str, env: Mapping[str, str] | None = None) -> list[str]:
        cmd = [
            "docker", "run", "--rm", "--name", name,
            "--network", "none",
            "--memory", self.memory, "--memory-swap", self.memory,
            "--cpus", str(self.cpus), "--pids-limit", str(self.pids),
            "--read-only", "--tmpfs", "/tmp:rw,exec,size=64m",
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
            "--user", self._user(workdir),
            "-e", "HOME=/tmp", "-e", "PYTHONDONTWRITEBYTECODE=1", "-e", "PYTHONUNBUFFERED=1",
            "-v", f"{workdir.resolve()}:/work:rw", "-w", "/work",
        ]
        for k, v in (env or {}).items():
            cmd += ["-e", f"{k}={v}"]
        return cmd + [self.image, *argv]

    def run(self, workdir: str | os.PathLike, cmd: str | Sequence[str], *, timeout: int | None = None,
            env: Mapping[str, str] | None = None, cwd: str = ".") -> ProcResult:
        """Run ``cmd`` inside a fresh container with ``workdir`` mounted at /work."""
        workdir = Path(workdir).resolve()
        argv = to_argv(cmd)
        if cwd not in ("", "."):
            argv = ["sh", "-c", 'cd "$0" && exec "$@"', cwd, *argv]
        name = f"apex-sbx-{uuid.uuid4().hex[:12]}"
        deps = f"/work/{cwd.strip('/')}/{DEPS_DIR}" if cwd not in ("", ".") else f"/work/{DEPS_DIR}"
        env = {"PYTHONPATH": deps, **(env or {})}
        r = run_argv(self.docker_argv(workdir, argv, name, env), workdir,
                     timeout=timeout or self.timeout, env=minimal_env(passthrough=_DOCKER_VARS))
        if r.timed_out:
            # Killing the docker CLI does not stop the container — do it explicitly.
            run_argv(["docker", "rm", "-f", name], workdir, timeout=30, env=minimal_env(passthrough=_DOCKER_VARS))
        return r

    # ── dependencies (host side, wheels only) ────────────────────────────────
    def install_python_deps(self, py_root: Path, extra: Sequence[str] = ("pytest",)) -> ProcResult:
        req = py_root / "requirements.txt"
        safe_req = py_root / ".apex-requirements.txt"
        lines = []
        if req.is_file():
            for line in req.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.split("#", 1)[0].strip()
                if not line or line.startswith("-"):
                    continue  # drop --index-url / -e / -r / --trusted-host etc.
                if re.search(r"(://|@\s*\S+:/|\.\./|^/)", line):
                    continue  # no direct URLs / local paths
                lines.append(line)
        lines += list(extra)
        safe_req.write_text("\n".join(lines) + "\n", encoding="utf-8")
        target = py_root / DEPS_DIR
        argv = [
            os.environ.get("APEX_SANDBOX_PIP", shutil.which("pip3") or "pip"), "install", "-q",
            "--disable-pip-version-check", "--no-input", "--no-compile",
            "--only-binary=:all:", "--target", str(target),
            "--python-version", self.pyver, "--implementation", "cp",
            "--platform", "manylinux2014_x86_64", "--platform", "manylinux_2_28_x86_64",
            "--platform", "linux_x86_64", "--platform", "any",
            "-r", str(safe_req),
        ]
        r = run_argv(argv, py_root, timeout=300, env=minimal_env(passthrough=_PROXY_VARS))
        try:
            safe_req.unlink()
        except OSError:
            pass
        return r

    # ── high level: smoke test a generated project ───────────────────────────
    @staticmethod
    def find_python_root(project: Path) -> Path | None:
        for cand in (project / "backend", project / "server", project / "api", project):
            if cand.is_dir() and any(p.suffix == ".py" for p in cand.glob("*.py")):
                return cand
        for p in sorted(project.rglob("*.py")):
            if not any(s in p.parts for s in _SKIP_DIRS):
                return p.parent
        return None

    @staticmethod
    def find_entrypoint(py_root: Path) -> str | None:
        for name in ("app.py", "main.py", "server.py", "wsgi.py", "run.py", "manage.py"):
            if (py_root / name).is_file():
                return name[:-3]
        for name in ("app", "src"):
            if (py_root / name / "__init__.py").is_file():
                return name
        return None

    def smoke_test(self, project: str | os.PathLike, *, files: Mapping[str, str] | None = None) -> SandboxReport:
        """
        Copy the project (or write ``files``) to a temp dir and run, inside the
        sandbox: compileall → import entry point → pytest. Never touches the
        original directory.
        """
        import time as _t
        t0 = _t.time()
        rep = SandboxReport()
        if not docker_available():
            rep.reason = "docker not available"
            return rep
        with tempfile.TemporaryDirectory(prefix="apex-sbx-") as tmp:
            work = Path(tmp) / "project"
            if files is not None:
                work.mkdir()
                write_files_contained(work, files)
            else:
                shutil.copytree(project, work, symlinks=True,
                                ignore=shutil.ignore_patterns(*_SKIP_DIRS))
                for p in list(work.rglob("*")):
                    if p.is_symlink():
                        p.unlink()  # never mount links that point outside
            py_root = self.find_python_root(work)
            if py_root is None:
                rep.reason = "no Python code to run"
                return rep
            rep.ran = True
            rep.python_root = str(py_root.relative_to(work)) or "."
            rel = rep.python_root

            def step(label: str, r: ProcResult) -> bool:
                ok = r.returncode == 0 and not r.timed_out
                rep.steps.append({"step": label, "ok": ok, "returncode": r.returncode,
                                  "timed_out": r.timed_out, "seconds": round(r.duration, 2),
                                  "output": (r.stdout or r.error or "")[-4000:]})
                return ok

            rep.deps_ok = step("pip install --only-binary=:all: (host, no code executed)",
                               self.install_python_deps(py_root))

            rep.compile_ok = step("python3 -m compileall",
                                  self.run(work, ["python3", "-m", "compileall", "-q",
                                                  "-x", re.escape(DEPS_DIR), "."], cwd=rel, timeout=60))

            entry = self.find_entrypoint(py_root)
            if entry:
                code = (f"import sys; sys.path.insert(0, '.'); import importlib; "
                        f"importlib.import_module({entry!r}); print('import ok')")
                rep.import_ok = step(f"import {entry}", self.run(work, ["python3", "-c", code], cwd=rel, timeout=30))

            has_tests = any(py_root.rglob("test_*.py")) or any(py_root.rglob("*_test.py"))
            if has_tests:
                r = self.run(work, ["python3", "-m", "pytest", "-q", "--no-header", "-p", "no:cacheprovider",
                                    "-o", "addopts=", "--ignore", DEPS_DIR], cwd=rel)
                counts = {k: int(n) for n, k in _PYTEST_COUNTS.findall(r.stdout or "")}
                rep.tests_passed = counts.get("passed", 0)
                rep.tests_failed = counts.get("failed", 0) + counts.get("error", 0) + counts.get("errors", 0)
                rep.tests_found = rep.tests_passed + rep.tests_failed
                rep.tests_ok = step("pytest", r) and rep.tests_failed == 0
        rep.seconds = round(_t.time() - t0, 2)
        return rep
