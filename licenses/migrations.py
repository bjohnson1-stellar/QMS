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

    if "association_date" not in cols:
        conn.execute("ALTER TABLE state_licenses ADD COLUMN association_date TEXT")

    if "disassociation_date" not in cols:
        conn.execute("ALTER TABLE state_licenses ADD COLUMN disassociation_date TEXT")

    if "business_entity" not in cols:
        conn.execute("ALTER TABLE state_licenses ADD COLUMN business_entity TEXT")
        # Backfill from holder_name for existing rows
        conn.execute(
            "UPDATE state_licenses SET business_entity = holder_name "
            "WHERE business_entity IS NULL"
        )

    # Remove NOT NULL + CHECK on holder_type (SQLite requires table rebuild)
    _relax_holder_type_constraint(conn)

    conn.commit()


def _relax_holder_type_constraint(conn: sqlite3.Connection):
    """Rebuild state_licenses to make holder_type nullable (no CHECK)."""
    # Check if holder_type still has NOT NULL constraint
    for row in conn.execute("PRAGMA table_info(state_licenses)").fetchall():
        # row: (cid, name, type, notnull, dflt_value, pk)
        if row[1] == "holder_type" and row[3] == 1:  # notnull=1
            break
    else:
        return  # Already relaxed

    # Get current column order
    col_info = conn.execute("PRAGMA table_info(state_licenses)").fetchall()
    col_names = [r[1] for r in col_info]

    conn.execute("PRAGMA foreign_keys = OFF")

    # Drop dependent view first
    conn.execute("DROP VIEW IF EXISTS v_expiring_licenses")

    conn.execute("""
        CREATE TABLE state_licenses_new (
            id              TEXT PRIMARY KEY,
            holder_type     TEXT,
            employee_id     TEXT,
            business_entity TEXT,
            state_code      TEXT NOT NULL,
            license_type    TEXT NOT NULL,
            license_number  TEXT NOT NULL,
            holder_name     TEXT NOT NULL DEFAULT '',
            issued_date     TEXT,
            expiration_date TEXT,
            status          TEXT NOT NULL DEFAULT 'active'
                            CHECK (status IN ('active','expired','pending','revoked','disassociation')),
            notes           TEXT,
            created_at      TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
            created_by      TEXT,
            reciprocal_state TEXT,
            association_date TEXT,
            disassociation_date TEXT,
            FOREIGN KEY (employee_id) REFERENCES employees(id)
        )
    """)

    # Copy data — map columns that exist in both old and new
    new_cols = [
        "id", "holder_type", "employee_id", "business_entity", "state_code",
        "license_type", "license_number", "holder_name", "issued_date",
        "expiration_date", "status", "notes", "created_at", "updated_at",
        "created_by", "reciprocal_state", "association_date", "disassociation_date",
    ]
    shared = [c for c in new_cols if c in col_names]
    cols_csv = ", ".join(shared)

    conn.execute(f"INSERT INTO state_licenses_new ({cols_csv}) SELECT {cols_csv} FROM state_licenses")
    conn.execute("DROP TABLE state_licenses")
    conn.execute("ALTER TABLE state_licenses_new RENAME TO state_licenses")

    # Recreate indexes
    conn.execute("CREATE INDEX IF NOT EXISTS idx_state_licenses_state_code ON state_licenses(state_code)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_state_licenses_status ON state_licenses(status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_state_licenses_expiration ON state_licenses(expiration_date)")

    # Recreate the view
    conn.execute("""
        CREATE VIEW IF NOT EXISTS v_expiring_licenses AS
        SELECT sl.*,
            CASE
                WHEN sl.expiration_date IS NULL THEN NULL
                ELSE CAST(julianday(sl.expiration_date) - julianday('now') AS INTEGER)
            END AS days_until_expiry
        FROM state_licenses sl
        WHERE sl.status = 'active'
    """)

    conn.execute("PRAGMA foreign_keys = ON")
