"""
Path utilities for QMS.

Directory creation and project path resolution.
"""

from pathlib import Path
from typing import Optional

from qms.core.config import QMS_PATHS


def ensure_directory(path: Path) -> Path:
    """Ensure a directory exists, creating if necessary. Returns path for chaining."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def resolve_project_path(project_id: str) -> Optional[Path]:
    """
    Find a project folder by ID (partial match supported).

    Args:
        project_id: Project ID or partial match (e.g., "07645" or "Vital")

    Returns:
        Path to project folder, or None if not found
    """
    projects_dir = QMS_PATHS.projects

    if not projects_dir.exists():
        return None

    for folder in projects_dir.iterdir():
        if folder.is_dir() and not folder.name.startswith("_"):
            if project_id in folder.name:
                return folder

    return None
