"""
License schema migrations — incremental column additions.

Called from core/db.py migrate_all().
"""

import sqlite3


def run_license_migrations(conn: sqlite3.Connection):
    """Add columns that don't exist yet in state_licenses."""
    # Get existing columns
    cols = {row[1] for row in conn.execute("PRAGMA table_info(state_licenses)").fetchall()}

    if "reciprocal_state" not in cols:
        conn.execute("ALTER TABLE state_licenses ADD COLUMN reciprocal_state TEXT")

    conn.commit()
