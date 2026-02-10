"""
Projects module schema migrations.

Handles incremental migrations for existing databases:
- departments -> business_units transition
- projects table: add stage, start_date, end_date, notes columns
"""

import sqlite3

from qms.core import get_db, get_logger

logger = get_logger("qms.projects.migrations")


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row["n"] > 0


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r["name"] == column for r in rows)


def migrate_departments_to_business_units(conn: sqlite3.Connection) -> None:
    """Copy rows from legacy 'departments' table into 'business_units'."""
    if not _table_exists(conn, "departments"):
        return
    if not _table_exists(conn, "business_units"):
        return

    existing = conn.execute("SELECT COUNT(*) AS n FROM business_units").fetchone()["n"]
    if existing > 0:
        logger.debug("business_units already populated, skipping departments migration")
        return

    rows = conn.execute(
        "SELECT department_number, name, full_name, manager, status FROM departments"
    ).fetchall()

    for r in rows:
        conn.execute(
            "INSERT OR IGNORE INTO business_units (code, name, full_name, manager, status) "
            "VALUES (?, ?, ?, ?, ?)",
            (r["department_number"], r["name"], r["full_name"], r["manager"], r["status"]),
        )

    if rows:
        logger.info("Migrated %d departments -> business_units", len(rows))
        conn.commit()


def migrate_projects_add_columns(conn: sqlite3.Connection) -> None:
    """Add stage/start_date/end_date/notes columns to existing projects table."""
    if not _table_exists(conn, "projects"):
        return

    migrations = [
        ("stage", "ALTER TABLE projects ADD COLUMN stage TEXT DEFAULT 'Proposal'"),
        ("start_date", "ALTER TABLE projects ADD COLUMN start_date TEXT"),
        ("end_date", "ALTER TABLE projects ADD COLUMN end_date TEXT"),
        ("notes", "ALTER TABLE projects ADD COLUMN notes TEXT"),
    ]

    for col, sql in migrations:
        if not _column_exists(conn, "projects", col):
            conn.execute(sql)
            logger.info("Added column projects.%s", col)

    # Map existing status values to stage
    if _column_exists(conn, "projects", "stage"):
        conn.execute("""
            UPDATE projects SET stage = CASE
                WHEN status = 'active' AND stage IS NULL THEN 'Course of Construction'
                WHEN status = 'completed' AND stage IS NULL THEN 'Post-Construction'
                WHEN status = 'inactive' AND stage IS NULL THEN 'Archive'
                WHEN stage IS NULL THEN 'Proposal'
                ELSE stage
            END
            WHERE stage IS NULL
        """)

    conn.commit()


def migrate_welding_add_bu_fk(conn: sqlite3.Connection) -> None:
    """Add business_unit_id FK to weld_welder_registry if missing."""
    if not _table_exists(conn, "weld_welder_registry"):
        return
    if _column_exists(conn, "weld_welder_registry", "business_unit_id"):
        return

    conn.execute(
        "ALTER TABLE weld_welder_registry ADD COLUMN "
        "business_unit_id INTEGER REFERENCES business_units(id)"
    )
    logger.info("Added column weld_welder_registry.business_unit_id")
    conn.commit()


def migrate_add_project_allocations(conn: sqlite3.Connection) -> None:
    """Create project_allocations table if not exists."""
    if _table_exists(conn, "project_allocations"):
        return

    conn.execute("""
        CREATE TABLE IF NOT EXISTS project_allocations (
            id INTEGER PRIMARY KEY,
            project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            business_unit_id INTEGER NOT NULL REFERENCES business_units(id),
            subjob TEXT NOT NULL DEFAULT '00',
            job_code TEXT NOT NULL,
            allocated_budget REAL NOT NULL DEFAULT 0,
            weight_adjustment REAL NOT NULL DEFAULT 1.0,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(project_id, business_unit_id, subjob)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pa_project ON project_allocations(project_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pa_bu ON project_allocations(business_unit_id)")
    logger.info("Created project_allocations table")
    conn.commit()


def migrate_add_project_description(conn: sqlite3.Connection) -> None:
    """Add description column to projects table."""
    if not _table_exists(conn, "projects"):
        return
    if _column_exists(conn, "projects", "description"):
        return

    conn.execute("ALTER TABLE projects ADD COLUMN description TEXT")
    logger.info("Added column projects.description")
    conn.commit()


def run_all_migrations() -> None:
    """Run all incremental migrations against the active database."""
    with get_db() as conn:
        migrate_departments_to_business_units(conn)
        migrate_projects_add_columns(conn)
        migrate_welding_add_bu_fk(conn)
        migrate_add_project_allocations(conn)
        migrate_add_project_description(conn)
