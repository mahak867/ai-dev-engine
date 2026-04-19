"""Tests for the core Orchestrator class.

All tests run in dry-run mode or with fully mocked LLM calls so that no
real network requests are made.  The LLMClient is replaced with a
lightweight stub that returns pre-canned JSON payloads from the
``tests/fixtures/`` directory.
"""
import json
import os
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock

import pytest

# Ensure the repo root is on the path so that ``from core.xxx import …`` works
REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

FIXTURES_DIR = Path(__file__).parent / "fixtures"

# ── Module stubs ──────────────────────────────────────────────────────────────
# core.orchestrator depends on several modules that require live API keys or
# optional third-party packages at import time.  We register lightweight stubs
# once via a session-scoped autouse fixture so pytest controls the lifetime and
# each entry in sys.modules is cleaned up after the session.

_STUB_NAMES = [
    "core.llm",
    "core.ai.response_cleaner",
    "core.execution",
    "core.execution.runner",
    "core.execution.debugger",
    "core.tools",
    "core.tools.dependency_installer",
]


def _make_stubs() -> dict:
    """Return a {name: module} mapping of all required stubs."""

    def _clean(text: str) -> str:
        return text

    def _clean_and_parse(text: str) -> dict:
        text = text.strip()
        start = text.find("{")
        end = text.rfind("}") + 1
        if start == -1 or end == 0:
            raise ValueError("No JSON object found")
        return json.loads(text[start:end])

    def _mod(name: str, **attrs) -> ModuleType:
        mod = ModuleType(name)
        for k, v in attrs.items():
            setattr(mod, k, v)
        return mod

    return {
        "core.llm": _mod("core.llm", LLMClient=MagicMock(name="LLMClient")),
        "core.ai.response_cleaner": _mod(
            "core.ai.response_cleaner", clean=_clean, clean_and_parse=_clean_and_parse
        ),
        "core.execution": _mod("core.execution"),
        "core.execution.runner": _mod("core.execution.runner", CodeRunner=MagicMock()),
        "core.execution.debugger": _mod("core.execution.debugger", Debugger=MagicMock()),
        "core.tools": _mod("core.tools"),
        "core.tools.dependency_installer": _mod(
            "core.tools.dependency_installer", DependencyInstaller=MagicMock()
        ),
    }


@pytest.fixture(scope="session", autouse=True)
def _install_stubs():
    """Register dependency stubs for the duration of the test session."""
    stubs = _make_stubs()
    originals = {name: sys.modules.get(name) for name in stubs}
    sys.modules.update(stubs)
    yield
    for name, original in originals.items():
        if original is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = original

# ── helpers ───────────────────────────────────────────────────────────────────

def _load_fixture(name: str) -> dict:
    with open(FIXTURES_DIR / name, encoding="utf-8") as fh:
        return json.load(fh)


def _make_stub_llm(raw_json: str) -> MagicMock:
    """Return a MagicMock that quacks like LLMClient."""
    stub = MagicMock()
    stub.generate.return_value = raw_json
    stub.plan.return_value = "Stub architecture plan"
    stub.code.return_value = raw_json
    stub.review.return_value = raw_json
    stub.run_project_pipeline.return_value = {"final_output": raw_json}
    stub.run_debug_pipeline.return_value = {"fixed_code": raw_json}
    return stub


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def sample_files_json() -> str:
    """Raw JSON string that matches the ``files`` schema expected by Orchestrator."""
    data = _load_fixture("sample_generation.json")
    return json.dumps(data)


@pytest.fixture()
def orchestrator_dry(tmp_path, monkeypatch):
    """Orchestrator in dry-run mode with working dir set to tmp_path."""
    monkeypatch.chdir(tmp_path)
    from core.orchestrator import Orchestrator
    return Orchestrator(dry_run=True)


@pytest.fixture()
def orchestrator_stub(tmp_path, monkeypatch, sample_files_json):
    """Orchestrator with a stubbed LLM (no network) and cwd = tmp_path."""
    monkeypatch.chdir(tmp_path)
    from core.orchestrator import Orchestrator
    stub = _make_stub_llm(sample_files_json)
    return Orchestrator(llm=stub, dry_run=False)


# ── Orchestrator.__init__ ─────────────────────────────────────────────────────

class TestOrchestratorInit:
    def test_dry_run_flag(self, orchestrator_dry):
        assert orchestrator_dry.dry_run is True

    def test_llm_is_set(self, orchestrator_stub):
        assert orchestrator_stub.llm is not None


# ── _safe_parse ───────────────────────────────────────────────────────────────

class TestSafeParse:
    def test_valid_json(self, orchestrator_dry, sample_files_json):
        data = orchestrator_dry._safe_parse(sample_files_json)
        assert "files" in data
        assert len(data["files"]) > 0

    def test_missing_files_key_raises(self, orchestrator_dry):
        with pytest.raises(Exception, match="missing 'files'"):
            orchestrator_dry._safe_parse('{"name": "oops"}')

    def test_malformed_json_raises(self, orchestrator_dry):
        with pytest.raises(Exception):
            orchestrator_dry._safe_parse("not json at all {{{{")

    def test_file_missing_path_raises(self, orchestrator_dry):
        bad = json.dumps({"files": [{"content": "x"}]})
        with pytest.raises(Exception, match="missing path/content"):
            orchestrator_dry._safe_parse(bad)

    def test_file_missing_content_raises(self, orchestrator_dry):
        bad = json.dumps({"files": [{"path": "x.py"}]})
        with pytest.raises(Exception, match="missing path/content"):
            orchestrator_dry._safe_parse(bad)


# ── _dry_run_data ─────────────────────────────────────────────────────────────

class TestDryRunData:
    def test_returns_two_files(self, orchestrator_dry):
        data = orchestrator_dry._dry_run_data("my_project")
        assert len(data["files"]) == 2

    def test_file_paths_present(self, orchestrator_dry):
        data = orchestrator_dry._dry_run_data("my_project")
        paths = {f["path"] for f in data["files"]}
        assert "main.py" in paths
        assert "README.md" in paths


# ── _merge_file_lists ─────────────────────────────────────────────────────────

class TestMergeFileLists:
    def test_merge_two_payloads(self, orchestrator_dry):
        a = json.dumps({"files": [{"path": "a.py", "content": "# a"}]})
        b = json.dumps({"files": [{"path": "b.py", "content": "# b"}]})
        merged = orchestrator_dry._merge_file_lists(a, b)
        paths = {f["path"] for f in merged["files"]}
        assert paths == {"a.py", "b.py"}

    def test_later_entry_wins_on_duplicate(self, orchestrator_dry):
        a = json.dumps({"files": [{"path": "x.py", "content": "v1"}]})
        b = json.dumps({"files": [{"path": "x.py", "content": "v2"}]})
        merged = orchestrator_dry._merge_file_lists(a, b)
        assert merged["files"][0]["content"] == "v2"

    def test_empty_strings_skipped(self, orchestrator_dry):
        good = json.dumps({"files": [{"path": "ok.py", "content": "x"}]})
        merged = orchestrator_dry._merge_file_lists("", good, "", "NO_DB")
        assert len(merged["files"]) == 1


# ── _write_files ──────────────────────────────────────────────────────────────

class TestWriteFiles:
    def test_creates_files_on_disk(self, orchestrator_dry, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        files = [
            {"path": "backend/app.py", "content": "# backend"},
            {"path": "README.md", "content": "# readme"},
        ]
        path = orchestrator_dry._write_files("proj", files)
        assert (Path(path) / "backend" / "app.py").read_text() == "# backend"
        assert (Path(path) / "README.md").read_text() == "# readme"

    def test_returns_absolute_path(self, orchestrator_dry, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        path = orchestrator_dry._write_files("myproj", [{"path": "x.py", "content": ""}])
        assert os.path.isabs(path)

    def test_list_content_joined(self, orchestrator_dry, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        files = [{"path": "out.py", "content": ["line1", "line2"]}]
        path = orchestrator_dry._write_files("listproj", files)
        text = (Path(path) / "out.py").read_text()
        assert "line1\nline2" == text


# ── generate_fullstack (dry-run) ──────────────────────────────────────────────

class TestGenerateFullstackDryRun:
    def test_returns_path_string(self, orchestrator_dry, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = orchestrator_dry.generate_fullstack(
            name="testapp", request="A todo app", output_dir=str(tmp_path)
        )
        assert isinstance(result, str)

    def test_creates_placeholder_files(self, orchestrator_dry, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        path = orchestrator_dry.generate_fullstack(
            name="dryapp", request="Any idea", output_dir=str(tmp_path)
        )
        assert Path(path).is_dir()
        assert (Path(path) / "main.py").exists()
        assert (Path(path) / "README.md").exists()

    def test_output_dir_respected(self, orchestrator_dry, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        out = tmp_path / "projects"
        out.mkdir()
        path = orchestrator_dry.generate_fullstack(
            name="outapp", request="x", output_dir=str(out)
        )
        assert path.startswith(str(out))


# ── generate_project_files (dry-run) ─────────────────────────────────────────

class TestGenerateProjectFilesDryRun:
    def test_returns_path(self, orchestrator_dry, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        path = orchestrator_dry.generate_project_files("simpleapp", "A simple app")
        assert isinstance(path, str)
        assert Path(path).is_dir()


# ── test_ai ───────────────────────────────────────────────────────────────────

class TestTestAi:
    def test_dry_run_returns_stub(self, orchestrator_dry):
        result = orchestrator_dry.test_ai("some prompt")
        assert "[dry-run]" in result

    def test_live_calls_llm(self, orchestrator_stub):
        orchestrator_stub.llm.generate.return_value = "hello"
        result = orchestrator_stub.test_ai("ping")
        assert result == "hello"
        orchestrator_stub.llm.generate.assert_called_once_with("ping")


# ── edit_app / add_feature ────────────────────────────────────────────────────

class TestEditApp:
    def test_edit_app_dry_run_returns_empty(self, orchestrator_dry, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "app.py").write_text("print('hello')", encoding="utf-8")
        # In dry-run the stub generate_fn always returns NO_CHANGES
        result = orchestrator_dry.edit_app(str(tmp_path), "add dark mode")
        assert isinstance(result, dict)

    def test_add_feature_dry_run_returns_list(self, orchestrator_dry, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = orchestrator_dry.add_feature(str(tmp_path), "Stripe checkout")
        assert isinstance(result, list)
