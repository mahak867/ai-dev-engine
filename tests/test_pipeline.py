"""Pipeline behaviour: review negotiation, failure tolerance, syntax checks, CLI."""
import json
import sys

import pytest

from apex import demo_llm


@pytest.fixture
def scripted_llm(monkeypatch):
    """Install a fake LLM whose Reviewer verdicts are scripted per round."""
    from apex.ai import provider
    state = {"reviews": [], "calls": [], "fail": set()}

    def respond(messages):
        system = messages[0]["content"]
        role = ("reviewer" if "senior code reviewer" in system else
                "planner" if "Output ONLY valid JSON, zero prose" in system else
                "architect" if system.startswith("You are an elite software architect") else "other")
        state["calls"].append(role)
        if role in state["fail"]:
            raise RuntimeError(f"{role} is down")
        if role == "reviewer" and state["reviews"]:
            return json.dumps(state["reviews"].pop(0))
        return demo_llm.respond(messages)

    provider.set_fake_responder(respond)
    monkeypatch.setenv("APEX_MODEL", "fake/canned")
    yield state
    provider.set_fake_responder(None)


def _orch(tmp_path, events=None, dialogue=None):
    from apex.memory.store import MemoryStore
    from apex.orchestrator import Orchestrator
    return Orchestrator(
        on_event=lambda a, s, m, extra=None: events.append((a, s, m)) if events is not None else None,
        on_dialogue=(lambda f, t, k, c: dialogue.append((f, t, k))) if dialogue is not None else None,
        memory_store=MemoryStore(str(tmp_path / "mem")))


REJECT = {"score": 55, "critical": ["hardcoded secret"], "warnings": [], "suggestions": [],
          "security_issues": [], "fixed_files": {}}
APPROVE = {"score": 93, "critical": [], "warnings": [], "suggestions": [], "security_issues": [], "fixed_files": {}}


class TestReviewNegotiation:
    def test_reject_then_approve(self, scripted_llm, tmp_path):
        scripted_llm["reviews"] = [dict(REJECT), dict(APPROVE)]
        events, dialogue = [], []
        orch = _orch(tmp_path, events, dialogue)
        orch.generate_fullstack("app", "todo api", str(tmp_path / "out"))
        assert ("Reviewer", "rejected") in [(a, s) for a, s, _ in events]
        assert ("Reviewer", "Coder", "request") in dialogue and ("Coder", "Reviewer", "patch") in dialogue
        assert any(a == "Reviewer" and s == "done" and "Approved" in m and "round 2" in m for a, s, m in events)
        mem = orch.memory.list_projects()[0]
        assert mem["quality_score"] == 93 and mem["review_rounds"] == 2

    def test_architect_rejoins_from_round_two(self, scripted_llm, tmp_path):
        scripted_llm["reviews"] = [dict(REJECT), dict(REJECT), dict(APPROVE)]
        dialogue = []
        _orch(tmp_path, [], dialogue).generate_fullstack("app", "x", str(tmp_path / "out"))
        assert ("Architect", "Coder", "negotiation") in dialogue
        assert scripted_llm["calls"].count("architect") == 2

    def test_round_limit_proceeds_with_unresolved_issues(self, scripted_llm, tmp_path):
        scripted_llm["reviews"] = [dict(REJECT)] * 3
        events = []
        orch = _orch(tmp_path, events)
        path = orch.generate_fullstack("app", "x", str(tmp_path / "out"))
        assert scripted_llm["calls"].count("reviewer") == 3
        assert any("Round limit reached" in m for _, _, m in events)
        assert (tmp_path / "out" / "app" / "backend" / "app.py").is_file() and path.endswith("app")
        mem = orch.memory.list_projects()[0]
        assert mem["review_rounds"] == 3 and any("hardcoded secret" in x for x in mem["lessons_learned"])

    def test_skip_review(self, scripted_llm, tmp_path):
        orch = _orch(tmp_path, [])
        orch.generate_fullstack("app", "x", str(tmp_path / "out"), skip_review=True)
        assert "reviewer" not in scripted_llm["calls"]


class TestFailureTolerance:
    @pytest.mark.parametrize("down", ["planner", "architect"])
    def test_one_planning_agent_down(self, scripted_llm, tmp_path, down):
        scripted_llm["fail"] = {down}
        events = []
        _orch(tmp_path, events).generate_fullstack("app", "x", str(tmp_path / "out"))
        assert any(s == "done" and "error" in m.lower() for a, s, m in events if a.lower() == down)
        assert any(a == "System" and s == "done" for a, s, _ in events)

    def test_stage_order(self, scripted_llm, tmp_path):
        events = []
        _orch(tmp_path, events).generate_fullstack("app", "x", str(tmp_path / "out"))
        first = {}
        for i, (a, s, _) in enumerate(events):
            if s == "running":
                first.setdefault(a, i)
        order = sorted((a for a in first if a != "System"), key=first.get)
        assert order[:2] == ["Planner", "Architect"]
        assert order[2:] == ["Coder", "Reviewer", "SelfHealer", "Debugger", "Executor", "DocWriter"]


class TestSyntaxCheck:
    def test_python(self):
        from apex.syntax_check import check_syntax
        r = check_syntax({"ok.py": "x = 1\n", "bad.py": "def (:\n", "notes.txt": "ignored"})
        assert (r.total, r.passed, r.ok) == (2, 1, False) and r.failed[0].startswith("bad.py")

    def test_js_falls_back_without_node(self, monkeypatch):
        from apex import syntax_check

        def no_node(*a, **k):
            raise FileNotFoundError("node")
        monkeypatch.setattr(syntax_check.subprocess, "run", no_node)
        r = syntax_check.check_syntax({"a.js": "function f(){ return (1) }", "b.ts": "function g(){ "})
        assert not r.node_available and r.passed == 1 and "unbalanced" in r.failed[0]

    def test_empty(self):
        from apex.syntax_check import check_syntax
        assert check_syntax({"README.md": "# hi"}).total == 0


class TestCli:
    def _run(self, monkeypatch, capsys, *argv):
        from apex import cli
        monkeypatch.setattr(sys, "argv", ["apex", *argv])
        cli.main()
        return capsys.readouterr().out

    def test_generate_dry_run_and_list(self, monkeypatch, capsys, tmp_path):
        out = self._run(monkeypatch, capsys, "generate", "a todo app", "--name", "todo",
                        "--output", str(tmp_path), "--dry-run")
        assert "Done!" in out and (tmp_path / "todo" / "README.md").is_file()
        assert "todo" in self._run(monkeypatch, capsys, "list")

    def test_models(self, monkeypatch, capsys):
        assert "groq/" in self._run(monkeypatch, capsys, "models")


class TestPublicApi:
    def test_generate_returns_result(self, scripted_llm, tmp_path):
        import apex
        events = []
        r = apex.generate("todo api", name="todo", output_dir=tmp_path, model="fake/canned",
                          memory_dir=tmp_path / "mem", on_event=lambda a, s, m, extra=None: events.append(a))
        assert isinstance(r, apex.GenerationResult)
        assert r.path.endswith("todo") and "backend/app.py" in r.files
        assert r.quality_score == 92 and r.review_rounds == 1
        assert r.sandbox is None and r.passed_sandbox is None
        assert r.usage["calls"] >= 7 and "Coder" in r.usage["by_agent"]
        assert "Planner" in events and (tmp_path / "mem").is_dir()

    def test_review_can_be_skipped(self, scripted_llm, tmp_path):
        import apex
        r = apex.generate("x", output_dir=tmp_path, model="fake/canned", review=False, memory_dir=tmp_path / "m")
        assert r.quality_score is None and r.review_rounds == 0

    def test_model_pin_does_not_leak(self, scripted_llm, tmp_path, monkeypatch):
        import apex
        from apex.ai.provider import _model_override
        monkeypatch.delenv("APEX_MODEL")
        apex.generate("x", output_dir=tmp_path, model="fake/canned", memory_dir=tmp_path / "m")
        assert _model_override.get() == ""

    def test_sandbox_flag_overrides_env(self, scripted_llm, tmp_path, monkeypatch):
        from apex import orchestrator
        from apex.memory.store import MemoryStore
        called = []
        monkeypatch.setattr(orchestrator.Orchestrator, "_sandbox_loop", lambda self, files: called.append(1) or files)
        monkeypatch.setattr(orchestrator, "sandbox_enabled", lambda: True)
        mk = lambda sb: orchestrator.Orchestrator(on_event=lambda *a, **k: None, sandbox=sb,  # noqa: E731
                                                  memory_store=MemoryStore(str(tmp_path / "m")))
        mk(False).generate_fullstack("a", "x", str(tmp_path))
        assert called == []
        mk(None).generate_fullstack("b", "x", str(tmp_path))
        assert called == [1]


class TestOpenAICompatible:
    def _provider(self, monkeypatch, seen):
        from apex.ai.provider import LLMProvider

        class Resp:
            status_code = 200
            def raise_for_status(self): pass
            def json(self): return {"choices": [{"message": {"content": "hi"}}],
                                    "usage": {"prompt_tokens": 3, "completion_tokens": 1}}

        p = LLMProvider("openai/my-local-model")

        def post(url, json=None, headers=None, **kw):
            seen.update(url=url, model=json["model"], auth=headers["Authorization"])
            return Resp()
        monkeypatch.setattr(p._session, "post", post)
        monkeypatch.delenv("APEX_MODEL", raising=False)
        return p

    def test_custom_base_url_without_key(self, monkeypatch):
        seen = {}
        monkeypatch.setenv("OPENAI_BASE_URL", "http://localhost:1234/v1/")
        assert self._provider(monkeypatch, seen).complete([{"role": "user", "content": "x"}]) == "hi"
        assert seen == {"url": "http://localhost:1234/v1/chat/completions", "model": "my-local-model",
                        "auth": "Bearer none"}

    def test_openai_requires_key(self, monkeypatch):
        monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
        with pytest.raises(RuntimeError):
            self._provider(monkeypatch, {}).complete([{"role": "user", "content": "x"}])

    def test_unknown_model_is_a_clear_error(self, monkeypatch):
        from apex.ai.provider import LLMProvider
        with pytest.raises(ValueError, match="apex models"):
            LLMProvider("nope/x")._call("nope/x", [], 10, False)


class TestCliExtras:
    def test_doctor(self, monkeypatch, capsys):
        from apex import cli
        monkeypatch.setenv("GROQ_API_KEY", "gsk_x")
        rows = {label: (ok, detail) for label, ok, detail in cli.doctor_report()}
        assert rows["LLM provider"][0] and "Groq" in rows["LLM provider"][1]
        assert "Docker sandbox" in rows and "MCP server" in rows
        monkeypatch.setattr(sys, "argv", ["apex", "doctor"])
        cli.main()
        assert "APEX doctor" in capsys.readouterr().out

    def test_eval_subcommand(self, monkeypatch, tmp_path):
        pytest.importorskip("bandit")
        from apex import cli
        monkeypatch.setattr(sys, "argv", ["apex", "eval", "--self-test", "--limit", "1",
                                          "--run-id", "t", "--out", str(tmp_path)])
        with pytest.raises(SystemExit) as e:
            cli.main()
        assert e.value.code == 0 and (tmp_path / "t" / "summary.md").is_file()

    def test_python_dash_m(self, tmp_path):
        import subprocess
        r = subprocess.run([sys.executable, "-m", "apex", "--help"], capture_output=True, text=True, timeout=60)
        assert r.returncode == 0 and "serve" in r.stdout and "doctor" in r.stdout
