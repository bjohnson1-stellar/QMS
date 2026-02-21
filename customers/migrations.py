"""
Incremental migrations for the customers module.

Extends the base customers table (defined in projects/schema.sql) with
profile fields for industry classification, account management, and
repeat-business tracking.
"""

import sqlite3

from qms.core.logging import get_logger

logger = get_logger("qms.customers.migrations")


def run_customer_migrations(conn: sqlite3.Connection) -> None:
    """Run all customer schema migrations (idempotent)."""
    _add_profile_columns(conn)


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    cols = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(c["name"] == column for c in cols)


def _add_profile_columns(conn: sqlite3.Connection) -> None:
    """Add extended profile columns to the base customers table."""
    additions = [
        ("industry", "TEXT"),
        ("territory", "TEXT"),
        ("tier", "TEXT DEFAULT 'standard'"),
        ("website", "TEXT"),
        ("account_manager_id", "INTEGER REFERENCES employees(id)"),
        ("onboarding_complete", "INTEGER NOT NULL DEFAULT 0"),
    ]
    for col_name, col_def in additions:
        if not _column_exists(conn, "customers", col_name):
            conn.execute(
                f"ALTER TABLE customers ADD COLUMN {col_name} {col_def}"
            )
            logger.info("Added %s column to customers", col_name)
    conn.commit()
