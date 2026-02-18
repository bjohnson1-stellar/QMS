"""
Database access for QMS.

Provides connection management, query execution, and schema migration.
Single source of truth for all database operations.
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from qms.core.config import QMS_PATHS


def get_db_path() -> Path:
    """Get database path from config."""
    return QMS_PATHS.database


@contextmanager
def get_db(readonly: bool = False) -> Generator[sqlite3.Connection, None, None]:
    """
    Context manager for database connections.

    Enables foreign keys and Row factory automatically.

    Args:
        readonly: Open in read-only mode (useful for queries)

    Yields:
        sqlite3.Connection with Row factory enabled
    """
    db_path = get_db_path()

    if readonly:
        uri = f"file:{db_path}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
    else:
        conn = sqlite3.connect(str(db_path))

    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.row_factory = sqlite3.Row
        yield conn
    finally:
        conn.close()


def execute_query(query: str, params: tuple = (), readonly: bool = True) -> list:
    """
    Execute a query and return results as list of Row objects.

    Args:
        query: SQL query
        params: Query parameters
        readonly: Use read-only connection

    Returns:
        List of sqlite3.Row objects
    """
    with get_db(readonly=readonly) as conn:
        cursor = conn.execute(query, params)
        return cursor.fetchall()


# Schema dependency order — foreign keys flow downhill through this list.
SCHEMA_ORDER = [
    "auth",
    "core",
    "workforce",
    "projects",
    "qualitydocs",
    "references",
    "welding",
    "pipeline",
    "engineering",
    "automation",
]


def migrate_all():
    """
    Run all module schemas in dependency order.

    Each module's schema.sql uses CREATE TABLE IF NOT EXISTS,
    making this safe to run repeatedly (idempotent).
    """
    from qms.core.logging import get_logger

    logger = get_logger("qms.migrate")
    package_dir = Path(__file__).parent.parent

    with get_db() as conn:
        for module_name in SCHEMA_ORDER:
            schema_file = package_dir / module_name / "schema.sql"
            if schema_file.exists():
                logger.info(f"Applying schema: {module_name}/schema.sql")
                sql = schema_file.read_text(encoding="utf-8")
                conn.executescript(sql)
            else:
                logger.debug(f"No schema for module: {module_name}")

        conn.commit()
        logger.info("All schemas applied successfully")

    # Run incremental migrations (column additions, data migrations)
    try:
        from qms.projects.migrations import run_all_migrations
        run_all_migrations()
        logger.info("Incremental migrations applied")
    except Exception as exc:
        logger.warning("Migration step failed (non-fatal): %s", exc)
