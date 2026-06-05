from __future__ import annotations
from dotenv import load_dotenv
load_dotenv()
"""
╔══════════════════════════════════════════╗
║   APEX AI DEV ENGINE  v3.0               ║
║   Multi-Agent • Multi-Model • Self-Heal  ║
╚══════════════════════════════════════════╝
"""
import argparse, os, sys, time, json, logging
from pathlib import Path

# ── colour helpers (no deps) ───────────────────────────────────────────────────
def _c(code: str, text: str) -> str:
    if os.name == "nt" and not os.environ.get("WT_SESSION"):
        return text  # plain on old Windows terminals
    return f"\033[{code}m{text}\033[0m"

def amber(t):   return _c("38;5;214", t)
def teal(t):    return _c("38;5;43",  t)
def red(t):     return _c("38;5;196", t)
def green(t):   return _c("38;5;82",  t)
def muted(t):   return _c("38;5;244", t)
def bold(t):    return _c("1",        t)
def dim(t):     return _c("2",        t)

BANNER = f"""
{amber("╔══════════════════════════════════════════════════╗")}
{amber("║")}  {bold("APEX AI DEV ENGINE")}  {_c("38;5;214","v3.0")}                    {amber("║")}
{amber("║")}  {teal("Qwen Cloud • Groq • OpenRouter • Ollama")}         {amber("║")}
{amber("║")}  {muted("Multi-Agent • Self-Healing • Persistent Memory")}  {amber("║")}
{amber("╚══════════════════════════════════════════════════╝")}
"""

AGENT_ICONS = {
    "Planner":   amber("🗺  Planner  "),
    "Architect": teal ("🏛  Architect"),
    "Coder":     _c("38;5;141","👨‍💻 Coder    "),
    "Reviewer":  _c("38;5;51", "🔍 Reviewer "),
    "SelfHealer":green("🔧 Healer   "),
    "Debugger":  red  ("🐛 Debugger "),
    "DocWriter": muted("📝 DocWriter"),
    "System":    bold ("⚙  System   "),
}

STATUS_ICONS = {
    "running": amber("⟳"),
    "done":    green("✓"),
    "error":   red  ("✗"),
    "skip":    muted("⊘"),
    "complete":green("✔"),
}


def _event(agent: str, status: str, msg: str):
    icon   = AGENT_ICONS.get(agent, agent)
    s_icon = STATUS_ICONS.get(status, " ")
    ts     = dim(time.strftime("%H:%M:%S"))
    print(f"  {ts}  {icon}  {s_icon}  {msg}")


# ── subcommand: generate ───────────────────────────────────────────────────────
def cmd_generate(args: argparse.Namespace):
    print(BANNER)
    print(f"  {bold('Project:')} {amber(args.name)}")
    print(f"  {bold('Request:')} {args.request[:80]}{'...' if len(args.request)>80 else ''}")
    print(f"  {bold('Model  :')} {teal(args.model)}")
    print(f"  {bold('Output :')} {args.output}/{args.name}")
    print(f"\n  {muted('─'*50)}\n")

    if args.stream:
        _stream_generate(args)
        return

    from core.orchestrator import Orchestrator
    orch = Orchestrator(model=args.model, dry_run=args.dry_run, on_event=_event)

    t0   = time.time()
    path = orch.generate_fullstack(
        name=args.name,
        request=args.request,
        output_dir=args.output,
        skip_review=args.no_review,
    )
    elapsed = time.time() - t0
    print(f"\n  {muted('─'*50)}")
    print(f"\n  {green('✔')} {bold('Done!')} in {amber(f'{elapsed:.1f}s')}")
    print(f"  {bold('Output:')} {teal(path)}\n")


def _stream_generate(args: argparse.Namespace):
    from core.orchestrator import Orchestrator
    orch = Orchestrator(model=args.model, dry_run=args.dry_run)
    print(f"  {muted('─'*50)}\n")
    for token in orch.generate_stream(args.name, args.request):
        print(token, end="", flush=True)
    print(f"\n\n  {green('✔')} {bold('Stream complete.')}\n")


# ── subcommand: edit ───────────────────────────────────────────────────────────
def cmd_edit(args: argparse.Namespace):
    print(BANNER)
    from core.orchestrator import Orchestrator
    orch = Orchestrator(model=args.model, on_event=_event)
    if args.edit:
        changed = orch.edit_app(args.path, args.edit)
        print(f"\n  {green('✔')} Changed {len(changed)} files\n")
    elif args.debug:
        result = orch.debug(args.path, args.debug, args.traceback or "")
        print(f"\n{result}\n")
    else:
        print(red("  ✗ Specify --edit <instruction> or --debug <error>"))
        sys.exit(1)


# ── subcommand: list ───────────────────────────────────────────────────────────
def cmd_list(args: argparse.Namespace):
    from core.memory.store import MemoryStore
    store = MemoryStore()
    projects = store.list_projects()
    if not projects:
        print(f"\n  {muted('No projects yet. Run: apex generate \"your app idea\"')}\n")
        return
    print(f"\n  {bold('Projects:')}\n")
    for p in projects:
        ts = time.strftime("%Y-%m-%d", time.localtime(p["created"]))
        print(f"  {amber(p['id'])}  {bold(p['name'][:20])}  "
              f"{muted(p['request'][:50])}  {dim(ts)}  {teal(str(p['file_count'])+' files')}")
    print()


# ── subcommand: models ─────────────────────────────────────────────────────────
def cmd_models(args: argparse.Namespace):
    from core.ai.provider import MODELS
    print(f"\n  {bold('Available Models:')}\n")
    by_provider: dict[str, list] = {}
    for m, info in MODELS.items():
        by_provider.setdefault(info["provider"], []).append((m, info))
    for provider, models in by_provider.items():
        print(f"  {amber(provider.upper())}")
        for model, info in models:
            ctx_k = info["ctx"] // 1000
            print(f"    {teal(model):45} {muted(f'{ctx_k}k ctx')}")
        print()


# ── subcommand: audit ──────────────────────────────────────────────────────────
def cmd_audit(args: argparse.Namespace):
    print(BANNER)
    path = Path(args.path)
    if not path.exists():
        print(red(f"  ✗ Path not found: {path}"))
        sys.exit(1)

    files = {}
    skip  = {".git", "node_modules", "__pycache__", ".next", "dist", "build"}
    for p in path.rglob("*"):
        if p.is_file() and not any(s in p.parts for s in skip):
            try:
                files[str(p.relative_to(path))] = p.read_text(encoding="utf-8")
            except Exception:
                pass

    print(f"  Found {amber(str(len(files)))} files to audit...\n")

    from core.agents.base import ReviewerAgent
    from core.ai.provider import LLMProvider
    agent = ReviewerAgent(LLMProvider("coding"))

    sample = "\n\n".join(
        f"// {p}\n{c[:500]}" for p, c in list(files.items())[:8]
    )
    result = agent.run({"code": sample})

    try:
        report = json.loads(result.output)
        score  = report.get("score", 75)
        color  = green if score >= 80 else amber if score >= 60 else red
        print(f"  {bold('Quality Score:')} {color(str(score))}/100\n")
        for issue in report.get("critical", []):
            print(f"  {red('✗ CRITICAL')} {issue}")
        for warn in report.get("warnings", []):
            print(f"  {amber('⚠ WARNING ')} {warn}")
        for sec in report.get("security_issues", []):
            print(f"  {red('🔒 SECURITY')} {sec}")
        for sug in report.get("suggestions", []):
            print(f"  {teal('→ SUGGEST ')} {sug}")
    except Exception:
        print(result.output)
    print()


# ── argument parser ────────────────────────────────────────────────────────────
def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="apex",
        description="APEX AI Dev Engine v3 — Multi-Agent Full-Stack Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  apex generate "SaaS todo app with auth and Stripe" --name taskmaster
  apex generate "REST API for a blog" --name blog-api --model groq/qwen-qwq-32b
  apex generate "e-commerce store" --name shop --stream
  apex edit --path ./taskmaster --edit "add dark mode"
  apex edit --path ./app/auth.py --debug "AttributeError: 'NoneType'"
  apex audit --path ./my-project
  apex list
  apex models
        """,
    )
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    # generate
    gen = sub.add_parser("generate", aliases=["gen", "g"], help="Generate a new project")
    gen.add_argument("request", help="What to build")
    gen.add_argument("--name",      default="my_app",    help="Project name")
    gen.add_argument("--output",    default=".",          help="Output directory")
    gen.add_argument("--model",     default="auto",       help="Model or cascade")
    gen.add_argument("--stream",    action="store_true",  help="Stream output token by token")
    gen.add_argument("--no-review", action="store_true",  help="Skip code review step")
    gen.add_argument("--dry-run",   action="store_true",  help="No AI calls, stub output")
    gen.set_defaults(func=cmd_generate)

    # edit
    edit = sub.add_parser("edit", aliases=["e"], help="Edit or debug an existing project")
    edit.add_argument("--path",      required=True, help="Path to file or project")
    edit.add_argument("--edit",      default=None,  help="Edit instruction")
    edit.add_argument("--debug",     default=None,  help="Error message to debug")
    edit.add_argument("--traceback", default=None,  help="Stack trace")
    edit.add_argument("--model",     default="coding", help="Model to use")
    edit.set_defaults(func=cmd_edit)

    # audit
    audit = sub.add_parser("audit", aliases=["a"], help="Audit existing code quality")
    audit.add_argument("--path", required=True, help="Project path to audit")
    audit.set_defaults(func=cmd_audit)

    # list
    ls = sub.add_parser("list", aliases=["ls"], help="List generated projects")
    ls.set_defaults(func=cmd_list)

    # models
    mdl = sub.add_parser("models", help="List available models")
    mdl.set_defaults(func=cmd_models)

    return parser


# ── entry ──────────────────────────────────────────────────────────────────────
def main():
    logging.basicConfig(level=logging.WARNING)
    parser = _build_parser()
    args   = parser.parse_args()
    if not args.command:
        print(BANNER)
        parser.print_help()
        sys.exit(0)
    args.func(args)


if __name__ == "__main__":
    main()
