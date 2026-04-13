# core/ai/memory_system.py
# Engine memory - remembers past projects, preferences, and learned fixes

import json
import os
from pathlib import Path
from datetime import datetime

MEMORY_FILE = Path.home() / ".apex_engine" / "memory.json"

def _load():
    try:
        MEMORY_FILE.parent.mkdir(exist_ok=True)
        if MEMORY_FILE.exists():
            return json.loads(MEMORY_FILE.read_text())
    except Exception:
        pass
    return {"projects": [], "preferences": {}, "learned_fixes": [], "stats": {"total_generated": 0, "favorite_type": {}}}

def _save(data):
    try:
        MEMORY_FILE.parent.mkdir(exist_ok=True)
        MEMORY_FILE.write_text(json.dumps(data, indent=2))
    except Exception:
        pass

def remember_project(name: str, request: str, spec: dict, files: list):
    """Save a generated project to memory."""
    data = _load()
    project = {
        "name": name,
        "request": request,
        "type": spec.get("project_type", "unknown"),
        "complexity": spec.get("complexity", "moderate"),
        "stack": f"{spec.get('backend_framework','flask')}+{spec.get('frontend_framework','react')}",
        "models": spec.get("core_models", []),
        "file_count": len(files),
        "timestamp": datetime.now().isoformat(),
        "integrations": spec.get("tech_stack", []),
    }
    data["projects"].append(project)
    data["stats"]["total_generated"] = data["stats"].get("total_generated", 0) + 1
    ptype = spec.get("project_type", "unknown")
    data["stats"]["favorite_type"][ptype] = data["stats"]["favorite_type"].get(ptype, 0) + 1
    _save(data)
    print(f"  [Memory] Project saved ({data['stats']['total_generated']} total generated)")

def get_context_hint(request: str) -> str:
    """Get relevant context from past projects to improve generation."""
    data = _load()
    projects = data.get("projects", [])
    if not projects:
        return ""
    
    # Find similar past projects
    request_lower = request.lower()
    similar = []
    for p in projects[-10:]:  # Last 10 projects
        if any(word in request_lower for word in p.get("request", "").lower().split()):
            similar.append(p)
    
    total = data["stats"].get("total_generated", 0)
    hints = [f"[Engine has generated {total} apps total]"]
    
    if similar:
        hints.append(f"Similar past projects: {', '.join(p['name'] for p in similar[:3])}")
    
    # Add learned fixes
    fixes = data.get("learned_fixes", [])
    if fixes:
        hints.append(f"Known issues to avoid: {'; '.join(f['issue'] for f in fixes[-3:])}")
    
    return "\n".join(hints) if hints else ""

def learn_fix(issue: str, fix: str, file_type: str):
    """Record a fix so engine avoids the same issue next time."""
    data = _load()
    data["learned_fixes"].append({
        "issue": issue,
        "fix": fix,
        "file_type": file_type,
        "timestamp": datetime.now().isoformat()
    })
    # Keep only last 50 fixes
    data["learned_fixes"] = data["learned_fixes"][-50:]
    _save(data)

def get_stats() -> dict:
    data = _load()
    return data.get("stats", {})

def get_recent_projects(n: int = 5) -> list:
    data = _load()
    return data.get("projects", [])[-n:]

def save_preference(key: str, value):
    data = _load()
    data["preferences"][key] = value
    _save(data)

def get_preference(key: str, default=None):
    data = _load()
    return data.get("preferences", {}).get(key, default)
