from core.ai.groq_provider import generate as _groq_generate
def generate(model: str, prompt: str) -> str:
    return _groq_generate(model, prompt)
