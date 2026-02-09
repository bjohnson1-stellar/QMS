"""
Weekly Weld Import Processing

Imports weekly welder jobsite assignments to create production weld records.
Each record automatically extends WPQ expiration dates via database trigger
(when continuity events tables are available).

Supports:
    - Excel (.xlsx, .xlsm, .xls) and CSV file formats
    - Auto-detection of column layout
    - Week ending date override
    - Preview mode (no DB changes)
    - Multiple date format parsing
"""

import csv
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from qms.core import get_db, get_logger

logger = get_logger("qms.welding.weekly")


# ---------------------------------------------------------------------------
# Column detection
# ---------------------------------------------------------------------------

COLUMN_ALIASES: Dict[str, List[str]] = {
    "stamp": ["stamp", "welder stamp", "stamp number", "welder"],
    "employee": ["employee", "emp", "employee #", "employee number"],
    "project": ["project", "job", "jobsite", "project number", "project #"],
    "week": ["week", "week ending", "date", "weld date", "week_ending"],
    "process": ["process", "process type", "weld process"],
}


def detect_columns(headers: List[str]) -> Dict[str, int]:
    """
    Detect column positions from headers.

    Args:
        headers: List of header strings from the file

    Returns:
        Mapping of field name to column index
    """
    column_map: Dict[str, int] = {}
    headers_lower = [h.lower().strip() if h else "" for h in headers]

    for field, aliases in COLUMN_ALIASES.items():
        for i, header in enumerate(headers_lower):
            for alias in aliases:
                if alias in header:
                    column_map[field] = i
                    break
            if field in column_map:
                break

    return column_map


# ---------------------------------------------------------------------------
# Date parsing
# ---------------------------------------------------------------------------

def parse_date(value: Any) -> Optional[date]:
    """
    Parse various date formats including Excel serial numbers.

    Args:
        value: Date string, int (Excel serial), or float

    Returns:
        Parsed date or None
    """
    if not value:
        return None

    if isinstance(value, date):
        return value

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, (int, float)):
        try:
            return date(1899, 12, 30) + timedelta(days=int(value))
        except (ValueError, OverflowError):
            pass

    value_str = str(value).strip()

    formats = [
        "%Y-%m-%d",
        "%m/%d/%Y",
        "%m/%d/%y",
        "%d-%b-%Y",
        "%B %d, %Y",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(value_str, fmt).date()
        except ValueError:
            continue

    return None


# ---------------------------------------------------------------------------
# File loading
# ---------------------------------------------------------------------------

def load_excel(filepath: Path) -> Tuple[List[str], List[List]]:
    """
    Load data from Excel file.

    Args:
        filepath: Path to .xlsx/.xlsm/.xls file

    Returns:
        (headers, data_rows)
    """
    try:
        import openpyxl
    except ImportError:
        logger.error("openpyxl not installed. Run: pip install openpyxl")
        return [], []

    wb = openpyxl.load_workbook(str(filepath), data_only=True)
    ws = wb.active

    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return [], []

    headers = [str(c) if c else "" for c in rows[0]]
    data = [list(row) for row in rows[1:] if any(row)]

    return headers, data


def load_csv(filepath: Path) -> Tuple[List[str], List[List]]:
    """
    Load data from CSV file.

    Args:
        filepath: Path to .csv file

    Returns:
        (headers, data_rows)
    """
    with open(filepath, "r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        rows = list(reader)

    if not rows:
        return [], []

    return rows[0], rows[1:]


# ---------------------------------------------------------------------------
# Database operations
# ---------------------------------------------------------------------------

def find_welder(conn: sqlite3.Connection, identifier: str) -> Optional[Dict[str, Any]]:
    """
    Find welder by stamp or employee number.

    Args:
        conn: Database connection
        identifier: Welder stamp or employee number

    Returns:
        Welder dict or None
    """
    row = conn.execute(
        "SELECT id, welder_stamp, employee_number, display_name "
        "FROM weld_welder_registry WHERE welder_stamp = ?",
        (identifier,),
    ).fetchone()
    if row:
        return dict(row)

    row = conn.execute(
        "SELECT id, welder_stamp, employee_number, display_name "
        "FROM weld_welder_registry WHERE employee_number = ?",
        (identifier,),
    ).fetchone()
    return dict(row) if row else None


def add_production_weld(
    conn: sqlite3.Connection,
    welder_id: int,
    project: str,
    process: str,
    weld_date: date,
    week_ending: date,
) -> int:
    """
    Add production weld via the continuity events model.

    Creates one event per welder/project/week (upsert), then links each
    process via the junction table. Each junction INSERT fires the trigger
    independently, ensuring all processes get their WPQs extended.

    Falls back to weld_production_welds table if continuity events tables
    are not available.

    Args:
        conn: Database connection
        welder_id: Welder registry ID
        project: Project number
        process: Welding process type (SMAW, GTAW, etc.)
        weld_date: Date of welding activity
        week_ending: Week ending date

    Returns:
        Event ID or production weld ID
    """
    process = process.upper()

    # Check if continuity events tables exist
    table_check = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='weld_continuity_events'"
    ).fetchone()

    if table_check:
        return _add_via_continuity_events(conn, welder_id, project, process, weld_date, week_ending)
    else:
        return _add_via_production_welds(conn, welder_id, project, process, weld_date, week_ending)


def _add_via_continuity_events(
    conn: sqlite3.Connection,
    welder_id: int,
    project: str,
    process: str,
    weld_date: date,
    week_ending: date,
) -> int:
    """Add production weld via weld_continuity_events + junction table."""
    # Look up wpq_id
    wpq_row = conn.execute(
        """SELECT id FROM weld_wpq
           WHERE welder_id = ? AND process_type = ?
           ORDER BY CASE status WHEN 'active' THEN 0 ELSE 1 END,
                    current_expiration_date DESC
           LIMIT 1""",
        (welder_id, process),
    ).fetchone()
    wpq_id = wpq_row["id"] if wpq_row else None

    # Upsert event
    conn.execute(
        """INSERT INTO weld_continuity_events (
               welder_id, event_type, event_date, week_ending,
               project_number, created_by
           ) VALUES (?, 'production_weld', ?, ?, ?, 'weekly_import')
           ON CONFLICT(welder_id, event_type, project_number, week_ending)
           DO UPDATE SET event_date = excluded.event_date""",
        (welder_id, weld_date, week_ending, project),
    )

    # Retrieve event_id
    event_row = conn.execute(
        """SELECT id FROM weld_continuity_events
           WHERE welder_id = ? AND event_type = 'production_weld'
             AND project_number = ? AND week_ending = ?""",
        (welder_id, project, week_ending),
    ).fetchone()
    event_id = event_row["id"]

    # Link process (trigger fires on INSERT)
    conn.execute(
        """INSERT OR IGNORE INTO weld_continuity_event_processes
               (event_id, process_type, wpq_id)
           VALUES (?, ?, ?)""",
        (event_id, process, wpq_id),
    )

    conn.commit()
    return event_id


def _add_via_production_welds(
    conn: sqlite3.Connection,
    welder_id: int,
    project: str,
    process: str,
    weld_date: date,
    week_ending: date,
) -> int:
    """Fallback: add production weld via weld_production_welds table."""
    cursor = conn.execute(
        """INSERT INTO weld_production_welds (
               welder_id, project_number, process_type,
               weld_date, week_ending, status, created_by
           ) VALUES (?, ?, ?, ?, ?, 'complete', 'weekly_import')
           ON CONFLICT(welder_id, project_number, week_ending)
           DO UPDATE SET process_type = excluded.process_type,
                         weld_date = excluded.weld_date""",
        (welder_id, project, process, weld_date, week_ending),
    )
    conn.commit()
    return cursor.lastrowid


def get_wpq_status(
    conn: sqlite3.Connection, welder_id: int, process: str
) -> Dict[str, Any]:
    """
    Get WPQ status for a welder/process combination.

    Args:
        conn: Database connection
        welder_id: Welder registry ID
        process: Welding process type

    Returns:
        Dict with wpq_number, current_expiration_date, days_remaining
    """
    row = conn.execute(
        """SELECT wpq_number, current_expiration_date,
                  CAST(JULIANDAY(current_expiration_date) - JULIANDAY(DATE('now')) AS INTEGER)
                      as days_remaining
           FROM weld_wpq
           WHERE welder_id = ? AND process_type = ? AND status = 'active'
           ORDER BY current_expiration_date DESC
           LIMIT 1""",
        (welder_id, process.upper()),
    ).fetchone()
    return dict(row) if row else {}


# ---------------------------------------------------------------------------
# Import processing
# ---------------------------------------------------------------------------

def process_weekly_import(
    filepath: Path,
    week_override: Optional[date] = None,
    preview: bool = False,
) -> Dict[str, Any]:
    """
    Process weekly import file.

    Args:
        filepath: Path to Excel or CSV file
        week_override: Override week ending date for all records
        preview: If True, report without making changes

    Returns:
        Dict with import statistics
    """
    stats: Dict[str, Any] = {
        "records_processed": 0,
        "welds_created": 0,
        "welds_updated": 0,
        "welders_not_found": [],
        "date_errors": [],
        "continuity_extended": 0,
        "errors": [],
    }

    ext = filepath.suffix.lower()
    if ext in (".xlsx", ".xlsm", ".xls"):
        headers, data = load_excel(filepath)
    elif ext == ".csv":
        headers, data = load_csv(filepath)
    else:
        logger.error("Unsupported file format: %s", ext)
        stats["errors"].append(f"Unsupported file format: {ext}")
        return stats

    if not headers or not data:
        logger.error("No data found in file")
        stats["errors"].append("No data found in file")
        return stats

    columns = detect_columns(headers)
    logger.info("Detected columns: %s", columns)

    # Validate required columns
    identifier = "stamp" if "stamp" in columns else "employee" if "employee" in columns else None
    if not identifier:
        stats["errors"].append("No welder identifier column found (stamp or employee)")
        return stats

    for col in ["project", "process"]:
        if col not in columns:
            stats["errors"].append(f"Required column '{col}' not found")
            return stats

    if preview:
        logger.info("PREVIEW MODE - No changes will be made")

    conn = None
    db_ctx = None
    if not preview:
        db_ctx = get_db()
        conn = db_ctx.__enter__()

    try:
        for row_num, row in enumerate(data, start=2):
            if not any(row):
                continue

            stats["records_processed"] += 1

            welder_id_str = (
                str(row[columns[identifier]]).strip()
                if columns[identifier] < len(row) else ""
            )
            if not welder_id_str or welder_id_str in ("None", "0", ""):
                continue

            project = (
                str(row[columns["project"]]).strip()
                if columns["project"] < len(row) else ""
            )
            if not project or project in ("None", "0", ""):
                continue

            process = (
                str(row[columns["process"]]).strip().upper()
                if columns["process"] < len(row) else "SMAW"
            )
            if not process or process in ("None", "0", ""):
                process = "SMAW"

            if week_override:
                weld_date = week_override
                week_ending = week_override
            elif "week" in columns and columns["week"] < len(row):
                weld_date = parse_date(row[columns["week"]])
                if not weld_date:
                    stats["date_errors"].append(
                        f"Row {row_num}: Invalid date '{row[columns['week']]}'"
                    )
                    weld_date = date.today()
                week_ending = weld_date
            else:
                weld_date = date.today()
                week_ending = weld_date

            if preview:
                logger.info("[PREVIEW] %s | %s | %s | %s", welder_id_str, project, process, weld_date)
                continue

            welder = find_welder(conn, welder_id_str)
            if not welder:
                if welder_id_str not in [w for w, _ in stats["welders_not_found"]]:
                    stats["welders_not_found"].append((welder_id_str, row_num))
                continue

            wpq_before = get_wpq_status(conn, welder["id"], process)

            try:
                add_production_weld(conn, welder["id"], project, process, weld_date, week_ending)
                stats["welds_created"] += 1

                wpq_after = get_wpq_status(conn, welder["id"], process)
                if wpq_after and wpq_before:
                    if wpq_after.get("current_expiration_date", "") > wpq_before.get(
                        "current_expiration_date", ""
                    ):
                        stats["continuity_extended"] += 1

                logger.info(
                    "[OK] %s: %s | %s | Expires: %s",
                    welder.get("welder_stamp") or welder_id_str,
                    project,
                    process,
                    wpq_after.get("current_expiration_date", "N/A"),
                )
            except Exception as exc:
                stats["errors"].append(f"Row {row_num}: {str(exc)}")
                logger.error("Error on row %d: %s", row_num, exc)
    finally:
        if db_ctx and conn:
            db_ctx.__exit__(None, None, None)

    logger.info(
        "Weekly import complete: %d processed, %d welds created, %d continuity extended",
        stats["records_processed"],
        stats["welds_created"],
        stats["continuity_extended"],
    )
    return stats
