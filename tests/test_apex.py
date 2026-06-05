"""
APEX v3 — Full test suite (no API keys required, no network calls)
Run: python -m pytest tests/ -v
"""
import pytest, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


# ── Provider ───────────────────────────────────────────────────────────────────
class TestProvider:
    def test_model_catalogue_has_free_models(self):
        from core.ai.provider import FREE_MODELS
        assert len(FREE_MODELS) >= 4

    def test_all_cascades_are_free_only(self):
        from core.ai.provider import DEFAULT_CASCADE, CODING_CASCADE, REASONING_CASCADE, MODELS
        for cascade in [DEFAULT_CASCADE, CODING_CASCADE, REASONING_CASCADE]:
            for model in cascade:
                assert MODELS[model]["free"] is True, f"{model} in cascade must be free"

    def test_paid_models_marked_correctly(self):
        from core.ai.provider import PAID_MODELS, MODELS
        for m in PAID_MODELS:
            assert MODELS[m]["free"] is False

    def test_default_cascade_resolution(self):
        from core.ai.provider import LLMProvider
        p = LLMProvider("auto")
        cascade = p._resolve_cascade()
        assert len(cascade) >= 2
        assert cascade[0].startswith("qwen/")

    def test_coding_cascade_starts_with_groq(self):
        from core.ai.provider import LLMProvider
        p = LLMProvider("coding")
        assert p._resolve_cascade()[0].startswith("qwen/")

    def test_reasoning_cascade_starts_with_groq(self):
        from core.ai.provider import LLMProvider
        p = LLMProvider("reasoning")
        assert p._resolve_cascade()[0].startswith("qwen/")

    def test_specific_model_cascade(self):
        from core.ai.provider import LLMProvider
        p = LLMProvider("groq/llama-3.3-70b")
        assert p._resolve_cascade() == ["groq/llama-3.3-70b"]

    def test_no_paid_in_cascade_without_keys(self):
        """Without any paid API keys, cascade must contain only free models."""
        import os
        from core.ai.provider import LLMProvider, MODELS
        env_backup = {}
        for k in ["OPENROUTER_API_KEY", "TOGETHER_API_KEY", "MISTRAL_API_KEY"]:
            env_backup[k] = os.environ.pop(k, None)
        try:
            p = LLMProvider("auto")
            for m in p._resolve_cascade():
                assert MODELS[m]["free"] is True, f"{m} should not appear without paid key"
        finally:
            for k, v in env_backup.items():
                if v is not None:
                    os.environ[k] = v


# ── Agents ─────────────────────────────────────────────────────────────────────
class TestAgents:
    def test_messages_format(self):
        from core.agents.base import PlannerAgent
        a = PlannerAgent()
        msgs = a._messages("sys", "user")
        assert msgs[0]["role"] == "system"
        assert msgs[1]["role"] == "user"
        assert msgs[0]["content"] == "sys"

    def test_parse_files_code_block(self):
        from core.agents.base import CoderAgent
        text = '```python\n# file: main.py\nprint("hi")\n```'
        files = CoderAgent()._parse_files(text)
        assert "main.py" in files

    def test_parse_files_multiple(self):
        from core.agents.base import CoderAgent
        text = (
            '```typescript\n# file: src/app.ts\nexport const x = 1;\n```\n'
            '```python\n# file: server.py\nfrom flask import Flask\n```'
        )
        files = CoderAgent()._parse_files(text)
        assert "src/app.ts" in files
        assert "server.py" in files

    def test_parse_files_header_format(self):
        from core.agents.base import CoderAgent
        text = "### backend/server.py\n```python\napp = 1\n```"
        files = CoderAgent()._parse_files(text)
        assert "backend/server.py" in files

    def test_agent_result_defaults(self):
        from core.agents.base import AgentResult
        r = AgentResult(agent="Coder", output="x")
        assert r.success is True
        assert r.error == ""
        assert r.files == {}
        assert r.duration == 0.0

    def test_agent_result_with_files(self):
        from core.agents.base import AgentResult
        r = AgentResult(agent="Coder", output="x", files={"a.py": "x=1"})
        assert "a.py" in r.files

    def test_all_agents_instantiate(self):
        from core.agents.base import (
            PlannerAgent, ArchitectAgent, CoderAgent,
            ReviewerAgent, DebuggerAgent, SelfHealerAgent, DocWriterAgent,
        )
        for AgentClass in [PlannerAgent, ArchitectAgent, CoderAgent,
                           ReviewerAgent, DebuggerAgent, SelfHealerAgent, DocWriterAgent]:
            a = AgentClass()
            assert a.name != ""
            assert a.model_profile in ("auto", "coding", "reasoning")


# ── Memory ─────────────────────────────────────────────────────────────────────
class TestMemory:
    def test_project_id_is_8_chars(self):
        from core.memory.store import ProjectMemory
        m = ProjectMemory(name="test", request="build a blog")
        assert len(m.id) == 8

    def test_two_projects_have_different_ids(self):
        from core.memory.store import ProjectMemory
        import time
        m1 = ProjectMemory(name="app1", request="req1")
        time.sleep(0.01)
        m2 = ProjectMemory(name="app2", request="req2")
        assert m1.id != m2.id

    def test_add_event(self):
        from core.memory.store import ProjectMemory
        m = ProjectMemory(name="t", request="r")
        m.add_event("Coder", "done", "10 files")
        assert len(m.history) == 1
        assert m.history[0]["agent"] == "Coder"
        assert m.history[0]["action"] == "done"

    def test_update_files(self):
        from core.memory.store import ProjectMemory
        m = ProjectMemory(name="t", request="r")
        m.update_files({"index.py": "print('hi')"})
        assert "index.py" in m.files
        assert len(m.history) == 1

    def test_save_and_load(self, tmp_path):
        from core.memory.store import MemoryStore, ProjectMemory
        store = MemoryStore(str(tmp_path))
        mem   = ProjectMemory(name="myapp", request="build todo")
        mem.update_files({"main.py": "x=1"})
        store.save(mem)
        loaded = store.load(mem.id)
        assert loaded is not None
        assert loaded.name == "myapp"
        assert "main.py" in loaded.files

    def test_list_projects(self, tmp_path):
        from core.memory.store import MemoryStore, ProjectMemory
        store = MemoryStore(str(tmp_path))
        store.save(ProjectMemory(name="app1", request="req1"))
        store.save(ProjectMemory(name="app2", request="req2"))
        projects = store.list_projects()
        assert len(projects) == 2

    def test_search(self, tmp_path):
        from core.memory.store import MemoryStore, ProjectMemory
        store = MemoryStore(str(tmp_path))
        store.save(ProjectMemory(name="todo_app", request="build todo with React"))
        store.save(ProjectMemory(name="blog",     request="build blog with Next.js"))
        assert any("todo" in p["name"] for p in store.search("todo"))

    def test_delete(self, tmp_path):
        from core.memory.store import MemoryStore, ProjectMemory
        store = MemoryStore(str(tmp_path))
        mem   = ProjectMemory(name="temp", request="temp")
        store.save(mem)
        store.delete(mem.id)
        assert store.load(mem.id) is None

    def test_load_nonexistent_returns_none(self, tmp_path):
        from core.memory.store import MemoryStore
        store = MemoryStore(str(tmp_path))
        assert store.load("nonexistent") is None


# ── Orchestrator ────────────────────────────────────────────────────────────────
class TestOrchestrator:
    def test_dry_run_emits_planner_event(self, tmp_path):
        from core.orchestrator import Orchestrator
        events = []
        orch = Orchestrator(dry_run=True, on_event=lambda a, s, m: events.append(a))
        orch.generate_fullstack("testapp", "a todo app", str(tmp_path))
        assert "Planner" in events

    def test_dry_run_emits_coder_event(self, tmp_path):
        from core.orchestrator import Orchestrator
        events = []
        orch = Orchestrator(dry_run=True, on_event=lambda a, s, m: events.append(a))
        orch.generate_fullstack("testapp", "a todo app", str(tmp_path))
        assert "Coder" in events

    def test_dry_run_creates_output_dir(self, tmp_path):
        from core.orchestrator import Orchestrator
        import os
        orch = Orchestrator(dry_run=True)
        path = orch.generate_fullstack("myapp", "simple app", str(tmp_path))
        assert os.path.exists(path)

    def test_dry_run_returns_string_path(self, tmp_path):
        from core.orchestrator import Orchestrator
        orch = Orchestrator(dry_run=True)
        result = orch.generate_fullstack("app", "test", str(tmp_path))
        assert isinstance(result, str)

    def test_dry_run_saves_to_memory(self, tmp_path):
        from core.orchestrator import Orchestrator
        from core.memory.store import MemoryStore
        orch = Orchestrator(dry_run=True)
        orch.generate_fullstack("memtest", "a test app", str(tmp_path))
        store = MemoryStore()
        projects = store.list_projects()
        assert any(p["name"] == "memtest" for p in projects)


# ── Executor ────────────────────────────────────────────────────────────────────
class TestExecutor:
    def test_echo_command_passes(self, tmp_path):
        from core.execution.runner import Executor
        r = Executor(str(tmp_path)).run("echo hello")
        assert r.ok
        assert "hello" in r.stdout

    def test_failing_command(self, tmp_path):
        from core.execution.runner import Executor
        r = Executor(str(tmp_path)).run("exit 1")
        assert not r.ok

    def test_run_python_file(self, tmp_path):
        from core.execution.runner import Executor
        (tmp_path / "hello.py").write_text('print("apex v3")')
        r = Executor(str(tmp_path)).run_file("hello.py")
        assert r.ok
        assert "apex v3" in r.stdout

    def test_no_deps_file(self, tmp_path):
        from core.execution.runner import Executor
        r = Executor(str(tmp_path)).install_deps()
        assert "No deps" in r.stdout

    def test_exec_result_ok_property(self, tmp_path):
        from core.execution.runner import Executor
        r = Executor(str(tmp_path)).run("echo ok")
        assert r.ok is True

    def test_exec_result_duration(self, tmp_path):
        from core.execution.runner import Executor
        r = Executor(str(tmp_path)).run("echo hi")
        assert r.duration >= 0
