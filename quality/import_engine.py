"""
Quality Issue CSV Import Engine.

Parses CSV files containing quality observations/issues, maps and normalizes
fields, deduplicates against existing records, and bulk-inserts into the
quality_issues schema.

Usage (Python):
    from qms.quality.import_engine import import_quality_csv
    with get_db() as conn:
        result = import_quality_csv(conn, "path/to/observations.csv", project_id=42)

Usage (CLI):
    qms quality import-csv "path/to/observations.csv" --project 07645
"""

import csv
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from qms.core import get_logger
from qms.quality.db import normalize_status, normalize_trade, normalize_type

logger = get_logger("qms.quality.import")

# ---------------------------------------------------------------------------
# Column alias mapping: canonical_name → list of CSV header aliases
# ---------------------------------------------------------------------------

_COLUMN_ALIASES: Dict[str, List[str]] = {
    "title": ["title", "name", "observation name", "issue title", "subject"],
    "type": ["type", "observation type", "issue type", "category"],
    "description": ["description", "body", "details", "notes", "observation description"],
    "trade": ["trade", "responsible contractor", "contractor", "responsible party", "spec section"],
    "status": ["status", "observation status", "state"],
    "location": ["location", "area", "building", "zone", "location description"],
    "priority": ["priority"],
    "severity": ["severity", "risk level"],
    "assigned_to": ["assignee", "assigned to", "assigned", "responsible"],
    "reported_by": ["reported by", "created by", "reporter", "author", "observer"],
    "due_date": ["due date", "due", "target date", "completion date"],
    "source_id": ["id", "observation id", "number", "observation number", "#", "ref", "reference"],
    "source_url": ["url", "link", "observation url", "procore url"],
    "created_at": ["created at", "created date", "created", "date created", "date"],
}

# Valid values for CHECK-constrained fields
_VALID_PRIORITIES = {"low", "medium", "high", "urgent"}
_VALID_SEVERITIES = {"low", "medium", "high", "critical"}

# Date parsing patterns
_DATE_PATTERNS = [
    (re.compile(r"^\d{4}-\d{2}-\d{2}$"), "%Y-%m-%d"),
    (re.compile(r"^\d{4}-\d{2}-\d{2}T"), None),  # ISO with time — handled specially
    (re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$"), None),  # M/D/YYYY — handled specially
    (re.compile(r"^\d{1,2}/\d{1,2}/\d{2}$"), None),  # M/D/YY — handled specially
]


# ---------------------------------------------------------------------------
# Header mapping
# ---------------------------------------------------------------------------


def _auto_map_headers(headers: List[str]) -> Dict[str, str]:
    """Map raw CSV headers to canonical field names.

    Args:
        headers: Raw CSV column headers.

    Returns:
        Dict mapping csv_header → canonical_field_name.
        Unmapped headers are excluded.
    """
    # Build reverse lookup: alias → canonical
    alias_to_canonical: Dict[str, str] = {}
    for canonical, aliases in _COLUMN_ALIASES.items():
        for alias in aliases:
            alias_to_canonical[alias] = canonical

    mapping: Dict[str, str] = {}
    used_canonicals: set = set()

    for header in headers:
        normalized = header.strip().lower()
        if normalized in alias_to_canonical:
            canonical = alias_to_canonical[normalized]
            if canonical not in used_canonicals:
                mapping[header] = canonical
                used_canonicals.add(canonical)

    return mapping


# ---------------------------------------------------------------------------
# Date parsing
# ---------------------------------------------------------------------------


def _parse_date(value: str) -> Optional[str]:
    """Parse various date formats into YYYY-MM-DD.

    Handles: YYYY-MM-DD, ISO datetime, M/D/YYYY, M/D/YY.
    Returns None if parsing fails.
    """
    if not value or not value.strip():
        return None

    value = value.strip()

    # YYYY-MM-DD (already correct)
    if re.match(r"^\d{4}-\d{2}-\d{2}$", value):
        return value

    # ISO datetime (YYYY-MM-DDTHH:MM:SS...) — extract date part
    if re.match(r"^\d{4}-\d{2}-\d{2}T", value):
        return value[:10]

    # M/D/YYYY
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", value)
    if m:
        month, day, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            return datetime(year, month, day).strftime("%Y-%m-%d")
        except ValueError:
            return None

    # M/D/YY
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{2})$", value)
    if m:
        month, day, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        year += 2000 if year < 70 else 1900
        try:
            return datetime(year, month, day).strftime("%Y-%m-%d")
        except ValueError:
            return None

    return None


# ---------------------------------------------------------------------------
# Row processing
# ---------------------------------------------------------------------------


def _extract_row(
    row: Dict[str, str],
    header_map: Dict[str, str],
) -> Dict[str, Any]:
    """Extract and normalize fields from a single CSV row.

    Args:
        row: Raw CSV row dict.
        header_map: Mapping of csv_header → canonical_field_name.

    Returns:
        Dict of canonical_field → processed_value.
    """
    fields: Dict[str, Any] = {}

    for csv_header, canonical in header_map.items():
        raw = row.get(csv_header, "").strip()
        if not raw:
            continue

        if canonical == "trade":
            fields["trade"] = normalize_trade(raw)
        elif canonical == "status":
            fields["status"] = normalize_status(raw)
        elif canonical == "type":
            fields["type"] = normalize_type(raw)
        elif canonical == "priority":
            val = raw.lower()
            if val in _VALID_PRIORITIES:
                fields["priority"] = val
        elif canonical == "severity":
            val = raw.lower()
            if val in _VALID_SEVERITIES:
                fields["severity"] = val
        elif canonical in ("due_date", "created_at"):
            parsed = _parse_date(raw)
            if parsed:
                fields[canonical] = parsed
        elif canonical == "source_id":
            fields["source_id"] = str(raw)
        else:
            fields[canonical] = raw

    return fields


# ---------------------------------------------------------------------------
# Main import function
# ---------------------------------------------------------------------------


def import_quality_csv(
    conn: sqlite3.Connection,
    csv_path: str,
    *,
    project_id: int,
    source: str = "procore",
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Import quality issues from a CSV file.

    Parses the CSV, maps headers, normalizes fields, deduplicates via
    source+source_id, and inserts/updates quality_issues rows.

    Args:
        conn: Database connection.
        csv_path: Path to the CSV file.
        project_id: QMS project ID to associate issues with.
        source: Source tag (default "procore").
        dry_run: If True, compute counts but don't write to DB.

    Returns:
        Dict with counts: issues_created, issues_updated, issues_skipped,
        rows_total, errors, skipped_details.
    """
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    result: Dict[str, Any] = {
        "issues_created": 0,
        "issues_updated": 0,
        "issues_skipped": 0,
        "rows_total": 0,
        "errors": [],
        "skipped_details": [],
    }

    # ------------------------------------------------------------------
    # 1. Parse CSV
    # ------------------------------------------------------------------
    raw_text = path.read_text(encoding="utf-8-sig")  # handle BOM
    reader = csv.DictReader(raw_text.splitlines())

    if not reader.fieldnames:
        result["errors"].append("CSV file has no headers")
        return result

    header_map = _auto_map_headers(list(reader.fieldnames))
    if "title" not in header_map.values():
        result["errors"].append(
            f"No 'title' column found. Headers: {list(reader.fieldnames)}"
        )
        return result

    logger.info(
        "Header mapping: %s",
        {k: v for k, v in header_map.items()},
    )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # ------------------------------------------------------------------
    # 2. Process rows
    # ------------------------------------------------------------------
    for row_idx, row in enumerate(reader, start=2):  # row 1 = header
        result["rows_total"] += 1
        fields = _extract_row(row, header_map)

        # Validate: title is required
        if not fields.get("title"):
            result["issues_skipped"] += 1
            result["skipped_details"].append({
                "row": row_idx,
                "reason": "Missing title",
            })
            continue

        # Set source fields
        fields["source"] = source
        fields["project_id"] = project_id
        fields["source_synced_at"] = now

        # Default type if not mapped
        if "type" not in fields:
            fields["type"] = "observation"

        # Default status if not mapped
        if "status" not in fields:
            fields["status"] = "open"

        if dry_run:
            # Check what would happen
            if fields.get("source_id"):
                existing = conn.execute(
                    "SELECT id FROM quality_issues WHERE source = ? AND source_id = ?",
                    (source, fields["source_id"]),
                ).fetchone()
                if existing:
                    result["issues_updated"] += 1
                else:
                    result["issues_created"] += 1
            else:
                result["issues_created"] += 1
            continue

        # ----------------------------------------------------------
        # 3. Dedup check and upsert
        # ----------------------------------------------------------
        try:
            if fields.get("source_id"):
                existing = conn.execute(
                    "SELECT id FROM quality_issues WHERE source = ? AND source_id = ?",
                    (source, fields["source_id"]),
                ).fetchone()

                if existing:
                    _update_issue(conn, existing["id"], fields)
                    result["issues_updated"] += 1
                    continue

            _insert_issue(conn, fields)
            result["issues_created"] += 1

        except Exception as e:
            logger.error("Error importing row %d: %s", row_idx, e)
            result["errors"].append({
                "row": row_idx,
                "title": fields.get("title", ""),
                "error": str(e),
            })

    if not dry_run:
        conn.commit()

    total = result["issues_created"] + result["issues_updated"] + result["issues_skipped"]
    logger.info(
        "Import complete: %d created, %d updated, %d skipped, %d errors (of %d rows)",
        result["issues_created"],
        result["issues_updated"],
        result["issues_skipped"],
        len(result["errors"]),
        result["rows_total"],
    )

    return result


# ---------------------------------------------------------------------------
# Insert / Update helpers
# ---------------------------------------------------------------------------

_INSERT_FIELDS = [
    "type", "title", "description", "project_id", "location", "trade",
    "severity", "priority", "status", "assigned_to", "reported_by",
    "due_date", "source", "source_id", "source_url", "source_synced_at",
    "created_at",
]


def _insert_issue(conn: sqlite3.Connection, fields: Dict[str, Any]) -> int:
    """Insert a new quality_issues row. Returns the new row id."""
    cols = []
    vals = []
    for f in _INSERT_FIELDS:
        if f in fields:
            cols.append(f)
            vals.append(fields[f])

    placeholders = ", ".join("?" for _ in cols)
    col_str = ", ".join(cols)
    cursor = conn.execute(
        f"INSERT INTO quality_issues ({col_str}) VALUES ({placeholders})",
        vals,
    )
    return cursor.lastrowid


_UPDATE_FIELDS = [
    "type", "title", "description", "location", "trade", "severity",
    "priority", "status", "assigned_to", "reported_by", "due_date",
    "source_url", "source_synced_at",
]


def _update_issue(conn: sqlite3.Connection, issue_id: int, fields: Dict[str, Any]) -> None:
    """Update an existing quality_issues row."""
    sets = []
    vals = []
    for f in _UPDATE_FIELDS:
        if f in fields:
            sets.append(f"{f} = ?")
            vals.append(fields[f])

    if not sets:
        return

    sets.append("updated_at = CURRENT_TIMESTAMP")
    vals.append(issue_id)

    conn.execute(
        f"UPDATE quality_issues SET {', '.join(sets)} WHERE id = ?",
        vals,
    )
