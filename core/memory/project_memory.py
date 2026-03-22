import json
from pathlib import Path


class ProjectMemory:

    def __init__(self, project_path):

        self.memory_file = Path(project_path) / ".ai_memory.json"

        if not self.memory_file.exists():

            with open(self.memory_file, "w") as f:
                json.dump({}, f)

    def load(self):

        with open(self.memory_file) as f:
            return json.load(f)

    def save(self, data):

        with open(self.memory_file, "w") as f:
            json.dump(data, f, indent=2)

    def update(self, key, value):

        data = self.load()

        data[key] = value

        self.save(data)