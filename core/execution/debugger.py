# core/execution/debugger.py
# Debugger — builds debug prompts, now aware of which model will handle them.

from core.ai.model_router import get_model


class Debugger:

    def build_debug_prompt(self, code: str, error: str) -> str:
        """
        Build a fix prompt for Qwen2.5 Coder 14B.
        The reasoner (DeepSeek R1 14B) analyses first in the pipeline,
        then this prompt is handed to the coder for the actual fix.
        """
        return f"""
You are a senior Python engineer fixing a broken project.

The project failed with this error:
{error}

Fix all issues in the project files below.

Return ONLY valid JSON:
{{
  "files": [
    {{"path": "file.py", "content": "fixed code here"}}
  ]
}}

No explanations. No markdown. Raw JSON only.

Project code:
{code}
"""

    def build_analysis_prompt(self, code: str, error: str) -> str:
        """
        Build an analysis prompt for DeepSeek R1 14B (reasoner).
        Used in the first step of the debug pipeline.
        """
        return f"""
You are a debugging expert.

Analyse this runtime error and describe exactly what code changes are needed.

Error:
{error}

Project code:
{code}
"""
