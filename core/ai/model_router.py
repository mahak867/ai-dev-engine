# core/ai/model_router.py

# ── Local Ollama models ───────────────────────────────────────────
MODELS = {
    "general":  "qwen3.5:9b",
    "coder":    "qwen2.5-coder:14b",
    "decoder":  "deepcoder:14b",
    "reasoner": "deepseek-r1:14b",
}

# ── Groq cloud models ─────────────────────────────────────────────
GROQ_MODELS = {
    "general":  "llama-3.3-70b-versatile",
    "coder":    "qwen/qwen3-32b",
    "decoder":  "llama-3.3-70b-versatile",
    "reasoner": "moonshotai/kimi-k2-instruct",
}

_CODING_KEYWORDS = [
    "write code", "generate code", "implement", "function", "class",
    "debug", "fix bug", "refactor", "unit test", "script", "module",
    "def ", "import ", "return ", "syntax", "compile", "program",
]

_REASONING_KEYWORDS = [
    "architect", "design", "plan", "strategy", "analyse", "analyze",
    "tradeoff", "compare", "evaluate", "explain why", "reasoning",
    "logic", "decision", "structure", "approach", "best practice",
]

_DECODER_KEYWORDS = [
    "format", "summarise", "summarize", "convert", "transform",
    "rewrite", "clean up", "beautify", "decode", "parse output",
    "produce json", "return json", "output as",
]


def get_provider() -> str:
    """Returns the active provider as set by provider_factory."""
    from core.ai.provider_factory import get_provider as _get
    return _get()


def route(prompt: str) -> str:
    """Auto-route prompt to best model name based on content."""
    lowered = prompt.lower()
    if any(kw in lowered for kw in _CODING_KEYWORDS):
        task = "coder"
    elif any(kw in lowered for kw in _REASONING_KEYWORDS):
        task = "reasoner"
    elif any(kw in lowered for kw in _DECODER_KEYWORDS):
        task = "decoder"
    else:
        task = "general"
    return get_model(task)


def get_model(task_type: str) -> str:
    """Get model name for a task type based on active provider."""
    if task_type not in MODELS:
        raise ValueError(f"Unknown task type '{task_type}'. Valid: {list(MODELS.keys())}")
    if get_provider() == "groq":
        return GROQ_MODELS[task_type]
    return MODELS[task_type]


def get_task_model(task_type: str, provider: str = None) -> str:
    """Get model name for explicit provider override."""
    provider = provider or get_provider()
    if task_type not in MODELS:
        raise ValueError(f"Unknown task type '{task_type}'.")
    return GROQ_MODELS[task_type] if provider == "groq" else MODELS[task_type]
