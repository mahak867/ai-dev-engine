# core/ai/ollama_provider.py
import os
import requests
from core.ai.response_cleaner import clean

OLLAMA_URL = "http://localhost:11434/api/generate"
_RESOLVED: dict = {}

def set_resolved_models(resolved: dict):
    global _RESOLVED
    _RESOLVED = resolved

def _resolve(model: str) -> str:
    if model in _RESOLVED:
        return _RESOLVED[model]
    for resolved_name in _RESOLVED.values():
        if resolved_name.startswith(model.split(":")[0]):
            return resolved_name
    return model

def generate(model: str, prompt: str, clean_output: bool = True) -> str:
    model = _resolve(model)
    print(f"    [Ollama] Calling {model}...")
    try:
        response = requests.post(
            OLLAMA_URL,
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=1200,
        )
        response.raise_for_status()
        raw = response.json().get("response", "")
        print(f"    [Ollama] {model} responded.")
        return clean(raw) if clean_output else raw
    except requests.exceptions.ConnectionError:
        raise ConnectionError("Cannot reach Ollama. Run: ollama serve")
    except requests.exceptions.Timeout:
        raise TimeoutError(f"Model '{model}' timed out. Try closing other apps.")
    except Exception as e:
        raise RuntimeError(f"Ollama error [{model}]: {e}")
