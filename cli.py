#!/usr/bin/env python3
# APEX AI Dev Engine CLI
import argparse
import os
import sys

_BANNER = """
+-------------------------------------------+
|   APEX AI DEV ENGINE  v2.0                |
|   Kimi K2 + Qwen3-32B + Llama 3.3 70B    |
|   Competition & Investor Grade Output     |
+-------------------------------------------+
"""


def _print_banner(provider: str = "") -> None:
    print(_BANNER, end="")
    if provider:
        print(f"  [Provider] Using: {provider.upper()}\n")


# ── subcommand: apex generate ─────────────────────────────────────────────────

def _cmd_generate(args: argparse.Namespace) -> None:
    os.environ.setdefault("PYTHONUTF8", "1")
    _print_banner(args.provider)

    from core.orchestrator import Orchestrator

    orch = Orchestrator(dry_run=args.dry_run)

    print(f"Full-Stack Generation: '{args.name}'")
    print(f"Idea: {args.request}")

    try:
        path = orch.generate_fullstack(
            name=args.name,
            request=args.request,
            output_dir=args.output,
        )
        print(f"\nGeneration complete! -> {path}")
    except Exception as e:
        print(f"\n[ERR] Full-stack generation failed: {e}")
        sys.exit(1)


# ── subcommand: apex edit ─────────────────────────────────────────────────────

def _cmd_edit(args: argparse.Namespace) -> None:
    os.environ.setdefault("PYTHONUTF8", "1")
    _print_banner()

    from core.orchestrator import Orchestrator

    orch = Orchestrator()

    if args.edit:
        changed = orch.edit_app(args.path, args.edit)
        print(f"Changed {len(changed)} files")
    elif args.add:
        added = orch.add_feature(args.path, args.add)
        print(f"Added {len(added)} files")
    else:
        print("[ERR] Specify --edit <instruction> or --add <feature>")
        sys.exit(1)


# ── argument parser ────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="apex",
        description="APEX AI Dev Engine",
    )
    subparsers = parser.add_subparsers(dest="command", metavar="<command>")

    # -- apex generate --
    gen = subparsers.add_parser(
        "generate",
        help="Generate a new full-stack application",
    )
    gen.add_argument("request", type=str, help="App idea / description to generate")
    gen.add_argument("--name", type=str, default="my_app", help="Project name")
    gen.add_argument("--output", type=str, default=".", help="Output directory")
    gen.add_argument("--provider", type=str, default="groq", help="AI provider")
    gen.add_argument("--clerk", action="store_true", help="Enable Clerk auth")
    gen.add_argument("--stripe", action="store_true", help="Enable Stripe payments")
    gen.add_argument("--dry-run", action="store_true", dest="dry_run", help="Dry-run mode (no AI calls)")
    gen.set_defaults(func=_cmd_generate)

    # -- apex edit --
    edit = subparsers.add_parser(
        "edit",
        help="Edit or extend an existing generated application",
    )
    edit.add_argument("--path", required=True, help="Path to the existing project")
    edit.add_argument("--edit", type=str, default=None, help="Edit instruction (e.g. 'add dark mode')")
    edit.add_argument("--add", type=str, default=None, help="Feature to add (e.g. 'Stripe checkout')")
    edit.set_defaults(func=_cmd_edit)

    return parser


# ── entry point ────────────────────────────────────────────────────────────────

def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
