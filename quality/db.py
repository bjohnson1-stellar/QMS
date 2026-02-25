"""
Quality Issues database helpers.

Provides normalization, audit logging, and lookup functions for the
unified quality issues schema.
"""

import sqlite3
from typing import Any, Dict, List, Optional

from qms.core import get_logger
from qms.core.config import get_config

logger = get_logger("qms.quality")


def get_root_causes(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Return all active root causes."""
    rows = conn.execute(
        "SELECT id, name, description, category FROM root_causes WHERE is_active = 1 ORDER BY name"
    ).fetchall()
    return [dict(r) for r in rows]


def get_tags(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Return all tags."""
    rows = conn.execute(
        "SELECT id, name, color, description FROM tags ORDER BY name"
    ).fetchall()
    return [dict(r) for r in rows]


def _get_normalize_map(key: str) -> Dict[str, str]:
    """Load a normalization mapping from config.yaml quality.normalize section."""
    cfg = get_config()
    quality_cfg = cfg.get("quality", {})
    normalize = quality_cfg.get("normalize", {})
    return normalize.get(key, {})


def normalize_trade(trade_name: str) -> str:
    """Normalize a trade name using config mappings.

    Returns the mapped value if found, otherwise returns the original
    with title-casing applied.
    """
    if not trade_name:
        return trade_name
    mapping = _get_normalize_map("trades")
    return mapping.get(trade_name, mapping.get(trade_name.strip(), trade_name.strip().title()))


def normalize_status(status: str) -> str:
    """Normalize a status string using config mappings.

    Returns the mapped value if found, otherwise returns the original
    lowercased with spaces replaced by underscores.
    """
    if not status:
        return status
    mapping = _get_normalize_map("statuses")
    return mapping.get(status, mapping.get(status.strip(), status.strip().lower().replace(" ", "_")))


def normalize_type(type_name: str) -> str:
    """Normalize an issue type string using config mappings.

    Returns the mapped value if found, otherwise returns 'other'.
    """
    if not type_name:
        return "other"
    mapping = _get_normalize_map("types")
    return mapping.get(type_name, mapping.get(type_name.strip(), "other"))


def log_issue_change(
    conn: sqlite3.Connection,
    issue_id: int,
    field: str,
    old_value: Optional[str],
    new_value: Optional[str],
    changed_by: Optional[str] = None,
) -> None:
    """Insert an audit trail row into quality_issue_history."""
    conn.execute(
        """INSERT INTO quality_issue_history
           (issue_id, field_changed, old_value, new_value, changed_by)
           VALUES (?, ?, ?, ?, ?)""",
        (issue_id, field, old_value, new_value, changed_by),
    )
