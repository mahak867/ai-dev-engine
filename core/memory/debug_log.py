import json
from pathlib import Path


class DebugLog:

    def __init__(self, project_path):
        self.file = Path(project_path) / ".debug_log.json"

        if not self.file.exists():
            with open(self.file, "w") as f:
                json.dump([], f)

    def add(self, error):

        with open(self.file) as f:
            data = json.load(f)

        data.append(error)

        with open(self.file, "w") as f:
            json.dump(data, f, indent=2)