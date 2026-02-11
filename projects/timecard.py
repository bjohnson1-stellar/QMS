"""
UKG Timecard Export — Core Business Logic

Generates daily timecard entries from projection data for UKG/Kronos import.
Pure business logic: no Flask or CLI imports.

Data flow:
    projection_snapshots → projection_entries (project_id, allocated_hours)
        ↓ join project_allocations (job_code)
        ↓ clean_job_number() + format_ukg_transfer()
        ↓ distribute_hours() across working dates
        ↓
    List[TimecardEntry] → CLI table / JSON API / Chrome MCP browser automation
"""

import sqlite3
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

from qms.core import get_db, get_logger
from qms.projects.budget import get_active_projection, parse_job_code

logger = get_logger("qms.projects.timecard")


# ---------------------------------------------------------------------------
# Job code formatting
# ---------------------------------------------------------------------------


def clean_job_number(job_code: str) -> str:
    """
    Clean a job code for UKG entry.

    Rules:
      - "07600-600-00" → "07600-600"   (strip trailing -00)
      - "06974-230-01" → "06974-230-01" (keep non-zero subjob)
      - "07600-600"    → "07600-600"    (already clean)
      - "07600"        → "07600"        (base only)
    """
    parsed = parse_job_code(job_code)
    if not parsed:
        return job_code

    base, bu_code, subjob = parsed
    if bu_code is None:
        return base
    if subjob == "00":
        return f"{base}-{bu_code}"
    return f"{base}-{bu_code}-{subjob}"


def format_ukg_transfer(cleaned_job_number: str) -> str:
    """
    Format a cleaned job number into UKG transfer string.

    "07600-600" → ";;;,,07600-600,,,;"
    """
    return f";;;,,{cleaned_job_number},,,;"


# ---------------------------------------------------------------------------
# Date and hour distribution
# ---------------------------------------------------------------------------


def get_working_dates(
    start_date: date,
    end_date: date,
    *,
    weekdays: Tuple[int, ...] = (0, 1, 2, 3),
) -> List[date]:
    """
    Return working dates in range [start_date, end_date].

    Default weekdays=(0,1,2,3) matches Mon-Thu used by the projection
    system's calculate_working_days().
    """
    dates = []
    current = start_date
    while current <= end_date:
        if current.weekday() in weekdays:
            dates.append(current)
        current += timedelta(days=1)
    return dates


def distribute_hours(total_hours: float, num_days: int) -> List[float]:
    """
    Spread total_hours evenly across num_days, rounding to 2 decimals.

    Remainder (±0.01) is distributed to the first days so the sum
    is guaranteed to match total_hours exactly.
    """
    if num_days <= 0 or total_hours <= 0:
        return []

    base = round(total_hours / num_days, 2)
    result = [base] * num_days

    # Fix rounding drift
    current_sum = round(base * num_days, 2)
    diff = round(total_hours - current_sum, 2)

    if diff != 0:
        # Distribute penny-level corrections across first days
        step = 0.01 if diff > 0 else -0.01
        corrections = int(round(abs(diff) / 0.01))
        for i in range(min(corrections, num_days)):
            result[i] = round(result[i] + step, 2)

    return result


# ---------------------------------------------------------------------------
# Main entry generation
# ---------------------------------------------------------------------------


def generate_timecard_entries(
    conn: sqlite3.Connection,
    period_id: int,
    *,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> Dict[str, Any]:
    """
    Generate timecard entries from the active projection snapshot.

    For each projection entry:
      - 1 allocation  → use that job_code for all hours
      - N allocations → split hours proportionally by allocated_budget
      - 0 allocations → fallback to project.number, log warning

    Returns dict with entries sorted by (date, project_name).
    """
    # 1. Load period info
    period = conn.execute(
        "SELECT * FROM projection_periods WHERE id = ?", (period_id,)
    ).fetchone()
    if not period:
        return {"error": "Period not found"}

    # 2. Load active projection snapshot
    projection = get_active_projection(conn, period_id)
    if not projection:
        return {"error": "No active projection snapshot for this period"}

    # 3. Determine date range
    year, month = period["year"], period["month"]
    if not start_date:
        start_date = date(year, month, 1)
    if not end_date:
        # Last day of month
        if month == 12:
            end_date = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(year, month + 1, 1) - timedelta(days=1)

    working_dates = get_working_dates(start_date, end_date)
    if not working_dates:
        return {"error": "No working days in the specified date range"}

    num_days = len(working_dates)

    # 4. Process each projection entry
    entries = []
    warnings = []

    for pe in projection["entries"]:
        project_id = pe["project_id"]
        total_hours = pe["allocated_hours"]

        if total_hours <= 0:
            continue

        project_name = pe["project_name"]
        project_code = pe["project_code"]

        # Get allocations for this project
        allocs = conn.execute(
            """
            SELECT pa.job_code, pa.allocated_budget, pa.subjob,
                   bu.code AS bu_code, bu.name AS bu_name
            FROM project_allocations pa
            JOIN business_units bu ON bu.id = pa.business_unit_id
            WHERE pa.project_id = ?
            ORDER BY pa.allocated_budget DESC
            """,
            (project_id,),
        ).fetchall()
        allocs = [dict(a) for a in allocs]

        # Build job code splits
        if len(allocs) == 0:
            # Fallback: use project number
            warnings.append(
                f"Project {project_code} ({project_name}) has no allocations; "
                f"using project number as job code"
            )
            job_splits = [
                {
                    "job_code": project_code,
                    "cleaned": project_code,
                    "transfer": format_ukg_transfer(project_code),
                    "hours": total_hours,
                    "bu_name": None,
                }
            ]
        elif len(allocs) == 1:
            # Single allocation: all hours go here
            jc = allocs[0]["job_code"]
            cleaned = clean_job_number(jc)
            job_splits = [
                {
                    "job_code": jc,
                    "cleaned": cleaned,
                    "transfer": format_ukg_transfer(cleaned),
                    "hours": total_hours,
                    "bu_name": allocs[0]["bu_name"],
                }
            ]
        else:
            # Multiple allocations: split proportionally by budget
            total_budget = sum(a["allocated_budget"] for a in allocs)
            if total_budget <= 0:
                # Equal split if no budgets
                per_alloc = round(total_hours / len(allocs), 2)
                job_splits = []
                for a in allocs:
                    jc = a["job_code"]
                    cleaned = clean_job_number(jc)
                    job_splits.append(
                        {
                            "job_code": jc,
                            "cleaned": cleaned,
                            "transfer": format_ukg_transfer(cleaned),
                            "hours": per_alloc,
                            "bu_name": a["bu_name"],
                        }
                    )
            else:
                job_splits = []
                allocated_so_far = 0.0
                for i, a in enumerate(allocs):
                    jc = a["job_code"]
                    cleaned = clean_job_number(jc)
                    if i == len(allocs) - 1:
                        # Last allocation gets remainder
                        hrs = round(total_hours - allocated_so_far, 2)
                    else:
                        proportion = a["allocated_budget"] / total_budget
                        hrs = round(total_hours * proportion, 2)
                        allocated_so_far += hrs
                    job_splits.append(
                        {
                            "job_code": jc,
                            "cleaned": cleaned,
                            "transfer": format_ukg_transfer(cleaned),
                            "hours": hrs,
                            "bu_name": a["bu_name"],
                        }
                    )

        # 5. Distribute each split's hours across working dates
        for split in job_splits:
            daily_amounts = distribute_hours(split["hours"], num_days)
            for i, dt in enumerate(working_dates):
                if i < len(daily_amounts) and daily_amounts[i] > 0:
                    entries.append(
                        {
                            "date": dt.isoformat(),
                            "day_name": dt.strftime("%A"),
                            "project_name": project_name,
                            "project_code": project_code,
                            "job_code": split["job_code"],
                            "cleaned_job_number": split["cleaned"],
                            "pay_code": "Hours Worked",
                            "transfer": split["transfer"],
                            "amount": daily_amounts[i],
                        }
                    )

    # Sort by date, then project name
    entries.sort(key=lambda e: (e["date"], e["project_name"]))

    # Summary stats
    total_entry_hours = round(sum(e["amount"] for e in entries), 2)

    return {
        "period_id": period_id,
        "year": year,
        "month": month,
        "snapshot_id": projection["id"],
        "snapshot_version": projection["version"],
        "date_range": {
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
        },
        "working_days": num_days,
        "total_hours": total_entry_hours,
        "entry_count": len(entries),
        "entries": entries,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# Convenience wrapper
# ---------------------------------------------------------------------------


def get_timecard_for_period(
    period_id: int,
    *,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> Dict[str, Any]:
    """Convenience wrapper that opens its own DB connection."""
    with get_db(readonly=True) as conn:
        return generate_timecard_entries(
            conn, period_id, start_date=start_date, end_date=end_date
        )
