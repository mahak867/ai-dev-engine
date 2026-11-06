"""
APEX Society — Persistent Memory System
Stores project context, learns from past runs, suggests improvements.
Track 3: agents accumulate experience across sessions.
"""
from __future__ import annotations
import json, os, re, time, hashlib, tempfile
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Any

from core.security import redact

# Where memory lives. Override with APEX_MEMORY_DIR (tests point this at a tmp dir).
DEFAULT_MEMORY_DIR = "~/.apex/memory"
_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
# Retention defaults: keep at most N records / D days. Override via env.
DEFAULT_MAX_RECORDS = int(os.environ.get("APEX_MEMORY_MAX_RECORDS", "500"))
DEFAULT_MAX_AGE_DAYS = float(os.environ.get("APEX_MEMORY_MAX_AGE_DAYS", "90"))


def default_memory_dir() -> str:
    return os.environ.get("APEX_MEMORY_DIR") or DEFAULT_MEMORY_DIR


@dataclass
class ProjectMemory:
    name: str
    request: str
    created: float = field(default_factory=time.time)
    plan: dict = field(default_factory=dict)
    files: dict[str, str] = field(default_factory=dict)
    history: list[dict] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    tech_stack: dict = field(default_factory=dict)
    quality_score: int = 0
    cve_count: int = 0
    review_rounds: int = 0
    file_count: int = 0
    lessons_learned: list[str] = field(default_factory=list)

    @property
    def id(self) -> str:
        return hashlib.sha256(f"{self.name}:{self.created}".encode()).hexdigest()[:8]

    def add_event(self, agent: str, action: str, detail: str = ""):
        self.history.append({
            "ts": time.time(), "agent": agent,
            "action": action, "detail": detail
        })

    def update_files(self, new_files: dict[str, str]):
        self.files.update(new_files)
        self.file_count = len(self.files)
        self.add_event("system", "files_updated", f"{len(new_files)} files changed")

    def add_lesson(self, lesson: str):
        """Record what was learned from this run for future context."""
        if lesson not in self.lessons_learned:
            self.lessons_learned.append(lesson)


class MemoryStore:
    """
    JSON-backed persistent memory. Agents learn from past runs.

    Privacy: generated file *contents* are never persisted (names only), and
    request text / history / lessons are passed through ``redact`` so pasted
    API keys or tokens are masked before hitting disk. Records are written
    0600 inside a 0700 directory and pruned by age and count.
    """

    def __init__(self, store_dir: str | None = None, *,
                 max_records: int = DEFAULT_MAX_RECORDS,
                 max_age_days: float = DEFAULT_MAX_AGE_DAYS):
        self.dir = Path(store_dir or default_memory_dir()).expanduser()
        self.dir.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.dir, 0o700)
        except OSError:
            pass
        self.max_records = max_records
        self.max_age_days = max_age_days

    def _path(self, project_id: str) -> Path | None:
        # project_id may come from an HTTP request; never let it become a path.
        if not isinstance(project_id, str) or not _ID_RE.match(project_id):
            return None
        return self.dir / f"{project_id}.json"

    def save(self, mem: ProjectMemory):
        path = self._path(mem.id)
        data = asdict(mem)
        # Don't store full file contents in memory — too large and may hold secrets
        data["files"] = {k: "" for k in data["files"].keys()}
        data["request"] = redact(data.get("request", ""))
        data["history"] = [{**h, "detail": redact(str(h.get("detail", "")))} for h in data.get("history", [])]
        data["lessons_learned"] = [redact(l) for l in data.get("lessons_learned", [])]
        fd, tmp = tempfile.mkstemp(prefix=".mem-", dir=str(self.dir))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.chmod(tmp, 0o600)
            os.replace(tmp, path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
        self.prune()

    def load(self, project_id: str) -> ProjectMemory | None:
        path = self._path(project_id)
        if path is None or not path.exists():
            return None
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return ProjectMemory(**{k: v for k, v in data.items()
                                if k in ProjectMemory.__dataclass_fields__})

    def prune(self) -> int:
        """Apply retention: drop records older than max_age_days, then keep newest max_records."""
        removed = 0
        files = sorted(self.dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        cutoff = time.time() - self.max_age_days * 86400 if self.max_age_days > 0 else None
        for i, p in enumerate(files):
            too_old = cutoff is not None and p.stat().st_mtime < cutoff
            too_many = self.max_records > 0 and i >= self.max_records
            if too_old or too_many:
                try:
                    p.unlink()
                    removed += 1
                except OSError:
                    pass
        return removed

    def clear(self) -> int:
        """Delete every memory record (user-initiated wipe)."""
        n = 0
        for p in self.dir.glob("*.json"):
            try:
                p.unlink()
                n += 1
            except OSError:
                pass
        return n

    def list_projects(self) -> list[dict]:
        projects = []
        for p in self.dir.glob("*.json"):
            try:
                with open(p, encoding="utf-8") as f:
                    data = json.load(f)
                projects.append({
                    "id": data.get("id", p.stem),
                    "name": data["name"],
                    "request": data["request"][:80],
                    "created": data["created"],
                    "file_count": data.get("file_count", 0),
                    "quality_score": data.get("quality_score", 0),
                    "tech_stack": data.get("tech_stack", {}),
                    "lessons_learned": data.get("lessons_learned", []),
                })
            except Exception:
                pass
        return sorted(projects, key=lambda x: x["created"], reverse=True)

    def get_context_for_request(self, request: str, limit: int = 3) -> str:
        """
        Find past projects similar to this request and return context.
        This is what makes agents smarter over time — they see what
        worked well in similar past projects.
        """
        past = self.list_projects()
        if not past:
            return ""

        # Simple keyword matching — good enough for hackathon
        req_words = set(request.lower().split())
        scored = []
        for p in past:
            past_words = set(p["request"].lower().split())
            overlap = len(req_words & past_words)
            if overlap > 1:
                scored.append((overlap, p))

        scored.sort(key=lambda x: x[0], reverse=True)
        relevant = scored[:limit]

        if not relevant:
            return ""

        lines = ["# Context from similar past projects:"]
        for _, p in relevant:
            lines.append(f"\n## Past project: {p['name']}")
            lines.append(f"Request: {p['request']}")
            if p.get("tech_stack"):
                lines.append(f"Tech stack used: {p['tech_stack']}")
            if p.get("quality_score"):
                lines.append(f"Quality score achieved: {p['quality_score']}/100")
            if p.get("lessons_learned"):
                lines.append("Lessons learned:")
                for lesson in p["lessons_learned"][:3]:
                    lines.append(f"  - {lesson}")

        return "\n".join(lines)

    def search(self, query: str) -> list[dict]:
        q = query.lower()
        return [p for p in self.list_projects()
                if q in p["name"].lower() or q in p["request"].lower()]

    def delete(self, project_id: str) -> bool:
        path = self._path(project_id)
        if path is not None and path.exists():
            path.unlink()
            return True
        return False

    def get_stats(self) -> dict:
        """Aggregate stats across all runs — for dashboard display."""
        projects = self.list_projects()
        if not projects:
            return {"total_runs": 0, "avg_quality": 0, "total_files": 0}
        scores = [p["quality_score"] for p in projects if p["quality_score"] > 0]
        return {
            "total_runs": len(projects),
            "avg_quality": round(sum(scores) / len(scores)) if scores else 0,
            "total_files": sum(p["file_count"] for p in projects),
            "best_quality": max(scores) if scores else 0,
        }
