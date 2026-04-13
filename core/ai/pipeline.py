from dataclasses import dataclass
from typing import Callable

@dataclass
class PipelineStep:
    name: str
    task_type: str
    prompt_fn: Callable
    output_key: str

class Pipeline:
    def __init__(self, steps: list, verbose: bool = True):
        self.steps = steps
        self.verbose = verbose

    def run(self, ctx: dict) -> dict:
        for i, step in enumerate(self.steps, 1):
            if self.verbose:
                from core.ai.model_router import get_model
                model = get_model(step.task_type)
                print(f"  Pipeline step {i}/{len(self.steps)}: {step.name}")
                print(f"     model: {model}")
            try:
                from core.ai.provider import generate
                from core.ai.model_router import get_model
                model = get_model(step.task_type)
                prompt = step.prompt_fn(ctx)
                result = generate(model, prompt)
                ctx[step.output_key] = result
            except Exception as e:
                print(f"  [Pipeline] Step failed: {e}")
                ctx[step.output_key] = ""
        return ctx
