import os


class ProjectManager:
    def create_project(self, name: str):
        base_path = os.path.join(os.getcwd(), name)
        os.makedirs(base_path, exist_ok=True)

        # Detect existing versions
        existing_versions = [
            d for d in os.listdir(base_path)
            if os.path.isdir(os.path.join(base_path, d)) and d.startswith("v")
        ]

        version_number = len(existing_versions) + 1
        version_folder = os.path.join(base_path, f"v{version_number}")

        os.makedirs(version_folder, exist_ok=True)

        return version_folder