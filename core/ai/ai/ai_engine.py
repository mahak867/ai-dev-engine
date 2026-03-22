# core/ai/ai_engine.py
# High-level AI interface — all calls go through provider.py
# which automatically routes to Ollama or Groq.

from core.ai.model_router import route, get_model
from core.ai.provider import generate
from core.ai.pipeline import Pipeline, build_project_pipeline, build_debug_pipeline


class AIEngine:

    def generate_text(self, prompt: str) -> str:
        model = route(prompt)
        print(f"  [Router] {model}")
        return generate(model, prompt)

    def generate_with_task(self, prompt: str, task_type: str) -> str:
        model = get_model(task_type)
        print(f"  [Task:{task_type}] {model}")
        return generate(model, prompt)

    def plan(self, prompt: str) -> str:
        return self.generate_with_task(prompt, "reasoner")

    def code(self, prompt: str) -> str:
        return self.generate_with_task(prompt, "coder")

    def review(self, prompt: str) -> str:
        return self.generate_with_task(prompt, "reasoner")

    def decode(self, prompt: str) -> str:
        return self.generate_with_task(prompt, "decoder")

    def chat(self, prompt: str) -> str:
        return self.generate_with_task(prompt, "general")

    def run_project_pipeline(self, request: str) -> dict:
        pipeline = build_project_pipeline()
        return pipeline.run({"request": request})

    def run_debug_pipeline(self, code: str, error: str) -> dict:
        pipeline = build_debug_pipeline()
        return pipeline.run({"code": code, "error": error})

    def run_custom_pipeline(self, pipeline: Pipeline, context: dict) -> dict:
        return pipeline.run(context)
