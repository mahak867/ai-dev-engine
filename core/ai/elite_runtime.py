import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from core.ai.doctor import run_doctor
from core.ai.tool_registry import ToolRegistry


class EliteRuntime:
    """
    Lightweight autonomous loop for local project execution.
    Stages:
    1. Inspect
    2. Plan
    3. Validate
    4. Finalize
    """

    def __init__(self, project_path: str, openrouter_key: str = "", groq_key: str = ""):
        self.project_path = Path(project_path).resolve()
        self.openrouter_key = openrouter_key
        self.groq_key = groq_key
        self.tools = ToolRegistry(
            str(self.project_path),
            granted_permissions={"file.read", "file.write", "shell", "git", "web"},
        )
        self.events: List[Dict[str, str]] = []

    def _event(self, stage: str, detail: str):
        self.events.append(
            {
                "time": datetime.now().isoformat(timespec="seconds"),
                "stage": stage,
                "detail": detail,
            }
        )

    def _inspect(self) -> Dict[str, object]:
        self._event("inspect", "Scanning key files and docs.")
        readme = self.project_path / "README.md"
        docs_elite = self.project_path / "docs" / "elite"
        return {
            "project": self.project_path.name,
            "readme_exists": readme.exists(),
            "elite_docs_exists": docs_elite.exists(),
            "python_files": len(list(self.project_path.rglob("*.py"))),
            "web_files": len(list((self.project_path / "web").glob("*"))) if (self.project_path / "web").exists() else 0,
        }

    def _plan(self, summary: Dict[str, object]) -> Dict[str, object]:
        self._event("plan", "Creating execution agenda from current project shape.")
        actions = [
            "Run doctor and capture score",
            "Ensure elite docs exist",
            "Run syntax checks",
            "Prepare release notes",
        ]
        if not summary.get("elite_docs_exists"):
            actions.insert(1, "Generate missing elite docs")
        return {"actions": actions, "priority": "high"}

    def _validate(self) -> Dict[str, object]:
        self._event("validate", "Running doctor checks and syntax validation.")
        doctor = run_doctor(self.project_path, self.openrouter_key, self.groq_key)
        syntax_ok = True
        syntax_msg = "No python files found"
        py_files = list(self.project_path.rglob("*.py"))
        if py_files:
            compile_cmd = ["py", "-m", "py_compile"] + [str(p) for p in py_files[:60]]
            result = self.tools.call("bash", command=" ".join(compile_cmd), cwd=".")
            syntax_ok = "Traceback" not in result and "SyntaxError" not in result and "Error" not in result
            syntax_msg = "syntax ok" if syntax_ok else result[:280]
        return {"doctor": doctor, "syntax_ok": syntax_ok, "syntax_message": syntax_msg}

    def _finalize(self, summary: Dict[str, object], plan: Dict[str, object], validation: Dict[str, object]) -> Dict[str, object]:
        self._event("finalize", "Writing runtime report.")
        report = {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "summary": summary,
            "plan": plan,
            "validation": validation,
            "events": self.events,
        }
        target = self.project_path / "docs" / "elite" / "runtime-report.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, indent=2), encoding="utf-8")
        return {"report_path": str(target), "doctor_score": validation["doctor"].get("score", 0)}

    def run(self) -> Dict[str, object]:
        summary = self._inspect()
        plan = self._plan(summary)
        validation = self._validate()
        final = self._finalize(summary, plan, validation)
        return {
            "ok": True,
            "summary": summary,
            "plan": plan,
            "validation": validation,
            "final": final,
        }
