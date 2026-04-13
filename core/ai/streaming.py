# core/ai/streaming.py
# Streaming token output - shows tokens as they arrive
# Gives real-time feedback during generation

import os
import sys
import time
import requests
import threading


class StreamingGenerator:
    """
    Streams tokens from Groq API in real-time.
    Shows a live progress indicator in the terminal.
    """

    def __init__(self):
        self.api_key = os.environ.get("GROQ_API_KEY", "")

    def generate_streaming(self, model: str, prompt: str,
                           on_token=None, on_done=None) -> str:
        """
        Generate with streaming. Calls on_token(chunk) for each token,
        on_done(full_text) when complete.
        Returns full generated text.
        """
        if len(prompt) > 80000:
            prompt = prompt[:80000]

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": self._system(model)},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": 8000,
            "temperature": 0.15,
            "stream": True,
        }

        full_text = []
        char_count = 0
        start = time.time()

        try:
            with requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers=headers,
                json=payload,
                stream=True,
                timeout=180
            ) as resp:
                if resp.status_code == 429:
                    raise RuntimeError("Rate limited")
                if resp.status_code == 413:
                    raise RuntimeError("413 Payload Too Large")
                resp.raise_for_status()

                for line in resp.iter_lines():
                    if not line:
                        continue
                    line = line.decode("utf-8")
                    if not line.startswith("data: "):
                        continue
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    try:
                        import json
                        chunk = json.loads(data)
                        delta = chunk["choices"][0]["delta"].get("content", "")
                        if delta:
                            full_text.append(delta)
                            char_count += len(delta)
                            if on_token:
                                on_token(delta)
                            else:
                                # Default: show progress dots
                                if char_count % 100 == 0:
                                    sys.stdout.write(".")
                                    sys.stdout.flush()
                    except Exception:
                        pass

        except Exception as e:
            raise RuntimeError(f"Streaming error: {e}")

        elapsed = time.time() - start
        result = "".join(full_text)
        if not on_token:
            print(f" ({len(result)} chars, {elapsed:.1f}s)")

        if on_done:
            on_done(result)

        return result

    def _system(self, model: str) -> str:
        if "kimi" in model:
            return "You are a world-class CTO. Think deeply. Be exhaustive."
        if "qwen" in model:
            return "You are a senior engineer. Write complete production code. No placeholders."
        return "You are a senior software engineer. Be accurate and concise."


class LiveProgressBar:
    """Shows a spinning progress indicator with token count."""

    SPINNERS = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(self, step_name: str):
        self.step_name = step_name
        self.token_count = 0
        self.running = False
        self._thread = None
        self._spinner_idx = 0

    def start(self):
        self.running = True
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()

    def add_tokens(self, text: str):
        self.token_count += len(text) // 4

    def stop(self, success: bool = True):
        self.running = False
        if self._thread:
            self._thread.join(timeout=1)
        status = "v" if success else "x"
        print(f"\r  [{status}] {self.step_name} ({self.token_count} tokens)    ")

    def _spin(self):
        while self.running:
            spinner = self.SPINNERS[self._spinner_idx % len(self.SPINNERS)]
            sys.stdout.write(
                f"\r  {spinner} {self.step_name} ... {self.token_count} tokens"
            )
            sys.stdout.flush()
            self._spinner_idx += 1
            time.sleep(0.1)
