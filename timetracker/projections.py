"""
Projection Business Logic

Budget-weighted hour allocation across projects.
Monthly projection periods, snapshots, and hour distribution for UKG timecard prep.
No Flask imports — used by both CLI and API layers.
"""

import sqlite3
from calendar import monthrange
from datetime import date, datetime, timedelta
from math import floor
from typing import Any, Dict, List, Optional

from qms.core import get_db, get_logger
from qms.timetracker.transactions import get_settings

logger = get_logger("qms.timetracker.projections")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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
    """Return all Monday-Friday dates in the given month, sorted."""
    _, num_days = monthrange(year, month)
    first = date(year, month, 1)
    return [
        first + timedelta(days=d)
        for d in range(num_days)
        if (first + timedelta(days=d)).weekday() < 5  # Mon=0 ... Fri=4
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

    # -- Phase 1: Group days into weeks and budget each week --
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

    # -- Phase 2: Schedule each week independently --
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

        # Enforce weekly budget cap -- scale down if over
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

    # -- Phase 3: Validation --
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
