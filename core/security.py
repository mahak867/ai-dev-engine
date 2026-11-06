"""
APEX — shared security primitives.

Everything that touches the filesystem with model-chosen paths, spawns a
process, or fetches a URL on behalf of an agent should go through here so the
policy lives in one place and is covered by one set of tests.

What this module is NOT: an OS sandbox. ``run_argv`` strips secrets from the
child environment, never uses a shell, and kills the whole process tree on
timeout — but the child still runs as the current user with network access.
Run generated code in a disposable container/VM if it is untrusted.
"""
from __future__ import annotations

import ipaddress
import os
import re
import shlex
import signal
import socket
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Iterable, Mapping, Sequence
from urllib.parse import urlparse


class UnsafePathError(ValueError):
    """A model- or user-supplied path tried to leave its root."""


class ExecutionDisabledError(RuntimeError):
    """Raised when a side-effecting action runs without explicit approval."""


# ── Feature gates ──────────────────────────────────────────────────────────────
_TRUTHY = {"1", "true", "yes", "on"}


def env_flag(name: str, default: bool = False) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in _TRUTHY


def execution_allowed() -> bool:
    """Host-side execution of generated code / installs is opt-in."""
    return env_flag("APEX_ALLOW_EXECUTION", False)


def require_approval(action: str, approved: bool | None) -> None:
    """Fail closed unless the caller (or env) explicitly approved ``action``."""
    if approved is None:
        approved = execution_allowed()
    if not approved:
        raise ExecutionDisabledError(
            f"'{action}' runs code on this machine and is disabled by default. "
            f"Pass approved=True / allow_execution=True or set APEX_ALLOW_EXECUTION=1."
        )


# ── Path containment ───────────────────────────────────────────────────────────
_WIN_RESERVED = re.compile(r"^(con|prn|aux|nul|com[1-9]|lpt[1-9])(\..*)?$", re.I)
MAX_PATH_LEN = 260


def safe_join(root: str | os.PathLike, rel_path: str) -> Path:
    """
    Resolve ``rel_path`` under ``root`` and guarantee the result stays inside.

    Rejects: empty paths, NUL bytes, absolute POSIX paths, Windows drive / UNC
    paths, any ``..`` component, Windows reserved device names, and anything
    whose *canonical* location (after following existing symlinks) is outside
    the canonical root. Uses ``Path.is_relative_to`` on resolved paths instead
    of a string-prefix check, so ``/x/project-other`` is not "inside"
    ``/x/project``.
    """
    if not isinstance(rel_path, str) or not rel_path.strip():
        raise UnsafePathError("empty path")
    if "\x00" in rel_path:
        raise UnsafePathError("NUL byte in path")
    if len(rel_path) > MAX_PATH_LEN:
        raise UnsafePathError("path too long")

    raw = rel_path.strip()
    win = PureWindowsPath(raw)
    if raw.startswith(("/", "\\")) or win.drive or win.root or PurePosixPath(raw).is_absolute():
        raise UnsafePathError(f"absolute path not allowed: {raw!r}")

    parts = [p for p in re.split(r"[\\/]+", raw) if p not in ("", ".")]
    if not parts:
        raise UnsafePathError(f"path has no components: {raw!r}")
    for part in parts:
        if part == "..":
            raise UnsafePathError(f"parent traversal not allowed: {raw!r}")
        if part.lower() == ".git":
            # .git/hooks/* and .git/config (core.fsmonitor, etc.) execute code
            # on the next git command — generated output must never touch them.
            raise UnsafePathError(f"writes into .git are not allowed: {raw!r}")
        if _WIN_RESERVED.match(part):
            raise UnsafePathError(f"reserved device name: {part!r}")
        if part.endswith((" ", ".")) and part not in (".",):
            raise UnsafePathError(f"trailing dot/space component: {part!r}")

    root_resolved = Path(root).resolve()
    candidate = root_resolved.joinpath(*parts)
    # resolve(strict=False) follows any symlinks that already exist on disk,
    # so a planted `out -> /etc` link is caught here.
    resolved = candidate.resolve()
    if resolved != root_resolved and not resolved.is_relative_to(root_resolved):
        raise UnsafePathError(f"path escapes project root: {raw!r}")
    return resolved


def safe_write_text(
    root: str | os.PathLike,
    rel_path: str,
    content: str,
    *,
    overwrite: bool = True,
    max_bytes: int = 5 * 1024 * 1024,
) -> Path:
    """Atomically write ``content`` to ``root/rel_path`` after containment checks."""
    data = content.encode("utf-8")
    if len(data) > max_bytes:
        raise UnsafePathError(f"{rel_path!r} exceeds {max_bytes} bytes")
    target = safe_join(root, rel_path)
    if target.is_dir():
        raise UnsafePathError(f"{rel_path!r} is a directory")
    if target.exists() and not overwrite:
        raise FileExistsError(str(target))

    Path(root).resolve().mkdir(parents=True, exist_ok=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    # Re-check after mkdir: a racing symlink in a parent would show up here.
    safe_join(root, rel_path)

    fd, tmp = tempfile.mkstemp(prefix=".apex-", dir=str(target.parent))
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        # os.replace swaps the directory entry; if `target` is a symlink the
        # link itself is replaced rather than its destination being written.
        os.replace(tmp, target)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return target


def write_files_contained(root: str | os.PathLike, files: Mapping[str, str], log=None) -> tuple[list[str], list[str]]:
    """Write many files; skip (and report) any whose path is unsafe."""
    written, rejected = [], []
    for rel, content in files.items():
        try:
            safe_write_text(root, rel, content if isinstance(content, str) else str(content))
            written.append(rel)
        except (UnsafePathError, FileExistsError, OSError) as e:
            rejected.append(f"{rel}: {e}")
            if log:
                log.warning("Refused to write %r: %s", rel, e)
    return written, rejected


# ── Child-process environment ──────────────────────────────────────────────────
_ENV_ALLOWLIST = {
    "PATH", "HOME", "USER", "LOGNAME", "LANG", "LANGUAGE", "TERM", "TZ", "SHELL",
    "TMPDIR", "TEMP", "TMP",
    # Windows essentials
    "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "COMSPEC", "PATHEXT", "USERPROFILE",
    "APPDATA", "LOCALAPPDATA", "PROGRAMDATA", "PROGRAMFILES", "PROGRAMFILES(X86)",
    "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE",
    # Toolchains
    "VIRTUAL_ENV", "PYTHONIOENCODING", "NODE_ENV", "NVM_DIR",
}
_ENV_PREFIX_ALLOW = ("LC_",)
_SECRET_NAME = re.compile(r"(KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL|AUTH|COOKIE|SESSION)", re.I)


def minimal_env(extra: Mapping[str, str] | None = None, passthrough: Iterable[str] = ()) -> dict[str, str]:
    """
    Build a child environment containing only an explicit allowlist.

    Provider API keys, cloud credentials and tokens in the parent process are
    NOT inherited. ``passthrough`` names extra variables a specific tool needs
    (e.g. ``RAILWAY_TOKEN`` for an approved deploy).
    """
    passthrough = set(passthrough)
    allowed = set(_ENV_ALLOWLIST) | passthrough
    env = {
        k: v for k, v in os.environ.items()
        if (k.upper() in allowed or k in allowed or k.startswith(_ENV_PREFIX_ALLOW))
        and (k in passthrough or not _SECRET_NAME.search(k))
    }
    env.update({"CI": "true", "NEXT_TELEMETRY_DISABLED": "1", "PYTHONDONTWRITEBYTECODE": "1"})
    if extra:
        env.update(extra)
    return env


# ── Process execution ──────────────────────────────────────────────────────────
MAX_OUTPUT_CHARS = 200_000


@dataclass
class ProcResult:
    stdout: str
    returncode: int
    duration: float
    timed_out: bool = False
    error: str = ""


def to_argv(cmd: str | Sequence[str]) -> list[str]:
    """Normalise a command to an argv list. Strings are split, never shell-parsed."""
    if isinstance(cmd, str):
        argv = shlex.split(cmd, posix=os.name != "nt")
    else:
        argv = [str(c) for c in cmd]
    if not argv:
        raise ValueError("empty command")
    return argv


def _kill_tree(proc: subprocess.Popen) -> None:
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                           capture_output=True, timeout=10)
        else:
            os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError, subprocess.SubprocessError):
        pass
    try:
        proc.kill()
    except OSError:
        pass


def run_argv(
    cmd: str | Sequence[str],
    cwd: str | os.PathLike,
    *,
    timeout: float = 120,
    env: Mapping[str, str] | None = None,
    max_output: int = MAX_OUTPUT_CHARS,
) -> ProcResult:
    """
    Run a command without a shell, in its own process group/session, with a
    minimal environment and a hard timeout that kills every descendant.
    """
    argv = to_argv(cmd)
    t0 = time.time()
    kwargs: dict = {}
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    else:
        kwargs["start_new_session"] = True
    try:
        proc = subprocess.Popen(
            argv, shell=False, cwd=str(cwd),
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            env=dict(env) if env is not None else minimal_env(),
            text=True, encoding="utf-8", errors="replace", **kwargs,
        )
    except (FileNotFoundError, PermissionError, OSError) as e:
        return ProcResult("", -1, time.time() - t0, error=f"{type(e).__name__}: {e}")

    try:
        out, _ = proc.communicate(timeout=timeout)
        timed_out = False
    except subprocess.TimeoutExpired:
        _kill_tree(proc)
        try:
            out, _ = proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            out = ""
        timed_out = True
    finally:
        # Reap anything the child left behind in its group.
        if os.name != "nt":
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError, OSError):
                pass

    out = out or ""
    if len(out) > max_output:
        out = out[:max_output] + f"\n... [truncated {len(out) - max_output} chars]"
    return ProcResult(
        stdout=out,
        returncode=-1 if timed_out else proc.returncode,
        duration=time.time() - t0,
        timed_out=timed_out,
        error="Timed out" if timed_out else "",
    )


def python_argv(*args: str) -> list[str]:
    return [sys.executable, *args]


# ── Outbound URL policy (SSRF) ─────────────────────────────────────────────────
def check_public_url(url: str) -> str:
    """
    Allow only http(s) URLs whose host resolves exclusively to public IPs.
    Blocks loopback, RFC1918, link-local (cloud metadata 169.254.169.254),
    CGNAT, multicast and reserved ranges. Returns the URL or raises ValueError.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"scheme not allowed: {parsed.scheme!r}")
    host = parsed.hostname
    if not host:
        raise ValueError("URL has no host")
    if parsed.username or parsed.password:
        raise ValueError("credentials in URL not allowed")
    try:
        infos = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80))
    except socket.gaierror as e:
        raise ValueError(f"cannot resolve {host!r}: {e}") from e
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global or ip.is_multicast:
            raise ValueError(f"{host!r} resolves to non-public address {ip}")
    return url


# ── Redaction ──────────────────────────────────────────────────────────────────
_SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{16,}"),                 # OpenAI/DashScope style
    re.compile(r"gsk_[A-Za-z0-9]{20,}"),                    # Groq
    re.compile(r"(?:ghp|gho|ghs|ghu|github_pat)_[A-Za-z0-9_]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),                       # AWS access key id
    re.compile(r"xox[abpors]-[A-Za-z0-9-]{10,}"),           # Slack
    re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),  # JWT
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"(?i)((?:api[_-]?key|secret|token|password)\s*[:=]\s*)['\"]?[^\s'\"]{8,}"),
]


def redact(text: str) -> str:
    """Mask likely credentials before persisting or logging free text."""
    if not text:
        return text
    for pat in _SECRET_PATTERNS:
        if pat.groups:
            text = pat.sub(lambda m: m.group(1) + "[REDACTED]", text)
        else:
            text = pat.sub("[REDACTED]", text)
    return text
