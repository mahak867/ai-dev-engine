# core/ai/parallel_gen.py
# Parallel generation - backend and frontend generated simultaneously
# 2x faster than sequential pipeline

import threading
import time
from typing import Callable


class ParallelGenerator:
    """
    Runs backend and frontend generation in parallel threads.
    Both get the architecture + schema as input, generate concurrently,
    then results are merged.
    """

    def __init__(self):
        self._results = {}
        self._errors = {}
        self._lock = threading.Lock()

    def run(self, tasks: dict[str, Callable]) -> dict[str, str]:
        """
        tasks = {"backend_files": fn, "frontend_files": fn, ...}
        Returns {"backend_files": result, "frontend_files": result, ...}
        """
        threads = []
        for name, fn in tasks.items():
            t = threading.Thread(target=self._run_task, args=(name, fn), daemon=True)
            threads.append(t)

        start = time.time()
        for t in threads:
            t.start()
            time.sleep(0.5)  # Stagger starts to avoid rate limits

        for t in threads:
            t.join(timeout=300)

        elapsed = time.time() - start
        print(f"  [Parallel] All tasks done in {elapsed:.1f}s")

        # Re-raise first error if any critical task failed
        for name, err in self._errors.items():
            if name in ("backend_files", "frontend_files"):
                raise RuntimeError(f"Parallel task '{name}' failed: {err}")

        return dict(self._results)

    def _run_task(self, name: str, fn: Callable):
        try:
            result = fn()
            with self._lock:
                self._results[name] = result
                print(f"  [Parallel] '{name}' complete ({len(result)} chars)")
        except Exception as e:
            with self._lock:
                self._errors[name] = str(e)
                print(f"  [Parallel] '{name}' failed: {e}")


class RateLimitedParallel:
    """
    Groq has per-model rate limits. This staggers parallel calls
    so backend (Qwen3) and frontend (Qwen3) don't hit the same limit.
    Uses different models where possible.
    """

    # Minimum gap between calls to same model (seconds)
    MODEL_GAPS = {
        "qwen/qwen3-32b": 3.0,
        "moonshotai/kimi-k2-instruct": 2.0,
        "llama-3.3-70b-versatile": 1.0,
    }

    def __init__(self):
        self._last_call: dict[str, float] = {}
        self._lock = threading.Lock()

    def wait_for_model(self, model: str):
        """Wait if needed to respect rate limit gaps."""
        with self._lock:
            last = self._last_call.get(model, 0)
            gap = self.MODEL_GAPS.get(model, 1.0)
            wait = gap - (time.time() - last)
            if wait > 0:
                time.sleep(wait)
            self._last_call[model] = time.time()
