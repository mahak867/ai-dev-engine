# core/reviewer.py
# Code review module — uses DeepSeek R1 14B for deep analysis.

from core.ai.model_router import get_model
from core.ai.provider import generate


def review_code(data: dict) -> str:
    """
    Review and improve generated project code.
    Uses DeepSeek R1 14B (reasoner) for deep analysis.
    Returns raw JSON string with improved files.
    """
    import json
    model = get_model("reasoner")

    prompt = f"""
You are a senior code reviewer.

Review the following generated project. Your job:
- Fix any bugs or logic errors
- Fix missing imports
- Improve code structure and readability
- Ensure all files are complete and runnable

Return the corrected project as valid JSON:
{{
  "files": [
    {{"path": "file.py", "content": "corrected code"}}
  ]
}}

No explanations. Raw JSON only.

Project to review:
{json.dumps(data)}
"""

    return generate(model, prompt)


def analyse_error(code: str, error: str) -> str:
    """
    Deeply analyse a runtime error and describe what needs fixing.
    Uses DeepSeek R1 14B (reasoner).
    """
    model = get_model("reasoner")

    prompt = f"""
You are a debugging expert.

A project failed at runtime with the following error.
Analyse the root cause and describe exactly what code changes are needed to fix it.

Error:
{error}

Project code:
{code}
"""

    return generate(model, prompt)
