"""
APEX v3 — Test Suite
Run: python -m pytest tests/ -v
"""
import pytest, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


# ── Provider tests ─────────────────────────────────────────────────────────────
class TestProvider:
    def test_model_catalogue_complete(self):
        from core.ai.provider import MODELS, DEFAULT_CASCADE, CODING_CASCADE, REASONING_CASCADE
        for model in DEFAULT_CASCADE + CODING_CASCADE + REASONING_CASCADE:
            assert model in MODELS, f"{model} missing from MODELS"

    def test_cascade_resolution(self):
        from core.ai.provider import LLMProvider
        p = LLMProvider("auto")
        cascade = p._resolve_cascade()
        assert len(cascade) >= 3

    def test_coding_cascade(self):
        from core.ai.provider import LLMProvider
        p = LLMProvider("coding")
        c = p._resolve_cascade()
        assert len(c) >= 2

    def test_specific_model(self):
        from core.ai.provider import LLMProvider
        p = LLMProvider("groq/llama-3.3-70b")
        assert p._resolve_cascade() == ["groq/llama-3.3-70b"]


# ── Agent tests ────────────────────────────────────────────────────────────────
class TestAgents:
    def test_planner_message_format(self):
        from core.agents.base import PlannerAgent
        a = PlannerAgent()
        msgs = a._messages("system", "user")
        assert msgs[0]["role"] == "system"
        assert msgs[1]["role"] == "user"

    def test_parse_files_code_block(self):
        from core.agents.base import CoderAgent
        agent = CoderAgent()
        text = """
```python
# file: main.py
print("hello")
```
```typescript
# file: src/app.ts
export const x = 1;
```
"""
        files = agent._parse_files(text)
        assert "main.py" in files
        assert "src/app.ts" in files
        assert 'print("hello")' in files["main.py"]

    def test_parse_files_header_format(self):
        from core.agents.base import CoderAgent
        agent = CoderAgent()
        text = """
### backend/server.py
```python
from flask import Flask
app = Flask(__name__)
```
"""
        files = agent._parse_files(text)
        assert "backend/server.py" in files

    def test_agent_result_fields(self):
        from core.agents.base import AgentResult
        r = AgentResult(agent="Coder", output="code", files={"a.py": "x=1"})
        assert r.success is True
        assert r.error == ""
        assert "a.py" in r.files


# ── Memory tests ───────────────────────────────────────────────────────────────
class TestMemory:
    def test_project_memory_id(self):
        from core.memory.store import ProjectMemory
        m = ProjectMemory(name="test_proj", request="build a blog")
        assert len(m.id) == 8

    def test_project_memory_events(self):
        from core.memory.store import ProjectMemory
        m = ProjectMemory(name="test", request="req")
        m.add_event("Coder", "done", "10 files")
        assert len(m.history) == 1
        assert m.history[0]["agent"] == "Coder"

    def test_memory_store_save_load(self, tmp_path):
        from core.memory.store import MemoryStore, ProjectMemory
        store = MemoryStore(str(tmp_path))
        mem   = ProjectMemory(name="proj", request="build todo app")
        mem.update_files({"index.py": "print('hi')"})
        store.save(mem)
        loaded = store.load(mem.id)
        assert loaded is not None
        assert loaded.name == "proj"
        assert "index.py" in loaded.files

    def test_memory_search(self, tmp_path):
        from core.memory.store import MemoryStore, ProjectMemory
        store = MemoryStore(str(tmp_path))
        m1 = ProjectMemory(name="todo_app",  request="build todo app with React")
        m2 = ProjectMemory(name="blog_site", request="build blog with Next.js")
        store.save(m1)
        store.save(m2)
        results = store.search("todo")
        assert any("todo" in r["name"] for r in results)

    def test_memory_delete(self, tmp_path):
        from core.memory.store import MemoryStore, ProjectMemory
        store = MemoryStore(str(tmp_path))
        mem   = ProjectMemory(name="temp", request="temp project")
        store.save(mem)
        assert store.load(mem.id) is not None
        store.delete(mem.id)
        assert store.load(mem.id) is None


# ── Orchestrator tests ─────────────────────────────────────────────────────────
class TestOrchestrator:
    def test_dry_run(self, tmp_path):
        from core.orchestrator import Orchestrator
        events = []
        orch = Orchestrator(dry_run=True, on_event=lambda a,s,m: events.append((a,s,m)))
        path = orch.generate_fullstack("test_app", "a todo app", str(tmp_path))
        assert any(a == "Planner" for a, _, _ in events)
        assert any(a == "Coder" for a, _, _ in events)

    def test_dry_run_creates_dir(self, tmp_path):
        from core.orchestrator import Orchestrator
        orch = Orchestrator(dry_run=True)
        path = orch.generate_fullstack("my_test_app", "a simple app", str(tmp_path))
        import os
        assert os.path.exists(path)


# ── Executor tests ─────────────────────────────────────────────────────────────
class TestExecutor:
    def test_run_simple_command(self, tmp_path):
        from core.execution.runner import Executor
        ex = Executor(str(tmp_path))
        r  = ex.run("echo hello")
        assert r.ok
        assert "hello" in r.stdout

    def test_run_failing_command(self, tmp_path):
        from core.execution.runner import Executor
        ex = Executor(str(tmp_path))
        r  = ex.run("exit 1")
        assert not r.ok

    def test_run_python_file(self, tmp_path):
        from core.execution.runner import Executor
        script = tmp_path / "hello.py"
        script.write_text('print("apex works")')
        ex = Executor(str(tmp_path))
        r  = ex.run_file("hello.py")
        assert r.ok
        assert "apex works" in r.stdout

    def test_install_no_deps_file(self, tmp_path):
        from core.execution.runner import Executor
        ex = Executor(str(tmp_path))
        r  = ex.install_deps()
        assert "No deps" in r.stdout
