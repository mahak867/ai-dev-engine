from core.ai.groq_provider import GROQ_MODELS
def get_model(task_type: str) -> str:
    return GROQ_MODELS.get(task_type, GROQ_MODELS["general"])
