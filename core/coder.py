# core/coder.py
# Code generation module — uses Qwen2.5 Coder 14B.

from core.ai.model_router import get_model
from core.ai.provider import generate


def generate_code(task: str) -> str:
    """
    Generate code for a single task.
    Uses Qwen2.5 Coder 14B (coder model).
    """
    model = get_model("coder")

    prompt = f"""
You are an expert software developer.

Write clean, complete, production-ready code for this task:

{task}

Return only the code. No explanations. No markdown fences.
"""

    return generate(model, prompt)


def generate_project_files(request: str, architecture: str) -> str:
    """
    Generate full project source files based on architecture plan.
    Uses Qwen2.5 Coder 14B (coder model).
    Returns raw JSON string.
    """
    model = get_model("coder")

    prompt = f"""
You are an autonomous software engineer.

Generate the COMPLETE project source code based on the architecture below.

Return ONLY valid JSON in this exact format:
{{
  "files": [
    {{"path": "relative/path/file.py", "content": "full file content here"}}
  ]
}}

No explanations. No markdown. Raw JSON only.

Architecture:
{architecture}

Project request:
{request}
"""

    return generate(model, prompt)


def fix_code(code: str, error: str) -> str:
    """
    Fix broken code given an error message.
    Uses Qwen2.5 Coder 14B (coder model).
    Returns raw JSON string with fixed files.
    """
    model = get_model("coder")

    prompt = f"""
You are an expert Python engineer fixing a broken project.

The project failed with the following error:
{error}

Fix all issues in the project code below.

Return ONLY valid JSON:
{{
  "files": [
    {{"path": "file.py", "content": "fixed code here"}}
  ]
}}

Project code:
{code}
"""

    return generate(model, prompt)
