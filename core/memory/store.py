"""
APEX v3 — Persistent Memory System
Stores project context, file trees, conversation history.
"""
from __future__ import annotations
import json, os, time, hashlib
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class ProjectMemory:
    name: str
    request: str
    created: float = field(default_factory=time.time)
    plan: dict = field(default_factory=dict)
    files: dict[str, str] = field(default_factory=dict)
    history: list[dict] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    @property
    def id(self) -> str:
        return hashlib.md5(f"{self.name}:{self.created}".encode()).hexdigest()[:8]

    def add_event(self, agent: str, action: str, detail: str = ""):
        self.history.append({
            "ts": time.time(), "agent": agent,
            "action": action, "detail": detail
        })

    def update_files(self, new_files: dict[str, str]):
        self.files.update(new_files)
        self.add_event("system", "files_updated", f"{len(new_files)} files changed")


class MemoryStore:
    """JSON-backed persistent memory for all projects."""

    def __init__(self, store_dir: str = "~/.apex/memory"):
        self.dir = Path(store_dir).expanduser()
        self.dir.mkdir(parents=True, exist_ok=True)

    def save(self, mem: ProjectMemory):
        path = self.dir / f"{mem.id}.json"
        with open(path, "w") as f:
            json.dump(asdict(mem), f, indent=2)

    def load(self, project_id: str) -> ProjectMemory | None:
        path = self.dir / f"{project_id}.json"
        if not path.exists():
            return None
        with open(path) as f:
            data = json.load(f)
        return ProjectMemory(**data)

    def list_projects(self) -> list[dict]:
        projects = []
        for p in self.dir.glob("*.json"):
            with open(p) as f:
                data = json.load(f)
            projects.append({
                "id": data["name"][:8],
                "name": data["name"],
                "request": data["request"][:80],
                "created": data["created"],
                "file_count": len(data.get("files", {})),
            })
        return sorted(projects, key=lambda x: x["created"], reverse=True)

    def delete(self, project_id: str):
        path = self.dir / f"{project_id}.json"
        if path.exists():
            path.unlink()

    def search(self, query: str) -> list[dict]:
        q = query.lower()
        return [p for p in self.list_projects()
                if q in p["name"].lower() or q in p["request"].lower()]
