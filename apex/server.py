"""
APEX Society — WebSocket Backend
Streams real-time agent events from the orchestrator to the dashboard.

Run (local, default 127.0.0.1:8000):
    apex serve          (or: python -m apex.server)
    # or: uvicorn apex.server:app --host 127.0.0.1 --port 8000

Exposing beyond localhost requires APEX_API_TOKEN (see apex/web_security.py)
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

from apex import web_security
from apex.tool_api import MCP_TOOLS, TOOLS_BY_NAME, MCPToolExecutor, validate_tool_inputs
from apex.web_security import RateLimiter, client_ip, get_settings, ws_reject_reason

log = logging.getLogger("apex.server")
logging.basicConfig(level=logging.INFO)

RUNS_DIR = Path(os.environ.get("APEX_RUNS_DIR", "runs")).resolve()
SESSION_ID_RE = re.compile(r"^[a-f0-9]{16}$")
MAX_EVENTS_PER_SESSION = 2000
SESSION_TTL_SECONDS = 2 * 3600
LLM_AGENTS = ["Planner", "Architect", "Coder", "Reviewer", "SelfHealer", "Debugger", "DocWriter"]
TOOL_AGENTS = ["Executor", "Memory"]
AGENTS = LLM_AGENTS + TOOL_AGENTS  # the 9-agent society

# ── state ──────────────────────────────────────────────────────────────────────
sessions: dict[str, dict] = {}
agent_dialogues: dict[str, list] = {}
_loop: asyncio.AbstractEventLoop | None = None
_job_slots = threading.BoundedSemaphore(get_settings().max_concurrent_jobs)
_rate = RateLimiter()

# Bring-your-own-key providers: visitor key -> (env var name, pinned model)
BYOK_PROVIDERS = {
    "groq": ("GROQ_API_KEY", "groq/llama-3.3-70b"),
    "openrouter": ("OPENROUTER_API_KEY", "or/kimi-k2"),
    "qwen": ("QWEN_API_KEY", "qwen/qwen-plus"),
}
_KEY_RE = re.compile(r"^[A-Za-z0-9_\-.]{20,200}$")
REPLAY_MODEL = "fake/canned"


def _install_replay_llm():
    """Canned outputs for the no-key 'demo replay' — clearly labelled, costs nothing."""
    from apex import demo_llm as fake_llm
    from apex.ai import provider
    delay = float(os.environ.get("APEX_REPLAY_DELAY", "0.8"))

    def slow(messages):
        time.sleep(delay)
        return fake_llm.respond(messages)
    provider.set_fake_responder(slow)


def _llm_context(byok: dict | None):
    """Context manager that scopes a visitor's key / replay model to one run."""
    from contextlib import nullcontext

    from apex.ai.provider import api_keys
    if not byok:
        return nullcontext()
    if byok.get("mode") == "replay":
        return api_keys(model=REPLAY_MODEL)
    env_name, model = BYOK_PROVIDERS[byok["provider"]]
    return api_keys(model=model, **{env_name: byok["key"]})


def _parse_byok(msg: dict, settings) -> tuple[dict | None, str | None]:
    """Validate BYOK / replay fields from a run message. Returns (byok, error)."""
    if msg.get("mode") == "replay":
        return {"mode": "replay"}, None
    key = msg.get("api_key")
    if key:
        prov = msg.get("provider", "groq")
        if prov not in BYOK_PROVIDERS:
            return None, f"provider must be one of {sorted(BYOK_PROVIDERS)}"
        if not isinstance(key, str) or not _KEY_RE.match(key.strip()):
            return None, "API key format looks wrong"
        return {"provider": prov, "key": key.strip()}, None
    if settings.public_demo:
        return None, "This public demo has no server-side API key. Paste your own key or tick 'Demo replay'."
    return None, None


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
    _install_replay_llm()
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


def _start_job(target, *args) -> bool:  # noqa: D401
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
def _run_society(session_id: str, task: str, byok: dict | None = None):
    with _llm_context(byok):
        _run_society_inner(session_id, task, replay=bool(byok and byok.get("mode") == "replay"))


def _run_society_inner(session_id: str, task: str, replay: bool = False):
    import tempfile

    from apex import telemetry
    from apex.memory.store import MemoryStore
    from apex.orchestrator import Orchestrator

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
        if replay:
            sync_emit(session_id, "System", "running",
                      "DEMO REPLAY — canned agent outputs, no LLM is called. Paste a key for a real run.")
        # Public demo / replay: a throwaway memory store, so one visitor's request
        # text is never injected into another visitor's prompts.
        store = MemoryStore(tempfile.mkdtemp(prefix="apex-mem-")) if (get_settings().public_demo or replay) else None
        tracker = telemetry.UsageTracker()
        with telemetry.track(tracker):
            orch = Orchestrator(model="auto", on_event=on_event, on_dialogue=on_dialogue, memory_store=store)
            path = orch.generate_fullstack(
                name=f"apex-{session_id[:8]}",
                request=task,
                output_dir=str(RUNS_DIR / session_id),
            )
        file_count = sum(1 for f in Path(path).rglob("*") if f.is_file())
        usage = tracker.summary()
        _set_status(session_id, "done", files=file_count, usage={k: usage[k] for k in (
            "calls", "total_tokens", "cost_usd", "llm_seconds", "wall_seconds")}, replay=replay)
    except Exception as e:
        log.exception("society run %s failed", session_id)
        sync_emit(session_id, "System", "error", f"error: {type(e).__name__}")
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

            if action == "run":
                default = "build a REST API with auth and CRUD"
                task = msg.get("task", default)
                if not isinstance(task, str) or not task.strip():
                    await _ws_send(ws, {"type": "error", "msg": "Task cannot be empty"})
                    continue
                # Cap prompt size for both actions to bound token spend.
                task = task.strip()[: settings.max_task_chars]
                byok, err = _parse_byok(msg, settings)
                if err:
                    await _ws_send(ws, {"type": "error", "msg": err})
                    continue
                if settings.public_demo and not (byok and byok.get("mode") == "replay") and \
                        not _rate.allow(client_ip(ws, settings), settings.runs_per_hour):
                    await _ws_send(ws, {"type": "error",
                                        "msg": f"Rate limit: {settings.runs_per_hour} runs per hour. Try later."})
                    continue
                session_id = _new_session(task, "run")
                manager.subscribe(session_id, ws)
                if not _start_job(_run_society, session_id, task, byok):
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
                if settings.public_demo:
                    await _ws_send(ws, {"type": "sessions", "sessions": []})
                    continue
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
    s = get_settings()
    return {"status": "ok", "public_demo": s.public_demo, "byok_providers": sorted(BYOK_PROVIDERS),
            "auth_required": s.auth_required}


def _demo_forbidden():
    return JSONResponse({"error": "disabled in the public demo"}, status_code=403)


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
    if get_settings().public_demo:
        return {"stats": {"total_runs": 0}, "projects": [], "note": "memory is per-run in the public demo"}
    from apex.memory.store import MemoryStore
    store = MemoryStore()
    return {"stats": store.get_stats(), "projects": store.list_projects()[:20]}


@app.get("/api/society/stats")
async def society_stats():
    """Aggregate stats across recorded runs (Reviewer scores are LLM self-assessment)."""
    from apex.memory.store import MemoryStore
    projects = [] if get_settings().public_demo else MemoryStore().list_projects()
    total_files = sum(p.get("file_count", 0) for p in projects)
    scores = [p["quality_score"] for p in projects if p.get("quality_score", 0) > 0]
    return {"society": {
        "total_runs": len(projects),
        "total_files_generated": total_files,
        "avg_quality_score": round(sum(scores) / len(scores)) if scores else 0,
        "best_quality_score": max(scores) if scores else 0,
        "agents": len(AGENTS), "llm_agents": len(LLM_AGENTS), "tool_agents": len(TOOL_AGENTS),
    }}


@app.get("/api/sessions")
async def list_sessions():
    if get_settings().public_demo:
        return _demo_forbidden()
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
            "description": f"{len(AGENTS)}-agent society; its {len(LLM_AGENTS)} LLM agents exposed as typed tools",
            "tools": MCP_TOOLS}


@app.post("/mcp/tools/{tool_name}")
async def mcp_call_tool(tool_name: str, inputs: dict = Body(...)):
    err = validate_tool_inputs(tool_name, inputs)
    if err:
        return JSONResponse({"error": err, "available": list(TOOLS_BY_NAME)}, status_code=400)
    if get_settings().public_demo:
        return _demo_forbidden()
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
_DASHBOARD = Path(__file__).resolve().parent / "web" / "dashboard.html"


@app.get("/")
async def serve_dashboard():
    if _DASHBOARD.exists():
        return FileResponse(_DASHBOARD)
    return {"message": "APEX Society API — dashboard.html not found"}


def main() -> None:
    import uvicorn

    s = get_settings()
    web_security.assert_safe_bind(s.host, s)
    print(f"APEX Society office: http://{'localhost' if s.host in ('127.0.0.1', '0.0.0.0') else s.host}:{s.port}")
    uvicorn.run("apex.server:app", host=s.host, port=s.port,
                reload=os.environ.get("APEX_DEV_RELOAD") == "1", proxy_headers=False)


if __name__ == "__main__":
    main()
