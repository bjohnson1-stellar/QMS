#!/usr/bin/env python3
"""
Weekly Jobsite Import for Welder Continuity Tracking

Imports weekly welder jobsite assignments to create production weld records.
Each record automatically extends WPQ expiration dates via database trigger.

Usage:
    python weld_weekly_import.py weekly_log.xlsx          # Import from Excel
    python weld_weekly_import.py weekly_log.csv           # Import from CSV
    python weld_weekly_import.py --week 2026-02-07        # Set week ending date
    python weld_weekly_import.py --preview weekly_log.xlsx  # Preview without changes
    python weld_weekly_import.py --manual                 # Interactive manual entry

Expected Input Formats:
    Excel/CSV columns: Stamp | Project | Week Ending | Process
    Or: Employee # | Project | Week Ending | Process

    Example:
        B-20    | 07645  | 2026-02-07 | SMAW
        A-8     | 07645  | 2026-02-07 | GTAW
        A-8     | 07645  | 2026-02-07 | SMAW   # Same welder, multiple processes

Created: 2026-02-05
"""

import sqlite3
import sys
import argparse
import csv
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import Optional, Dict, List, Tuple

# =============================================================================
# CONFIGURATION
# =============================================================================

DB_PATH = Path("D:/quality.db")

# Expected column names (case-insensitive, partial match)
COLUMN_ALIASES = {
    'stamp': ['stamp', 'welder stamp', 'stamp number', 'welder'],
    'employee': ['employee', 'emp', 'employee #', 'employee number'],
    'project': ['project', 'job', 'jobsite', 'project number', 'project #'],
    'week': ['week', 'week ending', 'date', 'weld date', 'week_ending'],
    'process': ['process', 'process type', 'weld process'],
}

# =============================================================================
# DATABASE FUNCTIONS
# =============================================================================

def get_db_connection() -> sqlite3.Connection:
    """Get database connection."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def find_welder(conn: sqlite3.Connection, identifier: str) -> Optional[Dict]:
    """Find welder by stamp or employee number."""
    cursor = conn.cursor()

    # Try stamp first
    cursor.execute(
        "SELECT id, welder_stamp, employee_number, display_name "
        "FROM weld_welder_registry WHERE welder_stamp = ?",
        (identifier,)
    )
    row = cursor.fetchone()
    if row:
        return dict(row)

    # Try employee number
    cursor.execute(
        "SELECT id, welder_stamp, employee_number, display_name "
        "FROM weld_welder_registry WHERE employee_number = ?",
        (identifier,)
    )
    row = cursor.fetchone()
    return dict(row) if row else None


def add_production_weld(conn: sqlite3.Connection, welder_id: int, project: str,
                        process: str, weld_date: date, week_ending: date) -> int:
    """
    Add production weld record. Triggers automatic WPQ expiration extension.

    Returns: ID of created/updated record
    """
    cursor = conn.cursor()

    # The UNIQUE constraint handles upsert (welder_id, project_number, week_ending)
    cursor.execute("""
        INSERT INTO weld_production_welds (
            welder_id, project_number, process_type, weld_date,
            week_ending, counts_for_continuity, created_by
        ) VALUES (?, ?, ?, ?, ?, 1, 'weekly_import')
        ON CONFLICT(welder_id, project_number, week_ending) DO UPDATE SET
            process_type = excluded.process_type,
            weld_date = excluded.weld_date
    """, (welder_id, project, process.upper(), weld_date, week_ending))

    conn.commit()
    return cursor.lastrowid


def get_wpq_status_after_import(conn: sqlite3.Connection, welder_id: int, process: str) -> Dict:
    """Get WPQ status after import to verify continuity was extended."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT wpq_number, current_expiration_date,
               CAST(JULIANDAY(current_expiration_date) - JULIANDAY(DATE('now')) AS INTEGER) as days_remaining
        FROM weld_wpq
        WHERE welder_id = ? AND process_type = ? AND status = 'active'
        ORDER BY current_expiration_date DESC
        LIMIT 1
    """, (welder_id, process.upper()))
    row = cursor.fetchone()
    return dict(row) if row else {}


# =============================================================================
# FILE PARSING
# =============================================================================

def detect_columns(headers: List[str]) -> Dict[str, int]:
    """Detect column positions from headers."""
    column_map = {}
    headers_lower = [h.lower().strip() if h else '' for h in headers]

    for field, aliases in COLUMN_ALIASES.items():
        for i, header in enumerate(headers_lower):
            for alias in aliases:
                if alias in header:
                    column_map[field] = i
                    break
            if field in column_map:
                break

    return column_map


def parse_date(value: str) -> Optional[date]:
    """Parse various date formats."""
    if not value:
        return None

    # Handle Excel date serial numbers
    if isinstance(value, (int, float)):
        try:
            # Excel date serial (days since 1900-01-01, with 1900 bug)
            return date(1899, 12, 30) + timedelta(days=int(value))
        except:
            pass

    value = str(value).strip()

    formats = [
        '%Y-%m-%d',       # 2026-02-07
        '%m/%d/%Y',       # 02/07/2026
        '%m/%d/%y',       # 02/07/26
        '%d-%b-%Y',       # 07-Feb-2026
        '%B %d, %Y',      # February 7, 2026
    ]

    for fmt in formats:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue

    return None


def load_excel(filepath: Path) -> Tuple[List[str], List[List]]:
    """Load data from Excel file."""
    try:
        import openpyxl
    except ImportError:
        print("ERROR: openpyxl not installed. Run: pip install openpyxl")
        sys.exit(1)

    wb = openpyxl.load_workbook(str(filepath), data_only=True)
    ws = wb.active

    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return [], []

    headers = [str(c) if c else '' for c in rows[0]]
    data = [list(row) for row in rows[1:] if any(row)]

    return headers, data


def load_csv(filepath: Path) -> Tuple[List[str], List[List]]:
    """Load data from CSV file."""
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        rows = list(reader)

    if not rows:
        return [], []

    return rows[0], rows[1:]


# =============================================================================
# IMPORT FUNCTIONS
# =============================================================================

def process_import(filepath: Path, week_override: date = None,
                   preview: bool = False) -> Dict:
    """
    Process weekly import file.

    Args:
        filepath: Path to Excel or CSV file
        week_override: Override week ending date for all records
        preview: If True, don't make changes

    Returns:
        Dict with import statistics
    """
    stats = {
        'records_processed': 0,
        'welds_created': 0,
        'welds_updated': 0,
        'welders_not_found': [],
        'date_errors': [],
        'continuity_extended': 0,
        'errors': [],
    }

    # Load file
    ext = filepath.suffix.lower()
    if ext in ('.xlsx', '.xlsm', '.xls'):
        headers, data = load_excel(filepath)
    elif ext == '.csv':
        headers, data = load_csv(filepath)
    else:
        print(f"ERROR: Unsupported file format: {ext}")
        return stats

    if not headers or not data:
        print("ERROR: No data found in file")
        return stats

    # Detect columns
    columns = detect_columns(headers)
    print(f"Detected columns: {columns}")
    print(f"Headers: {headers}")

    # Validate required columns
    required = ['project', 'process']
    identifier = 'stamp' if 'stamp' in columns else 'employee' if 'employee' in columns else None

    if not identifier:
        print("ERROR: No welder identifier column found (stamp or employee)")
        return stats

    for col in required:
        if col not in columns:
            print(f"ERROR: Required column '{col}' not found")
            return stats

    if preview:
        print("\n=== PREVIEW MODE - No changes will be made ===\n")

    conn = get_db_connection() if not preview else None

    # Process rows
    for row_num, row in enumerate(data, start=2):
        if not any(row):  # Skip empty rows
            continue

        stats['records_processed'] += 1

        # Get welder identifier
        welder_id_str = str(row[columns[identifier]]).strip() if columns[identifier] < len(row) else ''
        if not welder_id_str or welder_id_str in ('None', '0', ''):
            continue

        # Get project
        project = str(row[columns['project']]).strip() if columns['project'] < len(row) else ''
        if not project or project in ('None', '0', ''):
            continue

        # Get process
        process = str(row[columns['process']]).strip().upper() if columns['process'] < len(row) else 'SMAW'
        if not process or process in ('None', '0', ''):
            process = 'SMAW'  # Default

        # Get date
        if week_override:
            weld_date = week_override
            week_ending = week_override
        elif 'week' in columns and columns['week'] < len(row):
            weld_date = parse_date(row[columns['week']])
            if not weld_date:
                stats['date_errors'].append(f"Row {row_num}: Invalid date '{row[columns['week']]}'")
                weld_date = date.today()
            week_ending = weld_date
        else:
            weld_date = date.today()
            week_ending = weld_date

        if preview:
            # Just show what would happen
            print(f"[PREVIEW] {welder_id_str} | {project} | {process} | {weld_date}")
            continue

        # Find welder
        welder = find_welder(conn, welder_id_str)
        if not welder:
            if welder_id_str not in [w for w, _ in stats['welders_not_found']]:
                stats['welders_not_found'].append((welder_id_str, row_num))
            continue

        # Check current WPQ status before import
        wpq_before = get_wpq_status_after_import(conn, welder['id'], process)

        # Add production weld
        try:
            weld_id = add_production_weld(
                conn, welder['id'], project, process, weld_date, week_ending
            )
            stats['welds_created'] += 1

            # Check if continuity was extended
            wpq_after = get_wpq_status_after_import(conn, welder['id'], process)
            if wpq_after and wpq_before:
                if wpq_after.get('current_expiration_date', '') > wpq_before.get('current_expiration_date', ''):
                    stats['continuity_extended'] += 1

            print(f"[OK] {welder['welder_stamp'] or welder_id_str}: {project} | {process} | "
                  f"Expires: {wpq_after.get('current_expiration_date', 'N/A')}")

        except Exception as e:
            stats['errors'].append(f"Row {row_num}: {str(e)}")

    if conn:
        conn.close()

    return stats


def manual_entry():
    """Interactive manual entry mode."""
    print("\n=== Manual Production Weld Entry ===")
    print("Enter 'q' to quit\n")

    conn = get_db_connection()

    while True:
        # Get welder
        welder_input = input("Welder stamp (or 'q' to quit): ").strip()
        if welder_input.lower() == 'q':
            break

        welder = find_welder(conn, welder_input)
        if not welder:
            print(f"  Welder '{welder_input}' not found")
            continue

        print(f"  Found: {welder['display_name']} ({welder['welder_stamp']})")

        # Get project
        project = input("Project number: ").strip()
        if not project:
            continue

        # Get process
        process = input("Process type [SMAW]: ").strip().upper() or 'SMAW'

        # Get date
        date_input = input(f"Week ending date [today]: ").strip()
        if date_input:
            weld_date = parse_date(date_input)
            if not weld_date:
                print(f"  Invalid date format")
                continue
        else:
            weld_date = date.today()

        # Confirm
        print(f"\n  Will add: {welder['welder_stamp']} | {project} | {process} | {weld_date}")
        confirm = input("  Confirm? [Y/n]: ").strip().lower()

        if confirm in ('', 'y', 'yes'):
            try:
                add_production_weld(conn, welder['id'], project, process, weld_date, weld_date)
                wpq_status = get_wpq_status_after_import(conn, welder['id'], process)
                print(f"  [OK] Added. WPQ expires: {wpq_status.get('current_expiration_date', 'N/A')}\n")
            except Exception as e:
                print(f"  [ERROR] {str(e)}\n")
        else:
            print("  Cancelled\n")

    conn.close()


def print_stats(stats: Dict):
    """Print import statistics."""
    print("\n" + "=" * 50)
    print("IMPORT SUMMARY")
    print("=" * 50)
    print(f"Records processed:     {stats['records_processed']}")
    print(f"Production welds:      {stats['welds_created']}")
    print(f"Continuity extended:   {stats['continuity_extended']}")

    if stats['welders_not_found']:
        print(f"\nWelders not found ({len(stats['welders_not_found'])}):")
        for welder_id, row in stats['welders_not_found'][:10]:
            print(f"  - {welder_id} (row {row})")
        if len(stats['welders_not_found']) > 10:
            print(f"  ... and {len(stats['welders_not_found']) - 10} more")

    if stats['date_errors']:
        print(f"\nDate errors ({len(stats['date_errors'])}):")
        for err in stats['date_errors'][:5]:
            print(f"  - {err}")

    if stats['errors']:
        print(f"\nOther errors ({len(stats['errors'])}):")
        for err in stats['errors'][:5]:
            print(f"  - {err}")


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Import weekly welder jobsite assignments'
    )
    parser.add_argument('file', nargs='?', help='Excel or CSV file to import')
    parser.add_argument('--week', type=str, help='Week ending date (YYYY-MM-DD)')
    parser.add_argument('--preview', action='store_true', help='Preview without changes')
    parser.add_argument('--manual', action='store_true', help='Manual entry mode')

    args = parser.parse_args()

    if args.manual:
        manual_entry()
        return

    if not args.file:
        parser.print_help()
        print("\nExamples:")
        print("  python weld_weekly_import.py weekly_log.xlsx")
        print("  python weld_weekly_import.py --week 2026-02-07 weekly_log.csv")
        print("  python weld_weekly_import.py --preview weekly_log.xlsx")
        print("  python weld_weekly_import.py --manual")
        return

    filepath = Path(args.file)
    if not filepath.exists():
        print(f"ERROR: File not found: {filepath}")
        sys.exit(1)

    week_override = None
    if args.week:
        week_override = parse_date(args.week)
        if not week_override:
            print(f"ERROR: Invalid week date: {args.week}")
            sys.exit(1)
        print(f"Using week ending date: {week_override}")

    stats = process_import(filepath, week_override, args.preview)
    print_stats(stats)


if __name__ == '__main__':
    main()
