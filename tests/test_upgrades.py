"""
Tests for telemetry, the Docker sandbox, the eval harness and the MCP SDK server.
Everything runs offline via the ``fake/canned`` provider.
"""
import asyncio
import json
import os
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def fake_llm(monkeypatch):
    from core.ai import provider
    from eval import fake_llm as fl
    provider.set_fake_responder(fl.respond)
    monkeypatch.setenv("APEX_MODEL", "fake/canned")
    yield fl
    provider.set_fake_responder(None)


# ── telemetry ─────────────────────────────────────────────────────────────────
class TestTelemetry:
    def test_records_per_agent_through_pipeline(self, fake_llm, tmp_path):
        from core.memory.store import MemoryStore
        from core.orchestrator import Orchestrator
        orch = Orchestrator(on_event=lambda *a, **k: None, memory_store=MemoryStore(str(tmp_path / "m")))
        orch.generate_fullstack("app1", "todo api", str(tmp_path / "out"))
        s = orch.last_usage.summary()
        assert s["calls"] >= 7
        for agent in ("Planner", "Architect", "Coder", "Reviewer", "SelfHealer", "Debugger", "DocWriter"):
            assert s["by_agent"][agent]["calls"] >= 1, agent
        assert "unattributed" not in s["by_agent"]
        assert s["cost_usd"] == 0.0  # fake models are free
        mem = orch.memory.list_projects()
        assert mem[0]["name"] == "app1"

    def test_parallel_threads_attributed(self, fake_llm, tmp_path):
        """Planner and Architect run in threads; their calls must still be counted."""
        from core.memory.store import MemoryStore
        from core.orchestrator import Orchestrator
        orch = Orchestrator(on_event=lambda *a, **k: None, memory_store=MemoryStore(str(tmp_path / "m")))
        orch.generate_fullstack("app2", "x", str(tmp_path / "out"))
        by = orch.last_usage.summary()["by_agent"]
        assert by["Planner"]["calls"] == 1 and by["Architect"]["calls"] == 1

    def test_usage_from_provider_and_prices(self, monkeypatch):
        from core import telemetry
        monkeypatch.setenv("APEX_PRICES", json.dumps({"groq/x": {"input": 1.0, "output": 2.0}}))
        telemetry.reload_prices()
        t = telemetry.UsageTracker()
        with telemetry.track(t), telemetry.agent_scope("Coder"):
            telemetry.record("groq/x", 1_000_000, 500_000, 1.5)
            telemetry.record("unknown/model", 10, 10, 0.1)
        s = t.summary()
        assert s["by_agent"]["Coder"]["cost_usd"] is None  # one unknown price => unknown, not 0
        assert s["cost_usd"] is None
        t2 = telemetry.UsageTracker()
        with telemetry.track(t2):
            telemetry.record("groq/x", 1_000_000, 500_000, 1.5)
        assert t2.summary()["cost_usd"] == 2.0
        telemetry.reload_prices()

    def test_openai_usage_block_is_read(self, monkeypatch):
        from core import telemetry
        from core.ai.provider import LLMProvider

        class Resp:
            status_code = 200
            def raise_for_status(self): pass
            def json(self): return {"choices": [{"message": {"content": "hi"}}],
                                    "usage": {"prompt_tokens": 11, "completion_tokens": 7}}

        p = LLMProvider("groq/llama-3.3-70b")
        monkeypatch.setattr(p._session, "post", lambda *a, **k: Resp())
        monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
        t = telemetry.UsageTracker()
        with telemetry.track(t):
            assert p.complete([{"role": "user", "content": "x"}]) == "hi"
        rec = t.records[0]
        assert (rec.prompt_tokens, rec.completion_tokens, rec.estimated) == (11, 7, False)

    def test_byok_overrides_are_scoped(self, monkeypatch):
        from core.ai.provider import _key, api_keys, byok_active
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        assert _key("GROQ_API_KEY") == "" and not byok_active()
        with api_keys(GROQ_API_KEY="gsk_visitor"):
            assert _key("GROQ_API_KEY") == "gsk_visitor" and byok_active()
        assert _key("GROQ_API_KEY") == "" and "GROQ_API_KEY" not in os.environ


# ── sandbox ───────────────────────────────────────────────────────────────────
def _docker_image():
    from core.execution.sandbox import docker_available
    if not docker_available():
        return None
    img = os.environ.get("APEX_SANDBOX_IMAGE", "python:3.12-slim")
    import subprocess
    if subprocess.run(["docker", "image", "inspect", img], capture_output=True).returncode != 0:
        if subprocess.run(["docker", "pull", "-q", img], capture_output=True, timeout=300).returncode != 0:
            return None
    return img


needs_docker = pytest.mark.skipif(shutil.which("docker") is None, reason="docker CLI not installed")


class TestSandboxUnit:
    def test_docker_argv_is_locked_down(self, tmp_path):
        from core.execution.sandbox import DockerSandbox
        argv = DockerSandbox(image="img").docker_argv(tmp_path, ["python3", "-V"], "n")
        joined = " ".join(argv)
        for flag in ("--network none", "--read-only", "--cap-drop ALL", "no-new-privileges",
                     "--pids-limit", "--memory", "--rm"):
            assert flag in joined, flag
        assert "/var/run/docker.sock" not in joined
        assert not any("API_KEY" in a for a in argv)
        assert argv[argv.index("img") + 1:] == ["python3", "-V"]

    def test_requirements_option_lines_are_stripped(self, tmp_path, monkeypatch):
        from core.execution import sandbox as sb
        captured = {}

        def fake_run(argv, cwd, **kw):
            captured["req"] = Path(argv[argv.index("-r") + 1]).read_text()
            captured["argv"] = argv
            from core.security import ProcResult
            return ProcResult("", 0, 0.0)

        monkeypatch.setattr(sb, "run_argv", fake_run)
        (tmp_path / "requirements.txt").write_text(
            "flask>=3\n--index-url http://evil/simple\n-e .\ngit+https://x/y.git\nevil @ file:///etc\n../local\nrequests # c\n")
        sb.DockerSandbox().install_python_deps(tmp_path)
        lines = captured["req"].split()
        assert lines == ["flask>=3", "requests", "pytest"]
        assert "--only-binary=:all:" in captured["argv"]

    def test_disabled_without_env(self, monkeypatch):
        from core.execution.sandbox import sandbox_enabled
        monkeypatch.delenv("APEX_SANDBOX", raising=False)
        assert sandbox_enabled() is False

    def test_executor_routes_through_sandbox(self, tmp_path):
        from core.execution.runner import Executor
        calls = []

        class FakeSbx:
            def run(self, workdir, cmd, **kw):
                calls.append((workdir, cmd))
                from core.security import ProcResult
                return ProcResult("ok", 0, 0.1)

        ex = Executor(str(tmp_path), sandbox=FakeSbx())  # no allow_execution needed
        assert ex.run(["python3", "-V"]).ok and calls


@needs_docker
class TestSandboxDocker:
    @pytest.fixture(autouse=True)
    def _img(self, monkeypatch):
        img = _docker_image()
        if img is None:
            pytest.skip("docker daemon or sandbox image unavailable")
        monkeypatch.setenv("APEX_SANDBOX_IMAGE", img)
        monkeypatch.setenv("APEX_SANDBOX_PIP", str(Path(sys.executable).parent / "pip"))

    def _project(self, root: Path, app: str, test: str = "", reqs: str = "") -> Path:
        b = root / "proj" / "backend"
        (b / "tests").mkdir(parents=True)
        (b / "app.py").write_text(app)
        if test:
            (b / "tests" / "test_app.py").write_text(test)
        (b / "requirements.txt").write_text(reqs)
        return root / "proj"

    def test_passing_project(self, tmp_path):
        from core.execution.sandbox import DockerSandbox
        p = self._project(tmp_path, "def add(a, b):\n    return a + b\n",
                          "import sys, os\nsys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))\n"
                          "from app import add\n\ndef test_add():\n    assert add(1, 2) == 3\n")
        rep = DockerSandbox().smoke_test(p)
        assert rep.ok, rep.failure_log()
        assert rep.tests_passed == 1 and rep.import_ok

    def test_network_is_off_and_failures_reported(self, tmp_path):
        from core.execution.sandbox import DockerSandbox
        test = ("import socket\n\ndef test_net():\n"
                "    socket.create_connection(('1.1.1.1', 80), timeout=2)\n")
        p = self._project(tmp_path, "x = 1\n", test)
        rep = DockerSandbox().smoke_test(p)
        assert rep.tests_failed == 1 and not rep.ok
        assert "test_net" in rep.failure_log()

    def test_timeout_kills_container(self, tmp_path):
        import subprocess, time
        from core.execution.sandbox import DockerSandbox
        sbx = DockerSandbox(timeout=3)
        t0 = time.time()
        r = sbx.run(tmp_path, ["python3", "-c", "import time; time.sleep(60)"])
        assert r.timed_out and time.time() - t0 < 30
        left = subprocess.run(["docker", "ps", "-q", "--filter", "name=apex-sbx-"], capture_output=True, text=True)
        assert left.stdout.strip() == ""

    def test_cannot_see_host_secrets(self, tmp_path, monkeypatch):
        from core.execution.sandbox import DockerSandbox
        monkeypatch.setenv("QWEN_API_KEY", "sk-must-not-leak-1234567890")
        r = DockerSandbox().run(tmp_path, ["python3", "-c", "import os; print(sorted(os.environ))"])
        assert "QWEN_API_KEY" not in r.stdout and r.returncode == 0

    def test_pipeline_heals_from_sandbox_failure(self, tmp_path, monkeypatch):
        """Executor finds a real failing test, SelfHealer gets the real output and fixes it."""
        from core.ai import provider
        from core.memory.store import MemoryStore
        from core.orchestrator import Orchestrator
        from eval import fake_llm
        seen = {}
        broken = fake_llm._APP.replace('return jsonify(error="title required (1-200 chars)"), 400',
                                       'return jsonify(error="bad"), 418')

        def respond(messages):
            system = messages[0]["content"]
            if "elite full-stack engineer" in system:
                return (fake_llm._block("backend/app.py", broken) + fake_llm._block("backend/tests/test_app.py", fake_llm._TEST)
                        + fake_llm._block("backend/requirements.txt", "flask>=3.0\n", "text"))
            if "self-healing" in system and "sandbox" in messages[1]["content"]:
                seen["log"] = messages[1]["content"]
                return fake_llm._block("backend/app.py", fake_llm._APP)
            return fake_llm.respond(messages)

        provider.set_fake_responder(respond)
        monkeypatch.setenv("APEX_MODEL", "fake/canned")
        monkeypatch.setenv("APEX_SANDBOX", "docker")
        from core.execution import sandbox as sb
        sb.docker_available.cache_clear()
        try:
            orch = Orchestrator(on_event=lambda *a, **k: None, memory_store=MemoryStore(str(tmp_path / "m")))
            orch.generate_fullstack("healme", "todo", str(tmp_path / "out"))
        finally:
            provider.set_fake_responder(None)
        assert "418" in seen["log"] or "test_validation" in seen["log"]
        assert orch.last_sandbox["first_attempt_passed"] is False
        assert orch.last_sandbox["passed"] is True and orch.last_sandbox["attempts"] == 2


# ── eval harness ──────────────────────────────────────────────────────────────
class TestEval:
    def test_scoring_flags_bad_code(self, tmp_path):
        pytest.importorskip("bandit")
        pytest.importorskip("ruff")
        from eval.fake_llm import _SINGLE_APP, _APP
        from eval.scoring import score_project
        bad, good = tmp_path / "bad", tmp_path / "good"
        bad.mkdir(); good.mkdir()
        (bad / "app.py").write_text(_SINGLE_APP)
        (good / "app.py").write_text(_APP)
        sb, sg = score_project(bad), score_project(good)
        assert sb["secrets"] >= 1 and sg["secrets"] == 0
        assert sb["bandit_high"] >= 1 and sg["bandit_high"] == 0   # debug=True (B201)
        assert sb["ruff_security"] > sg["ruff_security"]

    def test_getenv_fallback_secret_detected(self, tmp_path):
        from eval.scoring import secret_hits
        (tmp_path / "c.py").write_text('import os\nKEY = os.getenv("JWT_SECRET", "supersecretvalue")\nok = os.getenv("JWT_SECRET")\n')
        assert secret_hits(tmp_path) == 1

    def test_self_test_end_to_end(self, tmp_path):
        pytest.importorskip("bandit")
        from eval import run_eval
        rc = run_eval.main(["--self-test", "--limit", "2", "--run-id", "t", "--out", str(tmp_path)])
        assert rc == 0
        s = json.loads((tmp_path / "t" / "summary.json").read_text())
        assert s["n_tasks"] == 2 and s["errors"] == 0 and s["meta"]["self_test"]
        assert s["metrics"]["secrets"]["paired"]["society_wins"] == 2
        assert "SELF-TEST" in (tmp_path / "t" / "summary.md").read_text()
        # resume: re-running the same id does no new generation
        rows_before = (tmp_path / "t" / "results.jsonl").read_text().count("\n")
        run_eval.main(["--self-test", "--limit", "2", "--run-id", "t", "--out", str(tmp_path)])
        assert (tmp_path / "t" / "results.jsonl").read_text().count("\n") == rows_before

    def test_bootstrap_ci(self):
        from eval.run_eval import bootstrap_ci
        lo, hi = bootstrap_ci([1.0, 2.0, 3.0, 4.0])
        assert 1.0 <= lo <= 2.5 <= hi <= 4.0

    def test_tasks_file(self):
        tasks = json.loads((ROOT / "eval" / "tasks.json").read_text())
        assert len(tasks) == 30 and len({t["id"] for t in tasks}) == 30


# ── MCP SDK server ────────────────────────────────────────────────────────────
mcp_mod = pytest.importorskip("mcp")


def _session_call(server, coro_fn):
    from mcp.shared.memory import create_connected_server_and_client_session

    async def go():
        async with create_connected_server_and_client_session(server._mcp_server) as client:
            return await coro_fn(client)
    return asyncio.run(go())


class TestMcpSdk:
    def test_lists_tools_and_resource(self):
        import apex_mcp
        server = apex_mcp.build_server()

        async def f(c):
            tools = await c.list_tools()
            res = await c.read_resource("apex://agents")
            return [t.name for t in tools.tools], res
        names, res = _session_call(server, f)
        assert set(names) == {"plan_project", "design_architecture", "generate_code", "review_code",
                              "heal_code", "debug_error", "write_documentation", "generate_project"}
        roster = json.loads(res.contents[0].text)
        assert roster["count"] == 9

    def test_review_and_generate_project(self, fake_llm, tmp_path, monkeypatch):
        import apex_mcp
        monkeypatch.setenv("APEX_MCP_OUTPUT_DIR", str(tmp_path / "projects"))
        apex_mcp._agents = None
        server = apex_mcp.build_server()

        async def f(c):
            r1 = await c.call_tool("review_code", {"code": "print(1)"})
            r2 = await c.call_tool("generate_project", {"request": "todo api", "name": "demo"})
            r3 = await c.call_tool("generate_project", {"request": "x", "name": "../evil"})
            r4 = await c.call_tool("heal_code", {"files": {"a.py": "x"}, "issues": ["bug"]})
            return r1, r2, r3, r4
        r1, r2, r3, r4 = _session_call(server, f)
        review = json.loads(r1.content[0].text)
        assert review["verdict"] == "approved" and review["score"] == 92
        proj = json.loads(r2.content[0].text)
        assert Path(proj["path"]).is_relative_to(tmp_path / "projects")
        assert "backend/app.py" in proj["files"] and proj["usage"]["calls"] >= 7
        assert r3.isError and not (tmp_path / "evil").exists()
        assert not r4.isError
        apex_mcp._agents = None

    def test_http_refuses_public_bind_without_token(self, monkeypatch):
        import apex_mcp
        monkeypatch.delenv("APEX_API_TOKEN", raising=False)
        assert apex_mcp.main(["--http", "--host", "0.0.0.0"]) == 2

    def test_http_bearer_gate(self):
        pytest.importorskip("httpx")
        from starlette.testclient import TestClient
        import apex_mcp
        app = apex_mcp._bearer_wrap(apex_mcp.build_server().streamable_http_app(), "s3cret")
        c = TestClient(app, base_url="http://127.0.0.1:8002")
        assert c.post("/mcp", json={}).status_code == 401
        assert c.post("/mcp", json={}, headers={"authorization": "Bearer wrong"}).status_code == 401

    def test_rest_adapter_fixes(self):
        from core.agent_tools import adapt_inputs
        h = adapt_inputs("heal_code", {"code": "x=1", "issues": ["a", "b"]})
        assert h == {"files": {"code.txt": "x=1"}, "error": "a\nb"}
        d = adapt_inputs("write_documentation", {"code": "c", "name": "n"})
        assert d["request"] == "n"


# ── public demo / BYOK ────────────────────────────────────────────────────────
@pytest.fixture
def demo_client(monkeypatch, tmp_path):
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient
    from core.web_security import get_settings
    monkeypatch.setenv("APEX_PUBLIC_DEMO", "1")
    monkeypatch.setenv("APEX_ALLOWED_HOSTS", "localhost,.hf.space")
    monkeypatch.setenv("APEX_ALLOWED_ORIGINS", "https://*.hf.space")
    monkeypatch.setenv("APEX_FRAME_ANCESTORS", "https://huggingface.co")
    monkeypatch.setenv("APEX_RUNS_PER_HOUR", "2")
    get_settings.cache_clear()
    import server
    monkeypatch.setattr(server, "RUNS_DIR", (tmp_path / "runs").resolve())
    monkeypatch.setattr(server, "_rate", server.RateLimiter())
    server.sessions.clear()
    yield server, TestClient(server.app, base_url="http://mahak867-apex.hf.space")
    get_settings.cache_clear()


class TestPublicDemo:
    def test_refuses_to_start_with_server_keys(self, monkeypatch):
        from core.web_security import assert_safe_bind, get_settings
        monkeypatch.setenv("APEX_PUBLIC_DEMO", "1")
        monkeypatch.setenv("GROQ_API_KEY", "gsk_owner_key_should_not_be_here")
        get_settings.cache_clear()
        with pytest.raises(SystemExit):
            assert_safe_bind("0.0.0.0")
        monkeypatch.delenv("GROQ_API_KEY")
        get_settings.cache_clear()
        assert_safe_bind("0.0.0.0")  # no token needed: nothing to spend

    def test_hf_hosts_origins_and_framing(self, demo_client):
        _, c = demo_client
        r = c.get("/api/health", headers={"origin": "https://mahak867-apex.hf.space"})
        assert r.status_code == 200 and r.json()["public_demo"] is True
        assert "x-frame-options" not in r.headers
        assert "frame-ancestors 'self' https://huggingface.co" in r.headers["content-security-policy"]
        assert c.get("/api/health", headers={"origin": "https://evil.example"}).status_code == 403
        assert c.get("/api/health", headers={"host": "evil.example"}).status_code == 403

    def test_sessions_memory_and_tools_locked(self, demo_client):
        _, c = demo_client
        assert c.get("/api/sessions").status_code == 403
        assert c.get("/api/memory/stats").json()["projects"] == []
        assert c.post("/mcp/tools/plan_project", json={"request": "x"}).status_code == 403

    def test_run_requires_key_or_replay(self, demo_client, monkeypatch):
        server, c = demo_client
        started = []
        monkeypatch.setattr(server, "_start_job", lambda fn, sid, task, byok: started.append(byok) or True)
        with c.websocket_connect("ws://mahak867-apex.hf.space/ws") as ws:
            ws.send_text(json.dumps({"action": "run", "task": "x"}))
            assert "own key" in json.loads(ws.receive_text())["msg"]
            ws.send_text(json.dumps({"action": "run", "task": "x", "api_key": "short"}))
            assert "format" in json.loads(ws.receive_text())["msg"]
            ws.send_text(json.dumps({"action": "run", "task": "x", "mode": "replay"}))
            assert json.loads(ws.receive_text())["type"] == "session_created"
            key = "gsk_" + "a" * 40
            ws.send_text(json.dumps({"action": "run", "task": "x", "api_key": key, "provider": "groq"}))
            assert json.loads(ws.receive_text())["type"] == "session_created"
            ws.send_text(json.dumps({"action": "list_sessions"}))
            assert json.loads(ws.receive_text())["sessions"] == []
        assert started[0] == {"mode": "replay"} and started[1]["key"] == key
        assert all(key not in json.dumps(s) for s in server.sessions.values())  # key never stored

    def test_rate_limit_per_ip(self, demo_client, monkeypatch):
        server, c = demo_client
        monkeypatch.setattr(server, "_start_job", lambda *a: True)
        key = "gsk_" + "b" * 40
        msgs = []
        with c.websocket_connect("ws://mahak867-apex.hf.space/ws") as ws:
            for _ in range(3):
                ws.send_text(json.dumps({"action": "run", "task": "x", "api_key": key}))
                msgs.append(json.loads(ws.receive_text()))
        assert [m["type"] for m in msgs] == ["session_created", "session_created", "error"]

    def test_replay_run_end_to_end(self, demo_client, monkeypatch):
        """A no-key replay goes through the real 9-agent pipeline with canned outputs."""
        server, _ = demo_client
        monkeypatch.setenv("APEX_REPLAY_DELAY", "0")
        server._install_replay_llm()
        events = []
        monkeypatch.setattr(server, "sync_emit", lambda sid, a, st, m, extra=None: events.append((a, st, m, extra)))
        sid = server._new_session("todo api", "run")
        server._run_society(sid, "todo api", {"mode": "replay"})
        assert server.sessions[sid]["status"] == "done" and server.sessions[sid]["replay"] is True
        assert any("DEMO REPLAY" in e[2] for e in events)
        done = [e for e in events if e[0] == "System" and e[1] == "done" and e[3] and "usage" in e[3]]
        assert done and done[-1][3]["usage"]["calls"] >= 7
        from core.ai.provider import _model_override
        assert _model_override.get() == ""  # replay model did not leak out of the run

    def test_byok_key_scoped_to_run(self, demo_client, monkeypatch):
        server, _ = demo_client
        from core.ai import provider
        seen = {}

        def fake_inner(sid, task, replay=False):
            seen["key"] = provider._key("GROQ_API_KEY")
            seen["model"] = provider._model_override.get()
        monkeypatch.setattr(server, "_run_society_inner", fake_inner)
        server._run_society("s", "t", {"provider": "groq", "key": "gsk_" + "c" * 40})
        assert seen == {"key": "gsk_" + "c" * 40, "model": "groq/llama-3.3-70b"}
        assert provider._key("GROQ_API_KEY") == ""
