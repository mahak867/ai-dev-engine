# core/ai/response_cleaner.py
# Cleans raw model output before JSON parsing.
# Handles DeepSeek R1 <think> tags, markdown fences, and leading/trailing garbage.

import re
import json


def clean(text: str) -> str:
    """
    Full cleaning pipeline — run this on EVERY model response before parsing.

    Handles:
      - DeepSeek R1 <think>...</think> blocks
      - Markdown code fences (```json ... ```)
      - Leading/trailing whitespace and garbage text
      - Multiple JSON objects (takes the last complete one)
    """
    if not text:
        return ""

    # 1. Strip <think>...</think> blocks (DeepSeek R1 reasoning traces)
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)

    # 2. Strip markdown code fences
    text = re.sub(r"```(?:json|python|javascript|typescript|html|css|bash|sh)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"```", "", text)

    # 3. Strip common preamble phrases models add before JSON
    preambles = [
        r"^here is the.*?:\s*",
        r"^here's the.*?:\s*",
        r"^sure[,!].*?:\s*",
        r"^certainly[,!].*?:\s*",
        r"^of course[,!].*?:\s*",
        r"^based on.*?:\s*",
        r"^the following.*?:\s*",
        r"^below is.*?:\s*",
    ]
    for p in preambles:
        text = re.sub(p, "", text, flags=re.IGNORECASE | re.DOTALL)

    text = text.strip()

    # 4. Try to extract the JSON object directly
    # Find outermost { ... } — take the LAST complete JSON object
    # (models sometimes explain after the JSON too)
    best = _extract_json_object(text)
    if best:
        return best

    return text.strip()


def clean_and_parse(text: str) -> dict:
    """
    Clean + parse in one call. Raises ValueError if no valid JSON found.
    """
    cleaned = clean(text)

    # Try direct parse
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Try json-repair if available
    try:
        from json_repair import repair_json
        fixed = repair_json(cleaned)
        return json.loads(fixed)
    except Exception:
        pass

    raise ValueError(
        f"Could not parse JSON from model response.\n"
        f"First 300 chars of cleaned output:\n{cleaned[:300]}"
    )


def _extract_json_object(text: str) -> str | None:
    """
    Find the outermost valid JSON object in a string.
    Scans for { ... } with proper brace matching.
    Returns the JSON string or None.
    """
    # Find all positions where { appears
    candidates = []
    depth = 0
    start = None

    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                candidates.append(text[start:i+1])
                start = None

    if not candidates:
        return None

    # Return the LAST complete JSON object (model output often ends with the real JSON)
    for candidate in reversed(candidates):
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            # Try repair
            try:
                from json_repair import repair_json
                fixed = repair_json(candidate)
                json.loads(fixed)
                return fixed
            except Exception:
                continue

    # If nothing parses, return the largest candidate for repair later
    return max(candidates, key=len)
