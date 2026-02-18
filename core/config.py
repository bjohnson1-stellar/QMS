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
        db_path = get_config_value('destinations', 'database', default='data/quality.db')
    """
    config = get_config()

    for key in keys:
        if isinstance(config, dict) and key in config:
            config = config[key]
        else:
            return default

    return config


_BRANDING_DEFAULTS = {
    "app_name": "QMS",
    "app_tagline": "Quality Management System",
    "preset": "default",
    "default_mode": "light",
    "colors": {
        "primary": "#2563eb",
        "primary_hover": "#1d4fd7",
        "primary_subtle": "#eef4ff",
        "nav_bg": "#16202e",
        "nav_hover": "#1e2d40",
        "nav_active": "#2563eb",
        "warning": "#d97706",
        "dark_surface": "#0f172a",
        "light_surface": "#f1f3f8",
        "neutral": "#5a6478",
    },
    "fonts": {
        "heading": "Outfit",
        "heading_fallback": "Outfit",
        "body": "DM Sans",
        "body_fallback": "DM Sans",
        "google_fonts_url": "https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700&family=DM+Sans:opsz,wght@9..40,400;9..40,500;9..40,600&family=JetBrains+Mono:wght@400;500&display=swap",
    },
}


def update_config_section(section_path: str, data: dict) -> None:
    """
    Update a section of config.yaml and write back to disk.

    Args:
        section_path: Dot-notation path (e.g., "welding.cert_requests")
        data: Dictionary of values to merge into the section

    Raises:
        KeyError: If the section path doesn't exist in config
    """
    global _config_cache

    # Always reload from disk to avoid overwriting concurrent changes
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    # Navigate to the target section
    keys = section_path.split(".")
    target = config
    for key in keys[:-1]:
        if key not in target or not isinstance(target[key], dict):
            raise KeyError(f"Config section not found: {section_path}")
        target = target[key]

    last_key = keys[-1]
    if last_key not in target:
        raise KeyError(f"Config section not found: {section_path}")

    # Merge data into the section (shallow merge for flat sections,
    # deep merge for nested dicts like colors/fonts)
    if isinstance(target[last_key], dict):
        for k, v in data.items():
            if isinstance(target[last_key].get(k), dict) and isinstance(v, dict):
                target[last_key][k].update(v)
            else:
                target[last_key][k] = v
    else:
        target[last_key] = data

    # Write back to disk
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(config, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    # Invalidate cache so next get_config() reloads from disk
    _config_cache = None


def get_branding() -> Dict[str, Any]:
    """Return merged branding config (config.yaml overrides defaults)."""
    cfg = get_config().get("branding", {})
    result = {}
    for key, default in _BRANDING_DEFAULTS.items():
        if isinstance(default, dict):
            merged = dict(default)
            merged.update(cfg.get(key, {}))
            result[key] = merged
        else:
            result[key] = cfg.get(key, default)
    return result


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

    def _resolve(self, raw: str) -> Path:
        """Resolve a path: if relative, resolve against _PACKAGE_DIR."""
        p = Path(raw)
        if not p.is_absolute():
            p = _PACKAGE_DIR / p
        return p

    @property
    def database(self) -> Path:
        self._ensure_config()
        raw = self._config.get("destinations", {}).get("database", "data/quality.db")
        return self._resolve(raw)

    @property
    def inbox(self) -> Path:
        self._ensure_config()
        raw = self._config.get("inbox", {}).get("path", "data/inbox")
        return self._resolve(raw)

    @property
    def projects(self) -> Path:
        self._ensure_config()
        raw = self._config.get("destinations", {}).get("projects", "data/projects")
        return self._resolve(raw)

    @property
    def quality_documents(self) -> Path:
        self._ensure_config()
        raw = self._config.get("destinations", {}).get("quality_documents", "data/quality-documents")
        return self._resolve(raw)

    @property
    def vector_database(self) -> Path:
        self._ensure_config()
        raw = self._config.get("destinations", {}).get("vector_database", "data/vectordb")
        return self._resolve(raw)

    @property
    def config_dir(self) -> Path:
        return _PACKAGE_DIR

    @property
    def root(self) -> Path:
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
