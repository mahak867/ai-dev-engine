# core/orchestrator.py

import json
from pathlib import Path
from typing import Dict, Any

from core.llm import LLMClient
from core.ai.response_cleaner import clean, clean_and_parse
from core.execution.runner import CodeRunner
from core.execution.debugger import Debugger
from core.tools.dependency_installer import DependencyInstaller

MAX_DEBUG_ATTEMPTS = 3


def _print_run_instructions(path):
    from pathlib import Path
    p = Path(path)
    name = p.name
    has_backend = (p / "backend" / "app.py").exists()
    has_frontend = (p / "frontend" / "package.json").exists()
    has_env = (p / "frontend" / ".env").exists()
    print("\n" + "="*50)
    print("  HOW TO RUN YOUR APP")
    print("="*50)
    if has_backend:
        print(f"\n  BACKEND (Terminal 1):")
        print(f"    cd {name}\\backend")
        print(f"    py app.py")
        print(f"    -> http://127.0.0.1:5000")
    if has_frontend:
        print(f"\n  FRONTEND (Terminal 2):")
        print(f"    cd {name}\\frontend")
        print(f"    npm install")
        print(f"    npm run dev")
        print(f"    -> http://localhost:5173")
    if has_env:
        print(f"\n  CLERK AUTH:")
        print(f"    Edit {name}\\frontend\\.env")
        print(f"    VITE_CLERK_PUBLISHABLE_KEY=pk_test_...")
    print("\n" + "="*50 + "\n")


class Orchestrator:

    def __init__(self, llm: LLMClient = None, dry_run: bool = False):
        self.llm     = llm or LLMClient()
        self.dry_run = dry_run  # If True: skip model calls, write placeholder files

    # ── JSON parsing ──────────────────────────────────────────────
    def _safe_parse(self, text: str) -> Dict[str, Any]:
        """Clean + parse JSON from any model response."""
        try:
            data = clean_and_parse(text)
        except ValueError as e:
            raise Exception(str(e))

        if "files" not in data:
            raise Exception("AI response missing 'files' field")
        for f in data.get("files", []):
            if "path" not in f or "content" not in f:
                raise Exception(f"File object missing path/content: {f}")
        return data

    # ── Dry-run stub ──────────────────────────────────────────────
    def _dry_run_data(self, name: str) -> Dict[str, Any]:
        """Returns placeholder files for --dry-run mode."""
        return {
            "files": [
                {
                    "path": "main.py",
                    "content": f'# DRY RUN — {name}\n# Real files would be generated here by the AI models.\nprint("Dry run complete.")\n'
                },
                {
                    "path": "README.md",
                    "content": f"# {name}\n\nGenerated in dry-run mode. Run without --dry-run to generate real code.\n"
                },
            ]
        }

    # ── Merge multiple file lists ─────────────────────────────────
    def _merge_file_lists(self, *raw_jsons: str) -> Dict[str, Any]:
        merged = {}
        for raw in raw_jsons:
            if not raw or clean(raw).strip() in ("", "NO_DB"):
                continue
            try:
                data = self._safe_parse(raw)
                for f in data.get("files", []):
                    merged[f["path"]] = f
            except Exception:
                pass
        return {"files": list(merged.values())}

    # ── File writer ───────────────────────────────────────────────
    def _write_files(self, project_name: str, files: list) -> str:
        base_path = Path(project_name)
        base_path.mkdir(parents=True, exist_ok=True)
        for file in files:
            file_path = base_path / file["path"]
            file_path.parent.mkdir(parents=True, exist_ok=True)
            content = file["content"]
            if isinstance(content, list):
                content = "\n".join(content)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
        return str(base_path.resolve())

    # ── Entry point guard ─────────────────────────────────────────
    def _ensure_entry_point(self, project_path: str, app_type: str = "unknown"):
        project_path = Path(project_path)
        entry_candidates = ["run.py", "app.py", "main.py"]
        for f in list(project_path.rglob("*.py"))[:20]:
            if f.name in entry_candidates:
                return
        for f in project_path.rglob("cli.py"):
            module = ".".join(f.relative_to(project_path).with_suffix("").parts)
            (project_path / "main.py").write_text(
                f"from {module} import main\n\nif __name__ == '__main__':\n    main()\n",
                encoding="utf-8",
            )
            print("  ⚙️  Created entry point: main.py")
            return
        (project_path / "main.py").write_text(
            'print("Project generated successfully.")\n', encoding="utf-8"
        )
        print("  ⚠️  Created fallback main.py")

    # ── Install dependencies ──────────────────────────────────────
    def _install_deps(self, project_path: str):
        if self.dry_run:
            print("  [dry-run] Skipping dependency install.")
            return
        installer = DependencyInstaller()
        print("\n  📦 Installing dependencies...")
        installer.install_all(project_path)

    # ── Auto debug loop ───────────────────────────────────────────
    def _auto_debug(self, project_path: str, data: Dict[str, Any], app_type: str = "auto"):
        if self.dry_run:
            print("  [dry-run] Skipping execution.")
            return

        runner    = CodeRunner(project_path, app_type=app_type)
        installer = DependencyInstaller()
        attempt   = 0
        current_data = data

        while attempt < MAX_DEBUG_ATTEMPTS:
            print(f"\n  🚀 Running project (attempt {attempt + 1}/{MAX_DEBUG_ATTEMPTS})...")
            result = runner.run()

            if result["success"]:
                print("  ✅ Project running successfully.")
                if result.get("output"):
                    print(result["output"])
                return

            error = result.get("error", "")
            print(f"  ❌ Failed:\n{error[:500]}")

            # Auto-install missing Python module
            missing = installer.extract_missing_module(error)
            if missing:
                print(f"  📦 Auto-installing: {missing}")
                installer.install(missing)
                attempt += 1
                continue

            # Debug pipeline: Reasoner analyses → Coder fixes
            print("  🔧 Running debug pipeline (DeepSeek R1 → Qwen Coder)...")
            ctx = self.llm.run_debug_pipeline(
                code=json.dumps(current_data),
                error=error,
            )
            fixed_raw = ctx.get("fixed_code", "")
            try:
                fixed = self._safe_parse(fixed_raw)
            except Exception as e:
                print(f"  ⚠️  Debug pipeline returned unparseable output: {e}")
                return

            print("  📂 Rewriting fixed files...")
            self._write_files(project_path, fixed["files"])
            current_data = fixed
            attempt += 1

        print("  ❌ Max debug attempts reached.")

    # ── PUBLIC: test AI ───────────────────────────────────────────
    def test_ai(self, prompt: str) -> str:
        if self.dry_run:
            return "[dry-run] Would call: " + prompt[:80]
        return self.llm.generate(prompt)

    # ── PUBLIC: scaffold ──────────────────────────────────────────
    def create_project(self, name: str, description: str) -> str:
        base = Path(name)
        if base.exists():
            raise FileExistsError(f"Project '{name}' already exists.")
        base.mkdir()
        (base / "README.md").write_text(f"# {name}\n\n{description}")
        return str(base.resolve())

    # ── PUBLIC: simple generate ───────────────────────────────────
    def generate_project_files(self, name: str, request: str) -> str:
        if self.dry_run:
            print("\n[dry-run] Would run: simple 3-step pipeline")
            print("  Step 1: DeepSeek R1 → architecture")
            print("  Step 2: Qwen Coder  → code")
            print("  Step 3: DeepSeek R1 → review")
            data = self._dry_run_data(name)
            path = self._write_files(name, data["files"])
            print(f"\n  ✅ Dry-run complete. Placeholder files at: {path}")
            return path

        print("\n🧠 Step 1: Architecture... (DeepSeek R1 14B)")
        arch = self.llm.plan(
            f"Design the architecture for this project.\nRequest:\n{request}"
        )

        print("\n👨‍💻 Step 2: Generating code... (Qwen2.5 Coder 14B)")
        raw = self.llm.code(
            f"Generate the FULL project. Return ONLY valid JSON.\n"
            f'{{"files":[{{"path":"app.py","content":"..."}}]}}\n\n'
            f"Architecture:\n{arch}\n\nRequest:\n{request}"
        )
        data = self._safe_parse(raw)

        print("\n🔍 Step 3: Reviewing... (DeepSeek R1 14B)")
        reviewed_raw = self.llm.review(
            f"Review and fix this project. Return same JSON format.\n{json.dumps(data)}"
        )
        try:
            data = self._safe_parse(reviewed_raw)
        except Exception:
            pass  # Keep original if review fails to parse

        print("\n📂 Writing files...")
        path = self._write_files(name, data["files"])
        self._ensure_entry_point(path)
        self._install_deps(path)

        print("\nFiles generated:")
        for f in data["files"]:
            print(f"  - {f['path']}")

        self._auto_debug(path, data)
        return path

    # ── PUBLIC: 4-model pipeline ──────────────────────────────────
    def generate_project_pipeline(self, name: str, request: str) -> str:
        if self.dry_run:
            print("\n[dry-run] Would run: 4-model pipeline")
            print("  Step 1: DeepSeek R1  → architecture")
            print("  Step 2: Qwen Coder   → code")
            print("  Step 3: DeepSeek R1  → review")
            print("  Step 4: Decoder 14B  → format")
            data = self._dry_run_data(name)
            path = self._write_files(name, data["files"])
            print(f"\n  ✅ Dry-run complete. Placeholder files at: {path}")
            return path

        print("\n🚀 Starting 4-model pipeline...\n")
        ctx = self.llm.run_project_pipeline(request)
        final_raw = ctx.get("final_output") or ctx.get("reviewed_code") or ctx.get("raw_code", "")
        data = self._safe_parse(final_raw)

        print("\n📂 Writing files...")
        path = self._write_files(name, data["files"])
        self._ensure_entry_point(path)
        self._install_deps(path)

        for f in data["files"]:
            print(f"  - {f['path']}")

        self._auto_debug(path, data)
        return path

    # ── PUBLIC: edit existing app ─────────────────────────────────
    def edit_app(self, project_path: str, instruction: str) -> dict:
        """Apply an edit instruction to an existing generated project.

        Returns a dict of {relative_path: new_content} for every file changed.
        """
        from core.ai.editor import AppEditor
        editor = AppEditor(project_path)
        generate_fn = self.llm.generate if not self.dry_run else (
            lambda prompt: "NO_CHANGES"
        )
        return editor.edit(instruction, generate_fn)

    # ── PUBLIC: add feature to existing app ───────────────────────
    def add_feature(self, project_path: str, feature: str) -> list:
        """Add a new feature to an existing generated project.

        Returns a list of file paths that were created/changed.
        """
        from core.ai.editor import AppEditor
        editor = AppEditor(project_path)
        generate_fn = self.llm.generate if not self.dry_run else (
            lambda prompt: '{"files":[]}'
        )
        return editor.add_feature(feature, generate_fn)

    # ── PUBLIC: full-stack ────────────────────────────────────────
    def generate_fullstack(self, name: str, request: str, output_dir: str = ".") -> str:
        from core.ai.fullstack_pipeline import run_fullstack_generation
        from core.ai.fullstack_pipeline import run_fullstack_generation
        from core.ai.senior_team import tech_lead_review, backend_review, frontend_review, final_review, apply_corrections
        if self.dry_run:
            print("\n[dry-run] Would run: 8-step full-stack pipeline")
            steps = [
                "DeepSeek R1  → classify project type",
                "DeepSeek R1  → architecture + API contract",
                "Qwen Coder   → database schema",
                "Qwen Coder   → backend code",
                "Qwen Coder   → frontend code",
                "Qwen Coder   → test suite",
                "Decoder 14B  → config files (.env, docker-compose)",
                "Decoder 14B  → merge + format all files",
            ]
            for i, s in enumerate(steps, 1):
                print(f"  Step {i}: {s}")
            data = self._dry_run_data(name)
            project_path = str(Path(output_dir) / name)
            path = self._write_files(project_path, data["files"])
            print(f"\n  ✅ Dry-run complete. Placeholder files at: {path}")
            return path

        import time as _time
        _start = _time.time()
        print(f"\n🏗️  Full-Stack Generation: '{name}'\n")
        ctx  = run_fullstack_generation(request)
        spec = ctx.get("spec", {})

        # Python merge — guaranteed lossless, keeps every file
        data = self._merge_file_lists(
            ctx.get("backend_files", ""),
            ctx.get("frontend_files", ""),
            ctx.get("test_files", ""),
            ctx.get("config_files", ""),
        )
        if not data.get("files"):
            raise Exception("No files were generated — all pipeline steps may have failed.")

        # ── SENIOR TEAM REVIEW ────────────────────────────────────
        complexity = spec.get("complexity", "moderate")
        run_reviews = complexity in ("complex", "advanced")

        if run_reviews and data.get("files"):
            print(f"\n  👥  Senior Team Review ({complexity} project)...")
            import json as _json

            # Backend lead reviews backend files
            backend_files = [f for f in data["files"] if str(f.get("path","")).startswith("backend/")]
            if backend_files:
                print("     Backend Lead reviewing...")
                try:
                    backend_fixes = backend_review(_json.dumps({"files": backend_files[:5]}), spec)
                    if backend_fixes:
                        data["files"] = apply_corrections(data["files"], backend_fixes)
                except Exception as e:
                    print(f"     ⚠️  Backend review error: {e}")

            # Frontend lead reviews frontend files
            frontend_files = [f for f in data["files"] if str(f.get("path","")).startswith("frontend/")]
            if frontend_files:
                print("     Frontend Lead reviewing...")
                try:
                    frontend_fixes = frontend_review(_json.dumps({"files": frontend_files[:5]}), spec)
                    if frontend_fixes:
                        data["files"] = apply_corrections(data["files"], frontend_fixes)
                except Exception as e:
                    print(f"     ⚠️  Frontend review error: {e}")

            # Final security + quality check
            print("     Final security review...")
            try:
                final_result = final_review(data["files"], spec)
                score = final_result.get("confidence_score", 75)
                print(f"\n  📊 Quality Score: {score}/100")
            except Exception as e:
                print(f"     ⚠️  Final review error: {e}")
        else:
            print(f"\n  ⚡ Fast mode ({complexity}) — skipping peer review")

        if not data.get("files"):
            raise Exception("No files were generated.")

        print(f"\n📂 Writing {len(data['files'])} files...")
        project_path = str(Path(output_dir) / name)
        path = self._write_files(project_path, data["files"])
        # Auto-fix common generation errors
        from core.ai.post_fixer import fix_project, print_run_instructions
        fix_project(path, request=request, spec=spec)
        self._ensure_entry_point(path, spec.get("project_type", "unknown"))
        self._install_deps(path)

        print("\n📁 Project structure:")
        for f in sorted(data["files"], key=lambda x: x["path"]):
            print(f"  - {f['path']}")

        self._auto_debug(path, data, app_type=spec.get("project_type", "auto"))
        print_run_instructions(path)
        return path
