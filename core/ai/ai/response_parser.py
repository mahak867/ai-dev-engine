import json
import re


class AIResponseParser:
    def parse_and_validate(self, response: str) -> dict:
        if not response:
            raise ValueError("Empty AI response.")

        cleaned = self._extract_json(response)

        # 🔎 DEBUG (optional — remove later if you want)
        print("\n---------- CLEANED JSON ----------")
        print(cleaned)
        print("----------------------------------\n")

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            raise ValueError(f"AI returned invalid JSON.\nError: {e}")

        # ---- Validate Structure ----
        if "files" not in data or not isinstance(data["files"], list):
            raise ValueError("Invalid structure: missing 'files' list.")

        for file in data["files"]:
            if not isinstance(file, dict):
                raise ValueError("Invalid file object structure.")
            if "path" not in file or "content" not in file:
                raise ValueError("Invalid file object structure.")

        return data

    def _extract_json(self, text: str) -> str:
        """
        Extract JSON safely from AI responses.
        Handles:
        - Markdown ```json blocks
        - Extra explanations before/after JSON
        - Multiple braces in text
        """

        # Remove markdown code fences (case-insensitive)
        text = re.sub(r"```json", "", text, flags=re.IGNORECASE)
        text = re.sub(r"```", "", text)

        text = text.strip()

        # 1️⃣ Try direct parse first
        try:
            json.loads(text)
            return text
        except:
            pass

        # 2️⃣ Extract from first { to last }
        start = text.find("{")
        end = text.rfind("}")

        if start == -1 or end == -1:
            raise ValueError("No JSON object found in AI response.")

        candidate = text[start:end + 1].strip()

        return candidate