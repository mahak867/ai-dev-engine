"""Pipeline behaviour: review negotiation, failure tolerance, syntax checks, CLI."""
import json
import sys

import pytest

from core import demo_llm


@pytest.fixture
def scripted_llm(monkeypatch):
    """Install a fake LLM whose Reviewer verdicts are scripted per round."""
    from core.ai import provider
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
    from core.memory.store import MemoryStore
    from core.orchestrator import Orchestrator
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
        from core.syntax_check import check_syntax
        r = check_syntax({"ok.py": "x = 1\n", "bad.py": "def (:\n", "notes.txt": "ignored"})
        assert (r.total, r.passed, r.ok) == (2, 1, False) and r.failed[0].startswith("bad.py")

    def test_js_falls_back_without_node(self, monkeypatch):
        from core import syntax_check

        def no_node(*a, **k):
            raise FileNotFoundError("node")
        monkeypatch.setattr(syntax_check.subprocess, "run", no_node)
        r = syntax_check.check_syntax({"a.js": "function f(){ return (1) }", "b.ts": "function g(){ "})
        assert not r.node_available and r.passed == 1 and "unbalanced" in r.failed[0]

    def test_empty(self):
        from core.syntax_check import check_syntax
        assert check_syntax({"README.md": "# hi"}).total == 0


class TestCli:
    def _run(self, monkeypatch, capsys, *argv):
        import cli
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
