"""
One-time migration from Time Tracker database into QMS.

Reads from the standalone time_tracker.db and maps data into
quality.db tables (business_units, projects, project_budgets,
project_transactions, budget_settings, projection tables).

Usage:
    qms projects migrate-timetracker "D:\\Time Tracker\\time_tracker.db"
"""

import sqlite3
from typing import Any, Dict, List

from qms.core import get_db, get_logger

logger = get_logger("qms.projects.migrate_timetracker")

# Time Tracker status -> QMS stage mapping
STATUS_TO_STAGE = {
    "Active": "Course of Construction",
    "On Hold": "Pre-Construction",
    "Completed": "Post-Construction",
}


def migrate(source_db_path: str) -> Dict[str, Any]:
    """
    Run the full migration from Time Tracker to QMS.

    Args:
        source_db_path: Path to time_tracker.db

    Returns:
        Dict with migration statistics
    """
    stats: Dict[str, Any] = {
        "business_units_migrated": 0,
        "projects_matched": 0,
        "projects_created": 0,
        "budgets_created": 0,
        "allocations_created": 0,
        "transactions_migrated": 0,
        "settings_migrated": False,
        "periods_migrated": 0,
        "snapshots_migrated": 0,
        "errors": [],
    }

    # Open source read-only
    src = sqlite3.connect(source_db_path)
    src.row_factory = sqlite3.Row

    with get_db() as dest:
        _migrate_business_units(src, dest, stats)
        id_map = _migrate_projects(src, dest, stats)
        _migrate_transactions(src, dest, id_map, stats)
        _migrate_settings(src, dest, stats)
        _migrate_projections(src, dest, id_map, stats)
        dest.commit()

    src.close()
    logger.info("Migration complete: %s", stats)
    return stats


def _migrate_business_units(
    src: sqlite3.Connection, dest: sqlite3.Connection, stats: Dict[str, Any]
) -> None:
    """Copy business_units from TT into QMS (skip duplicates by code)."""
    try:
        rows = src.execute("SELECT * FROM business_units").fetchall()
    except sqlite3.OperationalError:
        logger.warning("No business_units table in source DB")
        return

    for row in rows:
        code = row["code"]
        existing = dest.execute(
            "SELECT id FROM business_units WHERE code = ?", (code,)
        ).fetchone()
        if existing:
            continue
        try:
            dest.execute(
                """INSERT INTO business_units (code, name, description)
                   VALUES (?, ?, ?)""",
                (code, row["name"], row["description"]),
            )
            stats["business_units_migrated"] += 1
        except Exception as exc:
            stats["errors"].append(f"BU {code}: {exc}")


def _extract_base_number(code: str) -> str:
    """
    Extract the 5-digit base project number from a TT code.

    TT codes use NNNNN-CCC-SS format (e.g. 07600-600-00).
    QMS stores just the base NNNNN (e.g. 07600).
    Falls back to the full code if no dash is found.
    """
    return code.split("-")[0] if "-" in code else code


def _migrate_projects(
    src: sqlite3.Connection, dest: sqlite3.Connection, stats: Dict[str, Any]
) -> Dict[int, int]:
    """
    Migrate projects. Returns mapping: TT project_id -> QMS project_id.

    Matching strategy: extract 5-digit base from TT code (NNNNN-CCC-SS -> NNNNN)
    and match against QMS projects.number. Multiple TT entries sharing a base
    number map to the same QMS project; their budgets are summed.
    """
    id_map: Dict[int, int] = {}

    try:
        tt_projects = src.execute("SELECT * FROM projects").fetchall()
    except sqlite3.OperationalError:
        logger.warning("No projects table in source DB")
        return id_map

    for proj in tt_projects:
        tt_id = proj["id"]
        code = proj["code"] if "code" in proj.keys() else proj.get("project_number", "")
        base_number = _extract_base_number(code)
        name = proj["name"] if "name" in proj.keys() else ""
        tt_status = proj["status"] if "status" in proj.keys() else "Active"
        stage = STATUS_TO_STAGE.get(tt_status, "Proposal")

        logger.info("Mapping TT %s (base %s) -> QMS", code, base_number)

        # Try to find existing QMS project by base number
        qms_proj = dest.execute(
            "SELECT id FROM projects WHERE number = ?", (base_number,)
        ).fetchone()

        if qms_proj:
            qms_id = qms_proj["id"]
            stats["projects_matched"] += 1
            # Update stage only if it's still the default 'Proposal'
            dest.execute(
                """UPDATE projects SET
                       stage = CASE WHEN stage = 'Proposal' THEN ? ELSE stage END,
                       start_date = COALESCE(start_date, ?),
                       end_date = COALESCE(end_date, ?),
                       notes = COALESCE(notes, ?)
                   WHERE id = ?""",
                (
                    stage,
                    _get_field(proj, "start_date"),
                    _get_field(proj, "end_date"),
                    _get_field(proj, "notes"),
                    qms_id,
                ),
            )
        else:
            # Create new project using base number
            manager = _get_field(proj, "manager")
            client = _get_field(proj, "owner_name")
            try:
                cursor = dest.execute(
                    """INSERT INTO projects (name, number, client, pm, stage,
                           start_date, end_date, notes)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        name,
                        base_number,
                        client,
                        manager,
                        stage,
                        _get_field(proj, "start_date"),
                        _get_field(proj, "end_date"),
                        _get_field(proj, "notes"),
                    ),
                )
                qms_id = cursor.lastrowid
                stats["projects_created"] += 1
            except Exception as exc:
                stats["errors"].append(f"Project {code}: {exc}")
                continue

        id_map[tt_id] = qms_id

        # Create or accumulate budget record
        total_budget = float(_get_field(proj, "total_budget") or 0)
        weight_adj = float(_get_field(proj, "weight_adjustment") or 1.0)

        existing_budget = dest.execute(
            "SELECT id, total_budget FROM project_budgets WHERE project_id = ?",
            (qms_id,),
        ).fetchone()

        if existing_budget:
            # Another TT entry shares this base number — sum budgets
            new_total = existing_budget["total_budget"] + total_budget
            dest.execute(
                "UPDATE project_budgets SET total_budget = ? WHERE id = ?",
                (new_total, existing_budget["id"]),
            )
            logger.info(
                "  Budget for %s: added %.0f (now %.0f) from TT %s",
                base_number, total_budget, new_total, code,
            )
        else:
            dest.execute(
                """INSERT INTO project_budgets (project_id, total_budget, weight_adjustment)
                   VALUES (?, ?, ?)""",
                (qms_id, total_budget, weight_adj),
            )
            stats["budgets_created"] += 1

        # Create per-BU allocation from full TT code
        parts = code.split("-")
        if len(parts) >= 3:
            bu_code = parts[1]
            subjob = parts[2]
            bu_row = dest.execute(
                "SELECT id FROM business_units WHERE code = ?", (bu_code,)
            ).fetchone()
            if bu_row:
                try:
                    dest.execute(
                        """INSERT OR IGNORE INTO project_allocations
                           (project_id, business_unit_id, subjob, job_code,
                            allocated_budget, weight_adjustment)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (qms_id, bu_row["id"], subjob, code,
                         total_budget, weight_adj),
                    )
                    stats["allocations_created"] += 1
                except Exception as exc:
                    stats["errors"].append(f"Allocation {code}: {exc}")

    return id_map


def _migrate_transactions(
    src: sqlite3.Connection,
    dest: sqlite3.Connection,
    id_map: Dict[int, int],
    stats: Dict[str, Any],
) -> None:
    """Migrate transactions from TT to QMS project_transactions."""
    try:
        txns = src.execute("SELECT * FROM transactions").fetchall()
    except sqlite3.OperationalError:
        logger.warning("No transactions table in source DB")
        return

    for txn in txns:
        tt_pid = txn["project_id"]
        qms_pid = id_map.get(tt_pid)
        if not qms_pid:
            stats["errors"].append(
                f"Transaction {txn['id']}: unmapped project_id {tt_pid}"
            )
            continue

        try:
            dest.execute(
                """INSERT INTO project_transactions
                       (project_id, transaction_date, transaction_type,
                        description, amount, hours, rate, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    qms_pid,
                    txn["transaction_date"],
                    txn["transaction_type"],
                    txn["description"],
                    float(txn["amount"]),
                    float(txn["hours"]) if txn["hours"] else None,
                    float(txn["rate"]) if txn["rate"] else None,
                    _get_field(txn, "notes"),
                ),
            )
            stats["transactions_migrated"] += 1
        except Exception as exc:
            stats["errors"].append(f"Transaction {txn['id']}: {exc}")


def _migrate_settings(
    src: sqlite3.Connection, dest: sqlite3.Connection, stats: Dict[str, Any]
) -> None:
    """Migrate settings singleton."""
    try:
        row = src.execute("SELECT * FROM settings WHERE id = 1").fetchone()
    except sqlite3.OperationalError:
        return

    if not row:
        return

    existing = dest.execute("SELECT id FROM budget_settings WHERE id = 1").fetchone()
    if existing:
        return  # Don't overwrite existing QMS settings

    dest.execute(
        """INSERT OR IGNORE INTO budget_settings
               (id, company_name, default_hourly_rate,
                working_hours_per_month, fiscal_year_start_month)
           VALUES (1, ?, ?, ?, ?)""",
        (
            _get_field(row, "company_name") or "My Company",
            float(_get_field(row, "default_hourly_rate") or 150.0),
            int(_get_field(row, "working_hours_per_month") or 176),
            int(_get_field(row, "fiscal_year_start_month") or 1),
        ),
    )
    stats["settings_migrated"] = True


def _migrate_projections(
    src: sqlite3.Connection,
    dest: sqlite3.Connection,
    id_map: Dict[int, int],
    stats: Dict[str, Any],
) -> None:
    """Migrate projection periods, snapshots, and entries."""
    # Periods
    try:
        periods = src.execute("SELECT * FROM projection_periods").fetchall()
    except sqlite3.OperationalError:
        return

    period_map: Dict[int, int] = {}

    for p in periods:
        tt_pid = p["id"]
        year = p["year"]
        month = p["month"]

        existing = dest.execute(
            "SELECT id FROM projection_periods WHERE year = ? AND month = ?",
            (year, month),
        ).fetchone()

        if existing:
            period_map[tt_pid] = existing["id"]
        else:
            cursor = dest.execute(
                """INSERT INTO projection_periods
                       (year, month, working_days, total_hours, is_locked)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    year,
                    month,
                    p["working_days"],
                    p["total_hours"],
                    p["is_locked"],
                ),
            )
            period_map[tt_pid] = cursor.lastrowid
            stats["periods_migrated"] += 1

    # Snapshots
    try:
        snapshots = src.execute("SELECT * FROM projection_snapshots").fetchall()
    except sqlite3.OperationalError:
        return

    snapshot_map: Dict[int, int] = {}

    for s in snapshots:
        tt_sid = s["id"]
        qms_period_id = period_map.get(s["period_id"])
        if not qms_period_id:
            continue

        cursor = dest.execute(
            """INSERT INTO projection_snapshots
                   (period_id, version, name, description, hourly_rate,
                    total_hours, total_projected_cost, status, is_active,
                    finalized_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                qms_period_id,
                s["version"],
                _get_field(s, "name"),
                _get_field(s, "description"),
                float(s["hourly_rate"]),
                int(s["total_hours"]),
                float(s["total_projected_cost"]),
                s["status"],
                s["is_active"],
                _get_field(s, "finalized_at"),
            ),
        )
        snapshot_map[tt_sid] = cursor.lastrowid
        stats["snapshots_migrated"] += 1

    # Entries
    try:
        entries = src.execute("SELECT * FROM projection_entries").fetchall()
    except sqlite3.OperationalError:
        return

    for e in entries:
        qms_snap_id = snapshot_map.get(e["snapshot_id"])
        qms_proj_id = id_map.get(e["project_id"])
        if not qms_snap_id or not qms_proj_id:
            continue

        try:
            dest.execute(
                """INSERT INTO projection_entries
                       (snapshot_id, project_id, allocated_hours,
                        projected_cost, weight_used, remaining_budget_at_time, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    qms_snap_id,
                    qms_proj_id,
                    float(e["allocated_hours"]),
                    float(e["projected_cost"]),
                    float(e["weight_used"]) if e["weight_used"] else None,
                    (
                        float(e["remaining_budget_at_time"])
                        if e["remaining_budget_at_time"]
                        else None
                    ),
                    _get_field(e, "notes"),
                ),
            )
        except Exception as exc:
            stats["errors"].append(f"Projection entry: {exc}")


def _get_field(row: sqlite3.Row, field: str) -> Any:
    """Safely get a field from a Row, returning None if missing."""
    try:
        return row[field]
    except (IndexError, KeyError):
        return None
