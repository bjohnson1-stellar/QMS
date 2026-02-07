#!/usr/bin/env python3
"""
SIS Common Utilities

Shared utilities for all SIS Quality System scripts.
Provides consistent config loading, database access, logging, and path handling.

Usage:
    from sis_common import get_config, get_db_connection, get_logger, SIS_PATHS

Example:
    config = get_config()
    db_path = config['destinations']['database']

    with get_db_connection() as conn:
        cursor = conn.execute("SELECT * FROM projects")

    logger = get_logger('my_script')
    logger.info("Processing started")
"""

import logging
import sqlite3
import sys
import yaml
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Generator, Optional

# =============================================================================
# PATH RESOLUTION
# =============================================================================

# Script location - all paths relative to this
SCRIPT_DIR = Path(__file__).parent.resolve()

# Config file location
CONFIG_PATH = SCRIPT_DIR / "config.yaml"

# Cache for loaded config
_config_cache: Optional[Dict[str, Any]] = None


class SISPaths:
    """
    Centralized path access for SIS system.

    All paths are loaded from config.yaml with sensible fallbacks.

    Usage:
        from sis_common import SIS_PATHS

        db = SIS_PATHS.database
        inbox = SIS_PATHS.inbox
        projects = SIS_PATHS.projects
    """

    def __init__(self):
        self._config = None

    def _ensure_config(self):
        if self._config is None:
            self._config = get_config()

    @property
    def database(self) -> Path:
        """Path to quality.db"""
        self._ensure_config()
        return Path(self._config.get('destinations', {}).get('database', r'D:\quality.db'))

    @property
    def inbox(self) -> Path:
        """Path to unified inbox"""
        self._ensure_config()
        return Path(self._config.get('inbox', {}).get('path', r'D:\Inbox'))

    @property
    def projects(self) -> Path:
        """Path to projects folder"""
        self._ensure_config()
        return Path(self._config.get('destinations', {}).get('projects', r'D:\Projects'))

    @property
    def quality_documents(self) -> Path:
        """Path to quality documents folder"""
        self._ensure_config()
        return Path(self._config.get('destinations', {}).get('quality_documents', r'D:\Quality Documents'))

    @property
    def vector_database(self) -> Path:
        """Path to ChromaDB vector database folder"""
        self._ensure_config()
        return Path(self._config.get('destinations', {}).get('vector_database', r'D:\VectorDB'))

    @property
    def config_dir(self) -> Path:
        """Path to QC-DR config directory"""
        return SCRIPT_DIR

    @property
    def needs_review(self) -> Path:
        """Path to needs-review folder in inbox"""
        self._ensure_config()
        subdir = self._config.get('inbox', {}).get('subdirs', {}).get('needs_review', 'NEEDS-REVIEW')
        return self.inbox / subdir

    @property
    def conflicts(self) -> Path:
        """Path to conflicts folder in inbox"""
        self._ensure_config()
        subdir = self._config.get('inbox', {}).get('subdirs', {}).get('conflicts', 'CONFLICTS')
        return self.inbox / subdir

    @property
    def duplicates(self) -> Path:
        """Path to duplicates folder in inbox"""
        self._ensure_config()
        subdir = self._config.get('inbox', {}).get('subdirs', {}).get('duplicates', 'DUPLICATES')
        return self.inbox / subdir


# Singleton instance
SIS_PATHS = SISPaths()


# =============================================================================
# CONFIGURATION
# =============================================================================

def get_config(reload: bool = False) -> Dict[str, Any]:
    """
    Load configuration from config.yaml.

    Args:
        reload: Force reload even if cached

    Returns:
        Configuration dictionary

    Raises:
        FileNotFoundError: If config.yaml doesn't exist
        yaml.YAMLError: If config.yaml is invalid
    """
    global _config_cache

    if _config_cache is not None and not reload:
        return _config_cache

    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Config file not found: {CONFIG_PATH}")

    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        _config_cache = yaml.safe_load(f)

    return _config_cache


def get_config_value(*keys: str, default: Any = None) -> Any:
    """
    Get a nested config value safely.

    Args:
        *keys: Path of keys to traverse (e.g., 'destinations', 'database')
        default: Value to return if key not found

    Returns:
        Config value or default

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


# =============================================================================
# DATABASE
# =============================================================================

def get_db_path() -> Path:
    """Get database path from config."""
    return SIS_PATHS.database


@contextmanager
def get_db_connection(readonly: bool = False) -> Generator[sqlite3.Connection, None, None]:
    """
    Context manager for database connections.

    Automatically handles connection cleanup and enables foreign keys.

    Args:
        readonly: Open in read-only mode (useful for queries)

    Yields:
        sqlite3.Connection

    Example:
        with get_db_connection() as conn:
            cursor = conn.execute("SELECT * FROM projects")
            rows = cursor.fetchall()
    """
    db_path = get_db_path()

    if readonly:
        # SQLite URI for read-only
        uri = f"file:{db_path}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
    else:
        conn = sqlite3.connect(str(db_path))

    try:
        # Enable foreign keys
        conn.execute("PRAGMA foreign_keys = ON")
        # Return dicts instead of tuples (optional, but useful)
        conn.row_factory = sqlite3.Row
        yield conn
    finally:
        conn.close()


def execute_query(query: str, params: tuple = (), readonly: bool = True) -> list:
    """
    Execute a query and return results.

    Args:
        query: SQL query
        params: Query parameters
        readonly: Use read-only connection

    Returns:
        List of sqlite3.Row objects
    """
    with get_db_connection(readonly=readonly) as conn:
        cursor = conn.execute(query, params)
        return cursor.fetchall()


# =============================================================================
# LOGGING
# =============================================================================

# Track configured loggers
_loggers: Dict[str, logging.Logger] = {}


def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """
    Get a configured logger for a script.

    Creates a logger with consistent formatting across all SIS scripts.

    Args:
        name: Logger name (usually script name)
        level: Logging level (default: INFO)

    Returns:
        Configured logger

    Example:
        logger = get_logger('weld_intake')
        logger.info("Processing file: %s", filename)
        logger.error("Failed to parse: %s", error)
    """
    if name in _loggers:
        return _loggers[name]

    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Avoid duplicate handlers
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)

        formatter = logging.Formatter(
            '%(asctime)s [%(name)s] %(levelname)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    _loggers[name] = logger
    return logger


# =============================================================================
# UTILITIES
# =============================================================================

def ensure_directory(path: Path) -> Path:
    """
    Ensure a directory exists, creating if necessary.

    Args:
        path: Directory path

    Returns:
        The path (for chaining)
    """
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
    projects_dir = SIS_PATHS.projects

    if not projects_dir.exists():
        return None

    # Try exact match first
    for folder in projects_dir.iterdir():
        if folder.is_dir() and not folder.name.startswith('_'):
            if project_id in folder.name:
                return folder

    return None


# =============================================================================
# MODULE INFO
# =============================================================================

__version__ = "1.0.0"
__all__ = [
    'get_config',
    'get_config_value',
    'get_db_path',
    'get_db_connection',
    'execute_query',
    'get_logger',
    'ensure_directory',
    'resolve_project_path',
    'SIS_PATHS',
    'CONFIG_PATH',
    'SCRIPT_DIR',
]
