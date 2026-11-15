"""
APEX Society — a 9-agent AI software team.

    import apex
    result = apex.generate("todo API with tests", name="todo")
"""
from apex.api import GenerationResult, generate

__version__ = "4.0.0"
__all__ = ["GenerationResult", "generate", "__version__"]
