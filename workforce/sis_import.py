"""
SIS Employee Import

Imports employee data from SIS (Safety Information System) field-location
sheets into the workforce module.  Performs 4-level duplicate prevention,
job-assignment tracking, and hire-date correction for out-of-order imports.
"""

import sqlite3
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from qms.core import get_db, get_logger
from qms.workforce.employees import (
    create_employee,
    find_employee_by_name,
    find_employee_by_number,
    find_employee_by_phone,
    generate_uuid,
    update_employee,
)

logger = get_logger("qms.workforce.sis_import")


# ---------------------------------------------------------------------------
# Name parsing
# ---------------------------------------------------------------------------

def parse_name_from_record(record: Any) -> Tuple[str, str]:
    """Extract (last_name, first_name) from an SIS EmployeeRecord.

    The record is expected to carry ``last_name`` and ``first_name``
    attributes that were already split during the SIS sheet parse step.
    """
    return (getattr(record, "last_name", ""), getattr(record, "first_name", ""))


# ---------------------------------------------------------------------------
# Duplicate-prevention lookup
# ---------------------------------------------------------------------------

def find_existing_employee(
    conn: sqlite3.Connection,
    employee_number: str,
    phone: Optional[str],
    last_name: str,
    first_name: str,
) -> Optional[Dict[str, Any]]:
    """Find an existing employee using a 4-level matching strategy.

    Levels checked in order:
        1. employee_number (exact)
        2. phone (digit-normalised)
        3. name (case-insensitive, single-match only)

    Returns a dict with the employee row *plus* a ``match_method`` key,
    or ``None`` if no match was found.
    """
    # Level 1 -- employee number
    if employee_number:
        existing = find_employee_by_number(conn, employee_number=employee_number)
        if existing:
            return {**existing, "match_method": "employee_number"}

    # Level 2 -- phone
    if phone and phone != "nan":
        existing = find_employee_by_phone(conn, phone)
        if existing:
            return {**existing, "match_method": "phone"}

    # Level 3 -- fuzzy name (single hit only)
    candidates = find_employee_by_name(conn, last_name, first_name)
    if len(candidates) == 1:
        return {**candidates[0], "match_method": "name_fuzzy"}
    if len(candidates) > 1:
        logger.warning(
            "Multiple name matches for %s, %s -- skipping", last_name, first_name
        )
        return None

    return None


# ---------------------------------------------------------------------------
# Main import entry-point
# ---------------------------------------------------------------------------

def import_employees_from_sis(
    conn: sqlite3.Connection,
    employee_records: List[Any],
    week_ending: date,
) -> Dict[str, Any]:
    """Import employee data from a parsed SIS sheet into the employees table.

    For each record the function:
    * Skips rows without an employee_number.
    * Runs 4-level duplicate matching.
    * Updates contact info / job assignment for existing employees.
    * Corrects hire dates when an earlier week-ending is discovered.
    * Creates new employee records when no match is found.
    * Tracks job changes in ``employment_history``.

    Args:
        conn: Active database connection (caller manages transaction).
        employee_records: Parsed ``EmployeeRecord`` objects from the SIS
            sheet parser (must expose ``employee_number``, ``last_name``,
            ``first_name``, ``phone``, ``job_number``, ``designation``).
        week_ending: The week-ending date for this SIS import batch.

    Returns:
        A statistics dict with counts and any duplicate warnings.
    """
    stats: Dict[str, Any] = {
        "employees_processed": 0,
        "employees_created": 0,
        "employees_updated": 0,
        "employees_job_assigned": 0,
        "employees_skipped": 0,
        "hire_dates_corrected": 0,
        "duplicate_warnings": [],
    }

    for record in employee_records:
        stats["employees_processed"] += 1

        if not record.employee_number:
            stats["employees_skipped"] += 1
            continue

        last_name, first_name = parse_name_from_record(record)
        if not last_name or not first_name:
            logger.warning(
                "Could not parse name for employee %s", record.employee_number
            )
            stats["employees_skipped"] += 1
            continue

        existing = find_existing_employee(
            conn,
            employee_number=record.employee_number,
            phone=record.phone,
            last_name=last_name,
            first_name=first_name,
        )

        # Resolve job_id from job_number
        job_id = _resolve_job_id(conn, getattr(record, "job_number", None))

        if existing:
            _update_existing(conn, existing, record, job_id, week_ending, stats, last_name, first_name)
        else:
            _create_new(conn, record, job_id, week_ending, stats, last_name, first_name)

    conn.commit()
    return stats


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _resolve_job_id(conn: sqlite3.Connection, job_number: Optional[str]) -> Optional[int]:
    """Look up a jobs.id from job_number.  Returns None when not found."""
    if not job_number:
        return None
    row = conn.execute(
        "SELECT id FROM jobs WHERE job_number = ?", (job_number,)
    ).fetchone()
    return row["id"] if row else None


def _update_existing(
    conn: sqlite3.Connection,
    existing: Dict[str, Any],
    record: Any,
    job_id: Optional[int],
    week_ending: date,
    stats: Dict[str, Any],
    last_name: str,
    first_name: str,
) -> None:
    """Update an already-matched employee record."""
    match_method = existing["match_method"]
    employee_id = existing["id"]

    if match_method == "name_fuzzy":
        stats["duplicate_warnings"].append({
            "employee_number": record.employee_number,
            "matched_id": employee_id,
            "reason": "Fuzzy name match -- verify not duplicate",
        })

    # Fetch current data for comparison
    current = conn.execute(
        "SELECT job_id, original_hire_date, current_hire_date FROM employees WHERE id = ?",
        (employee_id,),
    ).fetchone()

    # Correct hire dates if this batch is earlier than what is stored
    current_original_hire = current["original_hire_date"]
    if current_original_hire and str(week_ending) < current_original_hire:
        conn.execute(
            "UPDATE employees SET original_hire_date = ?, current_hire_date = ? WHERE id = ?",
            (str(week_ending), str(week_ending), employee_id),
        )
        stats["hire_dates_corrected"] += 1
        logger.info(
            "Hire date corrected for %s: was %s, now %s",
            record.employee_number, current_original_hire, week_ending,
        )

    job_changed = (current["job_id"] != job_id) and job_id is not None

    update_employee(
        conn,
        employee_id,
        phone=record.phone if record.phone else None,
        job_id=job_id,
        notes=record.designation if record.designation else None,
    )

    if job_changed:
        # Close current employment period
        conn.execute(
            "UPDATE employment_history SET end_date = ? "
            "WHERE employee_id = ? AND end_date IS NULL",
            (str(week_ending), employee_id),
        )
        # Open new period for job transfer
        conn.execute(
            """INSERT INTO employment_history (
                id, employee_id, start_date, employment_type,
                position, job_id, transition_type, reason_for_change, created_by
            ) SELECT ?, ?, ?,
                CASE WHEN is_employee = 1 AND is_subcontractor = 1 THEN 'both'
                     WHEN is_employee = 1 THEN 'employee'
                     ELSE 'subcontractor' END,
                position, ?, 'transfer', 'Job assignment change from SIS import', 'SIS-IMPORT'
            FROM employees WHERE id = ?""",
            (generate_uuid(), employee_id, str(week_ending), job_id, employee_id),
        )
        logger.info(
            "Updated %s - %s, %s [%s] - job changed",
            record.employee_number, last_name, first_name, match_method,
        )
    else:
        logger.debug(
            "Updated %s - %s, %s [%s]",
            record.employee_number, last_name, first_name, match_method,
        )

    stats["employees_updated"] += 1
    if job_id:
        stats["employees_job_assigned"] += 1


def _create_new(
    conn: sqlite3.Connection,
    record: Any,
    job_id: Optional[int],
    week_ending: date,
    stats: Dict[str, Any],
    last_name: str,
    first_name: str,
) -> None:
    """Create a brand-new employee from an SIS record."""
    is_employee = not (
        record.employee_number.startswith("CONTRACT")
        or "contractor" in (record.designation or "").lower()
    )
    is_subcontractor = not is_employee

    role_row = conn.execute(
        "SELECT id FROM roles WHERE role_code = 'TECH'"
    ).fetchone()
    role_id = role_row["id"] if role_row else None

    employee_id = create_employee(
        conn,
        last_name=last_name,
        first_name=first_name,
        is_employee=is_employee,
        is_subcontractor=is_subcontractor,
        position="Field Personnel",
        job_id=job_id,
        role_id=role_id,
        phone=record.phone if record.phone else None,
        current_hire_date=str(week_ending),
        original_hire_date=str(week_ending),
        status="active",
        notes=record.designation if record.designation else None,
        created_by="SIS-IMPORT",
    )

    stats["employees_created"] += 1
    if job_id:
        stats["employees_job_assigned"] += 1

    logger.info(
        "Created %s - %s, %s (UUID: %s...)",
        record.employee_number, last_name, first_name, employee_id[:8],
    )


# ---------------------------------------------------------------------------
# Summary helper (for CLI output)
# ---------------------------------------------------------------------------

def format_import_summary(stats: Dict[str, Any]) -> str:
    """Return a human-readable summary string from an import stats dict."""
    lines = [
        "=" * 70,
        "EMPLOYEE IMPORT SUMMARY",
        "=" * 70,
        f"Employees processed: {stats['employees_processed']}",
        f"  Created: {stats['employees_created']}",
        f"  Updated: {stats['employees_updated']}",
        f"  Job assigned: {stats['employees_job_assigned']}",
        f"  Skipped: {stats['employees_skipped']}",
    ]
    if stats.get("hire_dates_corrected", 0) > 0:
        lines.append(
            f"  Hire dates corrected: {stats['hire_dates_corrected']} (earlier records found)"
        )

    warnings = stats.get("duplicate_warnings", [])
    if warnings:
        lines.append(f"\nDuplicate warnings (fuzzy name matches): {len(warnings)}")
        for w in warnings[:5]:
            lines.append(f"  - {w['employee_number']}: {w['reason']}")
        if len(warnings) > 5:
            lines.append(f"  ... and {len(warnings) - 5} more")

    lines.append("=" * 70)
    return "\n".join(lines)
