"""Contained writer for generated project files (see core.security.safe_join)."""
from __future__ import annotations

from core.security import UnsafePathError, safe_join, safe_write_text


class FileEngine:
    def write_files(self, project_path: str, files: list, *, overwrite: bool = True) -> list[str]:
        """
        Write ``[{"path": ..., "content": ...}, ...]`` under ``project_path``.

        Every path is validated before anything is written, so one bad entry
        aborts the batch without leaving a half-written project.
        """
        planned = []
        for file in files:
            relative_path = file.get("path")
            if not relative_path:
                raise ValueError("File entry missing 'path'.")
            safe_join(project_path, relative_path)  # raises UnsafePathError
            planned.append((relative_path, file.get("content", "")))

        written = []
        for rel, content in planned:
            safe_write_text(project_path, rel, content, overwrite=overwrite)
            written.append(rel)
        return written

    def _sanitize_path(self, base_path: str, relative_path: str) -> str:
        """Backward-compatible wrapper; prefer core.security.safe_join."""
        return str(safe_join(base_path, relative_path))


__all__ = ["FileEngine", "UnsafePathError"]
