"""
Budget Business Logic

Pure business logic for project and allocation management.
No Flask imports — this module is used by both CLI and API layers.

Functions are organized by domain:
  - Dashboard stats
  - Project CRUD (with budget info)
  - Project allocations (per-BU budget breakdown)
  - Business unit CRUD
  - Project status derivation
"""

import re
import sqlite3
from typing import Any, Dict, List, Optional, Tuple

from qms.core import get_db, get_logger

logger = get_logger("qms.projects.budget")

PROJECT_NUMBER_PATTERN = re.compile(r"^\d{5}(-\d{3}(-\d{2})?)?$")
_FULL_CODE = re.compile(r"^(\d{5})-(\d{3})-(\d{2})$")
_TWO_PART_CODE = re.compile(r"^(\d{5})-(\d{3})$")
_BASE_CODE = re.compile(r"^\d{5}$")

VALID_STAGES = [
    "Proposal",
    "Bidding",
    "Pre-Construction",
    "Construction and Bidding",
    "Course of Construction",
    "Post-Construction",
    "Warranty",
    "Archive",
    "Lost Proposal",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def parse_job_code(code: str) -> Optional[Tuple[str, Optional[str], Optional[str]]]:
    """
    Parse a project code into (base, bu_code, subjob).

    Accepts NNNNN, NNNNN-CCC, or NNNNN-CCC-SS. Returns None if invalid.
    Two-part codes (NNNNN-CCC) are normalized to subjob "00".
    """
    m = _FULL_CODE.match(code)
    if m:
        return m.group(1), m.group(2), m.group(3)
    m = _TWO_PART_CODE.match(code)
    if m:
        return m.group(1), m.group(2), "00"
    if _BASE_CODE.match(code):
        return code, None, None
    return None


def validate_project_number(project_number: str) -> Tuple[bool, Optional[str]]:
    """Validate project number format: NNNNN, NNNNN-CCC, or NNNNN-CCC-SS."""
    if not project_number:
        return False, "Project number is required"
    if not PROJECT_NUMBER_PATTERN.match(project_number):
        return False, "Project number must follow format NNNNN, NNNNN-CCC, or NNNNN-CCC-SS (e.g., 07587 or 06974-230-01)"
    return True, None


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


def _bu_filter_clause(
    bu_ids: Optional[List[int]], alias: str = "pa"
) -> Tuple[str, List[int]]:
    """Build a SQL WHERE clause fragment for BU filtering.

    Returns (sql_fragment, params).  When bu_ids is None, returns empty
    strings and no params (no filtering).
    """
    if not bu_ids:
        return "", []
    placeholders = ",".join("?" for _ in bu_ids)
    return (
        f" AND {alias}.business_unit_id IN ({placeholders})",
        list(bu_ids),
    )


def _accessible_project_ids_sql(bu_ids: Optional[List[int]]) -> Tuple[str, List[int]]:
    """Return a subquery + params that limits to projects with allocations in bu_ids.

    When bu_ids is None, returns a no-op (always true) condition.
    """
    if not bu_ids:
        return "", []
    placeholders = ",".join("?" for _ in bu_ids)
    return (
        f" AND p.id IN (SELECT project_id FROM project_allocations WHERE business_unit_id IN ({placeholders}))",
        list(bu_ids),
    )


def get_dashboard_stats(
    conn: Optional[sqlite3.Connection] = None,
    *,
    bu_ids: Optional[List[int]] = None,
) -> Dict[str, Any]:
    """Get aggregate stats for the dashboard page.

    When bu_ids is provided, only counts projects that have allocations
    in the given business units.
    """
    def _query(c: sqlite3.Connection) -> Dict[str, Any]:
        proj_filter, proj_params = _accessible_project_ids_sql(bu_ids)

        active = c.execute(
            f"SELECT COUNT(*) AS n FROM projects p WHERE stage = 'Course of Construction'{proj_filter}",
            proj_params,
        ).fetchone()["n"]

        budget_row = c.execute(
            f"SELECT COALESCE(SUM(b.total_budget), 0) AS total FROM project_budgets b "
            f"JOIN projects p ON p.id = b.project_id WHERE 1=1{proj_filter}",
            proj_params,
        ).fetchone()
        total_budget = budget_row["total"]

        spent_row = c.execute(
            f"SELECT COALESCE(SUM(t.amount), 0) AS spent FROM project_transactions t "
            f"JOIN projects p ON p.id = t.project_id WHERE 1=1{proj_filter}",
            proj_params,
        ).fetchone()
        total_spent = spent_row["spent"]

        return {
            "active_projects": active,
            "total_budget": total_budget,
            "budget_remaining": total_budget - total_spent,
            "total_spent": total_spent,
        }

    if conn:
        return _query(conn)
    with get_db(readonly=True) as c:
        return _query(c)


# ---------------------------------------------------------------------------
# Projects (with budget joins)
# ---------------------------------------------------------------------------


def list_projects_with_budgets(
    conn: Optional[sqlite3.Connection] = None,
    *,
    bu_ids: Optional[List[int]] = None,
) -> List[Dict[str, Any]]:
    """List all projects with budget, spent totals, and allocation count.

    When bu_ids is provided, only returns projects that have allocations
    in the given business units.
    """
    proj_filter, proj_params = _accessible_project_ids_sql(bu_ids)
    sql = f"""
        SELECT p.*,
               b.total_budget,
               b.weight_adjustment,
               COALESCE(spent.total, 0) AS budget_spent,
               COALESCE(alloc.count, 0) AS allocation_count
        FROM projects p
        LEFT JOIN project_budgets b ON b.project_id = p.id
        LEFT JOIN (
            SELECT project_id, SUM(amount) AS total
            FROM project_transactions GROUP BY project_id
        ) spent ON spent.project_id = p.id
        LEFT JOIN (
            SELECT project_id, COUNT(*) AS count
            FROM project_allocations GROUP BY project_id
        ) alloc ON alloc.project_id = p.id
        WHERE 1=1{proj_filter}
        ORDER BY p.created_at DESC
    """

    def _run(c: sqlite3.Connection):
        return [dict(r) for r in c.execute(sql, proj_params).fetchall()]

    if conn:
        return _run(conn)
    with get_db(readonly=True) as c:
        return _run(c)


def get_project_with_budget(
    conn: sqlite3.Connection, project_id: int
) -> Optional[Dict[str, Any]]:
    """Get a single project with its budget info."""
    row = conn.execute(
        """
        SELECT p.*, b.total_budget, b.weight_adjustment,
               COALESCE(spent.total, 0) AS budget_spent
        FROM projects p
        LEFT JOIN project_budgets b ON b.project_id = p.id
        LEFT JOIN (
            SELECT project_id, SUM(amount) AS total
            FROM project_transactions GROUP BY project_id
        ) spent ON spent.project_id = p.id
        WHERE p.id = ?
        """,
        (project_id,),
    ).fetchone()
    return dict(row) if row else None


def get_project_hub_data(
    conn: sqlite3.Connection, project_number: str
) -> Optional[Dict[str, Any]]:
    """Aggregate all data for the project hub page."""
    row = conn.execute(
        """SELECT p.*, b.total_budget, b.weight_adjustment,
               c.name AS customer_name
           FROM projects p
           LEFT JOIN project_budgets b ON b.project_id = p.id
           LEFT JOIN customers c ON p.customer_id = c.id
           WHERE p.number = ?""",
        (project_number,),
    ).fetchone()
    if not row:
        return None

    project = dict(row)
    pid = project["id"]

    # Allocations (job breakdown)
    allocations = get_project_allocations(conn, pid)

    # Discipline summary (drawings)
    disciplines = [
        dict(r) for r in conn.execute(
            "SELECT * FROM v_discipline_summary WHERE project = ?",
            (project_number,),
        ).fetchall()
    ]

    # Specifications
    specs = [
        dict(r) for r in conn.execute(
            "SELECT id, spec_number, title, spec_type, revision, revision_date "
            "FROM specifications WHERE project_id = ? ORDER BY spec_number",
            (pid,),
        ).fetchall()
    ]

    # Weld count
    weld_count = conn.execute(
        "SELECT COUNT(*) AS n FROM weld_production_welds WHERE project_number = ?",
        (project_number,),
    ).fetchone()["n"]

    # Open alerts
    alerts = [
        dict(r) for r in conn.execute(
            "SELECT flag, message, created_at FROM v_project_alerts WHERE number = ?",
            (project_number,),
        ).fetchall()
    ]

    project["allocations"] = allocations
    project["disciplines"] = disciplines
    project["specs"] = specs
    project["weld_count"] = weld_count
    project["alerts"] = alerts
    return project


def create_project_with_budget(
    conn: sqlite3.Connection,
    *,
    name: str,
    code: str,
    stage: str = "Proposal",
    total_budget: float = 0,
    weight_adjustment: float = 1.0,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    notes: Optional[str] = None,
    client: Optional[str] = None,
    street: Optional[str] = None,
    city: Optional[str] = None,
    state: Optional[str] = None,
    zip_code: Optional[str] = None,
    description: Optional[str] = None,
    allocations: Optional[List[Dict[str, Any]]] = None,
) -> int:
    """Create a project and its budget record. Returns project_id.

    PM is per-job, not per-project — set via job/allocation creation.
    """
    # Extract base number for projects.number (strip BU/subjob if present)
    parsed = parse_job_code(code)
    base_number = parsed[0] if parsed else code

    cursor = conn.execute(
        """
        INSERT INTO projects (number, name, client, stage, status,
                              start_date, end_date, notes, description,
                              street, city, state, zip)
        VALUES (?, ?, ?, ?, 'active', ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (base_number, name, client, stage,
         start_date, end_date, notes, description,
         street, city, state, zip_code),
    )
    project_id = cursor.lastrowid

    # Create allocations if provided, then rollup; else use direct budget
    if allocations:
        for alloc in allocations:
            _insert_allocation(
                conn, project_id, base_number,
                alloc["bu_code"], alloc.get("subjob", "00"),
                alloc.get("budget", 0), alloc.get("weight", 1.0),
                alloc.get("notes"),
            )
        sync_budget_rollup(conn, project_id)
    else:
        conn.execute(
            "INSERT INTO project_budgets (project_id, total_budget, weight_adjustment) "
            "VALUES (?, ?, ?)",
            (project_id, total_budget, weight_adjustment),
        )

    conn.commit()
    return project_id


def update_project_with_budget(
    conn: sqlite3.Connection,
    project_id: int,
    *,
    name: str,
    code: str,
    stage: str = "Proposal",
    total_budget: float = 0,
    weight_adjustment: float = 1.0,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    notes: Optional[str] = None,
    client: Optional[str] = None,
    street: Optional[str] = None,
    city: Optional[str] = None,
    state: Optional[str] = None,
    zip_code: Optional[str] = None,
    description: Optional[str] = None,
    allocations: Optional[List[Dict[str, Any]]] = None,
) -> None:
    """Update a project and its budget record.

    PM is per-job, not per-project — update via job/allocation.
    """
    parsed = parse_job_code(code)
    base_number = parsed[0] if parsed else code

    conn.execute(
        """
        UPDATE projects
        SET number=?, name=?, client=?, stage=?,
            start_date=?, end_date=?, notes=?, description=?,
            street=?, city=?, state=?, zip=?,
            updated_at=CURRENT_TIMESTAMP
        WHERE id=?
        """,
        (base_number, name, client, stage,
         start_date, end_date, notes, description,
         street, city, state, zip_code, project_id),
    )

    if allocations is not None:
        # Replace existing allocations
        conn.execute(
            "DELETE FROM project_allocations WHERE project_id = ?", (project_id,)
        )
        for alloc in allocations:
            _insert_allocation(
                conn, project_id, base_number,
                alloc["bu_code"], alloc.get("subjob", "00"),
                alloc.get("budget", 0), alloc.get("weight", 1.0),
                alloc.get("notes"),
            )
        sync_budget_rollup(conn, project_id)
    else:
        conn.execute(
            """
            INSERT INTO project_budgets (project_id, total_budget, weight_adjustment)
            VALUES (?, ?, ?)
            ON CONFLICT(project_id) DO UPDATE SET
                total_budget=excluded.total_budget,
                weight_adjustment=excluded.weight_adjustment,
                updated_at=CURRENT_TIMESTAMP
            """,
            (project_id, total_budget, weight_adjustment),
        )

    conn.commit()


def delete_project(conn: sqlite3.Connection, project_id: int) -> None:
    """Delete a project (cascades to budgets, transactions, projections).

    Raises ValueError if the project has committed projections.
    """
    if has_committed_projections(conn, project_id):
        raise ValueError("Cannot delete project with committed projections")
    conn.execute("DELETE FROM projects WHERE id=?", (project_id,))
    conn.commit()


# ---------------------------------------------------------------------------
# Project Allocations (per-BU budget breakdown)
# ---------------------------------------------------------------------------


def get_project_allocations(
    conn: sqlite3.Connection, project_id: int
) -> List[Dict[str, Any]]:
    """Get all allocations for a project with BU details."""
    rows = conn.execute(
        """
        SELECT pa.*, bu.code AS bu_code, bu.name AS bu_name
        FROM project_allocations pa
        JOIN business_units bu ON bu.id = pa.business_unit_id
        WHERE pa.project_id = ?
        ORDER BY bu.code, pa.subjob
        """,
        (project_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def upsert_allocation(
    conn: sqlite3.Connection,
    project_id: int,
    bu_code: str,
    subjob: str = "00",
    allocated_budget: float = 0,
    weight_adjustment: float = 1.0,
    notes: Optional[str] = None,
) -> int:
    """Create or update an allocation. Returns allocation id."""
    proj = conn.execute(
        "SELECT number FROM projects WHERE id = ?", (project_id,)
    ).fetchone()
    if not proj:
        raise ValueError(f"Project {project_id} not found")

    alloc_id = _insert_allocation(
        conn, project_id, proj["number"],
        bu_code, subjob, allocated_budget, weight_adjustment, notes,
    )
    sync_budget_rollup(conn, project_id)
    conn.commit()
    return alloc_id


def delete_allocation(conn: sqlite3.Connection, allocation_id: int) -> None:
    """Delete an allocation and sync the rollup."""
    row = conn.execute(
        "SELECT project_id FROM project_allocations WHERE id = ?",
        (allocation_id,),
    ).fetchone()
    if not row:
        return
    project_id = row["project_id"]
    # Remove child rows that lack ON DELETE CASCADE
    conn.execute(
        "DELETE FROM projection_entry_details WHERE allocation_id = ?",
        (allocation_id,),
    )
    conn.execute("DELETE FROM project_allocations WHERE id = ?", (allocation_id,))
    sync_budget_rollup(conn, project_id)
    conn.commit()


def _insert_allocation(
    conn: sqlite3.Connection,
    project_id: int,
    base_number: str,
    bu_code: str,
    subjob: str,
    allocated_budget: float,
    weight_adjustment: float,
    notes: Optional[str] = None,
    *,
    stage: Optional[str] = None,
    scope_name: Optional[str] = None,
    pm: Optional[str] = None,
) -> int:
    """Insert or replace an allocation row. Returns allocation id."""
    bu_row = conn.execute(
        "SELECT id FROM business_units WHERE code = ?", (bu_code,)
    ).fetchone()
    if not bu_row:
        raise ValueError(f"Business unit code '{bu_code}' not found")

    job_code = f"{base_number}-{bu_code}-{subjob}"

    # Try to auto-link to jobs table
    job_row = conn.execute(
        "SELECT id, scope_name, pm FROM jobs WHERE job_number = ?", (job_code,)
    ).fetchone()
    job_id = job_row["id"] if job_row else None
    if job_row and not scope_name:
        scope_name = job_row["scope_name"]
    if job_row and not pm:
        pm = job_row["pm"]

    cursor = conn.execute(
        """
        INSERT INTO project_allocations
            (project_id, business_unit_id, subjob, job_code,
             allocated_budget, weight_adjustment, notes,
             stage, scope_name, pm, job_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(project_id, business_unit_id, subjob) DO UPDATE SET
            job_code=excluded.job_code,
            allocated_budget=excluded.allocated_budget,
            weight_adjustment=excluded.weight_adjustment,
            notes=excluded.notes,
            updated_at=CURRENT_TIMESTAMP
        """,
        (project_id, bu_row["id"], subjob, job_code,
         allocated_budget, weight_adjustment, notes,
         stage, scope_name, pm, job_id),
    )
    return cursor.lastrowid


def list_projects_hierarchical(
    conn: Optional[sqlite3.Connection] = None,
    *,
    bu_ids: Optional[List[int]] = None,
) -> List[Dict[str, Any]]:
    """List projects with nested job (allocation) arrays for the hierarchical view.

    When bu_ids is provided, only returns projects that have allocations
    in the given business units, and only includes those allocations.
    """
    proj_filter, proj_params = _accessible_project_ids_sql(bu_ids)
    bu_filter, bu_params = _bu_filter_clause(bu_ids)

    proj_sql = f"""
        SELECT p.*,
               COALESCE(b.total_budget, 0) AS total_budget,
               COALESCE(b.weight_adjustment, 1.0) AS weight_adjustment,
               COALESCE(spent.total, 0) AS budget_spent
        FROM projects p
        LEFT JOIN project_budgets b ON b.project_id = p.id
        LEFT JOIN (
            SELECT project_id, SUM(amount) AS total
            FROM project_transactions GROUP BY project_id
        ) spent ON spent.project_id = p.id
        WHERE 1=1{proj_filter}
        ORDER BY p.created_at DESC
    """
    alloc_sql = f"""
        SELECT pa.*, bu.code AS bu_code, bu.name AS bu_name,
               COALESCE(j.scope_name, pa.scope_name) AS scope_name,
               COALESCE(j.pm, pa.pm) AS pm
        FROM project_allocations pa
        JOIN business_units bu ON bu.id = pa.business_unit_id
        LEFT JOIN jobs j ON j.id = pa.job_id
        WHERE 1=1{bu_filter}
        ORDER BY bu.code, pa.subjob
    """

    def _run(c: sqlite3.Connection):
        projects = [dict(r) for r in c.execute(proj_sql, proj_params).fetchall()]
        allocs = [dict(r) for r in c.execute(alloc_sql, bu_params).fetchall()]

        # Group allocations by project_id
        alloc_map: Dict[int, List[Dict[str, Any]]] = {}
        for a in allocs:
            alloc_map.setdefault(a["project_id"], []).append(a)

        for p in projects:
            p["jobs"] = alloc_map.get(p["id"], [])
        return projects

    if conn:
        return _run(conn)
    with get_db(readonly=True) as c:
        return _run(c)


INACTIVE_STAGES = {"Archive", "Lost Proposal", "Warranty"}


def update_allocation_field(
    conn: sqlite3.Connection, allocation_id: int, field: str, value: Any
) -> bool:
    """Update a single field on an allocation. Returns True if found."""
    allowed = {"weight_adjustment", "projection_enabled", "stage", "is_gmp"}
    if field not in allowed:
        raise ValueError(f"Field '{field}' not updatable via this API")
    if field == "stage" and value not in VALID_STAGES:
        raise ValueError(f"Invalid stage: {value}")
    cursor = conn.execute(
        f"UPDATE project_allocations SET {field}=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
        (value, allocation_id),
    )
    # Auto-clear projection flag when moving to an inactive stage
    if field == "stage" and value in INACTIVE_STAGES:
        conn.execute(
            "UPDATE project_allocations SET projection_enabled=0 WHERE id=? AND projection_enabled=1",
            (allocation_id,),
        )
    conn.commit()
    return cursor.rowcount > 0


def update_allocation_budget(
    conn: sqlite3.Connection, allocation_id: int, budget: float
) -> bool:
    """Update an allocation's budget and sync the project rollup."""
    row = conn.execute(
        "SELECT project_id FROM project_allocations WHERE id = ?",
        (allocation_id,),
    ).fetchone()
    if not row:
        return False
    conn.execute(
        "UPDATE project_allocations SET allocated_budget=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
        (budget, allocation_id),
    )
    sync_budget_rollup(conn, row["project_id"])
    conn.commit()
    return True


def bulk_update_allocations(
    conn: sqlite3.Connection,
    allocation_ids: List[int],
    action: str,
    value: Any = None,
) -> Dict[str, Any]:
    """Apply a bulk action to multiple allocations.

    Actions: 'set_stage', 'set_projection', 'set_gmp', 'set_weight', 'delete'.
    Returns summary dict with counts.
    """
    if not allocation_ids:
        return {"updated": 0}

    placeholders = ",".join("?" for _ in allocation_ids)
    updated = 0

    if action == "set_stage":
        if value not in VALID_STAGES:
            raise ValueError(f"Invalid stage: {value}")
        cursor = conn.execute(
            f"UPDATE project_allocations SET stage=?, updated_at=CURRENT_TIMESTAMP "
            f"WHERE id IN ({placeholders})",
            [value] + list(allocation_ids),
        )
        updated = cursor.rowcount
        # Auto-clear projection flag when moving to an inactive stage
        if value in INACTIVE_STAGES:
            conn.execute(
                f"UPDATE project_allocations SET projection_enabled=0 "
                f"WHERE id IN ({placeholders}) AND projection_enabled=1",
                list(allocation_ids),
            )

    elif action == "set_projection":
        flag = 1 if value else 0
        cursor = conn.execute(
            f"UPDATE project_allocations SET projection_enabled=?, updated_at=CURRENT_TIMESTAMP "
            f"WHERE id IN ({placeholders})",
            [flag] + list(allocation_ids),
        )
        updated = cursor.rowcount

    elif action == "set_gmp":
        flag = 1 if value else 0
        cursor = conn.execute(
            f"UPDATE project_allocations SET is_gmp=?, updated_at=CURRENT_TIMESTAMP "
            f"WHERE id IN ({placeholders})",
            [flag] + list(allocation_ids),
        )
        updated = cursor.rowcount

    elif action == "set_weight":
        weight = float(value)
        if not (0 <= weight <= 5):
            raise ValueError("Weight must be between 0 and 5")
        cursor = conn.execute(
            f"UPDATE project_allocations SET weight_adjustment=?, updated_at=CURRENT_TIMESTAMP "
            f"WHERE id IN ({placeholders})",
            [weight] + list(allocation_ids),
        )
        updated = cursor.rowcount

    elif action == "delete":
        # Gather affected project_ids for rollup sync
        rows = conn.execute(
            f"SELECT DISTINCT project_id FROM project_allocations WHERE id IN ({placeholders})",
            list(allocation_ids),
        ).fetchall()
        # Remove child rows that lack ON DELETE CASCADE
        conn.execute(
            f"DELETE FROM projection_entry_details WHERE allocation_id IN ({placeholders})",
            list(allocation_ids),
        )
        cursor = conn.execute(
            f"DELETE FROM project_allocations WHERE id IN ({placeholders})",
            list(allocation_ids),
        )
        updated = cursor.rowcount
        for row in rows:
            sync_budget_rollup(conn, row["project_id"])
    else:
        raise ValueError(f"Unknown bulk action: {action}")

    conn.commit()
    return {"updated": updated}


def sync_budget_rollup(conn: sqlite3.Connection, project_id: int) -> None:
    """Set project_budgets.total_budget = SUM of allocations."""
    result = conn.execute(
        "SELECT COALESCE(SUM(allocated_budget), 0) AS total "
        "FROM project_allocations WHERE project_id = ?",
        (project_id,),
    ).fetchone()
    total = result["total"]

    existing = conn.execute(
        "SELECT id FROM project_budgets WHERE project_id = ?", (project_id,)
    ).fetchone()
    if existing:
        conn.execute(
            "UPDATE project_budgets SET total_budget = ?, "
            "updated_at = CURRENT_TIMESTAMP WHERE project_id = ?",
            (total, project_id),
        )
    elif total > 0:
        conn.execute(
            "INSERT INTO project_budgets (project_id, total_budget) VALUES (?, ?)",
            (project_id, total),
        )


# ---------------------------------------------------------------------------
# Business Units
# ---------------------------------------------------------------------------


def list_business_units(
    conn: Optional[sqlite3.Connection] = None,
    *,
    bu_ids: Optional[List[int]] = None,
) -> List[Dict[str, Any]]:
    """List business units ordered by code.

    When bu_ids is provided, only returns those specific business units.
    """
    def _run(c: sqlite3.Connection):
        if bu_ids:
            placeholders = ",".join("?" for _ in bu_ids)
            return [dict(r) for r in c.execute(
                f"SELECT * FROM business_units WHERE id IN ({placeholders}) ORDER BY code",
                bu_ids,
            ).fetchall()]
        return [dict(r) for r in c.execute(
            "SELECT * FROM business_units ORDER BY code"
        ).fetchall()]

    if conn:
        return _run(conn)
    with get_db(readonly=True) as c:
        return _run(c)


def create_business_unit(
    conn: sqlite3.Connection, *, code: str, name: str, description: str = ""
) -> int:
    """Create a business unit. Returns its id."""
    cursor = conn.execute(
        "INSERT INTO business_units (code, name, description) VALUES (?, ?, ?)",
        (code, name, description),
    )
    conn.commit()
    return cursor.lastrowid


def update_business_unit(
    conn: sqlite3.Connection, bu_id: int, *, code: str, name: str, description: str = ""
) -> None:
    conn.execute(
        "UPDATE business_units SET code=?, name=?, description=?, "
        "updated_at=CURRENT_TIMESTAMP WHERE id=?",
        (code, name, description, bu_id),
    )
    conn.commit()


def delete_business_unit(conn: sqlite3.Connection, bu_id: int) -> bool:
    """Delete a BU. Returns False if it's referenced by projects."""
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM jobs WHERE department_id = ?", (bu_id,)
    ).fetchone()
    if row["n"] > 0:
        return False
    conn.execute("DELETE FROM business_units WHERE id=?", (bu_id,))
    conn.commit()
    return True


# ---------------------------------------------------------------------------
# Re-exports from timetracker (kept for backward compatibility)
# ---------------------------------------------------------------------------


def has_committed_projections(conn, project_id):
    """Thin stub — delegates to timetracker.projections."""
    from qms.timetracker.projections import has_committed_projections as _hcp
    return _hcp(conn, project_id)


# ---------------------------------------------------------------------------
# Project Status Derivation
# ---------------------------------------------------------------------------


def sync_project_status(
    conn: sqlite3.Connection, project_id: Optional[int] = None
) -> None:
    """Derive projects.status from jobs — active if ANY job is active.

    Call this after any job status change (SIS import, Procore import).
    """
    if project_id:
        conn.execute(
            """
            UPDATE projects SET status = CASE
                WHEN EXISTS (
                    SELECT 1 FROM jobs j WHERE j.project_id = projects.id AND j.status = 'active'
                ) THEN 'active'
                ELSE 'inactive'
            END
            WHERE id = ?
            """,
            (project_id,),
        )
    else:
        conn.execute("""
            UPDATE projects SET status = CASE
                WHEN EXISTS (
                    SELECT 1 FROM jobs j WHERE j.project_id = projects.id AND j.status = 'active'
                ) THEN 'active'
                ELSE 'inactive'
            END
        """)
    conn.commit()
