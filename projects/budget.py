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
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from qms.core import get_db, get_logger

logger = get_logger("qms.projects.budget")

PROJECT_NUMBER_PATTERN = re.compile(r"^\d{5}-\d{3}-\d{2}$")

VALID_STAGES = [
    "Archive",
    "Bidding",
    "Construction and Bidding",
    "Course of Construction",
    "Lost Proposal",
    "Post-Construction",
    "Pre-Construction",
    "Proposal",
    "Warranty",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def validate_project_number(project_number: str) -> Tuple[bool, Optional[str]]:
    """Validate project number format: NNNNN-CCC-SS."""
    if not project_number:
        return False, "Project number is required"
    if not PROJECT_NUMBER_PATTERN.match(project_number):
        return False, "Project number must follow format NNNNN-CCC-SS (e.g., 06974-230-01)"
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


def get_dashboard_stats(conn: Optional[sqlite3.Connection] = None) -> Dict[str, Any]:
    """Get aggregate stats for the dashboard page."""
    def _query(c: sqlite3.Connection) -> Dict[str, Any]:
        active = c.execute(
            "SELECT COUNT(*) AS n FROM projects WHERE stage = 'Course of Construction'"
        ).fetchone()["n"]

        budget_row = c.execute(
            "SELECT COALESCE(SUM(total_budget), 0) AS total FROM project_budgets"
        ).fetchone()
        total_budget = budget_row["total"]

        spent_row = c.execute(
            "SELECT COALESCE(SUM(amount), 0) AS spent FROM project_transactions"
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
) -> List[Dict[str, Any]]:
    """List all projects with budget and spent totals."""
    sql = """
        SELECT p.*,
               b.total_budget,
               b.weight_adjustment,
               COALESCE(spent.total, 0) AS budget_spent
        FROM projects p
        LEFT JOIN project_budgets b ON b.project_id = p.id
        LEFT JOIN (
            SELECT project_id, SUM(amount) AS total
            FROM project_transactions GROUP BY project_id
        ) spent ON spent.project_id = p.id
        ORDER BY p.created_at DESC
    """

    def _run(c: sqlite3.Connection):
        return [dict(r) for r in c.execute(sql).fetchall()]

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
    manager: Optional[str] = None,
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
) -> int:
    """Create a project and its budget record. Returns project_id."""
    cursor = conn.execute(
        """
        INSERT INTO projects (number, name, client, pm, stage, status,
                              start_date, end_date, notes,
                              street, city, state, zip)
        VALUES (?, ?, ?, ?, ?, 'active', ?, ?, ?, ?, ?, ?, ?)
        """,
        (code, name, client, manager, stage,
         start_date, end_date, notes,
         street, city, state, zip_code),
    )
    project_id = cursor.lastrowid

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
    manager: Optional[str] = None,
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
) -> None:
    """Update a project and its budget record."""
    conn.execute(
        """
        UPDATE projects
        SET number=?, name=?, client=?, pm=?, stage=?,
            start_date=?, end_date=?, notes=?,
            street=?, city=?, state=?, zip=?,
            updated_at=CURRENT_TIMESTAMP
        WHERE id=?
        """,
        (code, name, client, manager, stage,
         start_date, end_date, notes,
         street, city, state, zip_code, project_id),
    )

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
    """Delete a project (cascades to budgets, transactions, projections)."""
    conn.execute("DELETE FROM projects WHERE id=?", (project_id,))
    conn.commit()


# ---------------------------------------------------------------------------
# Business Units
# ---------------------------------------------------------------------------


def list_business_units(
    conn: Optional[sqlite3.Connection] = None,
) -> List[Dict[str, Any]]:
    """List all business units ordered by code."""
    def _run(c: sqlite3.Connection):
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
) -> List[Dict[str, Any]]:
    """List transactions with optional filters."""
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
                "working_hours_per_month, fiscal_year_start_month) "
                "VALUES (1, 'My Company', 150.0, 176, 1)"
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
) -> None:
    conn.execute(
        """
        UPDATE budget_settings
        SET company_name=?, default_hourly_rate=?, working_hours_per_month=?,
            fiscal_year_start_month=?, updated_at=CURRENT_TIMESTAMP
        WHERE id=1
        """,
        (company_name, default_hourly_rate, working_hours_per_month,
         fiscal_year_start_month),
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

    Algorithm:
    1. Get all active projects with remaining budget
    2. weight = remaining_budget * weight_adjustment
    3. Allocate hours proportionally, rounded to nearest 5
    4. Adjust largest project to match total hours exactly
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

    # Active projects with budget info
    rows = conn.execute(
        """
        SELECT p.id, p.number, p.name, p.stage,
               COALESCE(b.total_budget, 0) AS total_budget,
               COALESCE(b.weight_adjustment, 1.0) AS weight_adjustment,
               COALESCE(spent.total, 0) AS budget_spent
        FROM projects p
        LEFT JOIN project_budgets b ON b.project_id = p.id
        LEFT JOIN (
            SELECT project_id, SUM(amount) AS total
            FROM project_transactions GROUP BY project_id
        ) spent ON spent.project_id = p.id
        WHERE p.stage IN ('Course of Construction', 'Construction and Bidding',
                          'Pre-Construction')
        """
    ).fetchall()
    projects = [dict(r) for r in rows]

    if not projects:
        return {
            "period_id": period_id,
            "total_hours": period["total_hours"],
            "hourly_rate": hourly_rate,
            "entries": [],
            "total_cost": 0,
        }

    total_hours = period["total_hours"]

    # Calculate weights
    total_weighted_budget = 0
    for p in projects:
        p["remaining_budget"] = p["total_budget"] - p["budget_spent"]
        p["weight"] = p["remaining_budget"] * p["weight_adjustment"]
        total_weighted_budget += p["weight"]

    # Allocate hours
    allocations = []
    for p in projects:
        raw = (p["weight"] / total_weighted_budget * total_hours
               if total_weighted_budget > 0 else 0)
        rounded = round_to_nearest_5(raw)
        allocations.append({"project": p, "raw_hours": raw, "rounded_hours": rounded})

    # Adjust to match total
    rounded_total = sum(a["rounded_hours"] for a in allocations)
    if rounded_total != total_hours and allocations:
        diff = total_hours - rounded_total
        allocations.sort(key=lambda a: a["raw_hours"], reverse=True)
        allocations[0]["rounded_hours"] += diff

    entries = []
    total_cost = 0
    for a in allocations:
        p = a["project"]
        hours = a["rounded_hours"]
        cost = hours * hourly_rate
        total_cost += cost
        entries.append({
            "project_id": p["id"],
            "project_name": p["name"],
            "project_code": p["number"],
            "total_budget": p["total_budget"],
            "budget_spent": p["budget_spent"],
            "remaining_budget": p["remaining_budget"],
            "weight_adjustment": p["weight_adjustment"],
            "weight_used": p["weight"],
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
    hourly_rate: float,
    total_hours: int,
    name: Optional[str] = None,
    description: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a versioned snapshot with entries."""
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

    for e in entries:
        conn.execute(
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

    conn.commit()
    return {"id": snapshot_id, "version": next_ver}


def finalize_snapshot(conn: sqlite3.Connection, snapshot_id: int) -> bool:
    """Mark snapshot as Final, supersede previous Finals."""
    snap = conn.execute(
        "SELECT * FROM projection_snapshots WHERE id = ?", (snapshot_id,)
    ).fetchone()
    if not snap:
        return False

    conn.execute(
        "UPDATE projection_snapshots SET status = 'Superseded' "
        "WHERE period_id = ? AND id != ? AND status = 'Final'",
        (snap["period_id"], snapshot_id),
    )
    conn.execute(
        "UPDATE projection_snapshots SET status = 'Final', "
        "finalized_at = CURRENT_TIMESTAMP WHERE id = ?",
        (snapshot_id,),
    )
    conn.commit()
    return True
