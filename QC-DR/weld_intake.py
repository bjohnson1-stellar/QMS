#!/usr/bin/env python3
"""
SIS Welding Document Intake

Routes welding documents (WPS, PQR, WPQ, BPS, BPQ, BPQR) from the Inbox
to appropriate folders and creates database records.

Usage:
    python weld_intake.py                    # Process all welding docs in Inbox
    python weld_intake.py file1.pdf file2.pdf  # Process specific files
    python weld_intake.py --scan             # Scan only, don't move files
    python weld_intake.py --welder E001 "John Smith"  # Register a welder

Supports:
    - File classification by filename patterns
    - Routing to correct destination folders
    - Database record creation with basic metadata
    - Revision handling (supersedes older revisions)
    - Intake logging for audit trail

Future: PDF field extraction via OCR or form field parsing.
"""

import sqlite3
import re
import os
import sys
import shutil
from pathlib import Path
from datetime import datetime, date
from typing import Optional, Dict, List, Tuple

# Import shared utilities
from sis_common import get_config, get_db_path, get_logger, SIS_PATHS

# =============================================================================
# CONFIGURATION (loaded from sis_common)
# =============================================================================

DB_PATH = str(get_db_path())
logger = get_logger('weld_intake')

# Document type patterns (filename-based classification)
# More flexible patterns to handle various naming conventions:
#   WPS-001, WPS_001, WPS 001, WPS CS-01, etc.
DOC_PATTERNS = {
    'WPS': [
        re.compile(r'^WPS[-_\s]+([\w-]+)', re.I),        # WPS-001, WPS CS-01, WPS_001
        re.compile(r'^SWPS[-_\s]+([\w-]+)', re.I),       # SWPS 6010-7018
        re.compile(r'^SWPS\s+[\w-]+\s+(AWS[-\s]*B2)', re.I),  # SWPS 6010-7018 AWS B2.1...
        re.compile(r'^AWS[-_\s]*B2\.?1[-_\s]*([\d-]+)', re.I),  # AWS B2.1-1-022
        re.compile(r'^PWPS', re.I),                      # Pre-qualified WPS template
    ],
    'FPS': [
        re.compile(r'^FPS[-_\s]*([\w-]+)', re.I),        # FPS-001, FPS-ORB-P08-001
        re.compile(r'Orbital[-_\s]*Fusion', re.I),       # Orbital Fusion Procedure
        re.compile(r'Fusion[-_\s]*Procedure', re.I),    # Fusion Procedure Spec
    ],
    'PQR': [
        re.compile(r'^PQR[-_\s]*([\w-]+)', re.I),        # PQR-001, PQR P107-TB-01
    ],
    'WPQ': [
        re.compile(r'^WPQ[-_\s]*([\w-]+)', re.I),        # WPQ-001
        re.compile(r'^WQ[-_\s]*(\d+[\w-]*)', re.I),      # WQ-001
        re.compile(r'WPQ\s*Template[-_\s]*([\w-]+)', re.I),  # WPQ Template SS-01
        re.compile(r'Template[-_\s]*WPQ', re.I),         # Template - WPQ ...
        re.compile(r'WPQ\s+([\w-]+-P\d+)', re.I),        # F-19 ... WPQ SS-01-P8
        re.compile(r'Welder[-_\s]*Qual', re.I),          # Welder-Qual, Welder Qual
    ],
    'BPS': [
        re.compile(r'^BPS[-_\s]*([\w-]+)', re.I),        # BPS-001, BPS-P107-TB-01
        re.compile(r'^pBPS', re.I),                      # Pre-qualified BPS template
        re.compile(r'BPS[-_\s]*([\w-]+)\s*ACR', re.I),   # B-33 - BPS-TB-P107-01 ACR
        re.compile(r'BPS[-_\s]*([\w-]+)', re.I),         # Any BPS-xxx mid-filename
        re.compile(r'Braze\s*Test', re.I),               # Braze Test documents
    ],
    'BPQ': [
        re.compile(r'^BPQ[-_\s]*([\w-]+)', re.I),        # BPQ-001
        re.compile(r'^BPQR[-_\s]*([\w-]+)', re.I),       # BPQR-001
    ],
    'FORM': [
        re.compile(r'FORM\s+Q[WB][-_]?\d+', re.I),       # FORM QB-482, FORM QW-484
    ],
}

# Destination folders (relative to Quality Documents/Welding/)
DESTINATIONS = {
    'WPS': 'WPS',
    'SWPS': 'WPS/SWPS',
    'FPS': 'WPS/FPS',       # Fusion/Orbital procedures - subset of WPS
    'PQR': 'PQR',
    'WPQ': 'WPQ',
    'BPS': 'BPS',
    'BPQ': 'BPQ',
    'BPQR': 'BPQ',  # BPQR goes with BPQ
    'FORM': 'Forms',
}

# =============================================================================
# HELPERS
# =============================================================================

def load_config() -> dict:
    """Load configuration from YAML file."""
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def get_db_connection() -> sqlite3.Connection:
    """Get database connection with foreign keys enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def extract_doc_number(filename: str, pattern: re.Pattern) -> Optional[str]:
    """Extract document number from filename using pattern."""
    match = pattern.search(filename)
    if match and match.groups():
        return match.group(1)
    elif match:
        # Pattern matched but no capture group - use stem
        stem = Path(filename).stem
        return stem
    return None


def extract_revision(filename: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract revision from filename.
    Returns (revision, base_name_without_revision)

    Examples:
        WPS-001_Rev_A.pdf -> ('A', 'WPS-001')
        PQR-P107-TB-01.pdf -> (None, 'PQR-P107-TB-01')
        WPS-002-B.pdf -> ('B', 'WPS-002')
    """
    stem = Path(filename).stem

    # Pattern: _Rev_X or _Rev-X or _RevX
    rev_match = re.search(r'[-_]Rev[-_]?([A-Z0-9]+)$', stem, re.I)
    if rev_match:
        revision = rev_match.group(1).upper()
        base = stem[:rev_match.start()]
        return revision, base

    # Pattern: trailing -X where X is single letter
    rev_match = re.search(r'[-_]([A-Z])$', stem)
    if rev_match:
        revision = rev_match.group(1)
        base = stem[:rev_match.start()]
        return revision, base

    return None, stem


def classify_document(filename: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Classify a document based on filename patterns.
    Returns (doc_type, doc_number) or (None, None) if not recognized.

    Checks patterns in priority order - more specific patterns first.
    Also handles documents where the type keyword appears mid-filename.
    """
    stem = Path(filename).stem
    stem_upper = stem.upper()

    # Priority order: check specific types first
    # WPQ before SWPS because "WPQ Template SWPS..." is a WPQ template, not an SWPS
    # FPS (Fusion/Orbital) before generic WPS
    priority_order = ['WPQ', 'SWPS', 'FPS', 'WPS', 'PQR', 'BPS', 'BPQ', 'FORM']

    # First pass: check if keyword appears anywhere in filename
    # This catches "B-33 - BPS-TB-P107-01 ACR" and "F-19 Mark Foster WPQ SS-01"
    for doc_type in priority_order:
        if doc_type == 'SWPS':
            # Check for SWPS or AWS B2.1 - but NOT if WPQ is also present
            # "WPQ Template SWPS 6010-7018" should be WPQ, not SWPS
            if 'WPQ' in stem_upper or 'WQ-' in stem_upper:
                continue  # Let WPQ handle it

            if 'SWPS' in stem_upper or 'AWS B2' in stem_upper or 'AWS-B2' in stem_upper:
                # Extract number
                match = re.search(r'SWPS[-_\s]*([\w-]+)', stem, re.I)
                if match:
                    return 'SWPS', match.group(1)
                match = re.search(r'AWS[-_\s]*B2\.?1[-_\s]*([\d-]+)', stem, re.I)
                if match:
                    return 'SWPS', f"AWS-B2.1-{match.group(1)}"
                return 'SWPS', stem
            continue

        if doc_type in DOC_PATTERNS:
            for pattern in DOC_PATTERNS[doc_type]:
                match = pattern.search(stem)
                if match:
                    doc_number = match.group(1) if match.groups() else stem
                    return doc_type, doc_number

    return None, None


def is_swps(filename: str) -> bool:
    """Check if document is a Standard WPS (pre-qualified)."""
    stem = Path(filename).stem.upper()
    return stem.startswith('SWPS') or stem.startswith('AWS-B2.1') or stem.startswith('PWPS')


# =============================================================================
# DATABASE OPERATIONS
# =============================================================================

def log_intake(conn: sqlite3.Connection, filename: str, source_path: str,
               dest_path: str, doc_type: str, doc_number: str,
               doc_id: Optional[int], action: str, notes: str = None):
    """Log an intake action to the audit trail."""
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO weld_intake_log
        (file_name, source_path, destination_path, document_type, document_number, document_id, action, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (filename, source_path, dest_path, doc_type, doc_number, doc_id, action, notes))
    conn.commit()


def find_existing_document(conn: sqlite3.Connection, doc_type: str,
                           doc_number: str) -> Optional[dict]:
    """Find existing document record by type and number."""
    cursor = conn.cursor()

    table_map = {
        'WPS': 'weld_wps',
        'SWPS': 'weld_wps',
        'PQR': 'weld_pqr',
        'WPQ': 'weld_wpq',
        'BPS': 'weld_bps',
        'BPQ': 'weld_bpq',
    }

    number_col_map = {
        'WPS': 'wps_number',
        'SWPS': 'wps_number',
        'PQR': 'pqr_number',
        'WPQ': 'wpq_number',
        'BPS': 'bps_number',
        'BPQ': 'bpq_number',
    }

    table = table_map.get(doc_type)
    number_col = number_col_map.get(doc_type)

    if not table or not number_col:
        return None

    cursor.execute(f"SELECT * FROM {table} WHERE {number_col} = ?", (doc_number,))
    row = cursor.fetchone()
    return dict(row) if row else None


def create_wps_record(conn: sqlite3.Connection, doc_number: str, revision: str,
                      file_path: str, is_standard: bool = False, title: str = None) -> int:
    """Create a WPS database record. Also used for SWPS and FPS (orbital/fusion)."""
    cursor = conn.cursor()

    # Check for existing
    existing = find_existing_document(conn, 'WPS', doc_number)
    if existing:
        # Update file path and revision if newer
        cursor.execute("""
            UPDATE weld_wps
            SET file_path = ?, revision = ?, updated_at = CURRENT_TIMESTAMP, is_swps = ?,
                title = COALESCE(?, title)
            WHERE wps_number = ?
        """, (file_path, revision or existing.get('revision', '0'), 1 if is_standard else 0, title, doc_number))
        conn.commit()
        return existing['id']

    cursor.execute("""
        INSERT INTO weld_wps (wps_number, revision, status, is_swps, title, file_path)
        VALUES (?, ?, 'draft', ?, ?, ?)
    """, (doc_number, revision or '0', 1 if is_standard else 0, title, file_path))
    conn.commit()
    return cursor.lastrowid


def create_pqr_record(conn: sqlite3.Connection, doc_number: str, revision: str,
                      file_path: str) -> int:
    """Create a PQR database record."""
    cursor = conn.cursor()

    existing = find_existing_document(conn, 'PQR', doc_number)
    if existing:
        cursor.execute("""
            UPDATE weld_pqr
            SET file_path = ?, revision = ?, updated_at = CURRENT_TIMESTAMP
            WHERE pqr_number = ?
        """, (file_path, revision or existing.get('revision', '0'), doc_number))
        conn.commit()
        return existing['id']

    cursor.execute("""
        INSERT INTO weld_pqr (pqr_number, revision, status, file_path)
        VALUES (?, ?, 'active', ?)
    """, (doc_number, revision or '0', file_path))
    conn.commit()
    return cursor.lastrowid


def extract_process_from_filename(filename: str) -> Optional[str]:
    """Try to extract welding process type from filename."""
    stem = Path(filename).stem.upper()

    # Common welding processes
    processes = ['GTAW', 'SMAW', 'GMAW', 'FCAW', 'SAW', 'PAW', 'ESW', 'EGW', 'OFW']

    for proc in processes:
        if proc in stem:
            return proc

    return None


def create_wpq_record(conn: sqlite3.Connection, doc_number: str, revision: str,
                      file_path: str) -> int:
    """Create a WPQ database record."""
    cursor = conn.cursor()

    # Try to extract process type from filename
    process_type = extract_process_from_filename(file_path)
    if not process_type:
        process_type = 'UNKNOWN'  # Templates or unspecified

    existing = find_existing_document(conn, 'WPQ', doc_number)
    if existing:
        cursor.execute("""
            UPDATE weld_wpq
            SET file_path = ?, revision = ?, updated_at = CURRENT_TIMESTAMP
            WHERE wpq_number = ?
        """, (file_path, revision or existing.get('revision', '0'), doc_number))
        conn.commit()
        return existing['id']

    cursor.execute("""
        INSERT INTO weld_wpq (wpq_number, revision, status, process_type, file_path)
        VALUES (?, ?, 'active', ?, ?)
    """, (doc_number, revision or '0', process_type, file_path))
    conn.commit()
    return cursor.lastrowid


def create_bps_record(conn: sqlite3.Connection, doc_number: str, revision: str,
                      file_path: str) -> int:
    """Create a BPS database record."""
    cursor = conn.cursor()

    existing = find_existing_document(conn, 'BPS', doc_number)
    if existing:
        cursor.execute("""
            UPDATE weld_bps
            SET file_path = ?, revision = ?, updated_at = CURRENT_TIMESTAMP
            WHERE bps_number = ?
        """, (file_path, revision or existing.get('revision', '0'), doc_number))
        conn.commit()
        return existing['id']

    cursor.execute("""
        INSERT INTO weld_bps (bps_number, revision, status, file_path)
        VALUES (?, ?, 'draft', ?)
    """, (doc_number, revision or '0', file_path))
    conn.commit()
    return cursor.lastrowid


def create_bpq_record(conn: sqlite3.Connection, doc_number: str, revision: str,
                      file_path: str) -> int:
    """Create a BPQ database record."""
    cursor = conn.cursor()

    existing = find_existing_document(conn, 'BPQ', doc_number)
    if existing:
        cursor.execute("""
            UPDATE weld_bpq
            SET file_path = ?, revision = ?, updated_at = CURRENT_TIMESTAMP
            WHERE bpq_number = ?
        """, (file_path, revision or existing.get('revision', '0'), doc_number))
        conn.commit()
        return existing['id']

    cursor.execute("""
        INSERT INTO weld_bpq (bpq_number, revision, status, file_path)
        VALUES (?, ?, 'active', ?)
    """, (doc_number, revision or '0', file_path))
    conn.commit()
    return cursor.lastrowid


def register_welder(conn: sqlite3.Connection, employee_number: str, name: str,
                    stamp: str = None) -> int:
    """Register a new welder in the registry."""
    cursor = conn.cursor()

    # Parse name
    parts = name.strip().split()
    if len(parts) >= 2:
        first_name = parts[0]
        last_name = ' '.join(parts[1:])
    else:
        first_name = name
        last_name = ''

    # Check for existing
    cursor.execute("SELECT id FROM weld_welder_registry WHERE employee_number = ?",
                   (employee_number,))
    existing = cursor.fetchone()
    if existing:
        print(f"Welder {employee_number} already exists (ID: {existing[0]})")
        return existing[0]

    cursor.execute("""
        INSERT INTO weld_welder_registry (employee_number, first_name, last_name, welder_stamp, status)
        VALUES (?, ?, ?, ?, 'active')
    """, (employee_number, first_name, last_name, stamp))
    conn.commit()

    print(f"Registered welder: {employee_number} - {first_name} {last_name}")
    return cursor.lastrowid


# =============================================================================
# INTAKE PROCESSING
# =============================================================================

def process_file(conn: sqlite3.Connection, file_path: Path,
                 base_dest: Path, scan_only: bool = False) -> dict:
    """
    Process a single file: classify, route, and create database record.
    Returns processing result dict.
    """
    filename = file_path.name
    result = {
        'file': filename,
        'doc_type': None,
        'doc_number': None,
        'revision': None,
        'action': None,
        'destination': None,
        'db_id': None,
        'notes': None,
    }

    # Classify document
    doc_type, doc_number = classify_document(filename)

    if not doc_type:
        result['action'] = 'skipped'
        result['notes'] = 'Not recognized as welding document'
        return result

    result['doc_type'] = doc_type
    result['doc_number'] = doc_number

    # Extract revision
    revision, base_name = extract_revision(filename)
    result['revision'] = revision

    # Determine destination
    dest_folder = DESTINATIONS.get(doc_type, doc_type)
    dest_dir = base_dest / dest_folder
    dest_path = dest_dir / filename
    result['destination'] = str(dest_path)

    if scan_only:
        result['action'] = 'would_route'
        return result

    # Ensure destination directory exists
    dest_dir.mkdir(parents=True, exist_ok=True)

    # Check for existing file at destination
    if dest_path.exists():
        # Handle as potential revision update
        result['notes'] = f'File already exists at destination'
        result['action'] = 'duplicate'
        log_intake(conn, filename, str(file_path), str(dest_path),
                   doc_type, doc_number, None, 'duplicate', result['notes'])
        return result

    # Create database record based on type
    try:
        if doc_type in ('WPS', 'SWPS', 'FPS'):
            # FPS (Orbital/Fusion) stored as WPS with title indicating type
            db_id = create_wps_record(conn, doc_number, revision, str(dest_path),
                                      is_standard=is_swps(filename),
                                      title='Orbital Fusion Procedure' if doc_type == 'FPS' else None)
        elif doc_type == 'PQR':
            db_id = create_pqr_record(conn, doc_number, revision, str(dest_path))
        elif doc_type == 'WPQ':
            db_id = create_wpq_record(conn, doc_number, revision, str(dest_path))
        elif doc_type == 'BPS':
            db_id = create_bps_record(conn, doc_number, revision, str(dest_path))
        elif doc_type == 'BPQ':
            db_id = create_bpq_record(conn, doc_number, revision, str(dest_path))
        else:
            db_id = None

        result['db_id'] = db_id
    except Exception as e:
        result['action'] = 'error'
        result['notes'] = f'Database error: {e}'
        log_intake(conn, filename, str(file_path), str(dest_path),
                   doc_type, doc_number, None, 'failed', str(e))
        return result

    # Move file to destination
    try:
        shutil.move(str(file_path), str(dest_path))
        result['action'] = 'routed'
        log_intake(conn, filename, str(file_path), str(dest_path),
                   doc_type, doc_number, db_id, 'routed')
    except Exception as e:
        result['action'] = 'error'
        result['notes'] = f'File move error: {e}'
        log_intake(conn, filename, str(file_path), str(dest_path),
                   doc_type, doc_number, db_id, 'failed', str(e))

    return result


def process_inbox(scan_only: bool = False) -> List[dict]:
    """Process all welding documents in the Inbox."""
    config = load_config()

    inbox_path = Path(config['inbox']['path'])
    dest_base = Path(config['destinations']['quality_documents']) / 'Welding'

    if not inbox_path.exists():
        print(f"Inbox not found: {inbox_path}")
        return []

    # Find all PDF and Excel files in inbox (not subdirectories)
    # Use a set to avoid duplicates from case-insensitive matching on Windows
    seen_files = set()
    files = []
    for ext in ['*.pdf', '*.PDF', '*.xls', '*.xlsx', '*.xlsm', '*.XLS', '*.XLSX', '*.XLSM']:
        for f in inbox_path.glob(ext):
            # Normalize to lowercase for dedup on Windows (case-insensitive filesystem)
            normalized = str(f).lower()
            if normalized not in seen_files:
                seen_files.add(normalized)
                files.append(f)

    if not files:
        print("No files found in Inbox")
        return []

    print(f"Found {len(files)} files in Inbox")
    print()

    conn = get_db_connection()
    results = []

    for file_path in sorted(files):
        result = process_file(conn, file_path, dest_base, scan_only)
        results.append(result)

        # Print result
        if result['action'] == 'routed':
            print(f"[OK] {result['file']}")
            print(f"     -> {result['doc_type']} {result['doc_number']} (Rev {result['revision'] or '0'})")
            print(f"     -> {result['destination']}")
            if result['db_id']:
                print(f"     -> DB ID: {result['db_id']}")
        elif result['action'] == 'would_route':
            print(f"[..] {result['file']}")
            print(f"     -> Would route to: {result['doc_type']} folder")
        elif result['action'] == 'skipped':
            print(f"[--] {result['file']}")
            print(f"     -> {result['notes']}")
        elif result['action'] == 'duplicate':
            print(f"[!!] {result['file']}")
            print(f"     -> {result['notes']}")
        else:
            print(f"[XX] {result['file']}")
            print(f"     -> ERROR: {result['notes']}")
        print()

    conn.close()
    return results


def print_summary(results: List[dict]):
    """Print processing summary."""
    print("=" * 50)
    print("INTAKE SUMMARY")
    print("=" * 50)

    by_action = {}
    by_type = {}

    for r in results:
        action = r['action'] or 'unknown'
        doc_type = r['doc_type'] or 'unknown'

        by_action[action] = by_action.get(action, 0) + 1
        if doc_type != 'unknown':
            by_type[doc_type] = by_type.get(doc_type, 0) + 1

    print(f"Total files: {len(results)}")
    print()
    print("By action:")
    for action, count in sorted(by_action.items()):
        symbol = {'routed': '[OK]', 'would_route': '[..]', 'skipped': '[--]',
                  'duplicate': '[!!]', 'error': '[XX]'}.get(action, '[??]')
        print(f"  {symbol} {action}: {count}")

    if by_type:
        print()
        print("By document type:")
        for doc_type, count in sorted(by_type.items()):
            print(f"  {doc_type}: {count}")


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Main entry point."""
    args = sys.argv[1:]

    # Handle --welder command
    if args and args[0] == '--welder':
        if len(args) < 3:
            print("Usage: python weld_intake.py --welder EMPLOYEE_NUMBER \"Full Name\" [STAMP]")
            sys.exit(1)

        conn = get_db_connection()
        emp_num = args[1]
        name = args[2]
        stamp = args[3] if len(args) > 3 else None
        register_welder(conn, emp_num, name, stamp)
        conn.close()
        return

    # Handle --scan flag
    scan_only = '--scan' in args
    if scan_only:
        args = [a for a in args if a != '--scan']
        print("SCAN MODE - Files will not be moved")
        print()

    # Process specific files or entire inbox
    if args:
        # Process specific files
        config = load_config()
        dest_base = Path(config['destinations']['quality_documents']) / 'Welding'
        conn = get_db_connection()

        results = []
        for filepath in args:
            path = Path(filepath)
            if path.exists():
                result = process_file(conn, path, dest_base, scan_only)
                results.append(result)
            else:
                print(f"File not found: {filepath}")

        conn.close()
    else:
        # Process inbox
        results = process_inbox(scan_only)

    if results:
        print()
        print_summary(results)


if __name__ == '__main__':
    main()
