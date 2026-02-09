"""
Configuration management for QMS.

Loads config.yaml and provides type-safe access to settings.
"""

import yaml
from pathlib import Path
from typing import Any, Dict, Optional

# Config file location — lives alongside the qms package
_PACKAGE_DIR = Path(__file__).parent.parent.resolve()
CONFIG_PATH = _PACKAGE_DIR / "config.yaml"

# Cache for loaded config
_config_cache: Optional[Dict[str, Any]] = None


def get_config(reload: bool = False) -> Dict[str, Any]:
    """
    Load configuration from config.yaml.

    Args:
        reload: Force reload even if cached

    Returns:
        Configuration dictionary
    """
    global _config_cache

    if _config_cache is not None and not reload:
        return _config_cache

    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Config file not found: {CONFIG_PATH}")

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        _config_cache = yaml.safe_load(f)

    return _config_cache


def get_config_value(*keys: str, default: Any = None) -> Any:
    """
    Get a nested config value safely.

    Args:
        *keys: Path of keys to traverse (e.g., 'destinations', 'database')
        default: Value to return if key not found

    Example:
        db_path = get_config_value('destinations', 'database', default='D:/quality.db')
    """
    config = get_config()

    for key in keys:
        if isinstance(config, dict) and key in config:
            config = config[key]
        else:
            return default

    return config


class QMSPaths:
    """
    Centralized path access for QMS system.

    All paths are loaded from config.yaml with sensible fallbacks.

    Usage:
        from qms.core.config import QMS_PATHS
        db = QMS_PATHS.database
        inbox = QMS_PATHS.inbox
    """

    def __init__(self):
        self._config = None

    def _ensure_config(self):
        if self._config is None:
            self._config = get_config()

    @property
    def database(self) -> Path:
        self._ensure_config()
        return Path(self._config.get("destinations", {}).get("database", r"D:\quality.db"))

    @property
    def inbox(self) -> Path:
        self._ensure_config()
        return Path(self._config.get("inbox", {}).get("path", r"D:\Inbox"))

    @property
    def projects(self) -> Path:
        self._ensure_config()
        return Path(self._config.get("destinations", {}).get("projects", r"D:\Projects"))

    @property
    def quality_documents(self) -> Path:
        self._ensure_config()
        return Path(
            self._config.get("destinations", {}).get("quality_documents", r"D:\Quality Documents")
        )

    @property
    def vector_database(self) -> Path:
        self._ensure_config()
        return Path(
            self._config.get("destinations", {}).get("vector_database", r"D:\VectorDB")
        )

    @property
    def config_dir(self) -> Path:
        return _PACKAGE_DIR

    @property
    def needs_review(self) -> Path:
        self._ensure_config()
        subdir = self._config.get("inbox", {}).get("subdirs", {}).get(
            "needs_review", "NEEDS-REVIEW"
        )
        return self.inbox / subdir

    @property
    def conflicts(self) -> Path:
        self._ensure_config()
        subdir = self._config.get("inbox", {}).get("subdirs", {}).get("conflicts", "CONFLICTS")
        return self.inbox / subdir

    @property
    def duplicates(self) -> Path:
        self._ensure_config()
        subdir = self._config.get("inbox", {}).get("subdirs", {}).get("duplicates", "DUPLICATES")
        return self.inbox / subdir


# Singleton instance
QMS_PATHS = QMSPaths()
