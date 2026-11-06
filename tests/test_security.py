"""
Security-boundary regression tests (no network, no API keys, no real LLM calls).
Each class maps to a finding in the improvement report.
"""
import json
import os
import stat
import sys
import time

import pytest

IS_WIN = os.name == "nt"


def _alive(pid: int) -> bool:
    """True if pid is running (zombies awaiting reaping count as dead)."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    try:
        with open(f"/proc/{pid}/status") as f:
            for line in f:
                if line.startswith("State:"):
                    return "Z" not in line.split()[1]
    except OSError:
        pass
    return True


# ── F1: path containment ───────────────────────────────────────────────────────
class TestSafeJoin:
    @pytest.mark.parametrize("bad", [
        "../escape.txt", "a/../../escape.txt", "..", "/etc/passwd", "\\\\server\\share\\x",
        "C:\\Windows\\x", "C:/x", "a\\..\\..\\x", "", "   ", "a\x00b", ".git/hooks/pre-commit",
        "src/.git/config", "CON", "nul.txt", "x" * 300,
    ])
    def test_rejects_unsafe(self, tmp_path, bad):
        from core.security import UnsafePathError, safe_join
        with pytest.raises(UnsafePathError):
            safe_join(tmp_path, bad)

    def test_allows_nested(self, tmp_path):
        from core.security import safe_join
        p = safe_join(tmp_path, "backend/app/./main.py")
        assert p == (tmp_path / "backend" / "app" / "main.py").resolve()

    def test_allows_dotfiles(self, tmp_path):
        from core.security import safe_join
        safe_join(tmp_path, ".gitignore")
        safe_join(tmp_path, ".github/workflows/ci.yml")
        safe_join(tmp_path, ".env.example")

    def test_sibling_prefix_is_outside(self, tmp_path):
        """The exact startswith() bug from the report: /x/project vs /x/project-other."""
        from core.security import UnsafePathError, safe_join
        from core.file_engine import FileEngine
        root = tmp_path / "project"
        root.mkdir()
        (tmp_path / "project-other").mkdir()
        # Old check: str(target).startswith(str(root)) is True for project-other.
        assert str(tmp_path / "project-other" / "x").startswith(str(root))
        with pytest.raises(UnsafePathError):
            safe_join(root, "../project-other/x")
        with pytest.raises(UnsafePathError):
            FileEngine()._sanitize_path(str(root), "../project-other/x")

    @pytest.mark.skipif(IS_WIN, reason="symlinks need privileges on Windows")
    def test_symlink_escape_rejected(self, tmp_path):
        from core.security import UnsafePathError, safe_write_text
        root = tmp_path / "root"
        outside = tmp_path / "outside"
        root.mkdir(); outside.mkdir()
        (root / "out").symlink_to(outside, target_is_directory=True)
        with pytest.raises(UnsafePathError):
            safe_write_text(root, "out/sentinel.txt", "pwned")
        assert not (outside / "sentinel.txt").exists()

    @pytest.mark.skipif(IS_WIN, reason="symlinks need privileges on Windows")
    def test_final_symlink_replaced_not_followed(self, tmp_path):
        from core.security import UnsafePathError, safe_write_text
        root = tmp_path / "root"; root.mkdir()
        target = tmp_path / "victim.txt"; target.write_text("original")
        (root / "f.txt").symlink_to(target)
        with pytest.raises(UnsafePathError):
            safe_write_text(root, "f.txt", "pwned")
        assert target.read_text() == "original"

    def test_atomic_write_and_size_cap(self, tmp_path):
        from core.security import UnsafePathError, safe_write_text
        p = safe_write_text(tmp_path, "a/b.txt", "hello")
        assert p.read_text() == "hello"
        with pytest.raises(UnsafePathError):
            safe_write_text(tmp_path, "big.txt", "x" * 20, max_bytes=10)
        assert not [f for f in tmp_path.rglob(".apex-*")]  # no temp files left behind


class TestFileEngine:
    def test_batch_aborts_before_writing_anything(self, tmp_path):
        from core.file_engine import FileEngine, UnsafePathError
        with pytest.raises(UnsafePathError):
            FileEngine().write_files(str(tmp_path), [
                {"path": "ok.txt", "content": "fine"},
                {"path": "../escape.txt", "content": "bad"},
            ])
        assert not (tmp_path / "ok.txt").exists()
        assert not (tmp_path.parent / "escape.txt").exists()

    def test_writes_valid(self, tmp_path):
        from core.file_engine import FileEngine
        FileEngine().write_files(str(tmp_path), [{"path": "src/a.py", "content": "x=1"}])
        assert (tmp_path / "src" / "a.py").read_text() == "x=1"


class TestOrchestratorWrites:
    def test_model_paths_are_contained(self, tmp_path):
        """LLM-parsed filenames are untrusted (OWASP LLM05: improper output handling)."""
        from core.orchestrator import Orchestrator
        from core.memory.store import MemoryStore
        sentinel = tmp_path / "sentinel.txt"
        sentinel.write_text("untouched")
        orch = Orchestrator(dry_run=True, memory_store=MemoryStore(str(tmp_path / "mem")))
        out = tmp_path / "proj"
        rejected = orch._write_files(out, {
            "app.py": "ok", "../sentinel.txt": "pwned", str(sentinel): "pwned",
            ".git/hooks/post-checkout": "pwned",
        })
        assert (out / "app.py").read_text() == "ok"
        assert sentinel.read_text() == "untouched"
        assert len(rejected) == 3
        assert not (out / ".git").exists()

    def test_project_name_must_be_single_component(self, tmp_path):
        from core.orchestrator import Orchestrator
        from core.memory.store import MemoryStore
        from core.security import UnsafePathError
        orch = Orchestrator(dry_run=True, memory_store=MemoryStore(str(tmp_path / "mem")))
        with pytest.raises(UnsafePathError):
            orch.generate_fullstack("../evil", "x", str(tmp_path / "out"))


# ── X1 / X2: execution ─────────────────────────────────────────────────────────
class TestExecutor:
    def test_disabled_by_default(self, tmp_path):
        from core.execution.runner import Executor
        r = Executor(str(tmp_path)).run([sys.executable, "-c", "print(1)"])
        assert not r.ok and "disabled" in r.stderr

    def test_env_flag_enables(self, tmp_path, monkeypatch):
        from core.execution.runner import Executor
        monkeypatch.setenv("APEX_ALLOW_EXECUTION", "1")
        assert Executor(str(tmp_path)).run([sys.executable, "-c", "print(1)"]).ok

    def test_shell_metacharacters_are_inert(self, tmp_path):
        from core.execution.runner import Executor
        ex = Executor(str(tmp_path), allow_execution=True)
        r = ex.run(f'"{sys.executable}" -c "print(1)" ; touch pwned')
        assert not (tmp_path / "pwned").exists()
        r = ex.run([sys.executable, "-c", "import sys; print(sys.argv[1:])", "$(touch pwned2)", "`id`"])
        assert "$(touch pwned2)" in r.stdout
        assert not (tmp_path / "pwned2").exists()

    def test_child_env_has_no_secrets(self, tmp_path, monkeypatch):
        from core.execution.runner import Executor
        monkeypatch.setenv("QWEN_API_KEY", "sk-should-not-leak-123456789")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "nope")
        monkeypatch.setenv("GITHUB_TOKEN", "nope")
        r = Executor(str(tmp_path), allow_execution=True).run(
            [sys.executable, "-c", "import os, json; print(json.dumps(sorted(os.environ)))"])
        names = json.loads(r.stdout.strip().splitlines()[-1])
        assert "QWEN_API_KEY" not in names
        assert "AWS_SECRET_ACCESS_KEY" not in names
        assert "GITHUB_TOKEN" not in names
        assert "PATH" in names

    @pytest.mark.skipif(IS_WIN, reason="POSIX process groups")
    def test_timeout_kills_process_tree(self, tmp_path):
        from core.execution.runner import Executor
        script = tmp_path / "spawn.py"
        script.write_text(
            "import subprocess, sys, time\n"
            "p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
            "print(p.pid, flush=True)\n"
            "time.sleep(60)\n"
        )
        r = Executor(str(tmp_path), timeout=2, allow_execution=True).run([sys.executable, str(script)])
        assert r.timed_out
        grandchild = int(r.stdout.split()[0])
        time.sleep(0.5)
        assert not _alive(grandchild), "grandchild survived the timeout"

    def test_run_file_rejects_escape(self, tmp_path):
        from core.execution.runner import Executor
        r = Executor(str(tmp_path), allow_execution=True).run_file("../../etc/passwd")
        assert not r.ok

    def test_auto_run_requires_approval(self, tmp_path):
        from core.execution.auto_runner import auto_run
        from core.security import ExecutionDisabledError
        with pytest.raises(ExecutionDisabledError):
            auto_run(str(tmp_path))

    def test_deploy_requires_approval(self, tmp_path):
        from core.ai.deployer import deploy_to_railway
        from core.security import ExecutionDisabledError
        with pytest.raises(ExecutionDisabledError):
            deploy_to_railway(str(tmp_path))

    @pytest.mark.skipif(IS_WIN, reason="newline in filename")
    def test_render_yaml_name_sanitised(self, tmp_path):
        from core.ai.deployer import deploy_to_render
        proj = tmp_path / "evil\nname: x"
        proj.mkdir()
        deploy_to_render(str(proj))
        y = (proj / "render.yaml").read_text()
        assert "\nname: x" not in y


class TestAutoHeal:
    def test_error_text_cannot_pull_outside_files(self, tmp_path, monkeypatch):
        from core.execution import auto_heal
        outside = tmp_path / "secret.env"
        outside.write_text("API_KEY=xyz")
        proj = tmp_path / "proj"; proj.mkdir()
        (proj / "app.py").write_text("print(1)")
        healer = auto_heal.AutoHealPipeline.__new__(auto_heal.AutoHealPipeline)
        healer.project_dir = proj.resolve()
        files = healer._read_relevant_files(f"Error in app.py and ../secret.env and {outside} and /etc/passwd")
        assert list(files) == ["app.py"]


# ── tool registry ──────────────────────────────────────────────────────────────
class TestToolRegistry:
    def _reg(self, tmp_path, perms=None):
        from core.ai.tool_registry import ToolRegistry
        return ToolRegistry(str(tmp_path), perms or {"file.read", "file.write", "shell", "git", "git.write", "web"})

    def test_python_eval_cannot_escape(self, tmp_path):
        reg = self._reg(tmp_path)
        payload = "[c for c in ().__class__.__base__.__subclasses__() if c.__name__=='Popen'][0](['touch','pwned'])"
        out = reg.call("python_eval", code=payload)
        assert out.startswith("Error")
        assert not (tmp_path / "pwned").exists()
        assert reg.call("python_eval", code="[1, 2, {'a': 3}]") == "[1, 2, {'a': 3}]"

    def test_bash_has_no_shell(self, tmp_path):
        reg = self._reg(tmp_path)
        reg.call("bash", command=f'"{sys.executable}" -c "print(1)" ; touch pwned')
        assert not (tmp_path / "pwned").exists()

    def test_git_commit_message_not_interpreted(self, tmp_path):
        reg = self._reg(tmp_path)
        reg.call("git_commit", message='x"; touch pwned; echo "')
        assert not (tmp_path / "pwned").exists()

    def test_safe_path_sibling_prefix(self, tmp_path):
        from core.ai.tool_registry import ToolPermissionError
        root = tmp_path / "proj"; root.mkdir()
        (tmp_path / "proj-secrets").mkdir()
        (tmp_path / "proj-secrets" / "k").write_text("secret")
        reg = self._reg(root)
        with pytest.raises(ToolPermissionError):
            reg.call("read_file", path="../proj-secrets/k")

    def test_write_into_git_blocked(self, tmp_path):
        from core.ai.tool_registry import ToolPermissionError
        with pytest.raises(ToolPermissionError):
            self._reg(tmp_path).call("write_file", path=".git/hooks/pre-commit", content="x")

    @pytest.mark.parametrize("url", [
        "http://127.0.0.1:8000/", "http://localhost/", "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.1/", "http://[::1]/", "file:///etc/passwd", "gopher://example.com/",
        "http://user:pw@example.com/",
    ])
    def test_web_fetch_blocks_ssrf(self, tmp_path, url):
        out = self._reg(tmp_path).call("web_fetch", url=url)
        assert out.startswith("Fetch error")

    def test_permissions_enforced(self, tmp_path):
        from core.ai.tool_registry import ToolPermissionError
        with pytest.raises(ToolPermissionError):
            self._reg(tmp_path, {"file.read"}).call("bash", command="echo hi")


# ── O1: memory privacy / lifecycle ────────────────────────────────────────────
class TestMemoryStore:
    def test_ids_cannot_traverse(self, tmp_path):
        from core.memory.store import MemoryStore
        store = MemoryStore(str(tmp_path / "mem"))
        (tmp_path / "victim.json").write_text(json.dumps({"name": "x", "request": "y"}))
        assert store.load("../victim") is None
        assert store.delete("../victim") is False
        assert (tmp_path / "victim.json").exists()

    def test_secrets_redacted_and_contents_dropped(self, tmp_path):
        from core.memory.store import MemoryStore, ProjectMemory
        store = MemoryStore(str(tmp_path))
        m = ProjectMemory(name="a", request="build app, my key is sk-abcdefghijklmnopqrstuv1234")
        m.update_files({"main.py": "SECRET='hunter2hunter2'"})
        m.add_lesson("token: ghp_abcdefghijklmnopqrstuvwxyz0123")
        store.save(m)
        raw = (tmp_path / f"{m.id}.json").read_text()
        assert "sk-abcdefghijklmnopqrstuv1234" not in raw
        assert "ghp_abcdefghijklmnopqrstuvwxyz0123" not in raw
        assert "hunter2" not in raw
        assert "[REDACTED]" in raw

    @pytest.mark.skipif(IS_WIN, reason="POSIX permissions")
    def test_file_permissions(self, tmp_path):
        from core.memory.store import MemoryStore, ProjectMemory
        store = MemoryStore(str(tmp_path / "mem"))
        m = ProjectMemory(name="a", request="b")
        store.save(m)
        mode = stat.S_IMODE((tmp_path / "mem" / f"{m.id}.json").stat().st_mode)
        assert mode == 0o600
        assert stat.S_IMODE((tmp_path / "mem").stat().st_mode) == 0o700

    def test_retention_max_records(self, tmp_path):
        from core.memory.store import MemoryStore, ProjectMemory
        store = MemoryStore(str(tmp_path), max_records=3)
        for i in range(6):
            store.save(ProjectMemory(name=f"p{i}", request="r", created=1000.0 + i))
        assert len(store.list_projects()) == 3

    def test_retention_max_age(self, tmp_path):
        from core.memory.store import MemoryStore, ProjectMemory
        store = MemoryStore(str(tmp_path), max_age_days=1)
        m = ProjectMemory(name="old", request="r")
        store.save(m)
        old = time.time() - 3 * 86400
        os.utime(tmp_path / f"{m.id}.json", (old, old))
        assert store.prune() == 1

    def test_default_dir_respects_env(self, tmp_path, monkeypatch):
        from core.memory.store import MemoryStore
        monkeypatch.setenv("APEX_MEMORY_DIR", str(tmp_path / "custom"))
        assert MemoryStore().dir == tmp_path / "custom"

    def test_clear(self, tmp_path):
        from core.memory.store import MemoryStore, ProjectMemory
        store = MemoryStore(str(tmp_path))
        store.save(ProjectMemory(name="a", request="b"))
        assert store.clear() == 1 and store.list_projects() == []


class TestRedactAndUrls:
    def test_redact(self):
        from core.security import redact
        assert "[REDACTED]" in redact("api_key = abcdefghijkl")
        assert redact("plain text") == "plain text"

    def test_public_url_allowed_shape(self):
        from core.security import check_public_url
        with pytest.raises(ValueError):
            check_public_url("ftp://example.com")


# ── N1: server / MCP access control ───────────────────────────────────────────
@pytest.fixture
def client(monkeypatch, tmp_path):
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    monkeypatch.setenv("APEX_RUNS_DIR", str(tmp_path / "runs"))
    from fastapi.testclient import TestClient
    import server
    monkeypatch.setattr(server, "RUNS_DIR", (tmp_path / "runs").resolve())
    (tmp_path / "runs").mkdir()
    server.sessions.clear()
    return TestClient(server.app, base_url="http://localhost:8000")


def _token(monkeypatch, value="t0ken-for-tests"):
    from core.web_security import get_settings
    monkeypatch.setenv("APEX_API_TOKEN", value)
    get_settings.cache_clear()
    return value


class TestServer:
    def test_health_public_and_headers(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200
        assert r.headers["x-content-type-options"] == "nosniff"
        assert r.headers["x-frame-options"] == "DENY"
        assert "sessions" not in r.json()  # no info leak on the public route

    def test_dns_rebinding_host_rejected(self, client):
        r = client.get("/api/sessions", headers={"host": "attacker.example:8000"})
        assert r.status_code == 403

    def test_foreign_origin_rejected(self, client):
        r = client.get("/api/sessions", headers={"origin": "https://evil.example"})
        assert r.status_code == 403

    def test_cors_does_not_echo_foreign_origin(self, client):
        r = client.get("/api/health", headers={"origin": "http://localhost:8000"})
        assert r.headers.get("access-control-allow-origin") == "http://localhost:8000"

    def test_token_required_when_configured(self, client, monkeypatch):
        tok = _token(monkeypatch)
        assert client.get("/api/sessions").status_code == 401
        assert client.get("/mcp/tools").status_code == 401
        assert client.get("/api/sessions", headers={"authorization": "Bearer wrong"}).status_code == 401
        assert client.get("/api/sessions", headers={"authorization": f"Bearer {tok}"}).status_code == 200
        assert client.get("/api/health").status_code == 200

    def test_404s_are_real_404s(self, client):
        assert client.get("/api/sessions/nope").status_code == 404
        assert client.get("/api/sessions/nope/events").status_code == 404
        assert client.get("/api/sessions/nope/dialogue").status_code == 404

    def test_session_glob_injection(self, client, tmp_path):
        import server
        d = server.RUNS_DIR / "abcdef0123456789"
        d.mkdir(parents=True)
        (d / "secret.txt").write_text("x")
        for sid in ["*", "abcdef01*", "..", "%2e%2e"]:
            assert client.get(f"/api/sessions/{sid}/files").status_code == 404
            assert client.get(f"/api/sessions/{sid}/download").status_code == 404
        r = client.get("/api/sessions/abcdef0123456789/files")
        assert r.status_code == 200 and r.json()["file_count"] == 1

    @pytest.mark.skipif(IS_WIN, reason="symlinks")
    def test_download_skips_symlinks(self, client, tmp_path):
        import io, zipfile, server
        d = server.RUNS_DIR / "0123456789abcdef"
        d.mkdir(parents=True)
        (d / "ok.txt").write_text("ok")
        outside = tmp_path / "outside.txt"; outside.write_text("secret")
        (d / "leak.txt").symlink_to(outside)
        r = client.get("/api/sessions/0123456789abcdef/download")
        names = zipfile.ZipFile(io.BytesIO(r.content)).namelist()
        assert names == ["ok.txt"]

    def test_ws_requires_token(self, client, monkeypatch):
        from starlette.websockets import WebSocketDisconnect
        tok = _token(monkeypatch)
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("ws://localhost:8000/ws") as ws:
                ws.receive_text()
        with client.websocket_connect(f"ws://localhost:8000/ws?token={tok}") as ws:
            ws.send_text(json.dumps({"action": "ping"}))
            assert json.loads(ws.receive_text())["type"] == "pong"

    def test_ws_rejects_rebound_host(self, client):
        from starlette.websockets import WebSocketDisconnect
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("ws://attacker.example:8000/ws") as ws:
                ws.receive_text()

    def test_ws_rejects_foreign_origin(self, client):
        from starlette.websockets import WebSocketDisconnect
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("ws://localhost:8000/ws", headers={"origin": "https://evil.example"}) as ws:
                ws.receive_text()

    def test_ws_bad_json_and_caps(self, client, monkeypatch):
        import server
        started = []
        monkeypatch.setattr(server, "_start_job", lambda fn, sid, task, *a: started.append(task) or True)
        with client.websocket_connect("ws://localhost:8000/ws") as ws:
            ws.send_text("not json")
            assert json.loads(ws.receive_text())["msg"] == "invalid JSON"
            ws.send_text(json.dumps({"action": "benchmark", "task": "x" * 5000}))
            assert json.loads(ws.receive_text())["type"] == "session_created"
            ws.send_text("y" * 20000)
            assert json.loads(ws.receive_text())["msg"] == "message too large"
        assert len(started[0]) == 500

    def test_ws_busy_rejected(self, client, monkeypatch):
        import server
        monkeypatch.setattr(server, "_start_job", lambda *a: False)
        with client.websocket_connect("ws://localhost:8000/ws") as ws:
            ws.send_text(json.dumps({"action": "run", "task": "x"}))
            assert "busy" in json.loads(ws.receive_text())["msg"]

    def test_events_not_broadcast_to_other_clients(self, client, monkeypatch):
        import server
        monkeypatch.setattr(server, "_start_job", lambda *a: True)
        with client.websocket_connect("ws://localhost:8000/ws") as a, client.websocket_connect("ws://localhost:8000/ws"):
            a.send_text(json.dumps({"action": "run", "task": "secret project"}))
            sid = json.loads(a.receive_text())["session_id"]
            assert server.manager.subscribers[sid] and len(server.manager.subscribers[sid]) == 1

    def test_mcp_input_validation(self, client):
        r = client.post("/mcp/tools/plan_project", json={})
        assert r.status_code == 400
        r = client.post("/mcp/tools/plan_project", json={"request": 123})
        assert r.status_code == 400
        r = client.post("/mcp/tools/plan_project", json={"request": "x" * 30000})
        assert r.status_code == 400
        r = client.post("/mcp/tools/nope", json={"request": "x"})
        assert r.status_code == 400

    def test_mcp_static_benchmark_labelled(self, client):
        r = client.post("/mcp/tools/run_benchmark", json={"task": "x"})
        assert r.status_code == 200 and r.json()["static"] is True


class TestBindGuard:
    def test_public_bind_without_token_refused(self, monkeypatch):
        from core.web_security import assert_safe_bind, get_settings
        get_settings.cache_clear()
        with pytest.raises(SystemExit):
            assert_safe_bind("0.0.0.0")
        assert_safe_bind("127.0.0.1")

    def test_public_bind_with_token_ok(self, monkeypatch):
        from core.web_security import assert_safe_bind
        _token(monkeypatch)
        assert_safe_bind("0.0.0.0")

    def test_default_host_is_loopback(self):
        from core.web_security import get_settings
        assert get_settings().host == "127.0.0.1"


class TestMcpStandalone:
    def test_mcp_app_has_auth_and_no_wildcard_cors(self, monkeypatch):
        pytest.importorskip("fastapi")
        from fastapi.testclient import TestClient
        import mcp_server
        tok = _token(monkeypatch)
        c = TestClient(mcp_server.create_mcp_app(), base_url="http://127.0.0.1:8001")
        assert c.get("/mcp/tools").status_code == 401
        r = c.get("/mcp/tools", headers={"authorization": f"Bearer {tok}"})
        assert r.status_code == 200 and r.json()["count"] == 8
        r = c.get("/mcp/health", headers={"origin": "https://evil.example"})
        assert r.status_code == 403
