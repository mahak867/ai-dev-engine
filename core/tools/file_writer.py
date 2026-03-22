import os


class FileWriter:

    def __init__(self, project_path):
        self.project_path = project_path

    def write_files(self, files):
        """
        files format:
        {
            "main.py": "...code...",
            "utils.py": "...code..."
        }
        """

        for filename, content in files.items():

            path = os.path.join(self.project_path, filename)

            os.makedirs(os.path.dirname(path), exist_ok=True)

            with open(path, "w", encoding="utf-8") as f:
                f.write(content)