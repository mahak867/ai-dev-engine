# core/ai/provider.py
# Unified provider interface — delegates to provider_factory for all routing.
# This is the single generate() that all engine modules import.

def set_provider(provider: str):
    from core.ai.provider_factory import set_provider as _set
    _set(provider)

def get_provider() -> str:
    from core.ai.provider_factory import get_provider as _get
    return _get()

def auto_detect_provider() -> str:
    from core.ai.provider_factory import auto_detect
    auto_detect()
    return get_provider()

def generate(model: str, prompt: str, clean_output: bool = True) -> str:
    """
    Route generate() to the active provider (set via provider_factory).
    model: task type key ('general','coder','decoder','reasoner') or full model name.
    """
    from core.ai.provider_factory import generate as _generate
    return _generate(model, prompt, clean_output)
