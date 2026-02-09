"""
Welding Document Intake

Routes welding documents (WPS, PQR, WPQ, BPS, BPQ, BPQR) from the Inbox
to appropriate folders and creates database records.

Supports:
    - File classification by filename patterns
    - Routing to correct destination folders
    - Database record creation with basic metadata
    - Revision handling (supersedes older revisions)
    - Intake logging for audit trail
    - Welder registration
"""

import re
import shutil
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from qms.core import get_config, get_db, get_logger, QMS_PATHS

logger = get_logger("qms.welding.intake")


# ---------------------------------------------------------------------------
# Document type patterns (filename-based classification)
# ---------------------------------------------------------------------------

DOC_PATTERNS: Dict[str, List[re.Pattern]] = {
    "WPS": [
        re.compile(r"^WPS[-_\s]+([\w-]+)", re.I),
        re.compile(r"^SWPS[-_\s]+([\w-]+)", re.I),
        re.compile(r"^SWPS\s+[\w-]+\s+(AWS[-\s]*B2)", re.I),
        re.compile(r"^AWS[-_\s]*B2\.?1[-_\s]*([\d-]+)", re.I),
        re.compile(r"^PWPS", re.I),
    ],
    "FPS": [
        re.compile(r"^FPS[-_\s]*([\w-]+)", re.I),
        re.compile(r"Orbital[-_\s]*Fusion", re.I),
        re.compile(r"Fusion[-_\s]*Procedure", re.I),
    ],
    "PQR": [
        re.compile(r"^PQR[-_\s]*([\w-]+)", re.I),
    ],
    "WPQ": [
        re.compile(r"^WPQ[-_\s]*([\w-]+)", re.I),
        re.compile(r"^WQ[-_\s]*(\d+[\w-]*)", re.I),
        re.compile(r"WPQ\s*Template[-_\s]*([\w-]+)", re.I),
        re.compile(r"Template[-_\s]*WPQ", re.I),
        re.compile(r"WPQ\s+([\w-]+-P\d+)", re.I),
        re.compile(r"Welder[-_\s]*Qual", re.I),
    ],
    "BPS": [
        re.compile(r"^BPS[-_\s]*([\w-]+)", re.I),
        re.compile(r"^pBPS", re.I),
        re.compile(r"BPS[-_\s]*([\w-]+)\s*ACR", re.I),
        re.compile(r"BPS[-_\s]*([\w-]+)", re.I),
        re.compile(r"Braze\s*Test", re.I),
    ],
    "BPQ": [
        re.compile(r"^BPQ[-_\s]*([\w-]+)", re.I),
        re.compile(r"^BPQR[-_\s]*([\w-]+)", re.I),
    ],
    "FORM": [
        re.compile(r"FORM\s+Q[WB][-_]?\d+", re.I),
    ],
}

# Destination folders (relative to Quality Documents/Welding/)
DESTINATIONS: Dict[str, str] = {
    "WPS": "WPS",
    "SWPS": "WPS/SWPS",
    "FPS": "WPS/FPS",
    "PQR": "PQR",
    "WPQ": "WPQ",
    "BPS": "BPS",
    "BPQ": "BPQ",
    "BPQR": "BPQ",
    "FORM": "Forms",
}

# Table -> number column mapping for document lookups
_TABLE_MAP: Dict[str, str] = {
    "WPS": "weld_wps",
    "SWPS": "weld_wps",
    "PQR": "weld_pqr",
    "WPQ": "weld_wpq",
    "BPS": "weld_bps",
    "BPQ": "weld_bpq",
}

_NUMBER_COL_MAP: Dict[str, str] = {
    "WPS": "wps_number",
    "SWPS": "wps_number",
    "PQR": "pqr_number",
    "WPQ": "wpq_number",
    "BPS": "bps_number",
    "BPQ": "bpq_number",
}


# ---------------------------------------------------------------------------
# Classification helpers
# ---------------------------------------------------------------------------

def extract_doc_number(filename: str, pattern: re.Pattern) -> Optional[str]:
    """Extract document number from filename using pattern."""
    match = pattern.search(filename)
    if match and match.groups():
        return match.group(1)
    elif match:
        return Path(filename).stem
    return None


def extract_revision(filename: str) -> Tuple[Optional[str], str]:
    """
    Extract revision from filename.

    Returns:
        (revision, base_name_without_revision)

    Examples:
        WPS-001_Rev_A.pdf -> ('A', 'WPS-001')
        PQR-P107-TB-01.pdf -> (None, 'PQR-P107-TB-01')
    """
    stem = Path(filename).stem

    # Pattern: _Rev_X or _Rev-X or _RevX
    rev_match = re.search(r"[-_]Rev[-_]?([A-Z0-9]+)$", stem, re.I)
    if rev_match:
        revision = rev_match.group(1).upper()
        base = stem[: rev_match.start()]
        return revision, base

    # Pattern: trailing -X where X is single letter
    rev_match = re.search(r"[-_]([A-Z])$", stem)
    if rev_match:
        revision = rev_match.group(1)
        base = stem[: rev_match.start()]
        return revision, base

    return None, stem


def classify_document(filename: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Classify a document based on filename patterns.

    Returns:
        (doc_type, doc_number) or (None, None) if not recognized.
    """
    stem = Path(filename).stem
    stem_upper = stem.upper()

    priority_order = ["WPQ", "SWPS", "FPS", "WPS", "PQR", "BPS", "BPQ", "FORM"]

    for doc_type in priority_order:
        if doc_type == "SWPS":
            if "WPQ" in stem_upper or "WQ-" in stem_upper:
                continue
            if "SWPS" in stem_upper or "AWS B2" in stem_upper or "AWS-B2" in stem_upper:
                match = re.search(r"SWPS[-_\s]*([\w-]+)", stem, re.I)
                if match:
                    return "SWPS", match.group(1)
                match = re.search(r"AWS[-_\s]*B2\.?1[-_\s]*([\d-]+)", stem, re.I)
                if match:
                    return "SWPS", f"AWS-B2.1-{match.group(1)}"
                return "SWPS", stem
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
    return stem.startswith("SWPS") or stem.startswith("AWS-B2.1") or stem.startswith("PWPS")


def extract_process_from_filename(filename: str) -> Optional[str]:
    """Try to extract welding process type from filename."""
    stem = Path(filename).stem.upper()
    processes = ["GTAW", "SMAW", "GMAW", "FCAW", "SAW", "PAW", "ESW", "EGW", "OFW"]
    for proc in processes:
        if proc in stem:
            return proc
    return None


# ---------------------------------------------------------------------------
# Database operations
# ---------------------------------------------------------------------------

def log_intake(
    conn: sqlite3.Connection,
    filename: str,
    source_path: str,
    dest_path: str,
    doc_type: str,
    doc_number: str,
    doc_id: Optional[int],
    action: str,
    notes: Optional[str] = None,
) -> None:
    """Log an intake action to the audit trail."""
    conn.execute(
        """INSERT INTO weld_intake_log
           (file_name, source_path, destination_path, document_type,
            document_number, document_id, action, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (filename, source_path, dest_path, doc_type, doc_number, doc_id, action, notes),
    )
    conn.commit()


def find_existing_document(
    conn: sqlite3.Connection, doc_type: str, doc_number: str
) -> Optional[Dict[str, Any]]:
    """Find existing document record by type and number."""
    table = _TABLE_MAP.get(doc_type)
    number_col = _NUMBER_COL_MAP.get(doc_type)
    if not table or not number_col:
        return None

    row = conn.execute(
        f"SELECT * FROM {table} WHERE {number_col} = ?", (doc_number,)
    ).fetchone()
    return dict(row) if row else None


def create_wps_record(
    conn: sqlite3.Connection,
    doc_number: str,
    revision: Optional[str],
    file_path: str,
    is_standard: bool = False,
    title: Optional[str] = None,
) -> int:
    """Create or update a WPS database record. Also used for SWPS and FPS."""
    existing = find_existing_document(conn, "WPS", doc_number)
    if existing:
        conn.execute(
            """UPDATE weld_wps
               SET file_path = ?, revision = ?, updated_at = CURRENT_TIMESTAMP,
                   is_swps = ?, title = COALESCE(?, title)
               WHERE wps_number = ?""",
            (
                file_path,
                revision or existing.get("revision", "0"),
                1 if is_standard else 0,
                title,
                doc_number,
            ),
        )
        conn.commit()
        return existing["id"]

    cursor = conn.execute(
        """INSERT INTO weld_wps (wps_number, revision, status, is_swps, title, file_path)
           VALUES (?, ?, 'draft', ?, ?, ?)""",
        (doc_number, revision or "0", 1 if is_standard else 0, title, file_path),
    )
    conn.commit()
    return cursor.lastrowid


def create_pqr_record(
    conn: sqlite3.Connection,
    doc_number: str,
    revision: Optional[str],
    file_path: str,
) -> int:
    """Create or update a PQR database record."""
    existing = find_existing_document(conn, "PQR", doc_number)
    if existing:
        conn.execute(
            """UPDATE weld_pqr
               SET file_path = ?, revision = ?, updated_at = CURRENT_TIMESTAMP
               WHERE pqr_number = ?""",
            (file_path, revision or existing.get("revision", "0"), doc_number),
        )
        conn.commit()
        return existing["id"]

    cursor = conn.execute(
        """INSERT INTO weld_pqr (pqr_number, revision, status, file_path)
           VALUES (?, ?, 'active', ?)""",
        (doc_number, revision or "0", file_path),
    )
    conn.commit()
    return cursor.lastrowid


def create_wpq_record(
    conn: sqlite3.Connection,
    doc_number: str,
    revision: Optional[str],
    file_path: str,
) -> int:
    """Create or update a WPQ database record."""
    process_type = extract_process_from_filename(file_path) or "UNKNOWN"

    existing = find_existing_document(conn, "WPQ", doc_number)
    if existing:
        conn.execute(
            """UPDATE weld_wpq
               SET file_path = ?, revision = ?, updated_at = CURRENT_TIMESTAMP
               WHERE wpq_number = ?""",
            (file_path, revision or existing.get("revision", "0"), doc_number),
        )
        conn.commit()
        return existing["id"]

    cursor = conn.execute(
        """INSERT INTO weld_wpq (wpq_number, revision, status, process_type, file_path)
           VALUES (?, ?, 'active', ?, ?)""",
        (doc_number, revision or "0", process_type, file_path),
    )
    conn.commit()
    return cursor.lastrowid


def create_bps_record(
    conn: sqlite3.Connection,
    doc_number: str,
    revision: Optional[str],
    file_path: str,
) -> int:
    """Create or update a BPS database record."""
    existing = find_existing_document(conn, "BPS", doc_number)
    if existing:
        conn.execute(
            """UPDATE weld_bps
               SET file_path = ?, revision = ?, updated_at = CURRENT_TIMESTAMP
               WHERE bps_number = ?""",
            (file_path, revision or existing.get("revision", "0"), doc_number),
        )
        conn.commit()
        return existing["id"]

    cursor = conn.execute(
        """INSERT INTO weld_bps (bps_number, revision, status, file_path)
           VALUES (?, ?, 'draft', ?)""",
        (doc_number, revision or "0", file_path),
    )
    conn.commit()
    return cursor.lastrowid


def create_bpq_record(
    conn: sqlite3.Connection,
    doc_number: str,
    revision: Optional[str],
    file_path: str,
) -> int:
    """Create or update a BPQ database record."""
    existing = find_existing_document(conn, "BPQ", doc_number)
    if existing:
        conn.execute(
            """UPDATE weld_bpq
               SET file_path = ?, revision = ?, updated_at = CURRENT_TIMESTAMP
               WHERE bpq_number = ?""",
            (file_path, revision or existing.get("revision", "0"), doc_number),
        )
        conn.commit()
        return existing["id"]

    cursor = conn.execute(
        """INSERT INTO weld_bpq (bpq_number, revision, status, file_path)
           VALUES (?, ?, 'active', ?)""",
        (doc_number, revision or "0", file_path),
    )
    conn.commit()
    return cursor.lastrowid


def register_welder(
    conn: sqlite3.Connection,
    employee_number: str,
    name: str,
    stamp: Optional[str] = None,
) -> int:
    """
    Register a new welder in the registry.

    Args:
        conn: Database connection
        employee_number: Employee number or identifier
        name: Full name (parsed into first/last)
        stamp: Optional welder stamp

    Returns:
        Welder registry ID
    """
    parts = name.strip().split()
    if len(parts) >= 2:
        first_name = parts[0]
        last_name = " ".join(parts[1:])
    else:
        first_name = name
        last_name = ""

    row = conn.execute(
        "SELECT id FROM weld_welder_registry WHERE employee_number = ?",
        (employee_number,),
    ).fetchone()
    if row:
        logger.info("Welder %s already exists (ID: %d)", employee_number, row["id"])
        return row["id"]

    cursor = conn.execute(
        """INSERT INTO weld_welder_registry
           (employee_number, first_name, last_name, welder_stamp, status)
           VALUES (?, ?, ?, ?, 'active')""",
        (employee_number, first_name, last_name, stamp),
    )
    conn.commit()
    logger.info("Registered welder: %s - %s %s", employee_number, first_name, last_name)
    return cursor.lastrowid


# ---------------------------------------------------------------------------
# File processing
# ---------------------------------------------------------------------------

def process_file(
    conn: sqlite3.Connection,
    file_path: Path,
    base_dest: Path,
    scan_only: bool = False,
) -> Dict[str, Any]:
    """
    Process a single file: classify, route, and create database record.

    Args:
        conn: Database connection
        file_path: Path to the source file
        base_dest: Base destination directory for welding documents
        scan_only: If True, classify only without moving files

    Returns:
        Processing result dict with keys: file, doc_type, doc_number,
        revision, action, destination, db_id, notes
    """
    filename = file_path.name
    result: Dict[str, Any] = {
        "file": filename,
        "doc_type": None,
        "doc_number": None,
        "revision": None,
        "action": None,
        "destination": None,
        "db_id": None,
        "notes": None,
    }

    doc_type, doc_number = classify_document(filename)
    if not doc_type:
        result["action"] = "skipped"
        result["notes"] = "Not recognized as welding document"
        return result

    result["doc_type"] = doc_type
    result["doc_number"] = doc_number

    revision, _base_name = extract_revision(filename)
    result["revision"] = revision

    dest_folder = DESTINATIONS.get(doc_type, doc_type)
    dest_dir = base_dest / dest_folder
    dest_path = dest_dir / filename
    result["destination"] = str(dest_path)

    if scan_only:
        result["action"] = "would_route"
        return result

    dest_dir.mkdir(parents=True, exist_ok=True)

    if dest_path.exists():
        result["notes"] = "File already exists at destination"
        result["action"] = "duplicate"
        log_intake(conn, filename, str(file_path), str(dest_path),
                   doc_type, doc_number, None, "duplicate", result["notes"])
        return result

    # Create database record
    try:
        db_id: Optional[int] = None
        if doc_type in ("WPS", "SWPS", "FPS"):
            db_id = create_wps_record(
                conn, doc_number, revision, str(dest_path),
                is_standard=is_swps(filename),
                title="Orbital Fusion Procedure" if doc_type == "FPS" else None,
            )
        elif doc_type == "PQR":
            db_id = create_pqr_record(conn, doc_number, revision, str(dest_path))
        elif doc_type == "WPQ":
            db_id = create_wpq_record(conn, doc_number, revision, str(dest_path))
        elif doc_type == "BPS":
            db_id = create_bps_record(conn, doc_number, revision, str(dest_path))
        elif doc_type == "BPQ":
            db_id = create_bpq_record(conn, doc_number, revision, str(dest_path))

        result["db_id"] = db_id
    except Exception as exc:
        result["action"] = "error"
        result["notes"] = f"Database error: {exc}"
        log_intake(conn, filename, str(file_path), str(dest_path),
                   doc_type, doc_number, None, "failed", str(exc))
        logger.error("Database error processing %s: %s", filename, exc)
        return result

    # Move file
    try:
        shutil.move(str(file_path), str(dest_path))
        result["action"] = "routed"
        log_intake(conn, filename, str(file_path), str(dest_path),
                   doc_type, doc_number, db_id, "routed")
        logger.info("Routed %s -> %s (%s %s)", filename, dest_folder, doc_type, doc_number)
    except Exception as exc:
        result["action"] = "error"
        result["notes"] = f"File move error: {exc}"
        log_intake(conn, filename, str(file_path), str(dest_path),
                   doc_type, doc_number, db_id, "failed", str(exc))
        logger.error("File move error for %s: %s", filename, exc)

    return result


def process_inbox(scan_only: bool = False) -> List[Dict[str, Any]]:
    """
    Process all welding documents in the Inbox.

    Args:
        scan_only: If True, classify only without moving files

    Returns:
        List of processing result dicts
    """
    config = get_config()
    inbox_path = QMS_PATHS.inbox
    dest_base = QMS_PATHS.quality_documents / "Welding"

    if not inbox_path.exists():
        logger.warning("Inbox not found: %s", inbox_path)
        return []

    # Collect files (dedup for case-insensitive Windows filesystem)
    seen: set = set()
    files: List[Path] = []
    for ext in ["*.pdf", "*.PDF", "*.xls", "*.xlsx", "*.xlsm", "*.XLS", "*.XLSX", "*.XLSM"]:
        for f in inbox_path.glob(ext):
            normalized = str(f).lower()
            if normalized not in seen:
                seen.add(normalized)
                files.append(f)

    if not files:
        logger.info("No files found in Inbox")
        return []

    logger.info("Found %d files in Inbox", len(files))

    with get_db() as conn:
        results: List[Dict[str, Any]] = []
        for file_path in sorted(files):
            result = process_file(conn, file_path, dest_base, scan_only)
            results.append(result)

    return results


def get_intake_summary(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Compute intake processing summary.

    Args:
        results: List of processing result dicts from process_inbox

    Returns:
        Summary dict with by_action, by_type counts and totals
    """
    by_action: Dict[str, int] = {}
    by_type: Dict[str, int] = {}

    for r in results:
        action = r.get("action") or "unknown"
        doc_type = r.get("doc_type") or "unknown"

        by_action[action] = by_action.get(action, 0) + 1
        if doc_type != "unknown":
            by_type[doc_type] = by_type.get(doc_type, 0) + 1

    return {
        "total": len(results),
        "by_action": by_action,
        "by_type": by_type,
    }


# ---------------------------------------------------------------------------
# Dashboard / query helpers
# ---------------------------------------------------------------------------

def get_dashboard_data() -> Dict[str, Any]:
    """
    Retrieve welding program dashboard data.

    Returns:
        Dict with counts for active welders, WPS, WPQ, PQR, BPS, BPQ, BPQR
    """
    with get_db(readonly=True) as conn:
        welders = conn.execute(
            "SELECT COUNT(*) as n FROM weld_welder_registry WHERE status = 'active'"
        ).fetchone()
        wps = conn.execute(
            "SELECT COUNT(*) as n FROM weld_wps WHERE status IN ('active', 'draft')"
        ).fetchone()
        wpq = conn.execute(
            "SELECT COUNT(*) as n FROM weld_wpq WHERE status = 'active'"
        ).fetchone()
        pqr = conn.execute(
            "SELECT COUNT(*) as n FROM weld_pqr WHERE status = 'active'"
        ).fetchone()
        bps = conn.execute(
            "SELECT COUNT(*) as n FROM weld_bps WHERE status IN ('active', 'draft')"
        ).fetchone()
        bpq = conn.execute(
            "SELECT COUNT(*) as n FROM weld_bpq WHERE status = 'active'"
        ).fetchone()

    return {
        "active_welders": welders["n"],
        "wps_count": wps["n"],
        "wpq_count": wpq["n"],
        "pqr_count": pqr["n"],
        "bps_count": bps["n"],
        "bpq_count": bpq["n"],
    }


def find_wps(conn: sqlite3.Connection, wps_number: str) -> Optional[Dict[str, Any]]:
    """Look up a WPS by number."""
    row = conn.execute(
        "SELECT * FROM weld_wps WHERE wps_number = ?", (wps_number,)
    ).fetchone()
    return dict(row) if row else None


def list_active_welders(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """List all active welders."""
    rows = conn.execute(
        "SELECT * FROM weld_welder_registry WHERE status = 'active' ORDER BY last_name, first_name"
    ).fetchall()
    return [dict(r) for r in rows]
