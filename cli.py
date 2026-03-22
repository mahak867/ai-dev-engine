# cli.py

import argparse
import sys
from core.orchestrator import Orchestrator
from core.llm import LLMClient


def main():
    print("""
+-------------------------------------------+
|   APEX AI DEV ENGINE  v2.0                |
|   Kimi K2 + Qwen3-32B + Llama 3.3 70B    |
|   Competition & Investor Grade Output     |
+-------------------------------------------+
""")
    parser = argparse.ArgumentParser(
        description="AI Dev Engine — 4-Model Stack (Ollama or Groq)",
        formatter_class=argparse.RawTextHelpFormatter,
    )

    # Generation modes
    parser.add_argument("--fullstack", type=str, help="Full-stack app (8-step pipeline)")
    parser.add_argument("--pipeline",  type=str, help="4-model pipeline")
    parser.add_argument("--generate",  type=str, help="Single-model routed generation")
    parser.add_argument("--name",      type=str, help="Output project folder name")

    # Single model
    parser.add_argument("--chat",   type=str, help="Chat (general model)")
    parser.add_argument("--plan",   type=str, help="Plan/architect (reasoner model)")
    parser.add_argument("--code",   type=str, help="Generate code (coder model)")
    parser.add_argument("--ai",     type=str, help="Auto-routed prompt")

    # Provider selection
    parser.add_argument("--provider", type=str, choices=["ollama","groq"], default=None,
        help="AI provider: ollama (local) or groq (cloud, fast). Default: auto-detect")

    # Utilities
    parser.add_argument("--classify",  type=str,        help="Classify a project request")
    parser.add_argument("--check",     action="store_true", help="Check models are ready")
    parser.add_argument("--dry-run",   action="store_true", help="Test pipeline without calling models")
    parser.add_argument("--no-tests",  action="store_true", help="Skip test generation step")
    parser.add_argument("--clerk",      action="store_true", help="Use Clerk for auth instead of JWT")

    # Legacy
    parser.add_argument("pos_name",        nargs="?", type=str, help=argparse.SUPPRESS)
    parser.add_argument("pos_description", nargs="?", type=str, help=argparse.SUPPRESS)

    args    = parser.parse_args()
    dry_run = args.dry_run

    # ── Set provider ─────────────────────────────────────────────
    from core.ai.provider_factory import set_provider, auto_detect
    if args.provider:
        set_provider(args.provider)
    else:
        auto_detect()

    from core.ai.provider_factory import get_provider
    provider = get_provider()

    # ── Startup validation ────────────────────────────────────────
    skip_validation = dry_run or args.chat or args.plan or args.code or args.ai or args.classify or args.check
    if not skip_validation:
        if provider == "ollama":
            from core.ai.model_validator import startup_check
            from core.ai.ollama_provider import set_resolved_models
            try:
                resolved = startup_check()
                if resolved:
                    set_resolved_models(resolved)
            except RuntimeError:
                sys.exit(1)
        else:
            print("  [Groq] Skipping Ollama check — using Groq cloud.")

    llm          = LLMClient()
    orchestrator = Orchestrator(llm, dry_run=dry_run)

    # ── --check ──────────────────────────────────────────────────
    if args.check:
        if provider == "groq":
            from core.ai.groq_provider import check_groq, GROQ_MODELS
            import os
            print("\n[*] Checking Groq...")
            key = os.getenv("GROQ_API_KEY","")
            if not key:
                print("[ERR] GROQ_API_KEY not set.")
                print("  Get a free key at https://console.groq.com")
                sys.exit(1)
            print("[OK] GROQ_API_KEY found.")
            print("[OK] Groq models:")
            for task, model in GROQ_MODELS.items():
                print(f"     {task:10s} -> {model}")
            print("\n[OK] Ready to generate with Groq.\n")
        else:
            from core.ai.model_validator import startup_check
            try:
                startup_check()
                print("[OK] Everything looks good. Ready to generate.\n")
            except RuntimeError:
                pass
        sys.exit(0)

    # ── --classify ───────────────────────────────────────────────
    if args.classify:
        try:
            from core.ai.project_classifier import ProjectClassifier
            import json
            print("\n[SCAN] Classifying project...\n")
            spec = ProjectClassifier().classify(args.classify)
            print(json.dumps(spec, indent=2))
            sys.exit(0)
        except Exception as e:
            print(f"\n[ERR] Classification failed: {e}\n"); sys.exit(1)

    # ── --fullstack ──────────────────────────────────────────────
    if args.fullstack and args.name:
        try:
            if args.no_tests:
                import core.ai.fullstack_pipeline as fp
                _orig = fp.build_fullstack_pipeline
                def _patched(spec):
                    pipeline = _orig(spec)
                    pipeline.steps = [s for s in pipeline.steps if "Test" not in s.name]
                    return pipeline
                fp.build_fullstack_pipeline = _patched
                print("  [i] Test generation skipped (--no-tests)")
            if getattr(args, 'clerk', False):
                import core.ai.fullstack_pipeline as fp
                _orig_gen = fp.run_fullstack_generation
                def _clerk_gen(request):
                    ctx = _orig_gen(request)
                    ctx["spec"]["use_clerk"] = True
                    return ctx
                fp.run_fullstack_generation = _clerk_gen
                print("  [i] Using Clerk for authentication")
            path = orchestrator.generate_fullstack(args.name, args.fullstack)
            print(f"\n[OK] Project ready at: {path}\n")
            sys.exit(0)
        except Exception as e:
            print(f"\n[ERR] Full-stack generation failed: {e}\n"); sys.exit(1)

    # ── --pipeline ───────────────────────────────────────────────
    if args.pipeline and args.name:
        try:
            path = orchestrator.generate_project_pipeline(args.name, args.pipeline)
            print(f"\n[OK] Project ready at: {path}\n"); sys.exit(0)
        except Exception as e:
            print(f"\n[ERR] Pipeline failed: {e}\n"); sys.exit(1)

    # ── --generate ───────────────────────────────────────────────
    if args.generate and args.name:
        try:
            path = orchestrator.generate_project_files(args.name, args.generate)
            print(f"\n[OK] Project ready at: {path}\n"); sys.exit(0)
        except Exception as e:
            print(f"\n[ERR] Generation failed: {e}\n"); sys.exit(1)

    # ── single model ─────────────────────────────────────────────
    if args.chat:
        try:
            print(f"\n[Chat - {provider}]\n")
            print(llm.chat(args.chat)); sys.exit(0)
        except Exception as e:
            print(f"\n[ERR] {e}\n"); sys.exit(1)

    if args.plan:
        try:
            print(f"\n[Plan - {provider}]\n")
            print(llm.plan(args.plan)); sys.exit(0)
        except Exception as e:
            print(f"\n[ERR] {e}\n"); sys.exit(1)

    if args.code:
        try:
            print(f"\n[Code - {provider}]\n")
            print(llm.code(args.code)); sys.exit(0)
        except Exception as e:
            print(f"\n[ERR] {e}\n"); sys.exit(1)

    if args.ai:
        try:
            print(f"\n[Auto-route - {provider}]\n")
            print(orchestrator.test_ai(args.ai)); sys.exit(0)
        except Exception as e:
            print(f"\n[ERR] {e}\n"); sys.exit(1)

    # ── legacy scaffold ──────────────────────────────────────────
    project_name = args.name or args.pos_name
    project_desc = args.pos_description
    if project_name and project_desc:
        try:
            path = orchestrator.create_project(project_name, project_desc)
            print(f"\n[OK] Scaffolded at: {path}\n"); sys.exit(0)
        except Exception as e:
            print(f"\n[ERR] {e}\n"); sys.exit(1)

    # ── help ─────────────────────────────────────────────────────
    print("""
+=============================================================+
|        AI Dev Engine -- Ollama + Groq                       |
+=============================================================+
|  PROVIDERS:                                                 |
|    Ollama (local)  -- default, uses your PC                 |
|    Groq (cloud)    -- fast, free, no GPU needed             |
|                                                             |
|  SET GROQ KEY (auto-switches to Groq):                      |
|    set GROQ_API_KEY=your_key_here                           |
|    Get free key: https://console.groq.com                   |
|                                                             |
|  GENERATION:                                                |
|    py cli.py --fullstack "todo app" --name todo             |
|    py cli.py --fullstack "todo app" --name todo --provider groq
|    py cli.py --pipeline  "REST API" --name api              |
|    py cli.py --generate  "Flask app" --name app             |
|                                                             |
|  SINGLE MODEL:                                              |
|    py cli.py --chat "What is JWT?"                          |
|    py cli.py --plan "Design a microservices system"         |
|    py cli.py --code "Write a login component"               |
|                                                             |
|  UTILITIES:                                                 |
|    py cli.py --check                                        |
|    py cli.py --check --provider groq                        |
|    py cli.py --fullstack "..." --name app --dry-run         |
|    py cli.py --fullstack "..." --name app --no-tests        |
+=============================================================+
""")
    sys.exit(1)


if __name__ == "__main__":
    main()
