import os


class FileEngine:
    def write_files(self, project_path: str, files: list):
        base_path = os.path.abspath(project_path)

        for file in files:
            relative_path = file.get("path")
            content = file.get("content", "")

            if not relative_path:
                raise ValueError("File entry missing 'path'.")

            # ---- Sanitize Path ----
            safe_path = self._sanitize_path(base_path, relative_path)

            # ---- Ensure Directory Exists ----
            os.makedirs(os.path.dirname(safe_path), exist_ok=True)

            # ---- Write File ----
            with open(safe_path, "w", encoding="utf-8") as f:
                f.write(content)

    def _sanitize_path(self, base_path: str, relative_path: str) -> str:
        """
        Ensures the file path:
        - Is not absolute
        - Does not escape project directory
        - Is safely normalized
        """

        # Remove leading slashes/backslashes
        relative_path = relative_path.lstrip("/\\").strip()

        # Block obvious traversal attempts
        if ".." in relative_path:
            raise ValueError("Invalid file path detected (directory traversal).")

        # Build normalized absolute path
        full_path = os.path.abspath(
            os.path.normpath(
                os.path.join(base_path, relative_path)
            )
        )

        # Final safety check: must remain inside project directory
        if not full_path.startswith(base_path):
            raise ValueError("Invalid file path detected (directory traversal).")

        return full_path