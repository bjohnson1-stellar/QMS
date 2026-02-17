"""
Project Directory Scanner

Scans project folders on disk, catalogs PDF drawings by discipline,
compares with database records, inserts new sheets, updates discipline
counts, and generates MANIFEST.json files.
"""

import hashlib
import json
import os
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from qms.core import get_db, get_logger, get_config_value, QMS_PATHS

logger = get_logger("qms.projects.scanner")

# Folders to skip when scanning for discipline subdirectories
_SKIP_FOLDERS = {"Specs", "Specifications"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_file_hash(filepath: str) -> str:
    """Calculate MD5 hash of a file."""
    md5_hash = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            md5_hash.update(chunk)
    return md5_hash.hexdigest()


def _get_page_count(filepath: str) -> Optional[int]:
    """Get page count from a PDF file. Returns None if fitz is unavailable."""
    try:
        import fitz  # PyMuPDF — optional dependency

        doc = fitz.open(filepath)
        count = len(doc)
        doc.close()
        return count
    except Exception as exc:
        logger.debug("Could not get page count for %s: %s", filepath, exc)
        return None


def parse_filename(filename: str) -> Dict[str, Any]:
    """
    Extract drawing number, title, and revision from a filename.

    Examples:
        R7002-REFRIGERATION-P&ID-Rev.E.pdf  ->  drawing_number=R7002-REFRIGERATION-P&ID, revision=E
        P-101_B.pdf                          ->  drawing_number=P-101, revision=B
        M01-Rev-A.pdf                        ->  drawing_number=M01, revision=A

    Returns:
        Dict with keys: drawing_number, title, revision, is_superseded
    """
    base = filename.rsplit(".", 1)[0]  # strip extension

    # Try to extract revision (Rev.X, Rev-X, _X where X is a single letter)
    revision = None
    revision_match = re.search(
        r"(?:Rev\.?-?|_)([A-Z])(?:-SUPERSEDED)?$", base, re.IGNORECASE
    )
    if revision_match:
        revision = revision_match.group(1).upper()
        base = re.sub(
            r"(?:Rev\.?-?|_)[A-Z](?:-SUPERSEDED)?$",
            "",
            base,
            flags=re.IGNORECASE,
        ).rstrip("-_")

    is_superseded = "SUPERSEDED" in filename.upper()

    return {
        "drawing_number": base,
        "title": base,
        "revision": revision or "A",
        "is_superseded": is_superseded,
    }


# ---------------------------------------------------------------------------
# Core scan
# ---------------------------------------------------------------------------


def scan_project(
    project_id: int, project_number: str, project_path: str
) -> Dict[str, Any]:
    """
    Scan a single project directory and return a catalogue of its contents.

    Walks each sub-directory (discipline folder) inside *project_path*,
    enumerates PDFs, parses filenames for drawing metadata, and calculates
    file hashes.

    Args:
        project_id:      Database primary key for the project.
        project_number:   Human-readable project number (e.g. '07308').
        project_path:     Absolute path to the project root folder.

    Returns:
        Dict containing disciplines, files list, and summary counts.
    """
    results: Dict[str, Any] = {
        "project_id": project_id,
        "project_number": project_number,
        "path": project_path,
        "disciplines": {},
        "files": [],
        "total_pdfs_on_disk": 0,
        "already_indexed": 0,
        "newly_indexed": 0,
        "missing_from_disk": 0,
        "supersession_chains": [],
    }

    if not os.path.isdir(project_path):
        logger.warning("Project path does not exist: %s", project_path)
        return results

    for item in sorted(os.listdir(project_path)):
        item_path = os.path.join(project_path, item)

        # Skip non-directories and special folders
        if not os.path.isdir(item_path):
            continue
        if item.startswith("_") or item.startswith("."):
            continue
        if item in _SKIP_FOLDERS or item == "MANIFEST.json":
            continue

        discipline_name = item

        # Enumerate PDFs inside discipline folder
        pdfs: List[Dict[str, str]] = []
        try:
            for pdf_file in sorted(os.listdir(item_path)):
                if pdf_file.lower().endswith(".pdf"):
                    full_path = os.path.join(item_path, pdf_file)
                    if os.path.isfile(full_path):
                        pdfs.append(
                            {
                                "filename": pdf_file,
                                "full_path": full_path,
                                "rel_path": os.path.join(discipline_name, pdf_file),
                            }
                        )
        except PermissionError:
            logger.warning("Permission denied scanning %s", item_path)
            continue

        # Parse each PDF into a file record
        discipline_files: List[Dict[str, Any]] = []
        for pdf_info in pdfs:
            parsed = parse_filename(pdf_info["filename"])
            file_size = os.path.getsize(pdf_info["full_path"])
            file_hash = _get_file_hash(pdf_info["full_path"])

            file_record: Dict[str, Any] = {
                "project_id": project_id,
                "discipline": discipline_name,
                "file_name": pdf_info["filename"],
                "file_path": pdf_info["rel_path"],
                "drawing_number": parsed["drawing_number"],
                "title": parsed["title"],
                "revision": parsed["revision"],
                "is_superseded": parsed["is_superseded"],
                "file_size": file_size,
                "file_hash": file_hash,
                "page_count": _get_page_count(pdf_info["full_path"]),
                "full_path": pdf_info["full_path"],
            }

            discipline_files.append(file_record)
            results["files"].append(file_record)
            results["total_pdfs_on_disk"] += 1

        if discipline_files:
            results["disciplines"][discipline_name] = {
                "total": len(discipline_files),
                "files": discipline_files,
            }

    logger.info(
        "Scanned %s: %d disciplines, %d PDFs",
        project_number,
        len(results["disciplines"]),
        results["total_pdfs_on_disk"],
    )
    return results


# ---------------------------------------------------------------------------
# Database comparison
# ---------------------------------------------------------------------------


def compare_with_database(
    conn: sqlite3.Connection, scan_results: Dict[str, Any]
) -> None:
    """
    Compare scanned files against existing database sheet records.

    Mutates *scan_results* in place, populating:
      - already_indexed, newly_indexed, missing_from_disk counts
      - newly_indexed_files  (list of file records needing insert)
      - missing_files        (list of DB records missing from disk)
      - per-file 'status' field ('indexed', 'modified', 'unindexed')

    Args:
        conn:          Open database connection (read-only is fine).
        scan_results:  Dict returned by :func:`scan_project`.
    """
    project_id = scan_results["project_id"]

    rows = conn.execute(
        "SELECT id, drawing_number, revision, file_path, file_hash, extracted_at "
        "FROM sheets WHERE project_id = ?",
        (project_id,),
    ).fetchall()
    db_sheets = {(r["drawing_number"], r["revision"]): dict(r) for r in rows}

    indexed_count = 0
    newly_indexed: List[Dict[str, Any]] = []
    missing_from_disk: List[Dict[str, Any]] = []

    for file_record in scan_results["files"]:
        key = (file_record["drawing_number"], file_record["revision"])
        if key in db_sheets:
            db_record = db_sheets[key]
            if db_record["file_hash"] == file_record["file_hash"]:
                indexed_count += 1
                file_record["status"] = "indexed"
            else:
                newly_indexed.append(file_record)
                file_record["status"] = "modified"
                logger.info(
                    "File modified: %s (hash changed)", file_record["file_name"]
                )
        else:
            newly_indexed.append(file_record)
            file_record["status"] = "unindexed"

    # Check for DB records no longer on disk
    disk_keys = {
        (f["drawing_number"], f["revision"]) for f in scan_results["files"]
    }
    for (drawing_number, revision), db_record in db_sheets.items():
        if (drawing_number, revision) not in disk_keys:
            missing_from_disk.append(
                {
                    "drawing_number": drawing_number,
                    "revision": revision,
                    "file_path": db_record["file_path"],
                    "extracted_at": db_record["extracted_at"],
                }
            )

    scan_results["already_indexed"] = indexed_count
    scan_results["newly_indexed"] = len(newly_indexed)
    scan_results["missing_from_disk"] = len(missing_from_disk)
    scan_results["newly_indexed_files"] = newly_indexed
    scan_results["missing_files"] = missing_from_disk


# ---------------------------------------------------------------------------
# Insert / update helpers
# ---------------------------------------------------------------------------


def insert_new_sheets(
    conn: sqlite3.Connection, scan_results: Dict[str, Any]
) -> int:
    """
    Insert newly discovered sheets into the database.

    Determines *is_current* by comparing against existing revisions for each
    drawing number.

    Args:
        conn:          Writable database connection.
        scan_results:  Dict populated by :func:`compare_with_database`.

    Returns:
        Number of rows inserted.
    """
    project_id = scan_results["project_id"]
    newly_indexed_files = scan_results.get("newly_indexed_files", [])
    if not newly_indexed_files:
        return 0

    # Build map of existing revisions per drawing_number
    rows = conn.execute(
        "SELECT drawing_number, revision FROM sheets "
        "WHERE project_id = ? ORDER BY drawing_number, revision",
        (project_id,),
    ).fetchall()

    existing_sheets: Dict[str, List[str]] = {}
    for row in rows:
        existing_sheets.setdefault(row["drawing_number"], []).append(
            row["revision"]
        )

    inserted_count = 0
    for file_record in newly_indexed_files:
        drawing_number = file_record["drawing_number"]
        revision = file_record["revision"]

        all_revisions = sorted(
            existing_sheets.get(drawing_number, []) + [revision]
        )
        is_current = 1 if revision == all_revisions[-1] else 0

        try:
            conn.execute(
                "INSERT OR IGNORE INTO sheets ("
                "  project_id, discipline, file_name, file_path,"
                "  drawing_number, title, revision, is_current,"
                "  file_hash, file_size, page_count"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    project_id,
                    file_record["discipline"],
                    file_record["file_name"],
                    file_record["file_path"],
                    drawing_number,
                    file_record["title"],
                    revision,
                    is_current,
                    file_record["file_hash"],
                    file_record["file_size"],
                    file_record["page_count"],
                ),
            )
            inserted_count += 1
        except sqlite3.IntegrityError as exc:
            logger.warning(
                "Could not insert %s: %s", file_record["file_name"], exc
            )

    conn.commit()
    logger.info("Inserted %d new sheet(s) for project %s", inserted_count, project_id)
    return inserted_count


def update_discipline_counts(
    conn: sqlite3.Connection, scan_results: Dict[str, Any]
) -> None:
    """
    Upsert discipline records with sheet / processed counts.

    Args:
        conn:          Writable database connection.
        scan_results:  Dict returned by :func:`scan_project`.
    """
    project_id = scan_results["project_id"]

    for discipline_name, discipline_data in scan_results["disciplines"].items():
        sheet_count = discipline_data["total"]

        row = conn.execute(
            "SELECT COUNT(*) AS cnt FROM sheets "
            "WHERE project_id = ? AND discipline = ? AND extracted_at IS NOT NULL",
            (project_id, discipline_name),
        ).fetchone()
        processed_count = row["cnt"]

        conn.execute(
            "INSERT OR REPLACE INTO disciplines ("
            "  project_id, name, folder_path, normalized_name,"
            "  sheet_count, processed_count"
            ") VALUES (?, ?, ?, ?, ?, ?)",
            (
                project_id,
                discipline_name,
                os.path.join(scan_results["path"], discipline_name),
                discipline_name,
                sheet_count,
                processed_count,
            ),
        )

    conn.commit()


# ---------------------------------------------------------------------------
# MANIFEST
# ---------------------------------------------------------------------------


def create_manifest(
    conn: sqlite3.Connection, scan_results: Dict[str, Any]
) -> str:
    """
    Write a MANIFEST.json file in the project directory.

    Args:
        conn:          Read-only database connection.
        scan_results:  Dict populated by a full scan cycle.

    Returns:
        Absolute path to the written MANIFEST.json file.
    """
    project_path = scan_results["path"]
    manifest_path = os.path.join(project_path, "MANIFEST.json")
    project_id = scan_results["project_id"]

    total_current = 0
    total_superseded = 0
    disciplines_manifest: Dict[str, Dict[str, int]] = {}

    for discipline_name, discipline_data in sorted(
        scan_results["disciplines"].items()
    ):
        current = conn.execute(
            "SELECT COUNT(*) AS cnt FROM sheets "
            "WHERE project_id = ? AND discipline = ? AND is_current = 1",
            (project_id, discipline_name),
        ).fetchone()["cnt"]

        superseded = conn.execute(
            "SELECT COUNT(*) AS cnt FROM sheets "
            "WHERE project_id = ? AND discipline = ? AND is_current = 0",
            (project_id, discipline_name),
        ).fetchone()["cnt"]

        extracted = conn.execute(
            "SELECT COUNT(*) AS cnt FROM sheets "
            "WHERE project_id = ? AND discipline = ? AND extracted_at IS NOT NULL",
            (project_id, discipline_name),
        ).fetchone()["cnt"]

        total_current += current
        total_superseded += superseded

        disciplines_manifest[discipline_name] = {
            "total": discipline_data["total"],
            "current": current,
            "superseded": superseded,
            "extracted": extracted,
        }

    folder_name = Path(project_path).name
    project_name = (
        folder_name.split("-", 1)[1] if "-" in folder_name else "Unknown"
    )

    manifest = {
        "project": scan_results["project_number"],
        "name": project_name,
        "scanned_at": datetime.utcnow().isoformat() + "Z",
        "disciplines": disciplines_manifest,
        "total_sheets": sum(
            d["total"] for d in scan_results["disciplines"].values()
        ),
        "total_current": total_current,
        "total_superseded": total_superseded,
    }

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    logger.info("Wrote MANIFEST.json -> %s", manifest_path)
    return manifest_path


# ---------------------------------------------------------------------------
# High-level orchestration
# ---------------------------------------------------------------------------


def scan_and_sync_project(
    project_id: int,
    project_number: str,
    project_path: str,
    *,
    write_manifest: bool = True,
) -> Dict[str, Any]:
    """
    Full scan-compare-insert-manifest cycle for a single project.

    This is the main entry point that CLI commands should call.

    Args:
        project_id:       Database primary key.
        project_number:    Human-readable number (e.g. '07308').
        project_path:      Absolute path to project root.
        write_manifest:    Whether to write MANIFEST.json on disk.

    Returns:
        Dict with scan results, insert counts, and manifest path.
    """
    scan_results = scan_project(project_id, project_number, project_path)

    with get_db() as conn:
        compare_with_database(conn, scan_results)
        inserted = insert_new_sheets(conn, scan_results)
        scan_results["inserted_count"] = inserted
        update_discipline_counts(conn, scan_results)

        if write_manifest and scan_results["disciplines"]:
            manifest_path = create_manifest(conn, scan_results)
            scan_results["manifest_path"] = manifest_path

    return scan_results


def scan_all_projects(
    *, write_manifest: bool = True
) -> List[Dict[str, Any]]:
    """
    Scan every project registered in the database.

    Reads the ``projects`` table and runs :func:`scan_and_sync_project` for
    each row that has a non-null ``path``.

    Args:
        write_manifest: Whether to write MANIFEST.json for each project.

    Returns:
        List of scan-result dicts (one per project).
    """
    with get_db(readonly=True) as conn:
        rows = conn.execute(
            "SELECT id, number, path FROM projects "
            "WHERE path IS NOT NULL ORDER BY number"
        ).fetchall()
        projects = [dict(r) for r in rows]

    all_results: List[Dict[str, Any]] = []
    for proj in projects:
        if not os.path.isdir(proj["path"]):
            logger.warning(
                "Skipping project %s — path not found: %s",
                proj["number"],
                proj["path"],
            )
            continue

        result = scan_and_sync_project(
            proj["id"],
            proj["number"],
            proj["path"],
            write_manifest=write_manifest,
        )
        all_results.append(result)

    return all_results


# ---------------------------------------------------------------------------
# Read-only queries
# ---------------------------------------------------------------------------


def list_projects(
    *, status: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Return all projects from the database.

    Args:
        status: Filter by project status (e.g. 'active'). None = all.

    Returns:
        List of project dicts.
    """
    with get_db(readonly=True) as conn:
        if status:
            rows = conn.execute(
                "SELECT id, number, name, client, path, status, pm "
                "FROM projects WHERE status = ? ORDER BY number",
                (status,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, number, name, client, path, status, pm "
                "FROM projects ORDER BY number"
            ).fetchall()

    return [dict(r) for r in rows]


def get_project(project_number: str) -> Optional[Dict[str, Any]]:
    """
    Look up a single project by its number.

    Args:
        project_number: The project number (e.g. '07308').

    Returns:
        Project dict or None if not found.
    """
    with get_db(readonly=True) as conn:
        row = conn.execute(
            "SELECT * FROM projects WHERE number = ?", (project_number,)
        ).fetchone()
    return dict(row) if row else None


def get_project_summary(project_number: str) -> Optional[Dict[str, Any]]:
    """
    Build a summary dict for a project including discipline stats.

    Args:
        project_number: The project number.

    Returns:
        Summary dict with project info and discipline breakdown, or None.
    """
    with get_db(readonly=True) as conn:
        proj_row = conn.execute(
            "SELECT * FROM projects WHERE number = ?", (project_number,)
        ).fetchone()

        if not proj_row:
            return None

        project = dict(proj_row)
        project_id = project["id"]

        # Total sheets
        total = conn.execute(
            "SELECT COUNT(*) AS cnt FROM sheets WHERE project_id = ?",
            (project_id,),
        ).fetchone()["cnt"]

        # Processed (extracted)
        processed = conn.execute(
            "SELECT COUNT(*) AS cnt FROM sheets "
            "WHERE project_id = ? AND extracted_at IS NOT NULL",
            (project_id,),
        ).fetchone()["cnt"]

        # Discipline breakdown
        disc_rows = conn.execute(
            "SELECT name, sheet_count, processed_count "
            "FROM disciplines WHERE project_id = ? ORDER BY name",
            (project_id,),
        ).fetchall()
        disciplines = [dict(r) for r in disc_rows]

        # Open flags
        open_flags = conn.execute(
            "SELECT COUNT(*) AS cnt FROM project_flags "
            "WHERE project_id = ? AND resolved = 0",
            (project_id,),
        ).fetchone()["cnt"]

    return {
        "id": project_id,
        "number": project["number"],
        "name": project["name"],
        "client": project.get("client"),
        "path": project.get("path"),
        "status": project.get("status"),
        "pm": project.get("pm"),  # deprecated; PM is per-job now
        "total_sheets": total,
        "processed": processed,
        "open_flags": open_flags,
        "disciplines": disciplines,
    }
