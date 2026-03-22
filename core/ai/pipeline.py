# core/ai/pipeline.py
# Optional multi-model pipeline for complex operations that need more than one model.

import time
from typing import List, Dict, Any, Optional, Callable
from core.ai.model_router import get_model, route
from core.ai.provider import generate


class PipelineStep:
    def __init__(
        self,
        name: str,
        prompt_fn: Callable[[Dict[str, Any]], str],
        output_key: str,
        task_type: Optional[str] = None,
    ):
        self.name = name
        self.prompt_fn = prompt_fn
        self.output_key = output_key
        self.task_type = task_type


class Pipeline:
    def __init__(self, steps: List[PipelineStep], verbose: bool = True):
        self.steps = steps
        self.verbose = verbose

    def run(self, initial_context: Dict[str, Any]) -> Dict[str, Any]:
        context = dict(initial_context)
        for i, step in enumerate(self.steps, start=1):
            if self.verbose:
                print(f"  ⚙️  Pipeline step {i}/{len(self.steps)}: {step.name}")
            prompt = step.prompt_fn(context)
            model = get_model(step.task_type) if step.task_type else route(prompt)
            if self.verbose:
                print(f"     └─ model: {model}")
            # Auto-retry on Groq rate limit with backoff
            for attempt in range(3):
                try:
                    output = generate(model, prompt)
                    break
                except RuntimeError as e:
                    if "rate limit" in str(e).lower() and attempt < 2:
                        wait = 60 * (attempt + 1)
                        print(f"     Rate limit hit — waiting {wait}s then retrying...")
                        time.sleep(wait)
                    else:
                        raise
            context[step.output_key] = output
        return context


def build_project_pipeline() -> Pipeline:
    """
    4-step pipeline for full project generation:
      1. Architecture Design  → DeepSeek R1 14B  (reasoner)
      2. Code Generation      → Qwen2.5 Coder 14B (coder)
      3. Code Review          → DeepSeek R1 14B  (reasoner)
      4. Output Formatting    → Decoder 14B      (decoder)
    """
    steps = [
        PipelineStep(
            name="Architecture Design",
            task_type="reasoner",
            prompt_fn=lambda ctx: (
                "You are a senior software architect.\n\n"
                "Design a clear architecture for this project.\n\n"
                "Include: project structure, key modules, technologies, "
                "data flow, and important design decisions.\n\n"
                f"Project request:\n{ctx['request']}"
            ),
            output_key="architecture",
        ),
        PipelineStep(
            name="Code Generation",
            task_type="coder",
            prompt_fn=lambda ctx: (
                "You are an expert software engineer.\n\n"
                "Generate the COMPLETE project source code.\n\n"
                'Return ONLY valid JSON: {"files":[{"path":"path.py","content":"code"}]}\n\n'
                f"Architecture plan:\n{ctx['architecture']}\n\n"
                f"Project request:\n{ctx['request']}"
            ),
            output_key="raw_code",
        ),
        PipelineStep(
            name="Code Review & Bug Analysis",
            task_type="reasoner",
            prompt_fn=lambda ctx: (
                "You are a senior code reviewer.\n\n"
                "Review the project. Fix bugs, missing imports, bad practices.\n\n"
                'Return corrected project as JSON: {"files":[{"path":"path.py","content":"code"}]}\n\n'
                f"Code to review:\n{ctx['raw_code']}"
            ),
            output_key="reviewed_code",
        ),
        PipelineStep(
            name="Final Output Formatting",
            task_type="decoder",
            prompt_fn=lambda ctx: (
                "You are an output formatter.\n\n"
                "Clean and validate the following JSON. Fix syntax errors. "
                "Strip markdown fences. Return ONLY raw valid JSON.\n\n"
                f"Input:\n{ctx['reviewed_code']}"
            ),
            output_key="final_output",
        ),
    ]
    return Pipeline(steps=steps, verbose=True)


def build_debug_pipeline() -> Pipeline:
    """
    2-step debug pipeline:
      1. Error Analysis → DeepSeek R1 14B (reasoner)
      2. Apply Fix      → Qwen2.5 Coder 14B (coder)
    """
    steps = [
        PipelineStep(
            name="Error Analysis",
            task_type="reasoner",
            prompt_fn=lambda ctx: (
                "You are a debugging expert.\n\n"
                "Analyse this runtime error and describe exactly what needs to be fixed.\n\n"
                f"Error:\n{ctx['error']}\n\n"
                f"Project code:\n{ctx['code']}"
            ),
            output_key="analysis",
        ),
        PipelineStep(
            name="Apply Fix",
            task_type="coder",
            prompt_fn=lambda ctx: (
                "You are an expert Python engineer.\n\n"
                "Apply the fix to the project code.\n\n"
                'Return ONLY valid JSON: {"files":[{"path":"file.py","content":"fixed code"}]}\n\n'
                f"Fix analysis:\n{ctx['analysis']}\n\n"
                f"Original code:\n{ctx['code']}"
            ),
            output_key="fixed_code",
        ),
    ]
    return Pipeline(steps=steps, verbose=True)
