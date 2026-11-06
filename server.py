"""
APEX Society — WebSocket Backend
Streams real-time agent events from the orchestrator to the dashboard.

Run (local, default 127.0.0.1:8000):
    python server.py
    # or: uvicorn server:app --host 127.0.0.1 --port 8000

Exposing beyond localhost requires APEX_API_TOKEN (see core/web_security.py)
and should sit behind a TLS-terminating reverse proxy.
"""
from __future__ import annotations

from dotenv import load_dotenv

load_dotenv()

import asyncio
import io
import json
import logging
import os
import re
import threading
import time
import uuid
import zipfile
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Body, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

from core import web_security
from core.web_security import get_settings, ws_reject_reason
from mcp_server import MCP_TOOLS, TOOLS_BY_NAME, MCPToolExecutor, validate_tool_inputs

log = logging.getLogger("apex.server")
logging.basicConfig(level=logging.INFO)

RUNS_DIR = Path(os.environ.get("APEX_RUNS_DIR", "runs")).resolve()
SESSION_ID_RE = re.compile(r"^[a-f0-9]{16}$")
MAX_EVENTS_PER_SESSION = 2000
SESSION_TTL_SECONDS = 2 * 3600
LLM_AGENTS = ["Planner", "Architect", "Coder", "Reviewer", "SelfHealer", "Debugger", "DocWriter"]
PIPELINE_ROLES = LLM_AGENTS + ["Executor", "Memory"]

# ── state ──────────────────────────────────────────────────────────────────────
sessions: dict[str, dict] = {}
agent_dialogues: dict[str, list] = {}
_loop: asyncio.AbstractEventLoop | None = None
_job_slots = threading.BoundedSemaphore(get_settings().max_concurrent_jobs)


class ConnectionManager:
    """Tracks sockets and which sessions each one may see (no cross-session broadcast)."""

    def __init__(self):
        self.active: set[WebSocket] = set()
        self.subscribers: dict[str, set[WebSocket]] = {}

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.add(ws)
        log.info("Client connected. Total: %d", len(self.active))

    def disconnect(self, ws: WebSocket):
        self.active.discard(ws)
        for subs in self.subscribers.values():
            subs.discard(ws)
        log.info("Client disconnected. Total: %d", len(self.active))

    def subscribe(self, session_id: str, ws: WebSocket):
        self.subscribers.setdefault(session_id, set()).add(ws)

    async def send_to_session(self, session_id: str, data: dict):
        dead = []
        for ws in list(self.subscribers.get(session_id, ())):
            try:
                await ws.send_text(json.dumps(data))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()


def _new_session(task: str, kind: str) -> str:
    # Evict oldest sessions beyond the cap so memory can't grow without bound.
    cap = get_settings().max_sessions
    if len(sessions) >= cap:
        for sid in sorted(sessions, key=lambda k: sessions[k]["created"])[: len(sessions) - cap + 1]:
            sessions.pop(sid, None)
            agent_dialogues.pop(sid, None)
            manager.subscribers.pop(sid, None)
    sid = uuid.uuid4().hex[:16]
    sessions[sid] = {"id": sid, "task": task, "kind": kind, "status": "starting",
                     "events": [], "created": time.time()}
    return sid


async def _cleanup_sessions():
    """Delete sessions older than the TTL to prevent unbounded growth."""
    while True:
        await asyncio.sleep(1800)
        cutoff = time.time() - SESSION_TTL_SECONDS
        dead = [sid for sid, s in list(sessions.items()) if s.get("created", time.time()) < cutoff]
        for sid in dead:
            sessions.pop(sid, None)
            agent_dialogues.pop(sid, None)
            manager.subscribers.pop(sid, None)
        if dead:
            log.info("Cleaned %d expired sessions", len(dead))


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global _loop
    _loop = asyncio.get_running_loop()
    task = asyncio.create_task(_cleanup_sessions())
    try:
        yield
    finally:
        task.cancel()


app = FastAPI(title="APEX Society", version="1.1.0", lifespan=lifespan)
web_security.install(app)


# ── event emitter (called by orchestrator agents) ──────────────────────────────
async def emit(session_id: str, agent: str, status: str, msg: str, extra: dict | None = None):
    event = {
        "type": "agent_event",
        "session_id": session_id,
        "agent": agent,
        "status": status,
        "msg": msg,
        "ts": round(time.time() * 1000),
        **(extra or {}),
    }
    s = sessions.get(session_id)
    if s is not None and len(s["events"]) < MAX_EVENTS_PER_SESSION:
        s["events"].append(event)
    await manager.send_to_session(session_id, event)


def sync_emit(session_id: str, agent: str, status: str, msg: str, extra: dict | None = None):
    """Called from worker threads — schedules async emit on the server loop."""
    if _loop and not _loop.is_closed():
        asyncio.run_coroutine_threadsafe(emit(session_id, agent, status, msg, extra), _loop)


def _set_status(session_id: str, status: str, **fields):
    s = sessions.get(session_id)
    if s is not None:
        s["status"] = status
        s.update(fields)


def _start_job(target, *args) -> bool:
    """Run ``target`` in a worker thread if a job slot is free."""
    if not _job_slots.acquire(blocking=False):
        return False

    def runner():
        try:
            target(*args)
        finally:
            _job_slots.release()

    threading.Thread(target=runner, daemon=True).start()
    return True


# ── run agent society ──────────────────────────────────────────────────────────
def _run_society(session_id: str, task: str):
    from core.orchestrator import Orchestrator

    t_start = time.time()
    _set_status(session_id, "running")
    sync_emit(session_id, "System", "running", f"starting agent society for: {task[:60]}")

    def on_event(agent: str, status: str, msg: str, extra: dict | None = None):
        sync_emit(session_id, agent, status, msg, {"elapsed": round(time.time() - t_start, 1), **(extra or {})})

    def on_dialogue(from_agent, to_agent, msg_type, content):
        entry = {"from": from_agent, "to": to_agent, "type": msg_type,
                 "content": content[:400], "elapsed": round(time.time() - t_start, 1), "ts": time.time()}
        log_list = agent_dialogues.setdefault(session_id, [])
        if len(log_list) < MAX_EVENTS_PER_SESSION:
            log_list.append(entry)
        sync_emit(session_id, from_agent, "dialogue",
                  f"{from_agent} → {to_agent}: {content[:80]}", {"dialogue": entry})

    try:
        orch = Orchestrator(model="auto", on_event=on_event, on_dialogue=on_dialogue)
        path = orch.generate_fullstack(
            name=f"apex-{session_id[:8]}",
            request=task,
            output_dir=str(RUNS_DIR / session_id),
        )
        file_count = sum(1 for f in Path(path).rglob("*") if f.is_file())
        sync_emit(session_id, "System", "done", f"complete — {file_count} files generated", {"files": file_count})
        _set_status(session_id, "done", files=file_count)
    except Exception as e:
        log.exception("society run %s failed", session_id)
        sync_emit(session_id, "System", "error", f"error: {type(e).__name__}")
        _set_status(session_id, "error")


# ── run benchmark ──────────────────────────────────────────────────────────────
def _run_benchmark(session_id: str, task: str):
    t_start = time.time()
    _set_status(session_id, "benchmarking")
    sync_emit(session_id, "System", "running", "starting benchmark — single vs society")
    try:
        from benchmark import run_single_agent, score_output
        from core.orchestrator import Orchestrator

        base = RUNS_DIR / session_id
        sync_emit(session_id, "System", "running", "running single agent...")
        single = run_single_agent(task, str(base / "single"))
        sync_emit(session_id, "System", "running",
                  f"single agent done — {single['files_generated']} files, score {single['quality']['score']}")

        sync_emit(session_id, "System", "running", "running agent society...")

        def on_event(agent, status, msg, extra=None):
            sync_emit(session_id, agent, status, msg, {"elapsed": round(time.time() - t_start, 1), **(extra or {})})

        orch = Orchestrator(model="auto", on_event=on_event)
        path = orch.generate_fullstack(name=f"bench-society-{session_id[:8]}", request=task, output_dir=str(base))

        files = {}
        skip = {".git", "node_modules", "__pycache__"}
        for p in Path(path).rglob("*"):
            if p.is_file() and not p.is_symlink() and not any(s in p.parts for s in skip):
                try:
                    files[str(p.relative_to(path))] = p.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    pass

        society_quality = score_output(files, task)
        sync_emit(session_id, "System", "done", "benchmark complete", {
            "benchmark": {
                "single": {
                    "time": single["elapsed_seconds"],
                    "files": single["files_generated"],
                    "score": single["quality"]["score"],
                    "vulns": len(single["quality"].get("security_vulnerabilities", [])),
                },
                "society": {
                    "time": round(time.time() - t_start, 1),
                    "files": len(files),
                    "score": society_quality["score"],
                    "vulns": len(society_quality.get("security_vulnerabilities", [])),
                },
            }
        })
        _set_status(session_id, "done", files=len(files))
    except Exception as e:
        log.exception("benchmark %s failed", session_id)
        sync_emit(session_id, "System", "error", f"benchmark error: {type(e).__name__}")
        _set_status(session_id, "error")


# ── WebSocket endpoint ─────────────────────────────────────────────────────────
async def _ws_send(ws: WebSocket, data: dict):
    await ws.send_text(json.dumps(data))


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    settings = get_settings()
    reject = ws_reject_reason(ws, settings)
    if reject:
        code, reason = reject
        await ws.close(code=code, reason=reason)
        return

    await manager.connect(ws)
    try:
        while True:
            raw = await ws.receive_text()
            if len(raw.encode()) > settings.max_ws_message_bytes:
                await _ws_send(ws, {"type": "error", "msg": "message too large"})
                continue
            try:
                msg = json.loads(raw)
                if not isinstance(msg, dict):
                    raise ValueError
            except ValueError:
                await _ws_send(ws, {"type": "error", "msg": "invalid JSON"})
                continue
            action = msg.get("action")

            if action in ("run", "benchmark"):
                default = ("build a REST API with auth and CRUD" if action == "run"
                           else "build a REST API with JWT auth and PostgreSQL")
                task = msg.get("task", default)
                if not isinstance(task, str) or not task.strip():
                    await _ws_send(ws, {"type": "error", "msg": "Task cannot be empty"})
                    continue
                # Cap prompt size for both actions to bound token spend.
                task = task.strip()[: settings.max_task_chars]
                session_id = _new_session(task, action)
                manager.subscribe(session_id, ws)
                target = _run_society if action == "run" else _run_benchmark
                if not _start_job(target, session_id, task):
                    _set_status(session_id, "rejected")
                    await _ws_send(ws, {"type": "error", "session_id": session_id,
                                        "msg": "Server busy — too many jobs running. Try again shortly."})
                    continue
                await _ws_send(ws, {"type": "session_created", "session_id": session_id, "task": task})

            elif action == "subscribe":
                sid = msg.get("session_id")
                if isinstance(sid, str) and sid in sessions:
                    manager.subscribe(sid, ws)
                    await _ws_send(ws, {"type": "subscribed", "session_id": sid})
                else:
                    await _ws_send(ws, {"type": "error", "msg": "unknown session"})

            elif action == "list_sessions":
                await _ws_send(ws, {
                    "type": "sessions",
                    "sessions": [
                        {"id": s["id"], "task": s["task"][:50], "status": s["status"], "files": s.get("files", 0)}
                        for s in sessions.values()
                    ],
                })

            elif action == "ping":
                await _ws_send(ws, {"type": "pong", "ts": time.time()})

            else:
                await _ws_send(ws, {"type": "error", "msg": "unknown action"})

    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(ws)


# ── REST endpoints ─────────────────────────────────────────────────────────────
def _not_found(msg: str = "not found") -> JSONResponse:
    return JSONResponse({"error": msg}, status_code=404)


def _session_dir(session_id: str) -> Path | None:
    """Exact, validated lookup — the old prefix glob let `*` match any run."""
    if not SESSION_ID_RE.match(session_id or ""):
        return None
    d = (RUNS_DIR / session_id).resolve()
    if d.parent != RUNS_DIR or not d.is_dir():
        return None
    return d


def _iter_files(root: Path):
    for f in root.rglob("*"):
        if f.is_symlink():
            continue  # never follow a link out of the run directory
        if f.is_file() and f.resolve().is_relative_to(root):
            yield f


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/sessions/{session_id}/files")
async def get_session_files(session_id: str):
    """List all files generated for a session."""
    d = _session_dir(session_id)
    if d is None:
        return _not_found("No files generated yet or session not found")
    files = [{"path": str(f.relative_to(d)), "size": f.stat().st_size} for f in _iter_files(d)]
    return {"session_id": session_id, "file_count": len(files), "files": files}


@app.get("/api/sessions/{session_id}/download")
async def download_session(session_id: str):
    """Download all generated files for a session as a ZIP archive."""
    d = _session_dir(session_id)
    if d is None:
        return _not_found("No files found for this session")
    buf = io.BytesIO()
    file_count = 0
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in _iter_files(d):
            zf.write(f, f.relative_to(d))
            file_count += 1
    if file_count == 0:
        return _not_found("Session folder exists but contains no files")
    buf.seek(0)
    return StreamingResponse(
        buf, media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="apex-{session_id[:8]}.zip"'},
    )


@app.get("/api/memory/stats")
async def memory_stats():
    """Past-run stats for the dashboard Memory tab."""
    from core.memory.store import MemoryStore
    store = MemoryStore()
    return {"stats": store.get_stats(), "projects": store.list_projects()[:20]}


@app.get("/api/society/stats")
async def society_stats():
    """
    Aggregate stats across recorded runs. ``single_agent_baseline`` is the
    static result of the recorded hackathon benchmark (one task, n=1), not a
    live measurement — it is labelled as such.
    """
    from core.memory.store import MemoryStore
    projects = MemoryStore().list_projects()
    total_files = sum(p.get("file_count", 0) for p in projects)
    scores = [p["quality_score"] for p in projects if p.get("quality_score", 0) > 0]
    avg = round(sum(scores) / len(scores)) if scores else 0
    baseline = {"avg_files": 5, "avg_quality_score": 91, "cves_shipped": 1,
                "source": "static: recorded hackathon benchmark, single task, n=1"}
    return {
        "society": {
            "total_runs": len(projects),
            "total_files_generated": total_files,
            "avg_quality_score": avg,
            "best_quality_score": max(scores) if scores else 0,
            "llm_agents": len(LLM_AGENTS),
            "pipeline_roles": len(PIPELINE_ROLES),
            "agents": len(LLM_AGENTS),
            "conflict_resolution_rounds_max": 3,
        },
        "single_agent_baseline": baseline,
        "improvement": {
            "files_per_run": round(total_files / len(projects), 1) if projects else None,
            "quality_delta_vs_baseline": (avg - baseline["avg_quality_score"]) if scores else None,
            "note": "Quality scores come from the Reviewer agent (LLM self-assessment), "
                    "not an independent security scan.",
        },
    }


@app.get("/api/sessions")
async def list_sessions():
    return {"sessions": [
        {k: v for k, v in s.items() if k != "events"} | {"event_count": len(s["events"])}
        for s in sessions.values()
    ]}


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    s = sessions.get(session_id)
    return s if s else _not_found()


@app.get("/api/sessions/{session_id}/events")
async def get_events(session_id: str):
    s = sessions.get(session_id)
    return {"events": s.get("events", [])} if s else _not_found()


@app.get("/api/sessions/{session_id}/dialogue")
async def get_dialogue(session_id: str):
    """Structured agent-to-agent dialogue for a session."""
    if session_id not in sessions:
        return _not_found()
    msgs = agent_dialogues.get(session_id, [])
    return {"session_id": session_id, "messages": msgs, "count": len(msgs)}


# ── MCP-style tool API (same tools/validation as mcp_server.py) ────────────────
@app.get("/mcp/tools")
async def mcp_list_tools():
    return {"tools": MCP_TOOLS, "count": len(MCP_TOOLS),
            "security": "typed functions only — no shell execution exposed"}


@app.get("/mcp/schema")
async def mcp_schema():
    return {"name": "apex-society", "version": "1.1.0",
            "description": f"{len(LLM_AGENTS)} LLM agents exposed as typed tools",
            "tools": MCP_TOOLS}


@app.post("/mcp/tools/{tool_name}")
async def mcp_call_tool(tool_name: str, inputs: dict = Body(...)):
    err = validate_tool_inputs(tool_name, inputs)
    if err:
        return JSONResponse({"error": err, "available": list(TOOLS_BY_NAME)}, status_code=400)
    if not _job_slots.acquire(blocking=False):
        return JSONResponse({"error": "busy — too many concurrent jobs"}, status_code=429)
    try:
        return await run_in_threadpool(MCPToolExecutor.shared().execute, tool_name, inputs)
    finally:
        _job_slots.release()


@app.get("/mcp/health")
async def mcp_health():
    return {"status": "ok", "tools": len(MCP_TOOLS)}


# ── serve frontend ─────────────────────────────────────────────────────────────
_DASHBOARD = Path(__file__).resolve().parent / "dashboard.html"


@app.get("/")
async def serve_dashboard():
    if _DASHBOARD.exists():
        return FileResponse(_DASHBOARD)
    return {"message": "APEX Society API — dashboard.html not found"}


if __name__ == "__main__":
    import uvicorn

    s = get_settings()
    web_security.assert_safe_bind(s.host, s)
    uvicorn.run("server:app", host=s.host, port=s.port,
                reload=os.environ.get("APEX_DEV_RELOAD") == "1", proxy_headers=False)
