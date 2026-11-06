#!/usr/bin/env python3
"""
Deploy the dashboard + server to a Hugging Face Space (Docker SDK).

    pip install huggingface_hub
    export HF_TOKEN=hf_...            # a token with write access
    python scripts/deploy_hf_space.py --space <your-hf-username>/apex-society

Uploads only what the container needs, with deploy/hf-space/README.md as the
Space card. Never uploads .env or secrets. The Space holds no provider keys:
visitors use the demo replay or their own key.
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INCLUDE = ["Dockerfile", ".dockerignore", "requirements.txt", "server.py", "mcp_server.py",
           "benchmark.py", "dashboard.html", "LICENSE", "core"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--space", required=True, help="e.g. mahak867/apex-society")
    ap.add_argument("--private", action="store_true")
    args = ap.parse_args()
    token = os.environ.get("HF_TOKEN")
    if not token:
        print("Set HF_TOKEN (https://huggingface.co/settings/tokens, write scope).", file=sys.stderr)
        return 2
    from huggingface_hub import HfApi

    with tempfile.TemporaryDirectory() as tmp:
        stage = Path(tmp)
        for rel in INCLUDE:
            src = ROOT / rel
            if not src.exists():
                continue
            dst = stage / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.is_dir():
                shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            else:
                shutil.copy2(src, dst)
        shutil.copy2(ROOT / "deploy" / "hf-space" / "README.md", stage / "README.md")
        leaked = [p for p in stage.rglob("*") if p.name == ".env" or p.name.startswith(".env.")]
        assert not leaked, f"refusing to upload {leaked}"

        api = HfApi(token=token)
        api.create_repo(args.space, repo_type="space", space_sdk="docker",
                        private=args.private, exist_ok=True)
        api.upload_folder(folder_path=str(stage), repo_id=args.space, repo_type="space",
                          commit_message="Deploy APEX Society", delete_patterns=["*"])
    owner, name = args.space.split("/", 1)
    print(f"Deployed: https://huggingface.co/spaces/{args.space}")
    print(f"App URL:  https://{owner.lower()}-{name.lower().replace('_', '-')}.hf.space")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
