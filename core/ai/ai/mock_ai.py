import json


class MockAI:

    def generate(self, prompt: str) -> str:
        mock_response = {
            "files": [
                {
                    "path": "app.py",
                    "content": "print('Hello from generated project')"
                }
            ]
        }

        return json.dumps(mock_response)