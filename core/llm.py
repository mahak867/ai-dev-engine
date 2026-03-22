# core/llm.py
from core.ai.ai_engine import AIEngine


class LLMClient:
    """
    Unified LLM client.
    All calls route to the correct model automatically:
      plan/review   → deepseek-r1:14b
      code          → qwen2.5-coder:14b
      decode/format → decoder:14b
      chat/general  → qwen3:9b
    """

    def __init__(self):
        self.engine = AIEngine()

    def plan(self, prompt: str) -> str:
        return self.engine.plan(prompt)

    def code(self, prompt: str) -> str:
        return self.engine.code(prompt)

    def review(self, prompt: str) -> str:
        return self.engine.review(prompt)

    def decode(self, prompt: str) -> str:
        return self.engine.decode(prompt)

    def chat(self, prompt: str) -> str:
        return self.engine.chat(prompt)

    def generate(self, prompt: str) -> str:
        return self.engine.generate_text(prompt)

    def run_project_pipeline(self, request: str) -> dict:
        return self.engine.run_project_pipeline(request)

    def run_debug_pipeline(self, code: str, error: str) -> dict:
        return self.engine.run_debug_pipeline(code, error)
