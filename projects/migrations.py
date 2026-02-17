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


def migrate_add_project_type(conn: sqlite3.Connection) -> None:
    """Add project_type column to projects table."""
    if not _table_exists(conn, "projects"):
        return
    if _column_exists(conn, "projects", "project_type"):
        return

    conn.execute("ALTER TABLE projects ADD COLUMN project_type TEXT")
    logger.info("Added column projects.project_type")
    conn.commit()


def migrate_allocations_add_job_fields(conn: sqlite3.Connection) -> None:
    """Add stage, projection_enabled, scope_name, pm, job_id to project_allocations."""
    if not _table_exists(conn, "project_allocations"):
        return

    new_cols = [
        ("stage", "ALTER TABLE project_allocations ADD COLUMN stage TEXT DEFAULT 'Course of Construction'"),
        ("projection_enabled", "ALTER TABLE project_allocations ADD COLUMN projection_enabled INTEGER DEFAULT 1"),
        ("scope_name", "ALTER TABLE project_allocations ADD COLUMN scope_name TEXT"),
        ("pm", "ALTER TABLE project_allocations ADD COLUMN pm TEXT"),
        ("job_id", "ALTER TABLE project_allocations ADD COLUMN job_id INTEGER REFERENCES jobs(id)"),
    ]

    added = False
    for col, sql in new_cols:
        if not _column_exists(conn, "project_allocations", col):
            conn.execute(sql)
            logger.info("Added column project_allocations.%s", col)
            added = True

    if added:
        conn.commit()

    # Backfill: link allocations to jobs via matching job_code = job_number
    unlinked = conn.execute(
        "SELECT pa.id, pa.job_code, pa.project_id "
        "FROM project_allocations pa "
        "WHERE pa.job_id IS NULL AND pa.job_code IS NOT NULL"
    ).fetchall()
    for row in unlinked:
        job = conn.execute(
            "SELECT id, scope_name, pm FROM jobs WHERE job_number = ?",
            (row["job_code"],),
        ).fetchone()
        if job:
            conn.execute(
                "UPDATE project_allocations SET job_id=?, scope_name=COALESCE(scope_name,?), pm=COALESCE(pm,?) WHERE id=?",
                (job["id"], job["scope_name"], job["pm"], row["id"]),
            )
    if unlinked:
        logger.info("Backfilled %d allocation-job links", len(unlinked))

    # Backfill: default stage from parent project for allocations with NULL stage
    conn.execute("""
        UPDATE project_allocations SET stage = (
            SELECT COALESCE(p.stage, 'Course of Construction')
            FROM projects p WHERE p.id = project_allocations.project_id
        )
        WHERE stage IS NULL
    """)

    # Create stub allocations for orphan jobs (have job but no allocation)
    if _table_exists(conn, "jobs"):
        orphans = conn.execute("""
            SELECT j.id AS job_id, j.job_number, j.project_id, j.department_id,
                   j.suffix, j.scope_name, j.pm
            FROM jobs j
            WHERE j.status = 'active'
              AND NOT EXISTS (
                  SELECT 1 FROM project_allocations pa
                  WHERE pa.job_code = j.job_number
              )
        """).fetchall()
        for orph in orphans:
            conn.execute("""
                INSERT OR IGNORE INTO project_allocations
                    (project_id, business_unit_id, subjob, job_code,
                     allocated_budget, weight_adjustment, job_id,
                     scope_name, pm, stage)
                VALUES (?, ?, ?, ?, 0, 1.0, ?, ?, ?,
                        (SELECT COALESCE(p.stage, 'Course of Construction')
                         FROM projects p WHERE p.id = ?))
            """, (
                orph["project_id"], orph["department_id"], orph["suffix"],
                orph["job_number"], orph["job_id"],
                orph["scope_name"], orph["pm"], orph["project_id"],
            ))
        if orphans:
            logger.info("Created %d stub allocations for orphan jobs", len(orphans))

    conn.commit()


def migrate_add_project_gmp(conn: sqlite3.Connection) -> None:
    """Add GMP contract flag and weight multiplier for GMP projections."""
    # Legacy: projects.is_gmp was added first, kept for compat but unused
    if _table_exists(conn, "projects") and not _column_exists(conn, "projects", "is_gmp"):
        conn.execute(
            "ALTER TABLE projects ADD COLUMN is_gmp INTEGER NOT NULL DEFAULT 0"
        )
        logger.info("Added column projects.is_gmp")

    if _table_exists(conn, "budget_settings") and not _column_exists(
        conn, "budget_settings", "gmp_weight_multiplier"
    ):
        conn.execute(
            "ALTER TABLE budget_settings ADD COLUMN "
            "gmp_weight_multiplier REAL NOT NULL DEFAULT 1.5"
        )
        logger.info("Added column budget_settings.gmp_weight_multiplier")

    # GMP flag on allocations (job-level) — the active flag
    if _table_exists(conn, "project_allocations") and not _column_exists(
        conn, "project_allocations", "is_gmp"
    ):
        conn.execute(
            "ALTER TABLE project_allocations ADD COLUMN "
            "is_gmp INTEGER NOT NULL DEFAULT 0"
        )
        logger.info("Added column project_allocations.is_gmp")

    conn.commit()


def migrate_projection_overhaul(conn: sqlite3.Connection) -> None:
    """Add projection_period_jobs, projection_entry_details tables and committed_at column."""
    # New table: per-period job selection
    if not _table_exists(conn, "projection_period_jobs"):
        conn.execute("""
            CREATE TABLE IF NOT EXISTS projection_period_jobs (
                id INTEGER PRIMARY KEY,
                period_id INTEGER NOT NULL REFERENCES projection_periods(id) ON DELETE CASCADE,
                allocation_id INTEGER NOT NULL REFERENCES project_allocations(id) ON DELETE CASCADE,
                included INTEGER NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(period_id, allocation_id)
            )
        """)
        logger.info("Created projection_period_jobs table")

    # New table: job-level detail under projection_entries
    if not _table_exists(conn, "projection_entry_details"):
        conn.execute("""
            CREATE TABLE IF NOT EXISTS projection_entry_details (
                id INTEGER PRIMARY KEY,
                entry_id INTEGER NOT NULL REFERENCES projection_entries(id) ON DELETE CASCADE,
                allocation_id INTEGER NOT NULL REFERENCES project_allocations(id),
                job_code TEXT NOT NULL,
                allocated_hours REAL NOT NULL DEFAULT 0,
                projected_cost REAL NOT NULL DEFAULT 0,
                weight_used REAL,
                is_manual_override INTEGER NOT NULL DEFAULT 0,
                notes TEXT,
                UNIQUE(entry_id, allocation_id)
            )
        """)
        logger.info("Created projection_entry_details table")

    # Add committed_at to projection_snapshots
    if _table_exists(conn, "projection_snapshots") and not _column_exists(
        conn, "projection_snapshots", "committed_at"
    ):
        conn.execute(
            "ALTER TABLE projection_snapshots ADD COLUMN committed_at TEXT"
        )
        logger.info("Added column projection_snapshots.committed_at")

    # Migrate 'Final' status to 'Committed' for existing snapshots
    if _table_exists(conn, "projection_snapshots"):
        conn.execute(
            "UPDATE projection_snapshots SET status = 'Committed', "
            "committed_at = COALESCE(finalized_at, created_at) "
            "WHERE status = 'Final'"
        )

    conn.commit()


def migrate_add_max_hours_per_week(conn: sqlite3.Connection) -> None:
    """Add max_hours_per_week to budget_settings for configurable weekly cap."""
    if _table_exists(conn, "budget_settings") and not _column_exists(
        conn, "budget_settings", "max_hours_per_week"
    ):
        conn.execute(
            "ALTER TABLE budget_settings ADD COLUMN max_hours_per_week REAL NOT NULL DEFAULT 40.0"
        )
        logger.info("Added column budget_settings.max_hours_per_week")
        conn.commit()


def migrate_schema_refactor(conn: sqlite3.Connection) -> None:
    """Add facilities, project_contacts tables; add facility_id to projects, is_gmp to jobs.

    Implements the customers -> facilities -> projects -> jobs hierarchy.
    PM is per-job (not per-project), and is_gmp moves from projects to jobs.
    """
    # 1a. Create facilities table
    if not _table_exists(conn, "facilities"):
        conn.execute("""
            CREATE TABLE IF NOT EXISTS facilities (
                id INTEGER PRIMARY KEY,
                customer_id INTEGER NOT NULL REFERENCES customers(id),
                name TEXT NOT NULL,
                street TEXT,
                city TEXT,
                state TEXT,
                zip TEXT,
                status TEXT DEFAULT 'active',
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(customer_id, name)
            )
        """)
        logger.info("Created facilities table")

    # 1b. Create project_contacts table
    if not _table_exists(conn, "project_contacts"):
        conn.execute("""
            CREATE TABLE IF NOT EXISTS project_contacts (
                id INTEGER PRIMARY KEY,
                customer_id INTEGER REFERENCES customers(id),
                facility_id INTEGER REFERENCES facilities(id),
                project_id INTEGER REFERENCES projects(id),
                name TEXT NOT NULL,
                role TEXT,
                email TEXT,
                phone TEXT,
                is_primary INTEGER DEFAULT 0,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_pc_customer ON project_contacts(customer_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_pc_facility ON project_contacts(facility_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_pc_project ON project_contacts(project_id)")
        logger.info("Created project_contacts table")

    # 1c. Add is_gmp to jobs
    if _table_exists(conn, "jobs") and not _column_exists(conn, "jobs", "is_gmp"):
        conn.execute("ALTER TABLE jobs ADD COLUMN is_gmp INTEGER NOT NULL DEFAULT 0")
        logger.info("Added column jobs.is_gmp")

    # 1c. Add facility_id to projects
    if _table_exists(conn, "projects") and not _column_exists(conn, "projects", "facility_id"):
        conn.execute("ALTER TABLE projects ADD COLUMN facility_id INTEGER REFERENCES facilities(id)")
        logger.info("Added column projects.facility_id")

    conn.commit()

    # 1d. Backfill facilities from existing project address data
    if _table_exists(conn, "facilities") and _table_exists(conn, "projects"):
        # Create facility for each distinct (customer_id, city, state) combo
        rows = conn.execute("""
            SELECT DISTINCT p.customer_id, p.street, p.city, p.state, p.zip
            FROM projects p
            WHERE p.customer_id IS NOT NULL
              AND (p.city IS NOT NULL AND p.city != '')
              AND p.facility_id IS NULL
        """).fetchall()

        for r in rows:
            cust_id = r["customer_id"]
            # Derive facility name from city + state
            facility_name = f"{r['city']}, {r['state']}" if r["state"] else r["city"]
            if not facility_name:
                continue

            existing = conn.execute(
                "SELECT id FROM facilities WHERE customer_id = ? AND name = ?",
                (cust_id, facility_name),
            ).fetchone()

            if existing:
                fac_id = existing["id"]
            else:
                cur = conn.execute(
                    """INSERT INTO facilities (customer_id, name, street, city, state, zip)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (cust_id, facility_name, r["street"], r["city"], r["state"], r["zip"]),
                )
                fac_id = cur.lastrowid
                logger.info("Created facility '%s' for customer %d", facility_name, cust_id)

            # Link matching projects to this facility
            conn.execute(
                """UPDATE projects SET facility_id = ?
                   WHERE customer_id = ? AND facility_id IS NULL
                     AND COALESCE(city, '') = ? AND COALESCE(state, '') = ?""",
                (fac_id, cust_id, r["city"] or "", r["state"] or ""),
            )

        # Backfill jobs.is_gmp from projects.is_gmp (only if column still exists)
        if _column_exists(conn, "projects", "is_gmp"):
            conn.execute("""
                UPDATE jobs SET is_gmp = (
                    SELECT COALESCE(p.is_gmp, 0) FROM projects p WHERE p.id = jobs.project_id
                )
                WHERE is_gmp = 0
            """)

        # Backfill jobs.pm from projects.pm where jobs.pm is empty
        if _column_exists(conn, "projects", "pm"):
            conn.execute("""
                UPDATE jobs SET pm = (
                    SELECT p.pm FROM projects p
                    WHERE p.id = jobs.project_id AND p.pm IS NOT NULL AND p.pm != ''
                )
                WHERE (pm IS NULL OR pm = '')
            """)
            backfilled = conn.execute("SELECT changes()").fetchone()[0]
            if backfilled:
                logger.info("Backfilled PM on %d jobs from projects", backfilled)

        conn.commit()


def migrate_drop_deprecated_columns(conn: sqlite3.Connection) -> None:
    """Drop columns that moved to other tables (Phase 3).

    - pm, pm_employee_id from projects (now on jobs)
    - is_gmp from projects (now on jobs)
    - jobsites table (dead, 0 rows)
    - v_jobs_full view (legacy, references dropped columns + old departments table)
    """
    # Drop views that reference columns we're about to drop from projects
    # Only target views that directly use p.pm, p.pm_employee_id, or p.is_gmp
    views = conn.execute(
        "SELECT name, sql FROM sqlite_master WHERE type='view'"
    ).fetchall()
    dropped_views = []
    for v in views:
        sql = v["sql"] or ""
        # Only drop if the view references the specific columns being dropped
        if "p.pm" in sql or "projects.pm" in sql or "p.is_gmp" in sql or "pm_employee_id" in sql:
            conn.execute(f"DROP VIEW IF EXISTS [{v['name']}]")
            logger.info("Dropped view %s (references dropped projects columns)", v["name"])
            dropped_views.append(v["name"])

    # Drop indexes that reference columns we're about to drop
    for idx_name in ("idx_projects_pm_employee",):
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='index' AND name=?", (idx_name,)
        ).fetchone()
        if row:
            conn.execute(f"DROP INDEX IF EXISTS {idx_name}")
            logger.info("Dropped index %s", idx_name)

    # Drop pm from projects
    if _table_exists(conn, "projects") and _column_exists(conn, "projects", "pm"):
        conn.execute("ALTER TABLE projects DROP COLUMN pm")
        logger.info("Dropped column projects.pm")

    if _table_exists(conn, "projects") and _column_exists(conn, "projects", "pm_employee_id"):
        conn.execute("ALTER TABLE projects DROP COLUMN pm_employee_id")
        logger.info("Dropped column projects.pm_employee_id")

    # Drop is_gmp from projects (now on jobs)
    if _table_exists(conn, "projects") and _column_exists(conn, "projects", "is_gmp"):
        conn.execute("ALTER TABLE projects DROP COLUMN is_gmp")
        logger.info("Dropped column projects.is_gmp")

    # Drop dead jobsites table
    conn.execute("DROP TABLE IF EXISTS jobsites")

    # Recreate views that were dropped
    conn.execute("""
        CREATE VIEW IF NOT EXISTS v_jobs_full AS
        SELECT
            j.id,
            j.job_number,
            j.job_number || ' ' || j.scope_name AS job_display,
            j.scope_name,
            j.suffix,
            j.status AS job_status,
            j.last_updated,
            p.number AS project_number,
            p.name AS project_name,
            p.street AS project_street,
            p.city AS project_city,
            p.state AS project_state,
            p.zip AS project_zip,
            p.status AS project_status,
            c.id AS customer_id,
            c.name AS customer_name,
            c.contact_name AS customer_contact,
            c.billing_city AS customer_city,
            c.billing_state AS customer_state,
            bu.code AS department_number,
            bu.name AS department_name,
            bu.full_name AS department_full_name,
            bu.manager AS department_manager,
            j.pm
        FROM jobs j
        JOIN projects p ON j.project_id = p.id
        JOIN business_units bu ON j.department_id = bu.id
        LEFT JOIN customers c ON p.customer_id = c.id
    """)

    conn.execute("""
        CREATE VIEW IF NOT EXISTS v_expiring_certifications AS
        SELECT
            ec.id,
            ec.employee_id,
            e.first_name || ' ' || e.last_name AS employee_name,
            e.employee_number,
            ec.certification_type,
            ec.certification_number,
            ec.issuing_organization,
            ec.expiry_date,
            ec.status,
            CAST(julianday(ec.expiry_date) - julianday('now') AS INTEGER) AS days_until_expiry
        FROM employee_certifications ec
        JOIN employees e ON e.id = ec.employee_id
        WHERE ec.expiry_date IS NOT NULL
          AND ec.status = 'active'
    """)

    if dropped_views:
        logger.info("Recreated views: v_jobs_full, v_expiring_certifications")

    conn.commit()


def run_all_migrations() -> None:
    """Run all incremental migrations against the active database."""
    with get_db() as conn:
        migrate_departments_to_business_units(conn)
        migrate_projects_add_columns(conn)
        migrate_welding_add_bu_fk(conn)
        migrate_add_project_allocations(conn)
        migrate_add_project_description(conn)
        migrate_add_project_type(conn)
        migrate_allocations_add_job_fields(conn)
        migrate_add_project_gmp(conn)
        migrate_projection_overhaul(conn)
        migrate_add_max_hours_per_week(conn)
        migrate_schema_refactor(conn)
        migrate_drop_deprecated_columns(conn)
