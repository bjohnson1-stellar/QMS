"""
QMS Core - Shared services for all modules.

Usage:
    from qms.core import get_db, get_config, get_logger, QMS_PATHS
"""

from qms.core.config import get_config, get_config_value, QMS_PATHS
from qms.core.db import get_db, execute_query, migrate_all
from qms.core.logging import get_logger

__all__ = [
    "get_config",
    "get_config_value",
    "QMS_PATHS",
    "get_db",
    "execute_query",
    "migrate_all",
    "get_logger",
]
