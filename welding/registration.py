"""
Welder Registration

Handles new welder onboarding: interactive registration, batch import from CSV,
auto-assignment of stamp numbers, initial WPQ creation, and folder setup.

Usage:
    qms welding register                           # Interactive mode
    qms welding register --batch welders.csv       # Batch from CSV
    qms welding register --employee-number 12345 --first-name John --last-name Doe
"""

import csv
import re
import sqlite3
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from qms.core import get_db, get_logger, QMS_PATHS

logger = get_logger("qms.welding.registration")

# Stamp patterns:
#   New format: {LastInitial}{NN} — e.g. B01, B15, J03  (no dash, zero-padded)
#   Legacy format: {Letter}-{Num} — e.g. B-15, J-3      (dash, optional zero-pad)
#   Old auto format: Z-NN / ZA-NN                        (Z prefix)
# All three formats are recognized when scanning existing stamps.
STAMP_PATTERN_NEW = re.compile(r"^([A-Z])(\d{2,})$")
STAMP_PATTERN_LEGACY = re.compile(r"^([A-Z])-(\d+)$")
STAMP_PATTERN_Z = re.compile(r"^Z([A-Z]?)-(\d+)$")

# Valid welding processes
VALID_PROCESSES = {"SMAW", "GTAW", "GMAW", "FCAW", "SAW", "GTAW/SMAW"}


# ---------------------------------------------------------------------------
# Stamp assignment
# ---------------------------------------------------------------------------

def get_next_stamp(
    conn: sqlite3.Connection,
    last_name: Optional[str] = None,
) -> str:
    """
    Determine the next available welder stamp number.

    When *last_name* is provided, the stamp prefix is the first letter
    of the last name (e.g. ``last_name="Baker"`` → prefix ``B``).
    Otherwise falls back to ``Z`` for backward compatibility.

    Format: ``{Letter}{NN}`` — e.g. ``B01``, ``B15``, ``J03``.
    No dash, zero-padded to 2 digits.  Stamps are never recycled.

    Recognises three legacy formats when scanning existing stamps:
    - ``B-15``  (legacy dash format)
    - ``B15``   (new format)
    - ``Z-01``  (old auto-assign format)

    Args:
        conn: Database connection
        last_name: Welder's last name (used for prefix letter)

    Returns:
        Next stamp string (e.g. ``B16``)
    """
    if last_name and last_name.strip():
        prefix = last_name.strip()[0].upper()
    else:
        prefix = "Z"

    rows = conn.execute(
        "SELECT welder_stamp FROM weld_welder_registry WHERE welder_stamp IS NOT NULL"
    ).fetchall()

    max_num = 0
    for row in rows:
        stamp = row["welder_stamp"]
        if not stamp:
            continue
        stamp = stamp.strip().upper()

        # Try new format first: B01, B15
        m = STAMP_PATTERN_NEW.match(stamp)
        if m and m.group(1) == prefix:
            max_num = max(max_num, int(m.group(2)))
            continue

        # Try legacy dash format: B-15, B-3
        m = STAMP_PATTERN_LEGACY.match(stamp)
        if m and m.group(1) == prefix:
            max_num = max(max_num, int(m.group(2)))
            continue

        # Try old Z-prefix format (only when prefix is Z)
        if prefix == "Z":
            m = STAMP_PATTERN_Z.match(stamp)
            if m and not m.group(1):  # Plain Z-NN (no suffix letter)
                max_num = max(max_num, int(m.group(2)))

    next_num = max_num + 1
    return f"{prefix}{next_num:02d}"


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_registration(
    conn: sqlite3.Connection,
    employee_number: str,
    stamp: Optional[str] = None,
) -> List[str]:
    """
    Validate a welder registration for uniqueness constraints.

    Returns:
        List of error messages (empty = valid)
    """
    errors: List[str] = []

    if not employee_number or not employee_number.strip():
        errors.append("Employee number is required")
        return errors

    # Check employee number uniqueness
    existing = conn.execute(
        "SELECT id, first_name, last_name FROM weld_welder_registry WHERE employee_number = ?",
        (employee_number.strip(),),
    ).fetchone()
    if existing:
        errors.append(
            f"Employee number '{employee_number}' already registered "
            f"(ID {existing['id']}: {existing['first_name']} {existing['last_name']})"
        )

    # Check stamp uniqueness
    if stamp:
        existing_stamp = conn.execute(
            "SELECT id, first_name, last_name FROM weld_welder_registry WHERE welder_stamp = ?",
            (stamp.strip(),),
        ).fetchone()
        if existing_stamp:
            errors.append(
                f"Stamp '{stamp}' already assigned to "
                f"{existing_stamp['first_name']} {existing_stamp['last_name']} "
                f"(ID {existing_stamp['id']})"
            )

    return errors


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register_new_welder(
    conn: sqlite3.Connection,
    employee_number: str,
    first_name: str,
    last_name: str,
    stamp: Optional[str] = None,
    department: Optional[str] = None,
    supervisor: Optional[str] = None,
    business_unit: Optional[str] = None,
    preferred_name: Optional[str] = None,
    auto_stamp: bool = True,
) -> Dict[str, Any]:
    """
    Register a new welder with full details.

    Args:
        conn: Database connection
        employee_number: Employee number (required, unique)
        first_name: First name
        last_name: Last name
        stamp: Welder stamp (auto-assigned if None and auto_stamp=True)
        department: Department name
        supervisor: Supervisor name
        business_unit: Business unit
        preferred_name: Preferred/nickname
        auto_stamp: Auto-assign stamp if none provided

    Returns:
        Dict with: id, stamp, employee_number, name, status, errors
    """
    result: Dict[str, Any] = {
        "id": None,
        "stamp": stamp,
        "employee_number": employee_number.strip(),
        "name": f"{first_name} {last_name}",
        "status": "created",
        "errors": [],
    }

    # Validate
    errors = validate_registration(conn, employee_number, stamp)
    if errors:
        result["errors"] = errors
        result["status"] = "failed"
        return result

    # Auto-assign stamp if needed
    if not stamp and auto_stamp:
        stamp = get_next_stamp(conn, last_name=last_name)
        result["stamp"] = stamp

    display_name = f"{last_name}, {first_name}"
    if preferred_name:
        display_name = f"{last_name}, {preferred_name} ({first_name})"

    cursor = conn.execute(
        """INSERT INTO weld_welder_registry (
               employee_number, first_name, last_name, preferred_name,
               display_name, welder_stamp, department, supervisor,
               business_unit, status
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')""",
        (
            employee_number.strip(),
            first_name.strip(),
            last_name.strip(),
            preferred_name.strip() if preferred_name else None,
            display_name,
            stamp,
            department.strip() if department else None,
            supervisor.strip() if supervisor else None,
            business_unit.strip() if business_unit else None,
        ),
    )
    conn.commit()

    result["id"] = cursor.lastrowid

    logger.info(
        "Registered welder: %s %s (emp#: %s, stamp: %s, ID: %d)",
        first_name, last_name, employee_number, stamp, result["id"],
    )
    return result


def add_initial_wpq(
    conn: sqlite3.Connection,
    welder_id: int,
    welder_stamp: str,
    process_type: str,
    p_number: Optional[int] = None,
    f_number: Optional[int] = None,
    positions: Optional[str] = None,
    wps_number: Optional[str] = None,
    test_date: Optional[date] = None,
    expiration_months: int = 6,
) -> Dict[str, Any]:
    """
    Add an initial WPQ record for a newly registered welder.

    Args:
        conn: Database connection
        welder_id: Welder registry ID
        welder_stamp: Welder stamp number
        process_type: Welding process (SMAW, GTAW, etc.)
        p_number: P-number for base metal
        f_number: F-number for filler metal
        positions: Qualified positions (e.g. "1G, 2G, 3G, 4G, 5G, 6G")
        wps_number: Associated WPS number
        test_date: Date of qualification test (defaults to today)
        expiration_months: Months until expiration (default 6)

    Returns:
        Dict with: id, wpq_number, process_type, expiration_date, errors
    """
    result: Dict[str, Any] = {
        "id": None,
        "wpq_number": None,
        "process_type": process_type,
        "expiration_date": None,
        "errors": [],
    }

    if process_type not in VALID_PROCESSES:
        result["errors"].append(
            f"Invalid process type '{process_type}'. "
            f"Valid: {', '.join(sorted(VALID_PROCESSES))}"
        )
        return result

    test_dt = test_date or date.today()
    expiration_dt = test_dt + timedelta(days=expiration_months * 30)

    if wps_number:
        wpq_number = f"{welder_stamp}-{wps_number}"
    else:
        wpq_number = f"{welder_stamp}-{process_type}"

    # Check if WPQ already exists
    existing = conn.execute(
        "SELECT id FROM weld_wpq WHERE wpq_number = ?", (wpq_number,)
    ).fetchone()
    if existing:
        result["errors"].append(f"WPQ '{wpq_number}' already exists (ID {existing['id']})")
        return result

    cursor = conn.execute(
        """INSERT INTO weld_wpq (
               wpq_number, welder_id, welder_stamp, wps_number,
               process_type, p_number_base, f_number,
               groove_positions_qualified, test_date,
               initial_expiration_date, current_expiration_date,
               status, notes
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?)""",
        (
            wpq_number,
            welder_id,
            welder_stamp,
            wps_number,
            process_type,
            p_number,
            f_number,
            positions,
            test_dt.isoformat(),
            expiration_dt.isoformat(),
            expiration_dt.isoformat(),
            f"Initial qualification on registration ({test_dt.isoformat()})",
        ),
    )
    conn.commit()

    result["id"] = cursor.lastrowid
    result["wpq_number"] = wpq_number
    result["expiration_date"] = expiration_dt.isoformat()

    logger.info(
        "Created WPQ %s for welder %s (process: %s, expires: %s)",
        wpq_number, welder_stamp, process_type, expiration_dt,
    )
    return result


# ---------------------------------------------------------------------------
# Batch registration
# ---------------------------------------------------------------------------

# Expected CSV columns (case-insensitive, flexible naming)
_CSV_COLUMN_ALIASES: Dict[str, List[str]] = {
    "employee_number": ["employee_number", "employee_#", "employee #", "emp_num", "emp#", "id"],
    "first_name": ["first_name", "first name", "firstname", "first"],
    "last_name": ["last_name", "last name", "lastname", "last"],
    "stamp": ["stamp", "welder_stamp", "stamp_number", "stamp number"],
    "department": ["department", "dept"],
    "supervisor": ["supervisor", "super"],
    "business_unit": ["business_unit", "business unit", "bu"],
    "preferred_name": ["preferred_name", "preferred name", "nickname", "preferred"],
    "process_type": ["process_type", "process", "weld_process"],
}


def _resolve_csv_columns(headers: List[str]) -> Dict[str, Optional[int]]:
    """Map CSV headers to known field names."""
    mapping: Dict[str, Optional[int]] = {}
    lower_headers = [h.strip().lower() for h in headers]

    for field, aliases in _CSV_COLUMN_ALIASES.items():
        mapping[field] = None
        for alias in aliases:
            if alias.lower() in lower_headers:
                mapping[field] = lower_headers.index(alias.lower())
                break

    return mapping


def register_batch(
    csv_path: Path,
    dry_run: bool = False,
    auto_stamp: bool = True,
) -> Dict[str, Any]:
    """
    Register multiple welders from a CSV file.

    Expected CSV columns (flexible naming):
        employee_number (required), first_name (required), last_name (required),
        stamp, department, supervisor, business_unit, preferred_name, process_type

    Args:
        csv_path: Path to CSV file
        dry_run: Preview without database changes
        auto_stamp: Auto-assign stamps for rows without one

    Returns:
        Dict with: total, created, skipped, errors (list of error dicts)
    """
    stats: Dict[str, Any] = {
        "total": 0,
        "created": 0,
        "skipped": 0,
        "errors": [],
        "welders": [],
    }

    if not csv_path.exists():
        stats["errors"].append({"row": 0, "error": f"File not found: {csv_path}"})
        return stats

    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        headers = next(reader, None)
        if not headers:
            stats["errors"].append({"row": 0, "error": "CSV file is empty"})
            return stats

        col_map = _resolve_csv_columns(headers)

        if col_map["employee_number"] is None:
            stats["errors"].append({"row": 0, "error": "Missing required column: employee_number"})
            return stats
        if col_map["first_name"] is None:
            stats["errors"].append({"row": 0, "error": "Missing required column: first_name"})
            return stats
        if col_map["last_name"] is None:
            stats["errors"].append({"row": 0, "error": "Missing required column: last_name"})
            return stats

        def _get(row: List[str], field: str) -> Optional[str]:
            idx = col_map[field]
            if idx is not None and idx < len(row):
                val = row[idx].strip()
                return val if val else None
            return None

        rows_to_process: List[Tuple[int, List[str]]] = []
        for i, row in enumerate(reader, start=2):  # Row 2 = first data row
            if not any(cell.strip() for cell in row):
                continue
            rows_to_process.append((i, row))

    stats["total"] = len(rows_to_process)

    if not rows_to_process:
        return stats

    with get_db() as conn:
        for row_num, row in rows_to_process:
            emp = _get(row, "employee_number")
            first = _get(row, "first_name")
            last = _get(row, "last_name")

            if not emp or not first or not last:
                stats["errors"].append({
                    "row": row_num,
                    "error": f"Missing required field(s): "
                             f"{'employee_number ' if not emp else ''}"
                             f"{'first_name ' if not first else ''}"
                             f"{'last_name' if not last else ''}".strip(),
                })
                stats["skipped"] += 1
                continue

            stamp = _get(row, "stamp")
            process = _get(row, "process_type")

            if dry_run:
                preview_stamp = stamp or "(auto)"
                logger.info(
                    "[DRY] Row %d: %s %s (emp#: %s, stamp: %s)",
                    row_num, first, last, emp, preview_stamp,
                )
                stats["welders"].append({
                    "row": row_num,
                    "employee_number": emp,
                    "name": f"{first} {last}",
                    "stamp": preview_stamp,
                    "status": "would_create",
                })
                stats["created"] += 1
                continue

            result = register_new_welder(
                conn,
                employee_number=emp,
                first_name=first,
                last_name=last,
                stamp=stamp,
                department=_get(row, "department"),
                supervisor=_get(row, "supervisor"),
                business_unit=_get(row, "business_unit"),
                preferred_name=_get(row, "preferred_name"),
                auto_stamp=auto_stamp,
            )

            if result["errors"]:
                stats["errors"].append({
                    "row": row_num,
                    "employee_number": emp,
                    "error": "; ".join(result["errors"]),
                })
                stats["skipped"] += 1
                continue

            stats["created"] += 1
            stats["welders"].append(result)

            # Add initial WPQ if process_type provided
            if process and result["id"] and result["stamp"]:
                wpq_result = add_initial_wpq(
                    conn,
                    welder_id=result["id"],
                    welder_stamp=result["stamp"],
                    process_type=process.upper(),
                )
                if wpq_result["errors"]:
                    stats["errors"].append({
                        "row": row_num,
                        "employee_number": emp,
                        "error": f"WPQ: {'; '.join(wpq_result['errors'])}",
                    })

    logger.info(
        "Batch registration complete: %d total, %d created, %d skipped, %d errors",
        stats["total"], stats["created"], stats["skipped"], len(stats["errors"]),
    )
    return stats
