"""
Procore CSV Import for QMS Projects.

Reads a Procore "Company Home" CSV export and upserts projects + jobs
into the QMS database.  Each CSV row is a subjob; rows sharing the same
5-digit base number are grouped into one project.

Usage (CLI):
    qms projects import-procore "path/to/Company Home (3).csv"

Usage (Python):
    from qms.projects.procore_io import import_from_procore
    with get_db() as conn:
        result = import_from_procore(conn, "path/to/export.csv")
"""

import csv
import re
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from qms.core import get_logger
from qms.projects.budget import parse_job_code

logger = get_logger("qms.projects.procore")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PROCORE_NUMBER = re.compile(r"^\d{5}(-\d{3}(-\d{2})?)?$")

_DEPT_CODE = re.compile(r"^(\d{3})\s*-")

# Stage priority: higher index = more advanced
STAGE_PRIORITY = [
    "Archive",
    "Warranty",
    "Proposal",
    "Pre-Construction",
    "Construction and Bidding",
    "Course of Construction",
]

SCOPE_KEYWORDS = {
    "hvac", "plumbing", "utilities", "utility", "process", "electrical",
    "refrigeration", "controls", "mechanical", "piping", "fire protection",
    "additions", "mccs", "transformer", "switch", "procurement",
}

STATE_ABBREVS = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR",
    "California": "CA", "Colorado": "CO", "Connecticut": "CT",
    "Delaware": "DE", "Florida": "FL", "Georgia": "GA", "Hawaii": "HI",
    "Idaho": "ID", "Illinois": "IL", "Indiana": "IN", "Iowa": "IA",
    "Kansas": "KS", "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME",
    "Maryland": "MD", "Massachusetts": "MA", "Michigan": "MI",
    "Minnesota": "MN", "Mississippi": "MS", "Missouri": "MO",
    "Montana": "MT", "Nebraska": "NE", "Nevada": "NV",
    "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM",
    "New York": "NY", "North Carolina": "NC", "North Dakota": "ND",
    "Ohio": "OH", "Oklahoma": "OK", "Oregon": "OR", "Pennsylvania": "PA",
    "Rhode Island": "RI", "South Carolina": "SC", "South Dakota": "SD",
    "Tennessee": "TN", "Texas": "TX", "Utah": "UT", "Vermont": "VT",
    "Virginia": "VA", "Washington": "WA", "West Virginia": "WV",
    "Wisconsin": "WI", "Wyoming": "WY",
}


# ---------------------------------------------------------------------------
# Name parsing
# ---------------------------------------------------------------------------


def _is_scope_keyword(text: str) -> bool:
    """Check if text contains a known scope keyword (case-insensitive)."""
    lower = text.lower()
    return any(kw in lower for kw in SCOPE_KEYWORDS)


def parse_procore_name(
    name: str,
) -> Tuple[str, Optional[str], Optional[str]]:
    """
    Split a Procore Name column into (project_name, description, scope_name).

    Format: "Project Name - Description - Scope Name"
    - 3+ parts: first=name, second=description, rest=scope
    - 2 parts: first=name; second is scope if keyword match, else description
    - 1 part: just name
    """
    parts = [p.strip() for p in name.split(" - ")]

    if len(parts) >= 3:
        return parts[0], parts[1], " - ".join(parts[2:])
    elif len(parts) == 2:
        if _is_scope_keyword(parts[1]):
            return parts[0], None, parts[1]
        else:
            return parts[0], parts[1], None
    else:
        return parts[0], None, None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_stage(stages: List[str]) -> str:
    """Pick the most advanced stage from a list using STAGE_PRIORITY."""
    best_idx = -1
    best_stage = "Proposal"
    for s in stages:
        try:
            idx = STAGE_PRIORITY.index(s)
        except ValueError:
            idx = -1
        if idx > best_idx:
            best_idx = idx
            best_stage = s
    return best_stage


def _abbreviate_state(state: str) -> str:
    """Convert full state name to 2-letter abbreviation."""
    if not state:
        return ""
    # Already abbreviated?
    if len(state) <= 2:
        return state.upper()
    return STATE_ABBREVS.get(state.strip(), state.strip())


def _extract_bu_from_department(dept: str) -> Optional[str]:
    """Extract 3-digit BU code from Department column like '650 - SIS Mechanical'."""
    if not dept:
        return None
    m = _DEPT_CODE.match(dept.strip())
    return m.group(1) if m else None


# ---------------------------------------------------------------------------
# Main import function
# ---------------------------------------------------------------------------


def import_from_procore(
    conn: sqlite3.Connection, csv_path: str, *, dry_run: bool = False
) -> Dict[str, Any]:
    """
    Import projects and jobs from a Procore Company Home CSV export.

    Upserts into projects and jobs tables. Never deletes existing data.

    Args:
        conn: Database connection.
        csv_path: Path to the Procore CSV file.
        dry_run: If True, parse and validate but roll back all DB changes.

    Returns:
        dict with counts of created/updated/skipped items and any errors.
    """
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    result: Dict[str, Any] = {
        "projects_created": 0,
        "projects_updated": 0,
        "jobs_created": 0,
        "jobs_updated": 0,
        "rows_skipped": 0,
        "skipped_details": [],
        "errors": [],
    }

    # -----------------------------------------------------------------------
    # 1. Parse CSV
    # -----------------------------------------------------------------------
    rows: List[Dict[str, str]] = []
    raw_text = path.read_text(encoding="utf-8-sig")  # handle BOM
    reader = csv.DictReader(raw_text.splitlines())
    for i, row in enumerate(reader, start=2):  # row 1 is header
        # Strip whitespace from keys and values
        cleaned = {k.strip(): (v.strip() if v else "") for k, v in row.items()}
        cleaned["_row"] = str(i)
        rows.append(cleaned)

    # -----------------------------------------------------------------------
    # 2. Filter rows
    # -----------------------------------------------------------------------
    valid_rows: List[Dict[str, str]] = []
    for row in rows:
        number = row.get("Project Number", "")
        address = row.get("Address", "")
        program = row.get("Program", "")

        # Skip internal projects
        if "2900 Hartley" in address:
            result["rows_skipped"] += 1
            result["skipped_details"].append({
                "row": int(row["_row"]),
                "number": number,
                "reason": "Internal project (2900 Hartley address)",
            })
            continue

        # Skip test projects
        if program == "Test Project":
            result["rows_skipped"] += 1
            result["skipped_details"].append({
                "row": int(row["_row"]),
                "number": number,
                "reason": "Test project (Program = 'Test Project')",
            })
            continue

        # Skip non-standard project numbers
        if not _PROCORE_NUMBER.match(number):
            result["rows_skipped"] += 1
            result["skipped_details"].append({
                "row": int(row["_row"]),
                "number": number,
                "reason": f"Non-standard project number: {number}",
            })
            continue

        valid_rows.append(row)

    # -----------------------------------------------------------------------
    # 3. Group by base project number
    # -----------------------------------------------------------------------
    groups: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    for row in valid_rows:
        number = row["Project Number"]
        parsed = parse_job_code(number)
        if parsed:
            base = parsed[0]
            groups[base].append(row)

    # -----------------------------------------------------------------------
    # 4. Process each project group
    # -----------------------------------------------------------------------
    for base_number, group_rows in sorted(groups.items()):
        try:
            _process_project_group(conn, base_number, group_rows, result)
        except Exception as e:
            logger.error("Error processing project %s: %s", base_number, e)
            result["errors"].append({
                "row": int(group_rows[0]["_row"]),
                "name": group_rows[0].get("Name", ""),
                "errors": [str(e)],
            })

    if dry_run:
        conn.rollback()
        result["dry_run"] = True
    else:
        conn.commit()
    return result


def _process_project_group(
    conn: sqlite3.Connection,
    base_number: str,
    group_rows: List[Dict[str, str]],
    result: Dict[str, Any],
) -> None:
    """Process a group of CSV rows sharing the same base project number."""

    # -- Parse names from primary row --
    primary = group_rows[0]
    proj_name, description, _ = parse_procore_name(primary.get("Name", ""))

    # -- Address fields --
    street = primary.get("Address", "")
    city = primary.get("City", "")
    state = _abbreviate_state(primary.get("State", ""))
    zip_code = primary.get("Zip", "")

    # -- Stage: pick most advanced across all rows in group --
    stages = [r.get("Stage", "") for r in group_rows if r.get("Stage", "")]
    stage = _resolve_stage(stages) if stages else "Proposal"

    # -- Project type from primary row --
    project_type = primary.get("Type", "") or None

    # -- Client name (from Name parsing — project_name IS the client) --
    client = proj_name

    # -- Upsert project --
    existing = conn.execute(
        "SELECT id FROM projects WHERE number = ?", (base_number,)
    ).fetchone()

    if existing:
        project_id = existing["id"]
        conn.execute(
            """
            UPDATE projects
            SET street=?, city=?, state=?, zip=?, stage=?,
                description=?, project_type=?,
                updated_at=CURRENT_TIMESTAMP
            WHERE id=?
            """,
            (street, city, state, zip_code, stage,
             description, project_type, project_id),
        )
        result["projects_updated"] += 1
        logger.debug("Updated project %s (id=%d)", base_number, project_id)
    else:
        cursor = conn.execute(
            """
            INSERT INTO projects (number, name, client, street, city, state,
                                  zip, stage, status, description, project_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)
            """,
            (base_number, proj_name, client, street, city, state,
             zip_code, stage, description, project_type),
        )
        project_id = cursor.lastrowid
        result["projects_created"] += 1
        logger.debug("Created project %s (id=%d)", base_number, project_id)

    # -- Process jobs for rows with BU codes --
    for row in group_rows:
        number = row["Project Number"]
        parsed = parse_job_code(number)
        if not parsed:
            continue

        _, bu_code, subjob = parsed

        # If no BU code from project number, try Department column
        if not bu_code:
            bu_code = _extract_bu_from_department(row.get("Department", ""))
        if not bu_code:
            continue  # Base-only row, no job to create

        if not subjob:
            subjob = "00"

        # Build full job number
        job_number = f"{base_number}-{bu_code}-{subjob}"

        # Scope name from parsed Name
        _, _, scope_name = parse_procore_name(row.get("Name", ""))
        if not scope_name:
            # Use full name as fallback
            scope_name = row.get("Name", "Unknown")

        # Look up BU
        bu_row = conn.execute(
            "SELECT id FROM business_units WHERE code = ?", (bu_code,)
        ).fetchone()
        if not bu_row:
            logger.warning(
                "BU code %s not found for job %s, skipping job",
                bu_code, job_number,
            )
            continue

        bu_id = bu_row["id"]

        # PM from Notes column (Procore doesn't have a dedicated PM field)
        pm = row.get("Notes", "") or None

        # Upsert job
        existing_job = conn.execute(
            "SELECT id FROM jobs WHERE job_number = ?", (job_number,)
        ).fetchone()

        if existing_job:
            job_id = existing_job["id"]
            conn.execute(
                """
                UPDATE jobs
                SET scope_name=?, pm=?, status='active',
                    updated_at=CURRENT_TIMESTAMP
                WHERE id=?
                """,
                (scope_name, pm, job_id),
            )
            result["jobs_updated"] += 1
        else:
            cursor = conn.execute(
                """
                INSERT INTO jobs (job_number, project_id, department_id,
                                  project_number, department_number, suffix,
                                  scope_name, pm, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active')
                """,
                (job_number, project_id, bu_id,
                 base_number, bu_code, subjob,
                 scope_name, pm),
            )
            job_id = cursor.lastrowid
            result["jobs_created"] += 1

        # Auto-create/link corresponding allocation
        existing_alloc = conn.execute(
            "SELECT id FROM project_allocations WHERE project_id=? AND business_unit_id=? AND subjob=?",
            (project_id, bu_id, subjob),
        ).fetchone()
        if existing_alloc:
            conn.execute(
                "UPDATE project_allocations SET job_id=?, scope_name=?, pm=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (job_id, scope_name, pm, existing_alloc["id"]),
            )
        else:
            conn.execute(
                """
                INSERT INTO project_allocations
                    (project_id, business_unit_id, subjob, job_code,
                     allocated_budget, weight_adjustment, job_id,
                     scope_name, pm, stage)
                VALUES (?, ?, ?, ?, 0, 1.0, ?, ?, ?,
                        (SELECT COALESCE(p.stage, 'Course of Construction')
                         FROM projects p WHERE p.id = ?))
                """,
                (project_id, bu_id, subjob, job_number,
                 job_id, scope_name, pm, project_id),
            )
