"""Tests for CLI argument parsing and subcommand wiring.

No actual AI or file generation is triggered — the orchestrator calls are
patched out so only the argument parsing / routing logic is exercised.
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from cli import _build_parser, main  # noqa: E402


# ── _build_parser ─────────────────────────────────────────────────────────────

class TestBuildParser:
    def test_generate_subcommand_exists(self):
        parser = _build_parser()
        args = parser.parse_args(["generate", "A todo app"])
        assert args.command == "generate"
        assert args.request == "A todo app"

    def test_generate_defaults(self):
        args = _build_parser().parse_args(["generate", "idea"])
        assert args.name == "my_app"
        assert args.output == "."
        assert args.provider == "groq"
        assert args.dry_run is False
        assert args.clerk is False
        assert args.stripe is False

    def test_generate_custom_flags(self):
        args = _build_parser().parse_args([
            "generate", "idea",
            "--name", "coolapp",
            "--output", "/tmp/out",
            "--provider", "openai",
            "--clerk",
            "--stripe",
            "--dry-run",
        ])
        assert args.name == "coolapp"
        assert args.output == "/tmp/out"
        assert args.provider == "openai"
        assert args.clerk is True
        assert args.stripe is True
        assert args.dry_run is True

    def test_edit_subcommand_exists(self):
        args = _build_parser().parse_args(["edit", "--path", "/some/project", "--edit", "add dark mode"])
        assert args.command == "edit"
        assert args.path == "/some/project"
        assert args.edit == "add dark mode"

    def test_edit_add_flag(self):
        args = _build_parser().parse_args(["edit", "--path", "/proj", "--add", "Stripe"])
        assert args.add == "Stripe"

    def test_edit_path_required(self):
        parser = _build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["edit", "--edit", "add dark mode"])

    def test_generate_request_required(self):
        parser = _build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["generate"])

    def test_func_set_for_generate(self):
        from cli import _cmd_generate
        args = _build_parser().parse_args(["generate", "x"])
        assert args.func is _cmd_generate

    def test_func_set_for_edit(self):
        from cli import _cmd_edit
        args = _build_parser().parse_args(["edit", "--path", "/p"])
        assert args.func is _cmd_edit


# ── main() routing ─────────────────────────────────────────────────────────────

class TestMainRouting:
    def test_no_subcommand_exits_nonzero(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["apex"])
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code != 0

    def test_generate_routes_to_orchestrator(self):
        # Verify the parser correctly routes `generate` to _cmd_generate and
        # sets the expected attributes — no real Orchestrator is instantiated.
        from cli import _cmd_generate
        args = _build_parser().parse_args(["generate", "A blog app", "--name", "blog", "--dry-run"])
        assert args.func is _cmd_generate
        assert args.name == "blog"
        assert args.dry_run is True

    def test_edit_routes_correctly(self):
        from cli import _cmd_edit
        args = _build_parser().parse_args(["edit", "--path", "/proj", "--edit", "add dark mode"])
        assert args.func is _cmd_edit
        assert args.path == "/proj"
        assert args.edit == "add dark mode"
