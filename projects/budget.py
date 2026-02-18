"""
Budget & Projection Business Logic

Pure business logic for budget-weighted hour allocation across projects.
No Flask imports — this module is used by both CLI and API layers.

Functions are organized by domain:
  - Dashboard stats
  - Project CRUD (with budget info)
  - Business unit CRUD
  - Transaction CRUD
  - Settings CRUD
  - Projection calculation & management
"""

import re
import sqlite3
from calendar import monthrange
from datetime import date, datetime, timedelta
from math import floor
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


def round_to_nearest_5(num: float) -> float:
    """Round a number to the nearest 5."""
    return round(num / 5) * 5


def calculate_working_days(year: int, month: int) -> int:
    """Calculate working days (Mon-Thu) in a given month."""
    days_in_month = monthrange(year, month)[1]
    working_days = 0
    for day in range(1, days_in_month + 1):
        dt = datetime(year, month, day)
        if dt.weekday() <= 3:  # Mon=0 .. Thu=3
            working_days += 1
    return working_days


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
# Transactions
# ---------------------------------------------------------------------------


def list_transactions(
    conn: Optional[sqlite3.Connection] = None,
    *,
    project_id: Optional[int] = None,
    transaction_type: Optional[str] = None,
    bu_ids: Optional[List[int]] = None,
) -> List[Dict[str, Any]]:
    """List transactions with optional filters.

    When bu_ids is provided, only returns transactions for projects that
    have allocations in the given business units.
    """
    sql = """
        SELECT t.*, p.name AS project_name, p.number AS project_code
        FROM project_transactions t
        JOIN projects p ON t.project_id = p.id
    """
    conditions = []
    params: list = []
    if project_id:
        conditions.append("t.project_id = ?")
        params.append(project_id)
    if transaction_type:
        conditions.append("t.transaction_type = ?")
        params.append(transaction_type)
    if bu_ids:
        placeholders = ",".join("?" for _ in bu_ids)
        conditions.append(
            f"p.id IN (SELECT project_id FROM project_allocations WHERE business_unit_id IN ({placeholders}))"
        )
        params.extend(bu_ids)
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY t.transaction_date DESC, t.created_at DESC"

    def _run(c: sqlite3.Connection):
        return [dict(r) for r in c.execute(sql, params).fetchall()]

    if conn:
        return _run(conn)
    with get_db(readonly=True) as c:
        return _run(c)


def get_transaction(conn: sqlite3.Connection, txn_id: int) -> Optional[Dict[str, Any]]:
    row = conn.execute(
        """
        SELECT t.*, p.name AS project_name, p.number AS project_code
        FROM project_transactions t
        JOIN projects p ON t.project_id = p.id
        WHERE t.id = ?
        """,
        (txn_id,),
    ).fetchone()
    return dict(row) if row else None


def create_transaction(
    conn: sqlite3.Connection,
    *,
    project_id: int,
    transaction_date: str,
    transaction_type: str,
    description: str,
    amount: float,
    hours: Optional[float] = None,
    rate: Optional[float] = None,
    notes: Optional[str] = None,
) -> int:
    """Create a transaction. For Time type, amount = hours * rate."""
    if transaction_type == "Time" and hours and rate:
        amount = hours * rate

    cursor = conn.execute(
        """
        INSERT INTO project_transactions
            (project_id, transaction_date, transaction_type, description,
             amount, hours, rate, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (project_id, transaction_date, transaction_type, description,
         amount, hours, rate, notes),
    )
    conn.commit()
    return cursor.lastrowid


def update_transaction(
    conn: sqlite3.Connection,
    txn_id: int,
    *,
    project_id: int,
    transaction_date: str,
    transaction_type: str,
    description: str,
    amount: float,
    hours: Optional[float] = None,
    rate: Optional[float] = None,
    notes: Optional[str] = None,
) -> None:
    if transaction_type == "Time" and hours and rate:
        amount = hours * rate

    conn.execute(
        """
        UPDATE project_transactions
        SET project_id=?, transaction_date=?, transaction_type=?, description=?,
            amount=?, hours=?, rate=?, notes=?, updated_at=CURRENT_TIMESTAMP
        WHERE id=?
        """,
        (project_id, transaction_date, transaction_type, description,
         amount, hours, rate, notes, txn_id),
    )
    conn.commit()


def delete_transaction(conn: sqlite3.Connection, txn_id: int) -> None:
    conn.execute("DELETE FROM project_transactions WHERE id=?", (txn_id,))
    conn.commit()


# ---------------------------------------------------------------------------
# Settings (singleton)
# ---------------------------------------------------------------------------


def get_settings(conn: Optional[sqlite3.Connection] = None) -> Dict[str, Any]:
    """Get budget settings, creating defaults if missing."""
    def _run(c: sqlite3.Connection) -> Dict[str, Any]:
        row = c.execute("SELECT * FROM budget_settings WHERE id = 1").fetchone()
        if not row:
            c.execute(
                "INSERT INTO budget_settings (id, company_name, default_hourly_rate, "
                "working_hours_per_month, fiscal_year_start_month, gmp_weight_multiplier, "
                "max_hours_per_week) "
                "VALUES (1, 'My Company', 150.0, 176, 1, 1.5, 40.0)"
            )
            c.commit()
            row = c.execute("SELECT * FROM budget_settings WHERE id = 1").fetchone()
        return dict(row)

    if conn:
        return _run(conn)
    with get_db() as c:
        return _run(c)


def update_settings(
    conn: sqlite3.Connection,
    *,
    company_name: str = "My Company",
    default_hourly_rate: float = 150.0,
    working_hours_per_month: int = 176,
    fiscal_year_start_month: int = 1,
    gmp_weight_multiplier: float = 1.5,
    max_hours_per_week: float = 40.0,
) -> None:
    conn.execute(
        """
        UPDATE budget_settings
        SET company_name=?, default_hourly_rate=?, working_hours_per_month=?,
            fiscal_year_start_month=?, gmp_weight_multiplier=?,
            max_hours_per_week=?,
            updated_at=CURRENT_TIMESTAMP
        WHERE id=1
        """,
        (company_name, default_hourly_rate, working_hours_per_month,
         fiscal_year_start_month, gmp_weight_multiplier, max_hours_per_week),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Projection Periods
# ---------------------------------------------------------------------------


def list_projection_periods(
    conn: Optional[sqlite3.Connection] = None,
) -> List[Dict[str, Any]]:
    sql = """
        SELECT pp.*,
               COUNT(DISTINCT ps.id) AS snapshot_count,
               MAX(ps.version) AS latest_version
        FROM projection_periods pp
        LEFT JOIN projection_snapshots ps ON pp.id = ps.period_id
        GROUP BY pp.id
        ORDER BY pp.year DESC, pp.month DESC
    """

    def _run(c: sqlite3.Connection):
        return [dict(r) for r in c.execute(sql).fetchall()]

    if conn:
        return _run(conn)
    with get_db(readonly=True) as c:
        return _run(c)


def create_projection_period(
    conn: sqlite3.Connection, *, year: int, month: int
) -> Dict[str, Any]:
    """Create a period with auto-calculated working days. Returns period dict."""
    working_days = calculate_working_days(year, month)
    total_hours = working_days * 10

    cursor = conn.execute(
        "INSERT INTO projection_periods (year, month, working_days, total_hours) "
        "VALUES (?, ?, ?, ?)",
        (year, month, working_days, total_hours),
    )
    conn.commit()
    return {
        "id": cursor.lastrowid,
        "year": year,
        "month": month,
        "working_days": working_days,
        "total_hours": total_hours,
    }


def get_projection_period(
    conn: sqlite3.Connection, period_id: int
) -> Optional[Dict[str, Any]]:
    row = conn.execute(
        "SELECT * FROM projection_periods WHERE id = ?", (period_id,)
    ).fetchone()
    if not row:
        return None

    result = dict(row)
    snap = conn.execute(
        "SELECT * FROM projection_snapshots "
        "WHERE period_id = ? AND is_active = 1 ORDER BY version DESC LIMIT 1",
        (period_id,),
    ).fetchone()
    result["active_snapshot"] = dict(snap) if snap else None
    return result


def toggle_period_lock(
    conn: sqlite3.Connection, period_id: int, *, locked: bool
) -> bool:
    """Lock or unlock a period. Returns True if found."""
    cursor = conn.execute(
        "UPDATE projection_periods SET is_locked = ? WHERE id = ?",
        (1 if locked else 0, period_id),
    )
    conn.commit()
    return cursor.rowcount > 0


# ---------------------------------------------------------------------------
# Projection Calculation & Snapshots
# ---------------------------------------------------------------------------


def calculate_projection(
    conn: sqlite3.Connection, period_id: int
) -> Dict[str, Any]:
    """
    Calculate budget-weighted hour allocation for a period (preview only).

    Algorithm (job-level):
    1. Get included jobs from projection_period_jobs (auto-populated on load)
    2. Pro-rate each job's budget by project remaining-budget ratio
    3. weight = effective_budget * weight_adjustment * gmp_factor
    4. Allocate hours proportionally, rounded to nearest 5
    5. Adjust largest job to match total hours exactly
    """
    period = conn.execute(
        "SELECT * FROM projection_periods WHERE id = ?", (period_id,)
    ).fetchone()
    if not period:
        return {"error": "Period not found"}
    if period["is_locked"]:
        return {"error": "Period is locked"}

    settings = get_settings(conn)
    hourly_rate = settings["default_hourly_rate"]
    gmp_multiplier = settings.get("gmp_weight_multiplier", 1.5)

    # Ensure period_jobs are populated
    load_period_jobs(conn, period_id)

    # Job-level query: uses projection_period_jobs for per-period toggles
    rows = conn.execute(
        """
        SELECT pa.id AS allocation_id,
               pa.job_code,
               pa.allocated_budget,
               pa.weight_adjustment,
               pa.is_gmp,
               COALESCE(pa.scope_name, '') AS scope_name,
               bu.code AS bu_code,
               bu.name AS bu_name,
               p.id AS project_id,
               p.number AS project_number,
               p.name AS project_name,
               COALESCE(b.total_budget, 0) AS project_total_budget,
               COALESCE(spent.total, 0) AS project_budget_spent
        FROM projection_period_jobs ppj
        JOIN project_allocations pa ON pa.id = ppj.allocation_id
        JOIN projects p ON p.id = pa.project_id
        JOIN business_units bu ON bu.id = pa.business_unit_id
        LEFT JOIN project_budgets b ON b.project_id = p.id
        LEFT JOIN (
            SELECT project_id, SUM(amount) AS total
            FROM project_transactions GROUP BY project_id
        ) spent ON spent.project_id = p.id
        WHERE ppj.period_id = ?
          AND ppj.included = 1
          AND pa.allocated_budget > 0
        ORDER BY pa.allocated_budget DESC
        """,
        (period_id,),
    ).fetchall()
    jobs = [dict(r) for r in rows]

    if not jobs:
        return {
            "period_id": period_id,
            "total_hours": period["total_hours"],
            "hourly_rate": hourly_rate,
            "entries": [],
            "total_cost": 0,
        }

    total_hours = period["total_hours"]

    # Calculate per-job weights
    total_weight = 0
    for j in jobs:
        ptb = j["project_total_budget"]
        remaining_ratio = max(0, (ptb - j["project_budget_spent"]) / ptb) if ptb > 0 else 0
        j["effective_budget"] = j["allocated_budget"] * remaining_ratio
        gmp_factor = gmp_multiplier if j["is_gmp"] else 1.0
        j["weight"] = j["effective_budget"] * j["weight_adjustment"] * gmp_factor
        total_weight += j["weight"]

    # Allocate hours proportionally
    allocs = []
    for j in jobs:
        raw = (j["weight"] / total_weight * total_hours
               if total_weight > 0 else 0)
        rounded = round_to_nearest_5(raw)
        allocs.append({"job": j, "raw_hours": raw, "rounded_hours": rounded})

    # Adjust largest job to match total exactly (only if there are valid weights)
    rounded_total = sum(a["rounded_hours"] for a in allocs)
    if rounded_total != total_hours and allocs and total_weight > 0:
        diff = total_hours - rounded_total
        allocs.sort(key=lambda a: a["raw_hours"], reverse=True)
        allocs[0]["rounded_hours"] += diff

    entries = []
    total_cost = 0
    for a in allocs:
        j = a["job"]
        hours = a["rounded_hours"]
        cost = hours * hourly_rate
        total_cost += cost
        entries.append({
            "allocation_id": j["allocation_id"],
            "job_code": j["job_code"],
            "bu_code": j["bu_code"],
            "bu_name": j["bu_name"],
            "scope_name": j["scope_name"],
            "is_gmp": bool(j["is_gmp"]),
            "project_id": j["project_id"],
            "project_name": j["project_name"],
            "project_code": j["project_number"],
            "allocated_budget": j["allocated_budget"],
            "effective_budget": j["effective_budget"],
            "weight_adjustment": j["weight_adjustment"],
            "weight_used": j["weight"],
            "allocated_hours": hours,
            "projected_cost": cost,
        })

    return {
        "period_id": period_id,
        "year": period["year"],
        "month": period["month"],
        "working_days": period["working_days"],
        "total_hours": total_hours,
        "hourly_rate": hourly_rate,
        "entries": entries,
        "total_cost": total_cost,
    }


def get_active_projection(
    conn: sqlite3.Connection, period_id: int
) -> Optional[Dict[str, Any]]:
    """Get the active snapshot for a period with its entries."""
    snap = conn.execute(
        "SELECT * FROM projection_snapshots "
        "WHERE period_id = ? AND is_active = 1 ORDER BY version DESC LIMIT 1",
        (period_id,),
    ).fetchone()
    if not snap:
        return None

    entries = conn.execute(
        """
        SELECT pe.*, p.name AS project_name, p.number AS project_code
        FROM projection_entries pe
        JOIN projects p ON pe.project_id = p.id
        WHERE pe.snapshot_id = ?
        ORDER BY pe.allocated_hours DESC
        """,
        (snap["id"],),
    ).fetchall()

    result = dict(snap)
    result["entries"] = [dict(e) for e in entries]
    return result


def create_projection_snapshot(
    conn: sqlite3.Connection,
    period_id: int,
    *,
    entries: List[Dict[str, Any]],
    detail_entries: Optional[List[Dict[str, Any]]] = None,
    hourly_rate: float,
    total_hours: int,
    name: Optional[str] = None,
    description: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a versioned snapshot with project-level and optional job-level entries."""
    next_ver = conn.execute(
        "SELECT COALESCE(MAX(version), 0) + 1 AS v FROM projection_snapshots "
        "WHERE period_id = ?",
        (period_id,),
    ).fetchone()["v"]

    total_cost = sum(e["projected_cost"] for e in entries)

    cursor = conn.execute(
        """
        INSERT INTO projection_snapshots
            (period_id, version, name, description, hourly_rate,
             total_hours, total_projected_cost, status, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'Draft', 1)
        """,
        (period_id, next_ver, name or f"Version {next_ver}", description,
         hourly_rate, total_hours, total_cost),
    )
    snapshot_id = cursor.lastrowid

    # Deactivate other snapshots
    conn.execute(
        "UPDATE projection_snapshots SET is_active = 0 "
        "WHERE period_id = ? AND id != ?",
        (period_id, snapshot_id),
    )

    # Build map of project_id -> entry_id for linking details
    entry_id_map: Dict[int, int] = {}
    for e in entries:
        cur = conn.execute(
            """
            INSERT INTO projection_entries
                (snapshot_id, project_id, allocated_hours, projected_cost,
                 weight_used, remaining_budget_at_time, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (snapshot_id, e["project_id"], e["allocated_hours"],
             e["projected_cost"], e.get("weight_used"),
             e.get("remaining_budget"), e.get("notes")),
        )
        entry_id_map[e["project_id"]] = cur.lastrowid

    # Insert job-level details if provided
    if detail_entries:
        for d in detail_entries:
            eid = entry_id_map.get(d.get("project_id"))
            if not eid:
                continue
            conn.execute(
                """
                INSERT INTO projection_entry_details
                    (entry_id, allocation_id, job_code, allocated_hours,
                     projected_cost, weight_used, is_manual_override, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (eid, d["allocation_id"], d["job_code"],
                 d.get("allocated_hours", 0), d.get("projected_cost", 0),
                 d.get("weight_used"), d.get("is_manual_override", 0),
                 d.get("notes")),
            )

    conn.commit()
    return {"id": snapshot_id, "version": next_ver}


def finalize_snapshot(conn: sqlite3.Connection, snapshot_id: int) -> bool:
    """Mark snapshot as Final, supersede previous Finals.  (Legacy compat.)"""
    snap = conn.execute(
        "SELECT * FROM projection_snapshots WHERE id = ?", (snapshot_id,)
    ).fetchone()
    if not snap:
        return False

    conn.execute(
        "UPDATE projection_snapshots SET status = 'Superseded' "
        "WHERE period_id = ? AND id != ? AND status IN ('Final','Committed')",
        (snap["period_id"], snapshot_id),
    )
    conn.execute(
        "UPDATE projection_snapshots SET status = 'Committed', "
        "committed_at = CURRENT_TIMESTAMP, finalized_at = CURRENT_TIMESTAMP WHERE id = ?",
        (snapshot_id,),
    )
    conn.commit()
    return True


# ---------------------------------------------------------------------------
# Per-Period Job Selection
# ---------------------------------------------------------------------------


def load_period_jobs(
    conn: sqlite3.Connection, period_id: int
) -> List[Dict[str, Any]]:
    """Load eligible jobs for a period, auto-populating on first access.

    Only considers allocations where the global ``projection_enabled=1``
    (set on the Projects page).  If no rows exist in
    ``projection_period_jobs`` for this period, auto-populate from eligible
    allocations with ``included=1``.
    """
    # Sync: remove allocations that are no longer eligible
    conn.execute(
        """
        DELETE FROM projection_period_jobs
        WHERE period_id = ?
          AND allocation_id IN (
              SELECT pa.id FROM project_allocations pa
              WHERE pa.projection_enabled = 0
                 OR pa.stage IN ('Archive', 'Lost Proposal', 'Warranty')
          )
        """,
        (period_id,),
    )
    # Sync: add any newly-enabled allocations (INSERT OR IGNORE preserves existing toggles)
    conn.execute(
        """
        INSERT OR IGNORE INTO projection_period_jobs (period_id, allocation_id, included)
        SELECT ?, pa.id, 1
        FROM project_allocations pa
        WHERE pa.projection_enabled = 1
          AND pa.stage NOT IN ('Archive', 'Lost Proposal', 'Warranty')
        """,
        (period_id,),
    )
    conn.commit()

    # Return all eligible jobs with details
    rows = conn.execute(
        """
        SELECT ppj.id AS period_job_id,
               ppj.included,
               pa.id AS allocation_id,
               pa.job_code,
               pa.allocated_budget,
               pa.weight_adjustment,
               pa.is_gmp,
               pa.projection_enabled,
               COALESCE(pa.scope_name, '') AS scope_name,
               COALESCE(pa.pm, '') AS pm,
               bu.code AS bu_code,
               bu.name AS bu_name,
               p.id AS project_id,
               p.number AS project_number,
               p.name AS project_name,
               p.stage AS project_stage,
               COALESCE(b.total_budget, 0) AS project_total_budget,
               COALESCE(spent.total, 0) AS project_budget_spent
        FROM projection_period_jobs ppj
        JOIN project_allocations pa ON pa.id = ppj.allocation_id
        JOIN projects p ON p.id = pa.project_id
        JOIN business_units bu ON bu.id = pa.business_unit_id
        LEFT JOIN project_budgets b ON b.project_id = p.id
        LEFT JOIN (
            SELECT project_id, SUM(amount) AS total
            FROM project_transactions GROUP BY project_id
        ) spent ON spent.project_id = p.id
        WHERE ppj.period_id = ?
        ORDER BY pa.allocated_budget DESC
        """,
        (period_id,),
    ).fetchall()

    result = []
    for r in rows:
        d = dict(r)
        ptb = d["project_total_budget"]
        d["remaining_budget"] = ptb - d["project_budget_spent"]
        result.append(d)
    return result


def toggle_period_job(
    conn: sqlite3.Connection,
    period_id: int,
    allocation_id: int,
    included: bool,
) -> bool:
    """Toggle a single job's inclusion for a period. Returns True on success."""
    cursor = conn.execute(
        """
        INSERT INTO projection_period_jobs (period_id, allocation_id, included)
        VALUES (?, ?, ?)
        ON CONFLICT(period_id, allocation_id) DO UPDATE SET included = excluded.included
        """,
        (period_id, allocation_id, 1 if included else 0),
    )
    conn.commit()
    return cursor.rowcount > 0


def bulk_toggle_period_jobs(
    conn: sqlite3.Connection,
    period_id: int,
    allocation_ids: List[int],
    included: bool,
) -> int:
    """Bulk toggle job inclusion. Returns count of affected rows."""
    if not allocation_ids:
        return 0
    flag = 1 if included else 0
    count = 0
    for aid in allocation_ids:
        conn.execute(
            """
            INSERT INTO projection_period_jobs (period_id, allocation_id, included)
            VALUES (?, ?, ?)
            ON CONFLICT(period_id, allocation_id) DO UPDATE SET included = excluded.included
            """,
            (period_id, aid, flag),
        )
        count += 1
    conn.commit()
    return count


# ---------------------------------------------------------------------------
# Snapshot Listing & Details
# ---------------------------------------------------------------------------


def list_snapshots(
    conn: sqlite3.Connection, period_id: int
) -> List[Dict[str, Any]]:
    """List all snapshots for a period, ordered by version DESC."""
    rows = conn.execute(
        """
        SELECT id, period_id, version, name, status, is_active,
               total_hours, total_projected_cost, hourly_rate,
               created_at, committed_at
        FROM projection_snapshots
        WHERE period_id = ?
        ORDER BY version DESC
        """,
        (period_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_snapshot_with_details(
    conn: sqlite3.Connection, snapshot_id: int
) -> Optional[Dict[str, Any]]:
    """Return snapshot metadata + project entries with nested job details."""
    snap = conn.execute(
        "SELECT * FROM projection_snapshots WHERE id = ?", (snapshot_id,)
    ).fetchone()
    if not snap:
        return None

    result = dict(snap)

    # Project-level entries
    entries = conn.execute(
        """
        SELECT pe.*, p.name AS project_name, p.number AS project_code
        FROM projection_entries pe
        JOIN projects p ON pe.project_id = p.id
        WHERE pe.snapshot_id = ?
        ORDER BY pe.allocated_hours DESC
        """,
        (snapshot_id,),
    ).fetchall()

    entry_list = []
    for e in entries:
        ed = dict(e)
        # Fetch job-level details for this entry
        details = conn.execute(
            """
            SELECT ped.*, bu.code AS bu_code, bu.name AS bu_name,
                   COALESCE(pa.scope_name, '') AS scope_name,
                   pa.is_gmp
            FROM projection_entry_details ped
            JOIN project_allocations pa ON pa.id = ped.allocation_id
            JOIN business_units bu ON bu.id = pa.business_unit_id
            WHERE ped.entry_id = ?
            ORDER BY ped.allocated_hours DESC
            """,
            (e["id"],),
        ).fetchall()
        ed["details"] = [dict(d) for d in details]
        entry_list.append(ed)

    result["entries"] = entry_list
    return result


def activate_snapshot(
    conn: sqlite3.Connection, snapshot_id: int
) -> bool:
    """Activate a snapshot (must be Draft). Deactivates others in same period."""
    snap = conn.execute(
        "SELECT * FROM projection_snapshots WHERE id = ?", (snapshot_id,)
    ).fetchone()
    if not snap or snap["status"] != "Draft":
        return False

    conn.execute(
        "UPDATE projection_snapshots SET is_active = 0 WHERE period_id = ?",
        (snap["period_id"],),
    )
    conn.execute(
        "UPDATE projection_snapshots SET is_active = 1 WHERE id = ?",
        (snapshot_id,),
    )
    conn.commit()
    return True


# ---------------------------------------------------------------------------
# Commit / Uncommit
# ---------------------------------------------------------------------------


def commit_snapshot(
    conn: sqlite3.Connection, snapshot_id: int
) -> Dict[str, Any]:
    """Commit a snapshot: lock period, record costs, supersede others."""
    snap = conn.execute(
        "SELECT * FROM projection_snapshots WHERE id = ?", (snapshot_id,)
    ).fetchone()
    if not snap:
        return {"error": "Snapshot not found"}
    if snap["status"] != "Draft":
        return {"error": f"Cannot commit: snapshot is {snap['status']}"}

    # Check period not already committed
    already = conn.execute(
        "SELECT id FROM projection_snapshots WHERE period_id = ? AND status = 'Committed'",
        (snap["period_id"],),
    ).fetchone()
    if already:
        return {"error": "Period already has a committed snapshot"}

    # Commit the snapshot
    conn.execute(
        "UPDATE projection_snapshots SET status = 'Committed', "
        "committed_at = CURRENT_TIMESTAMP, is_active = 1 WHERE id = ?",
        (snapshot_id,),
    )

    # Lock the period
    conn.execute(
        "UPDATE projection_periods SET is_locked = 1 WHERE id = ?",
        (snap["period_id"],),
    )

    # Supersede all other snapshots in period
    conn.execute(
        "UPDATE projection_snapshots SET status = 'Superseded', is_active = 0 "
        "WHERE period_id = ? AND id != ?",
        (snap["period_id"], snapshot_id),
    )

    conn.commit()

    # Return summary
    totals = conn.execute(
        "SELECT SUM(allocated_hours) AS hours, SUM(projected_cost) AS cost "
        "FROM projection_entries WHERE snapshot_id = ?",
        (snapshot_id,),
    ).fetchone()

    return {
        "id": snapshot_id,
        "status": "Committed",
        "total_hours": totals["hours"] or 0,
        "total_cost": totals["cost"] or 0,
    }


def uncommit_snapshot(
    conn: sqlite3.Connection, snapshot_id: int
) -> Dict[str, Any]:
    """Revert a committed snapshot back to Draft. Unlock period."""
    snap = conn.execute(
        "SELECT * FROM projection_snapshots WHERE id = ?", (snapshot_id,)
    ).fetchone()
    if not snap:
        return {"error": "Snapshot not found"}
    if snap["status"] != "Committed":
        return {"error": f"Cannot uncommit: snapshot is {snap['status']}"}

    # Revert to Draft
    conn.execute(
        "UPDATE projection_snapshots SET status = 'Draft', committed_at = NULL WHERE id = ?",
        (snapshot_id,),
    )

    # Unlock the period
    conn.execute(
        "UPDATE projection_periods SET is_locked = 0 WHERE id = ?",
        (snap["period_id"],),
    )

    # Un-supersede other snapshots in the period
    conn.execute(
        "UPDATE projection_snapshots SET status = 'Draft' "
        "WHERE period_id = ? AND id != ? AND status = 'Superseded'",
        (snap["period_id"], snapshot_id),
    )

    conn.commit()
    return {"id": snapshot_id, "status": "Draft"}


# ---------------------------------------------------------------------------
# Budget Integration
# ---------------------------------------------------------------------------


def has_committed_projections(
    conn: sqlite3.Connection, project_id: int
) -> bool:
    """True if any committed snapshot references this project."""
    row = conn.execute(
        """
        SELECT COUNT(*) AS n
        FROM projection_entries pe
        JOIN projection_snapshots ps ON ps.id = pe.snapshot_id
        WHERE pe.project_id = ? AND ps.status = 'Committed'
        """,
        (project_id,),
    ).fetchone()
    return row["n"] > 0


def get_budget_summary(
    conn: sqlite3.Connection, project_id: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Extended project listing with committed + projected costs."""
    where = "WHERE p.id = ?" if project_id else ""
    params: list = [project_id] if project_id else []

    rows = conn.execute(
        f"""
        SELECT p.id, p.number, p.name, p.stage,
               COALESCE(b.total_budget, 0) AS total_budget,
               COALESCE(spent.total, 0) AS budget_spent,
               COALESCE(committed.cost, 0) AS committed_cost,
               COALESCE(projected.cost, 0) AS projected_cost
        FROM projects p
        LEFT JOIN project_budgets b ON b.project_id = p.id
        LEFT JOIN (
            SELECT project_id, SUM(amount) AS total
            FROM project_transactions GROUP BY project_id
        ) spent ON spent.project_id = p.id
        LEFT JOIN (
            SELECT pe.project_id, SUM(pe.projected_cost) AS cost
            FROM projection_entries pe
            JOIN projection_snapshots ps ON ps.id = pe.snapshot_id
            WHERE ps.status = 'Committed'
            GROUP BY pe.project_id
        ) committed ON committed.project_id = p.id
        LEFT JOIN (
            SELECT pe.project_id, SUM(pe.projected_cost) AS cost
            FROM projection_entries pe
            JOIN projection_snapshots ps ON ps.id = pe.snapshot_id
            WHERE ps.status = 'Draft' AND ps.is_active = 1
            GROUP BY pe.project_id
        ) projected ON projected.project_id = p.id
        {where}
        ORDER BY p.created_at DESC
        """,
        params,
    ).fetchall()

    result = []
    for r in rows:
        d = dict(r)
        d["budget_remaining"] = d["total_budget"] - d["budget_spent"] - d["committed_cost"]
        result.append(d)
    return result


# ---------------------------------------------------------------------------
# Hour Distribution (UKG Timecard Prep)
# ---------------------------------------------------------------------------


def _get_working_days_mf(year: int, month: int) -> List[date]:
    """Return all Monday–Friday dates in the given month, sorted."""
    _, num_days = monthrange(year, month)
    first = date(year, month, 1)
    return [
        first + timedelta(days=d)
        for d in range(num_days)
        if (first + timedelta(days=d)).weekday() < 5  # Mon=0 … Fri=4
    ]


def _distribute_single_job(total_hours: float, num_days: int) -> List[float]:
    """Spread *total_hours* across *num_days*, rounding to 0.5 increments.

    Uses floor-and-spread: base daily amount is floored to nearest 0.5,
    then the remaining 0.5-blocks are distributed at evenly spaced
    intervals so no part of the month looks disproportionately heavy.

    Returns a list of length *num_days* whose sum equals *total_hours*.
    """
    if num_days == 0 or total_hours <= 0:
        return [0.0] * num_days

    base = floor(total_hours / num_days / 0.5) * 0.5
    remainder = round(total_hours - base * num_days, 2)
    extra_count = int(round(remainder / 0.5))

    daily = [base] * num_days

    if extra_count > 0:
        stride = num_days / extra_count
        for i in range(extra_count):
            idx = int(i * stride)
            daily[idx] += 0.5

    # Guard against floating-point dust: force exact total
    running = sum(daily)
    if abs(running - total_hours) > 0.01:
        daily[-1] += round(total_hours - running, 2)

    return daily


MAX_ENTRIES_PER_DAY = 3


def _assign_days_to_jobs(
    jobs: List[Dict[str, Any]], num_days: int, max_per_day: int = MAX_ENTRIES_PER_DAY
) -> None:
    """Assign each job to a subset of working days, respecting the per-day cap.

    Mutates each job dict to add ``assigned_days`` (list of day indices).
    Large-hour jobs get more days; small jobs get fewer but with bigger
    daily entries.  Jobs are processed largest-first so they get first
    pick of available slots.
    """
    total_hours = sum(j["hours"] for j in jobs)
    total_slots = num_days * max_per_day

    # Simple case: all jobs fit on every day
    if len(jobs) <= max_per_day:
        for job in jobs:
            job["assigned_days"] = list(range(num_days))
        return

    # Calculate proportional day-count for each job
    for job in jobs:
        share = job["hours"] / total_hours if total_hours > 0 else 1 / len(jobs)
        prop = share * total_slots
        job["days_needed"] = max(1, min(num_days, round(prop)))

    # Sort largest-first so big jobs get best slot availability
    jobs.sort(key=lambda j: j["days_needed"], reverse=True)

    day_counts = [0] * num_days  # how many jobs assigned per day

    for job in jobs:
        available = [i for i in range(num_days) if day_counts[i] < max_per_day]
        if not available:
            job["assigned_days"] = []
            continue

        n_pick = min(job["days_needed"], len(available))
        stride = len(available) / n_pick
        picked = [available[int(k * stride)] for k in range(n_pick)]

        job["assigned_days"] = picked
        for d in picked:
            day_counts[d] += 1


def _group_days_by_week(
    working_days: List[date],
) -> List[Dict[str, Any]]:
    """Group M-F working days into ISO weeks.

    Returns list of ``{'week_key': '2026-W06', 'days': [date, ...]}``.
    """
    weeks: List[Dict[str, Any]] = []
    current_key: Optional[str] = None
    current_days: List[date] = []
    for d in working_days:
        iso_yr, iso_wk, _ = d.isocalendar()
        key = f"{iso_yr}-W{iso_wk:02d}"
        if key != current_key:
            if current_days:
                weeks.append({"week_key": current_key, "days": current_days})
            current_key = key
            current_days = []
        current_days.append(d)
    if current_days:
        weeks.append({"week_key": current_key, "days": current_days})
    return weeks


def distribute_projection_hours(
    conn: sqlite3.Connection, snapshot_id: int
) -> Dict[str, Any]:
    """Distribute a snapshot's job-level hours across M-F working days.

    Schedules week-by-week so that no week exceeds ``max_hours_per_week``
    (from budget_settings, default 40).  Each day has at most
    ``MAX_ENTRIES_PER_DAY`` job entries (default 3).

    Algorithm:
      1. Group working days into ISO weeks.
      2. Budget each week proportionally by its number of days, capped at
         ``max_hours_per_week``.  Excess is redistributed to under-cap weeks.
      3. Within each week, allocate per-job hours proportionally, assign
         jobs to days (max 3/day), then floor-and-spread with 0.5 rounding.
      4. The last week uses each job's remaining hours (capped by the
         weekly budget) to absorb rounding drift.  If total hours exceed
         weekly capacity, undistributed hours generate a warning.
    """
    snapshot = get_snapshot_with_details(conn, snapshot_id)
    if not snapshot:
        return {"error": "Snapshot not found"}

    period = conn.execute(
        "SELECT * FROM projection_periods WHERE id = ?",
        (snapshot["period_id"],),
    ).fetchone()
    if not period:
        return {"error": "Period not found"}

    settings = get_settings(conn)
    max_hrs_week = settings.get("max_hours_per_week", 40.0)

    working_days = _get_working_days_mf(period["year"], period["month"])
    num_days = len(working_days)

    # Collect job-level entries with hours > 0
    jobs: List[Dict[str, Any]] = []
    for entry in snapshot["entries"]:
        for detail in entry.get("details", []):
            hrs = detail.get("allocated_hours", 0) or 0
            if hrs > 0:
                jobs.append({
                    "allocation_id": detail["allocation_id"],
                    "job_code": detail["job_code"],
                    "hours": hrs,
                    "project_name": entry.get("project_name", ""),
                    "project_code": entry.get("project_code", ""),
                    "bu_code": detail.get("bu_code", ""),
                    "scope_name": detail.get("scope_name", ""),
                })

    total_job_hours = sum(j["hours"] for j in jobs)
    if not jobs or num_days == 0:
        return {
            "snapshot_id": snapshot_id,
            "period": f"{period['year']}-{period['month']:02d}",
            "schedule": [],
            "weekly_totals": {},
            "total_hours": 0,
            "num_working_days": num_days,
            "num_jobs": 0,
            "max_entries_per_day": MAX_ENTRIES_PER_DAY,
            "max_hours_per_week": max_hrs_week,
            "warnings": [],
        }

    # ── Phase 1: Group days into weeks and budget each week ──
    week_groups = _group_days_by_week(working_days)
    week_budgets: List[float] = []
    for wg in week_groups:
        share = total_job_hours * len(wg["days"]) / num_days
        week_budgets.append(min(share, max_hrs_week))

    # Redistribute any excess from capped weeks to under-cap weeks
    allocated = sum(week_budgets)
    shortfall = total_job_hours - allocated
    warnings: List[str] = []
    if shortfall > 0.01:
        for i, wg in enumerate(week_groups):
            room = max_hrs_week - week_budgets[i]
            if room > 0 and shortfall > 0:
                add = min(room, shortfall)
                week_budgets[i] += add
                shortfall -= add
        if shortfall > 0.5:
            warnings.append(
                f"Cannot fit {shortfall:.1f} hrs within {max_hrs_week}-hour weekly cap"
            )

    # ── Phase 2: Schedule each week independently ──
    schedule: List[Dict[str, Any]] = []
    weekly_totals: Dict[str, float] = {}
    job_allocated: Dict[str, float] = {j["job_code"]: 0.0 for j in jobs}

    for w_idx, wg in enumerate(week_groups):
        week_budget = week_budgets[w_idx]
        week_days = wg["days"]
        n_week_days = len(week_days)
        is_last_week = w_idx == len(week_groups) - 1

        # Calculate per-job hours for this week
        week_jobs: List[Dict[str, Any]] = []
        for job in jobs:
            remaining = job["hours"] - job_allocated[job["job_code"]]
            if remaining < 0.25:
                continue
            if is_last_week:
                # Last week: allocate remaining hours for this job
                raw = remaining
            else:
                # Proportional share, capped at what the job still needs
                raw = week_budget * job["hours"] / total_job_hours if total_job_hours > 0 else 0
                raw = min(raw, remaining)
            hrs = round(raw / 0.5) * 0.5
            hrs = max(0.0, hrs)
            if hrs > 0:
                week_jobs.append({
                    "allocation_id": job["allocation_id"],
                    "job_code": job["job_code"],
                    "hours": hrs,
                    "project_name": job["project_name"],
                    "project_code": job["project_code"],
                    "bu_code": job["bu_code"],
                    "scope_name": job["scope_name"],
                })

        # Enforce weekly budget cap — scale down if over
        wj_total = sum(j["hours"] for j in week_jobs)
        if week_jobs and wj_total > week_budget + 0.01:
            scale = week_budget / wj_total
            for j in week_jobs:
                j["hours"] = round(j["hours"] * scale / 0.5) * 0.5
            # Re-adjust largest to hit budget after rounding
            wj_total = sum(j["hours"] for j in week_jobs)
            diff = round((week_budget - wj_total) / 0.5) * 0.5
            if abs(diff) >= 0.5:
                week_jobs.sort(key=lambda j: j["hours"], reverse=True)
                week_jobs[0]["hours"] = max(0.5, week_jobs[0]["hours"] + diff)
        elif week_jobs and not is_last_week:
            # Normal weeks: nudge largest to fill budget exactly
            diff = round((week_budget - wj_total) / 0.5) * 0.5
            if abs(diff) >= 0.5:
                week_jobs.sort(key=lambda j: j["hours"], reverse=True)
                week_jobs[0]["hours"] = max(0.5, week_jobs[0]["hours"] + diff)

        # Assign jobs to days within this week (max 3/day)
        _assign_days_to_jobs(week_jobs, n_week_days, MAX_ENTRIES_PER_DAY)

        # Distribute each job's weekly hours across its assigned days
        for job in week_jobs:
            job["daily_hours"] = _distribute_single_job(
                job["hours"], len(job["assigned_days"])
            )

        # Build daily schedule entries
        week_total = 0.0
        for d_idx, day_date in enumerate(week_days):
            entries = []
            day_total = 0.0
            for job in week_jobs:
                if d_idx not in job["assigned_days"]:
                    continue
                pos = job["assigned_days"].index(d_idx)
                hrs = job["daily_hours"][pos]
                if hrs > 0:
                    entries.append({
                        "job_code": job["job_code"],
                        "hours": hrs,
                        "project_name": job["project_name"],
                        "project_code": job["project_code"],
                        "bu_code": job["bu_code"],
                        "scope_name": job["scope_name"],
                        "allocation_id": job["allocation_id"],
                    })
                    day_total += hrs
                    job_allocated[job["job_code"]] += hrs
            schedule.append({
                "date": day_date.isoformat(),
                "weekday": day_date.strftime("%a"),
                "entries": entries,
                "day_total": round(day_total, 2),
            })
            week_total += day_total

        weekly_totals[wg["week_key"]] = round(week_total, 2)

    # ── Phase 3: Validation ──
    for week_key, total in weekly_totals.items():
        if total > max_hrs_week + 0.01:
            warnings.append(f"{week_key}: {total:.1f} hrs exceeds {max_hrs_week}-hour cap")

    max_entries = max((len(d["entries"]) for d in schedule), default=0)
    if max_entries > MAX_ENTRIES_PER_DAY:
        warnings.append(
            f"Some days have {max_entries} entries (cap is {MAX_ENTRIES_PER_DAY})"
        )

    return {
        "snapshot_id": snapshot_id,
        "period": f"{period['year']}-{period['month']:02d}",
        "schedule": schedule,
        "weekly_totals": weekly_totals,
        "total_hours": round(sum(j["hours"] for j in jobs), 2),
        "num_working_days": num_days,
        "num_jobs": len(jobs),
        "max_entries_per_day": MAX_ENTRIES_PER_DAY,
        "max_hours_per_week": max_hrs_week,
        "warnings": warnings,
    }


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
