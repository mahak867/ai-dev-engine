"""
APEX Society — WebSocket Backend
Streams real-time agent events from the Qwen orchestrator to the UI.

Run: uvicorn server:app --reload --port 8000
"""
from __future__ import annotations
from dotenv import load_dotenv
load_dotenv()

import asyncio, json, time, logging, os, uuid
from typing import Any
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

log = logging.getLogger("apex.server")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="APEX Society", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ── connection manager ─────────────────────────────────────────────────────────
class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)
        log.info(f"Client connected. Total: {len(self.active)}")

    def disconnect(self, ws: WebSocket):
        self.active.remove(ws)
        log.info(f"Client disconnected. Total: {len(self.active)}")

    async def broadcast(self, data: dict):
        dead = []
        for ws in self.active:
            try:
                await ws.send_text(json.dumps(data))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.active.remove(ws)

manager = ConnectionManager()

# ── session state ──────────────────────────────────────────────────────────────
sessions: dict[str, dict] = {}

# ── event emitter (called by orchestrator agents) ──────────────────────────────
async def emit(session_id: str, agent: str, status: str, msg: str, extra: dict = {}):
    event = {
        "type": "agent_event",
        "session_id": session_id,
        "agent": agent,
        "status": status,
        "msg": msg,
        "ts": round(time.time() * 1000),
        **extra,
    }
    await manager.broadcast(event)
    # store in session
    if session_id in sessions:
        sessions[session_id]["events"].append(event)

# ── sync wrapper for orchestrator callbacks ────────────────────────────────────
_loop: asyncio.AbstractEventLoop | None = None

def sync_emit(session_id: str, agent: str, status: str, msg: str, extra: dict = {}):
    """Called from sync orchestrator code — schedules async emit."""
    global _loop
    if _loop and not _loop.is_closed():
        asyncio.run_coroutine_threadsafe(
            emit(session_id, agent, status, msg, extra), _loop
        )

# ── run agent society ──────────────────────────────────────────────────────────
async def run_society(session_id: str, task: str):
    import threading
    from core.orchestrator import Orchestrator

    sessions[session_id]["status"] = "running"
    sessions[session_id]["task"] = task
    t_start = time.time()

    await emit(session_id, "System", "running", f"starting agent society for: {task[:60]}")

    def on_event(agent: str, status: str, msg: str):
        elapsed = round(time.time() - t_start, 1)
        sync_emit(session_id, agent, status, msg, {"elapsed": elapsed})

    def _run():
        try:
            orch = Orchestrator(model="auto", on_event=on_event)
            path = orch.generate_fullstack(
                name=f"apex-{session_id[:8]}",
                request=task,
                output_dir=f"./runs/{session_id}",
            )
            # count files
            import pathlib
            files = list(pathlib.Path(path).rglob("*"))
            file_count = len([f for f in files if f.is_file()])
            sync_emit(session_id, "System", "done",
                f"complete — {file_count} files generated",
                {"files": file_count, "path": str(path)})
            sessions[session_id]["status"] = "done"
            sessions[session_id]["files"] = file_count
        except Exception as e:
            sync_emit(session_id, "System", "error", f"error: {str(e)[:100]}")
            sessions[session_id]["status"] = "error"

    global _loop
    _loop = asyncio.get_event_loop()
    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

# ── run benchmark ──────────────────────────────────────────────────────────────
async def run_benchmark_task(session_id: str, task: str):
    import threading, pathlib

    sessions[session_id]["status"] = "benchmarking"
    t_start = time.time()

    await emit(session_id, "System", "running", "starting benchmark — single vs society")

    def _run():
        try:
            from benchmark import run_single_agent, run_agent_society, score_output

            # single agent
            sync_emit(session_id, "System", "running", "running single agent...")
            single = run_single_agent(task, f"./runs/{session_id}/single")
            sync_emit(session_id, "System", "running",
                f"single agent done — {single['files_generated']} files, score {single['quality']['score']}")

            # society
            sync_emit(session_id, "System", "running", "running agent society...")

            def on_event(agent, status, msg):
                elapsed = round(time.time() - t_start, 1)
                sync_emit(session_id, agent, status, msg, {"elapsed": elapsed})

            from core.orchestrator import Orchestrator
            events = []
            def on_event2(agent, status, msg):
                elapsed = round(time.time() - t_start, 1)
                sync_emit(session_id, agent, status, msg, {"elapsed": elapsed})
                events.append({"agent": agent, "status": status, "msg": msg})

            orch = Orchestrator(model="auto", on_event=on_event2)
            path = orch.generate_fullstack(
                name=f"bench-society-{session_id[:8]}",
                request=task,
                output_dir=f"./runs/{session_id}",
            )

            files = {}
            skip = {".git","node_modules","__pycache__"}
            import pathlib as pl
            for p in pl.Path(path).rglob("*"):
                if p.is_file() and not any(s in p.parts for s in skip):
                    try: files[str(p.relative_to(path))] = p.read_text(encoding="utf-8")
                    except: pass

            society_quality = score_output(files, task)
            society = {
                "elapsed_seconds": round(time.time() - t_start, 1),
                "files_generated": len(files),
                "quality": society_quality,
                "events": events,
            }

            # broadcast results
            sync_emit(session_id, "System", "done", "benchmark complete", {
                "benchmark": {
                    "single": {
                        "time": single["elapsed_seconds"],
                        "files": single["files_generated"],
                        "score": single["quality"]["score"],
                        "vulns": len(single["quality"].get("security_vulnerabilities", [])),
                    },
                    "society": {
                        "time": society["elapsed_seconds"],
                        "files": society["files_generated"],
                        "score": society_quality["score"],
                        "vulns": len(society_quality.get("security_vulnerabilities", [])),
                    }
                }
            })
            sessions[session_id]["status"] = "done"
        except Exception as e:
            sync_emit(session_id, "System", "error", f"benchmark error: {str(e)[:100]}")

    global _loop
    _loop = asyncio.get_event_loop()
    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

# ── WebSocket endpoint ─────────────────────────────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)
            action = msg.get("action")

            if action == "run":
                session_id = str(uuid.uuid4())[:12]
                task = msg.get("task", "build a REST API with auth and CRUD")
                sessions[session_id] = {
                    "id": session_id, "task": task,
                    "status": "starting", "events": [],
                    "created": time.time(),
                }
                await ws.send_text(json.dumps({
                    "type": "session_created",
                    "session_id": session_id,
                    "task": task,
                }))
                asyncio.create_task(run_society(session_id, task))

            elif action == "benchmark":
                session_id = str(uuid.uuid4())[:12]
                task = msg.get("task", "build a REST API with JWT auth and PostgreSQL")
                sessions[session_id] = {
                    "id": session_id, "task": task,
                    "status": "starting", "events": [],
                    "created": time.time(),
                }
                await ws.send_text(json.dumps({
                    "type": "session_created",
                    "session_id": session_id,
                    "task": task,
                }))
                asyncio.create_task(run_benchmark_task(session_id, task))

            elif action == "list_sessions":
                await ws.send_text(json.dumps({
                    "type": "sessions",
                    "sessions": [
                        {"id": s["id"], "task": s["task"][:50],
                         "status": s["status"], "files": s.get("files", 0)}
                        for s in sessions.values()
                    ]
                }))

            elif action == "ping":
                await ws.send_text(json.dumps({"type": "pong", "ts": time.time()}))

    except WebSocketDisconnect:
        manager.disconnect(ws)

# ── REST endpoints ─────────────────────────────────────────────────────────────
@app.get("/api/health")
async def health():
    return {"status": "ok", "sessions": len(sessions), "clients": len(manager.active)}

@app.get("/api/sessions")
async def list_sessions():
    return {"sessions": list(sessions.values())}

@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    s = sessions.get(session_id)
    if not s:
        return {"error": "not found"}, 404
    return s

@app.get("/api/sessions/{session_id}/events")
async def get_events(session_id: str):
    s = sessions.get(session_id)
    if not s:
        return {"error": "not found"}, 404
    return {"events": s.get("events", [])}

# ── serve frontend ─────────────────────────────────────────────────────────────
@app.get("/")
async def serve_dashboard():
    if os.path.exists("dashboard.html"):
        return FileResponse("dashboard.html")
    return {"message": "APEX Society API — dashboard.html not found"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
