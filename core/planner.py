# core/planner.py
# Planning module — uses DeepSeek R1 14B for deep reasoning & task breakdown.

from core.ai.model_router import get_model
from core.ai.provider import generate


def create_plan(goal: str) -> list:
    """
    Break a development goal into numbered tasks.
    Uses DeepSeek R1 14B (reasoner) for deep reasoning.
    """
    model = get_model("reasoner")

    prompt = f"""
You are a senior software architect.

Break the following development goal into a numbered list of clear, 
specific, actionable tasks that a developer can implement one by one.

Goal:
{goal}

Return ONLY the numbered task list. No explanations.
"""

    result = generate(model, prompt)
    tasks = [t.strip() for t in result.split("\n") if t.strip()]
    return tasks


def create_architecture(request: str) -> str:
    """
    Design detailed software architecture for a project request.
    Uses DeepSeek R1 14B (reasoner).
    """
    model = get_model("reasoner")

    prompt = f"""
You are a senior software architect.

Design a complete architecture for the following project.

Include:
- Project folder structure
- Key modules and their responsibilities
- Technologies and libraries to use
- Data flow between components
- Any important design decisions

Project request:
{request}
"""

    return generate(model, prompt)
