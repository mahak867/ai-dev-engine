# core/ai/editor.py
# Multi-file editor - modify an existing generated app
# "add dark mode", "add Stripe", "add search" etc.

import os
import json
from pathlib import Path
from typing import Optional


class AppEditor:
    """
    Edit an existing generated app without full regeneration.
    Reads existing files, generates targeted patches, applies them.
    """

    def __init__(self, project_path: str):
        self.path = Path(project_path)
        self.files = self._read_project()

    def _read_project(self) -> dict:
        """Read all source files from the project."""
        files = {}
        for ext in ["*.py", "*.jsx", "*.js", "*.css", "*.json", "*.md"]:
            for f in self.path.rglob(ext):
                # Skip node_modules and __pycache__
                if any(skip in str(f) for skip in ["node_modules", "__pycache__", ".git"]):
                    continue
                try:
                    rel = str(f.relative_to(self.path))
                    files[rel] = f.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    pass
        return files

    def edit(self, instruction: str, generate_fn) -> dict:
        """
        Apply an edit instruction to the project.
        Returns dict of changed files.
        """
        print(f"\n  Editing: {instruction}")
        print(f"  Reading {len(self.files)} existing files...")

        # Identify which files need changing
        relevant = self._identify_relevant_files(instruction)
        print(f"  Targeting {len(relevant)} files for edit")

        # Generate patch
        changed = {}
        for filepath, content in relevant.items():
            patched = self._patch_file(filepath, content, instruction, generate_fn)
            if patched and patched != content:
                changed[filepath] = patched
                full_path = self.path / filepath
                full_path.write_text(patched, encoding="utf-8")
                print(f"  [Editor] Updated: {filepath}")

        if not changed:
            print(f"  [Editor] No changes needed")

        return changed

    def _identify_relevant_files(self, instruction: str) -> dict:
        """Figure out which files need to change for this instruction."""
        inst = instruction.lower()
        relevant = {}

        # Dark mode -> index.css + components with theme
        if "dark mode" in inst or "theme" in inst:
            for path, content in self.files.items():
                if path.endswith("index.css") or "App.jsx" in path or "Navbar" in path:
                    relevant[path] = content

        # Stripe -> payment routes + checkout component
        elif "stripe" in inst or "payment" in inst:
            for path, content in self.files.items():
                if "payment" in path.lower() or "checkout" in path.lower() or "app.py" in path:
                    relevant[path] = content

        # Search -> search component + backend search route
        elif "search" in inst:
            for path, content in self.files.items():
                if "routes" in path or "pages" in path.lower():
                    relevant[path] = content

        # Auth -> main.jsx + protected routes + auth routes
        elif "auth" in inst or "login" in inst or "clerk" in inst:
            for path, content in self.files.items():
                if "main.jsx" in path or "App.jsx" in path or "auth" in path.lower():
                    relevant[path] = content

        # Default: identify by keyword matching
        else:
            keywords = inst.split()
            for path, content in self.files.items():
                if any(kw in content.lower() for kw in keywords if len(kw) > 3):
                    relevant[path] = content

        # Always limit to most relevant files
        if len(relevant) > 5:
            # Prioritize by relevance
            relevant = dict(list(relevant.items())[:5])

        return relevant

    def _patch_file(self, filepath: str, content: str,
                    instruction: str, generate_fn) -> Optional[str]:
        """Generate a patch for a single file."""
        prompt = f"""Edit this file to: {instruction}

FILE: {filepath}
CURRENT CONTENT:
{content[:2000]}

Rules:
- Make ONLY the changes needed for the instruction
- Keep all existing functionality intact
- Return the COMPLETE updated file
- No markdown fences, no explanation
- If no changes needed, return exactly: NO_CHANGES"""

        try:
            result = generate_fn(prompt).strip()
            if result == "NO_CHANGES" or not result:
                return None
            if result.startswith("```"):
                result = "\n".join(result.split("\n")[1:]).rstrip("`").strip()
            return result
        except Exception as e:
            print(f"  [Editor] Patch failed for {filepath}: {e}")
            return None

    def add_feature(self, feature: str, generate_fn) -> list:
        """
        Add a complete new feature (new files + modifications).
        Returns list of new/changed files.
        """
        # Build context from existing project
        project_summary = []
        for path, content in list(self.files.items())[:8]:
            project_summary.append(f"FILE: {path}\n{content[:300]}")

        prompt = f"""Add this feature to an existing Flask+React app: {feature}

EXISTING PROJECT:
{chr(10).join(project_summary)}

Generate ONLY the new/changed files needed.
Return JSON: {{"files":[{{"path":"backend/routes/new.py","content":"..."}}]}}"""

        try:
            result = generate_fn(prompt).strip()
            if result.startswith("```"):
                result = "\n".join(result.split("\n")[1:]).rstrip("`").strip()
            start = result.find("{")
            end = result.rfind("}") + 1
            data = json.loads(result[start:end])
            files = data.get("files", [])

            # Write new files
            written = []
            for f in files:
                fp = self.path / f["path"]
                fp.parent.mkdir(parents=True, exist_ok=True)
                fp.write_text(f["content"], encoding="utf-8")
                written.append(f["path"])
                print(f"  [Editor] Added: {f['path']}")

            return written
        except Exception as e:
            print(f"  [Editor] Feature add failed: {e}")
            return []
