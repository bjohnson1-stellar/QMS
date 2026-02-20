"""
Incremental migrations for the blog module.

Adds publish_at column for scheduled publishing.
"""

import sqlite3

from qms.core.logging import get_logger

logger = get_logger("qms.blog.migrations")


def run_blog_migrations(conn: sqlite3.Connection) -> None:
    """Run all blog schema migrations (idempotent)."""
    _add_publish_at(conn)


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    cols = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(c["name"] == column for c in cols)


def _add_publish_at(conn: sqlite3.Connection) -> None:
    if not _column_exists(conn, "blog_posts", "publish_at"):
        conn.execute(
            "ALTER TABLE blog_posts ADD COLUMN publish_at TEXT DEFAULT NULL"
        )
        conn.commit()
        logger.info("Added publish_at column to blog_posts")
