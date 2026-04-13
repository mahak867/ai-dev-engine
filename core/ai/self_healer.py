# core/ai/self_healer.py
# Self-healing generation loop
# If generated code fails syntax/import checks, retry with the error as context

import ast
import re
import json
import subprocess
import sys
from pathlib import Path


class SelfHealer:
    """
    Runs syntax checks on generated files and retries generation
    with error context if they fail. Like having a compiler in the loop.
    """

    MAX_HEAL_ATTEMPTS = 2

    def heal_backend(self, files: list, generate_fn) -> list:
        """Check backend Python files, heal any with syntax errors."""
        healed = list(files)
        errors_found = []

        for f in healed:
            path = f.get("path", "")
            content = f.get("content", "")
            if not path.endswith(".py") or not content:
                continue

            error = self._check_python_syntax(content)
            if error:
                errors_found.append({"file": path, "error": error, "content": content})

        if not errors_found:
            return healed

        print(f"  [Healer] Found {len(errors_found)} syntax error(s) - attempting auto-fix...")

        for attempt in range(self.MAX_HEAL_ATTEMPTS):
            for err_info in errors_found:
                fixed_content = self._fix_python_file(
                    err_info["file"],
                    err_info["content"],
                    err_info["error"],
                    generate_fn,
                    attempt
                )
                if fixed_content:
                    # Update in healed list
                    for f in healed:
                        if f.get("path") == err_info["file"]:
                            f["content"] = fixed_content
                            print(f"  [Healer] Fixed: {err_info['file']}")
                    err_info["content"] = fixed_content
                    err_info["error"] = self._check_python_syntax(fixed_content)

            # Check if all fixed
            remaining = [e for e in errors_found if e.get("error")]
            if not remaining:
                print(f"  [Healer] All syntax errors fixed!")
                break

        return healed

    def heal_frontend(self, files: list, generate_fn) -> list:
        """Check frontend JSX/JS files for common errors."""
        healed = list(files)
        errors_found = []

        for f in healed:
            path = f.get("path", "")
            content = f.get("content", "")
            if not (path.endswith(".jsx") or path.endswith(".js")):
                continue
            if not content:
                continue

            errors = self._check_jsx_patterns(content, path)
            if errors:
                errors_found.append({"file": path, "errors": errors, "content": content})

        if not errors_found:
            return healed

        print(f"  [Healer] Found {len(errors_found)} JSX issue(s) - auto-patching...")

        for err_info in errors_found:
            patched = self._patch_jsx(err_info["content"], err_info["errors"])
            for f in healed:
                if f.get("path") == err_info["file"]:
                    f["content"] = patched
            print(f"  [Healer] Patched: {err_info['file']} ({len(err_info['errors'])} fixes)")

        return healed

    def _check_python_syntax(self, content: str) -> str:
        """Return error message if Python has syntax error, else empty string."""
        try:
            ast.parse(content)
            return ""
        except SyntaxError as e:
            return f"Line {e.lineno}: {e.msg}"
        except Exception as e:
            return str(e)

    def _fix_python_file(self, filepath: str, content: str, error: str,
                          generate_fn, attempt: int) -> str:
        """Ask AI to fix a specific Python syntax error."""
        prompt = f"""Fix this Python syntax error. Return ONLY the corrected Python code, no markdown.

FILE: {filepath}
ERROR: {error}

CURRENT CODE:
{content[:3000]}

Rules:
- Fix ONLY the syntax error, don't rewrite everything
- Keep all existing logic intact
- Return complete corrected file content
- No markdown fences, no explanation"""

        try:
            result = generate_fn(prompt)
            # Strip markdown if present
            result = result.strip()
            if result.startswith("```"):
                lines = result.split("\n")
                result = "\n".join(lines[1:])
                result = result.rstrip("`").strip()

            # Verify fix worked
            fixed_error = self._check_python_syntax(result)
            if not fixed_error:
                return result
            print(f"  [Healer] Fix attempt {attempt+1} didn't resolve error: {fixed_error}")
            return ""
        except Exception as e:
            print(f"  [Healer] Fix generation failed: {e}")
            return ""

    def _check_jsx_patterns(self, content: str, filepath: str) -> list:
        """Check for common JSX/React errors that can be auto-patched."""
        errors = []

        # Missing key prop in map
        if ".map(" in content and "key=" not in content and filepath != "main.jsx":
            errors.append(("missing_key", "Missing key prop in .map()"))

        # path="/:" typo
        if 'path="/:"' in content or "path='/:'":
            errors.append(("path_typo", 'path="/:" should be path="/"'))

        # from app import - wrong import
        if "from 'app'" in content or 'from "app"' in content:
            errors.append(("bad_import", "Importing from 'app' - should use relative path"))

        # http:// hardcoded instead of api.js
        if "fetch('http://localhost:5000" in content or 'fetch("http://localhost:5000' in content:
            errors.append(("hardcoded_url", "Hardcoded API URL - use api.js service"))

        return errors

    def _patch_jsx(self, content: str, errors: list) -> str:
        """Apply mechanical patches for known JSX issues."""
        for error_type, _ in errors:
            if error_type == "path_typo":
                content = content.replace('path="/:"', 'path="/"')
                content = content.replace("path='/:'", "path='/'")

            elif error_type == "hardcoded_url":
                # Replace direct fetch calls with api.js pattern
                import re
                content = re.sub(
                    r"fetch\(['\"]http://localhost:5000/api/v1([^'\"]*)['\"]",
                    r"fetch('/api/v1\1'",
                    content
                )

        return content

    def check_imports(self, files: list) -> list:
        """Check for obviously broken imports across all Python files."""
        issues = []
        file_names = {Path(f["path"]).name for f in files if f.get("path")}

        for f in files:
            path = f.get("path", "")
            content = f.get("content", "")
            if not path.endswith(".py"):
                continue

            # Check from X import Y where X.py doesn't exist in project
            imports = re.findall(r"^from (\w+) import", content, re.MULTILINE)
            for imp in imports:
                if imp in ("flask", "flask_sqlalchemy", "flask_bcrypt", "flask_cors",
                           "extensions", "config", "models", "utils", "routes",
                           "os", "sys", "json", "re", "time", "datetime",
                           "functools", "enum", "uuid", "hashlib", "base64"):
                    continue
                if f"{imp}.py" not in file_names and imp not in file_names:
                    issues.append(f"{path}: 'from {imp} import' - {imp}.py not in project")

        return issues


def heal_generated_project(files: list, generate_fn=None) -> list:
    """Main entry point - heal all files in a generated project."""
    healer = SelfHealer()

    if not files:
        return files

    # Heal backend Python
    backend = [f for f in files if str(f.get("path","")).startswith("backend/")]
    frontend = [f for f in files if str(f.get("path","")).startswith("frontend/")]
    other = [f for f in files if not str(f.get("path","")).startswith(("backend/","frontend/"))]

    if backend and generate_fn:
        backend = healer.heal_backend(backend, generate_fn)

    if frontend:
        frontend = healer.heal_frontend(frontend, generate_fn)

    # Check imports
    all_files = backend + frontend + other
    import_issues = healer.check_imports(backend)
    if import_issues:
        print(f"  [Healer] Import warnings ({len(import_issues)}):")
        for issue in import_issues[:3]:
            print(f"     - {issue}")

    return all_files
