#!/usr/bin/env python3
# APEX AI Dev Engine CLI
import argparse, sys, os

def main():
    parser = argparse.ArgumentParser(description="APEX AI Dev Engine")
    parser.add_argument("--fullstack", type=str, help="App idea to generate")
    parser.add_argument("--name", type=str, default="my_app", help="Project name")
    parser.add_argument("--output", type=str, default=".", help="Output directory")
    parser.add_argument("--provider", type=str, default="groq", help="AI provider")
    parser.add_argument("--clerk", action="store_true", help="Enable Clerk auth")
    parser.add_argument("--stripe", action="store_true", help="Enable Stripe payments")
    parser.add_argument("--dry-run", action="store_true", help="Dry run mode")
    args = parser.parse_args()

    if not args.fullstack:
        parser.print_help()
        sys.exit(1)

    os.environ.setdefault("PYTHONUTF8", "1")

    print(f"""
+-------------------------------------------+
|   APEX AI DEV ENGINE  v2.0                |
|   Kimi K2 + Qwen3-32B + Llama 3.3 70B    |
|   Competition & Investor Grade Output     |
+-------------------------------------------+
  [Provider] Using: {args.provider.upper()}
""")

    from core.orchestrator import Orchestrator
    orch = Orchestrator(dry_run=args.dry_run)

    print(f"Full-Stack Generation: '{args.name}'")
    print(f"Idea: {args.fullstack}")

    try:
        path = orch.generate_fullstack(
            name=args.name,
            request=args.fullstack,
            output_dir=args.output,
        )
        print(f"\nGeneration complete! -> {path}")
    except Exception as e:
        print(f"\n[ERR] Full-stack generation failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()


def edit_cmd():
    """Edit an existing generated app."""
    import argparse, sys, os
    parser = argparse.ArgumentParser(description="Edit existing app")
    parser.add_argument("--path", required=True, help="Path to existing project")
    parser.add_argument("--edit", type=str, help="Edit instruction")
    parser.add_argument("--add", type=str, help="Feature to add")
    args = parser.parse_args(sys.argv[2:])

    from core.orchestrator import Orchestrator
    orch = Orchestrator()

    if args.edit:
        changed = orch.edit_app(args.path, args.edit)
        print(f"Changed {len(changed)} files")
    elif args.add:
        added = orch.add_feature(args.path, args.add)
        print(f"Added {len(added)} files")
    else:
        print("Specify --edit or --add")
