# core/ai/session_store.py
# Session persistence - save/resume full generation sessions
# Pattern from claw-code: session_store.py persists to .port_sessions/ as JSON

import json
import uuid
import time
from pathlib import Path
from typing import Optional


SESSIONS_DIR = Path.home() / ".apex_engine" / "sessions"


class SessionStore:
    """
    Persists complete session state as JSON.
    Enables /resume command to restore previous conversations.
    Pattern: .port_sessions/ directory from claw-code.
    """

    def __init__(self, sessions_dir: Optional[Path] = None):
        self.sessions_dir = sessions_dir or SESSIONS_DIR
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    def save(self, session_id: str, data: dict) -> str:
        """Save session state to disk."""
        session_file = self.sessions_dir / f"{session_id}.json"
        full_data = {
            "session_id": session_id,
            "saved_at": time.time(),
            "saved_at_human": time.strftime("%Y-%m-%d %H:%M:%S"),
            **data
        }
        session_file.write_text(json.dumps(full_data, indent=2))
        return str(session_file)

    def load(self, session_id: str) -> Optional[dict]:
        """Load session state from disk."""
        session_file = self.sessions_dir / f"{session_id}.json"
        if not session_file.exists():
            return None
        try:
            return json.loads(session_file.read_text())
        except Exception:
            return None

    def list_sessions(self, limit: int = 10) -> list:
        """List recent sessions sorted by date."""
        sessions = []
        for f in self.sessions_dir.glob("*.json"):
            try:
                data = json.loads(f.read_text())
                sessions.append({
                    "id": data.get("session_id", f.stem),
                    "saved_at": data.get("saved_at_human", "unknown"),
                    "project": data.get("project_name", "unknown"),
                    "turns": data.get("turn_count", 0),
                })
            except Exception:
                pass
        sessions.sort(key=lambda x: x.get("saved_at", ""), reverse=True)
        return sessions[:limit]

    def delete(self, session_id: str) -> bool:
        """Delete a session."""
        session_file = self.sessions_dir / f"{session_id}.json"
        if session_file.exists():
            session_file.unlink()
            return True
        return False

    def new_session_id(self) -> str:
        return uuid.uuid4().hex


class GenerationSession:
    """
    Full generation session - wraps the orchestrator with session persistence.
    Allows resuming failed/interrupted generations.
    """

    def __init__(self, name: str, request: str):
        self.session_id = uuid.uuid4().hex
        self.name = name
        self.request = request
        self.store = SessionStore()
        self.ctx = {}
        self.steps_done = []
        self.started_at = time.time()

    def checkpoint(self, step: str, data: dict):
        """Save checkpoint after each pipeline step."""
        self.steps_done.append(step)
        self.ctx.update(data)
        self.store.save(self.session_id, {
            "project_name": self.name,
            "request": self.request,
            "steps_done": self.steps_done,
            "ctx_keys": list(self.ctx.keys()),
            "turn_count": len(self.steps_done),
        })

    def can_resume_from(self, step: str) -> bool:
        """Check if we can skip a step because it completed in a previous run."""
        return step in self.steps_done and step in self.ctx

    @classmethod
    def resume(cls, session_id: str) -> Optional["GenerationSession"]:
        """Resume a session from a saved checkpoint."""
        store = SessionStore()
        data = store.load(session_id)
        if not data:
            return None

        session = cls(data.get("project_name", ""), data.get("request", ""))
        session.session_id = session_id
        session.steps_done = data.get("steps_done", [])
        print(f"  [Session] Resumed: {session_id[:8]}... ({len(session.steps_done)} steps done)")
        return session

    def elapsed(self) -> str:
        secs = int(time.time() - self.started_at)
        return f"{secs//60}m {secs%60}s"
