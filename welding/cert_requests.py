"""
Weld Certification Request Processing

Handles the full lifecycle of welder certification test requests:
  request → approval → testing → results → WPQ assignment

JSON intake from Power Automate, status tracking, coupon-level results,
WPQ creation from passed coupons, and retest scheduling for failed ones.
"""

import json
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from qms.core import get_db, get_logger
from qms.core.config import get_config_value

logger = get_logger("qms.welding.cert_requests")

# Valid status transitions for WCR
VALID_STATUSES = {
    "pending_approval", "approved", "testing",
    "results_received", "completed", "cancelled",
}

# Valid coupon statuses
VALID_COUPON_STATUSES = {
    "pending", "testing", "passed", "failed",
    "wpq_assigned", "retest_scheduled",
}

VALID_PROCESSES = {"SMAW", "GTAW", "GMAW", "FCAW", "SAW", "GTAW/SMAW"}


# ---------------------------------------------------------------------------
# WCR Number Generation
# ---------------------------------------------------------------------------

def get_next_wcr_number(conn: sqlite3.Connection) -> str:
    """Generate the next WCR number in format WCR-YYYY-NNNN."""
    prefix = get_config_value("welding", "cert_requests", "wcr_prefix", default="WCR")
    year = date.today().year

    row = conn.execute(
        "SELECT wcr_number FROM weld_cert_requests "
        "WHERE wcr_number LIKE ? ORDER BY wcr_number DESC LIMIT 1",
        (f"{prefix}-{year}-%",),
    ).fetchone()

    if row:
        try:
            last_seq = int(row["wcr_number"].split("-")[-1])
            next_seq = last_seq + 1
        except (ValueError, IndexError):
            next_seq = 1
    else:
        next_seq = 1

    return f"{prefix}-{year}-{next_seq:04d}"


# ---------------------------------------------------------------------------
# JSON Validation
# ---------------------------------------------------------------------------

def validate_cert_request_json(data: Dict[str, Any]) -> List[str]:
    """
    Validate the structure of a cert request JSON payload.

    Expected structure:
    {
        "type": "weld_cert_request",
        "welder": {
            "employee_number": "12345",
            "name": "John Doe",
            "stamp": "Z-15",          // optional
            "is_new": false            // optional
        },
        "project": {
            "number": "07645",
            "name": "Test Project"
        },
        "coupons": [
            {
                "process": "SMAW",
                "position": "6G",
                "wps_number": "WPS-001",
                "base_material": "A106",
                "filler_metal": "7018",
                "thickness": "3/4\"",
                "diameter": "6\""
            }
        ],
        "submitted_by": "Jane Smith",
        "request_date": "2026-02-11",
        "notes": "..."
    }

    Returns:
        List of error messages (empty = valid)
    """
    errors: List[str] = []

    # Welder section
    welder = data.get("welder")
    if not welder or not isinstance(welder, dict):
        errors.append("Missing or invalid 'welder' section")
    else:
        if not welder.get("employee_number") and not welder.get("stamp"):
            errors.append("Welder must have 'employee_number' or 'stamp'")
        if not welder.get("name"):
            errors.append("Welder 'name' is required")

    # Coupons
    coupons = data.get("coupons")
    if not coupons or not isinstance(coupons, list):
        errors.append("Missing or empty 'coupons' list")
    else:
        max_coupons = get_config_value(
            "welding", "cert_requests", "max_coupons_per_request", default=4
        )
        if len(coupons) > max_coupons:
            errors.append(f"Too many coupons ({len(coupons)}), max is {max_coupons}")

        for i, coupon in enumerate(coupons, 1):
            if not isinstance(coupon, dict):
                errors.append(f"Coupon {i}: must be a dict")
                continue
            if not coupon.get("process"):
                errors.append(f"Coupon {i}: 'process' is required")
            elif coupon["process"].upper() not in VALID_PROCESSES:
                errors.append(
                    f"Coupon {i}: invalid process '{coupon['process']}'. "
                    f"Valid: {', '.join(sorted(VALID_PROCESSES))}"
                )

    return errors


# ---------------------------------------------------------------------------
# Welder Lookup / Registration
# ---------------------------------------------------------------------------

def _lookup_or_register_welder(
    conn: sqlite3.Connection, welder_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Look up a welder by employee_number or stamp. If is_new=true and not found,
    register via registration.register_new_welder().

    Returns:
        Dict with: welder_id, stamp, was_created, errors
    """
    result: Dict[str, Any] = {
        "welder_id": None,
        "stamp": None,
        "was_created": False,
        "errors": [],
    }

    emp_num = welder_data.get("employee_number", "").strip()
    stamp = welder_data.get("stamp", "").strip()
    is_new = welder_data.get("is_new", False)

    # Try lookup by employee number first
    row = None
    if emp_num:
        row = conn.execute(
            "SELECT id, welder_stamp FROM weld_welder_registry WHERE employee_number = ?",
            (emp_num,),
        ).fetchone()

    # Try by stamp if not found
    if not row and stamp:
        row = conn.execute(
            "SELECT id, welder_stamp FROM weld_welder_registry WHERE welder_stamp = ?",
            (stamp,),
        ).fetchone()

    if row:
        result["welder_id"] = row["id"]
        result["stamp"] = row["welder_stamp"]
        return result

    # Not found — register if is_new
    if is_new and emp_num:
        from qms.welding.registration import register_new_welder

        name_parts = welder_data.get("name", "").strip().split(None, 1)
        first = name_parts[0] if name_parts else "Unknown"
        last = name_parts[1] if len(name_parts) > 1 else "Unknown"

        reg_result = register_new_welder(
            conn,
            employee_number=emp_num,
            first_name=first,
            last_name=last,
            stamp=stamp or None,
            auto_stamp=not bool(stamp),
        )

        if reg_result["errors"]:
            result["errors"] = reg_result["errors"]
        else:
            result["welder_id"] = reg_result["id"]
            result["stamp"] = reg_result["stamp"]
            result["was_created"] = True
    else:
        identifier = emp_num or stamp or "unknown"
        result["errors"].append(f"Welder not found: {identifier}")

    return result


# ---------------------------------------------------------------------------
# JSON Intake
# ---------------------------------------------------------------------------

def process_cert_request(json_path: Path) -> Dict[str, Any]:
    """
    Full intake pipeline for a cert request JSON file.

    Parse → validate → lookup/register welder → generate WCR# →
    insert weld_cert_requests + weld_cert_request_coupons rows.

    Returns:
        Dict with: wcr_number, welder_id, welder_stamp, coupon_count,
                    welder_created, status, summary, errors
    """
    result: Dict[str, Any] = {
        "wcr_number": None,
        "welder_id": None,
        "welder_stamp": None,
        "coupon_count": 0,
        "welder_created": False,
        "status": "pending_approval",
        "summary": None,
        "errors": [],
    }

    # Parse JSON
    raw_text = json_path.read_text(encoding="utf-8")
    data = json.loads(raw_text)

    # Validate
    validation_errors = validate_cert_request_json(data)
    if validation_errors:
        result["errors"] = validation_errors
        result["status"] = "failed"
        result["summary"] = f"Validation failed: {len(validation_errors)} error(s)"
        return result

    with get_db() as conn:
        # Lookup/register welder
        welder_data = data["welder"]
        welder_result = _lookup_or_register_welder(conn, welder_data)
        if welder_result["errors"]:
            result["errors"] = welder_result["errors"]
            result["status"] = "failed"
            result["summary"] = "Welder lookup/registration failed"
            return result

        result["welder_id"] = welder_result["welder_id"]
        result["welder_stamp"] = welder_result["stamp"]
        result["welder_created"] = welder_result["was_created"]

        # Generate WCR number
        wcr_number = get_next_wcr_number(conn)
        result["wcr_number"] = wcr_number

        # Insert WCR
        project = data.get("project", {})
        conn.execute(
            """INSERT INTO weld_cert_requests (
                   wcr_number, welder_id, employee_number, welder_name,
                   welder_stamp, project_number, project_name,
                   request_date, submitted_by, submitted_at,
                   status, is_new_welder, notes, source_file
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                wcr_number,
                welder_result["welder_id"],
                welder_data.get("employee_number"),
                welder_data.get("name"),
                welder_result["stamp"],
                project.get("number"),
                project.get("name"),
                data.get("request_date", date.today().isoformat()),
                data.get("submitted_by"),
                datetime.now().isoformat(),
                "pending_approval",
                1 if welder_data.get("is_new") else 0,
                data.get("notes"),
                json_path.name,
            ),
        )
        wcr_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Insert coupons
        coupons = data.get("coupons", [])
        for i, coupon in enumerate(coupons, 1):
            conn.execute(
                """INSERT INTO weld_cert_request_coupons (
                       wcr_id, coupon_number, process, position,
                       wps_number, base_material, filler_metal,
                       thickness, diameter, status
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')""",
                (
                    wcr_id,
                    i,
                    coupon.get("process", "").upper(),
                    coupon.get("position"),
                    coupon.get("wps_number"),
                    coupon.get("base_material"),
                    coupon.get("filler_metal"),
                    coupon.get("thickness"),
                    coupon.get("diameter"),
                ),
            )
        conn.commit()

        result["coupon_count"] = len(coupons)
        result["summary"] = (
            f"Created {wcr_number}: {welder_data.get('name')} "
            f"({len(coupons)} coupon(s))"
        )

    logger.info("Processed cert request: %s", result["summary"])
    return result


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------

def list_cert_requests(
    status: Optional[str] = None,
    project: Optional[str] = None,
    welder: Optional[str] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """List cert requests with optional filters."""
    query = """
        SELECT wcr.*, COUNT(c.id) as coupon_count
        FROM weld_cert_requests wcr
        LEFT JOIN weld_cert_request_coupons c ON c.wcr_id = wcr.id
        WHERE 1=1
    """
    params: List[Any] = []

    if status:
        query += " AND wcr.status = ?"
        params.append(status)
    if project:
        query += " AND wcr.project_number LIKE ?"
        params.append(f"%{project}%")
    if welder:
        query += " AND (wcr.welder_name LIKE ? OR wcr.welder_stamp LIKE ? OR wcr.employee_number LIKE ?)"
        params.extend([f"%{welder}%"] * 3)

    query += " GROUP BY wcr.id ORDER BY wcr.created_at DESC LIMIT ?"
    params.append(limit)

    with get_db(readonly=True) as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def get_cert_request_detail(wcr_number: str) -> Optional[Dict[str, Any]]:
    """Get full cert request detail including coupons."""
    with get_db(readonly=True) as conn:
        wcr = conn.execute(
            "SELECT * FROM weld_cert_requests WHERE wcr_number = ?",
            (wcr_number,),
        ).fetchone()

        if not wcr:
            return None

        result = dict(wcr)
        coupons = conn.execute(
            "SELECT * FROM weld_cert_request_coupons WHERE wcr_id = ? ORDER BY coupon_number",
            (wcr["id"],),
        ).fetchall()
        result["coupons"] = [dict(c) for c in coupons]

        return result


# ---------------------------------------------------------------------------
# Results Entry
# ---------------------------------------------------------------------------

def enter_coupon_result(
    wcr_number: str,
    coupon_number: int,
    result: str,
    test_date: Optional[str] = None,
    tested_by: Optional[str] = None,
    visual_result: Optional[str] = None,
    bend_result: Optional[str] = None,
    rt_result: Optional[str] = None,
    failure_reason: Optional[str] = None,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Enter test results for a specific coupon.

    Args:
        wcr_number: WCR number (e.g. WCR-2026-0001)
        coupon_number: Coupon number (1-4)
        result: "pass" or "fail"
        test_date: Date of test (defaults to today)
        tested_by: Name of tester

    Returns:
        Dict with: wcr_number, coupon_number, status, wcr_status, errors
    """
    output: Dict[str, Any] = {
        "wcr_number": wcr_number,
        "coupon_number": coupon_number,
        "status": None,
        "wcr_status": None,
        "errors": [],
    }

    if result not in ("pass", "fail"):
        output["errors"].append(f"Result must be 'pass' or 'fail', got '{result}'")
        return output

    with get_db() as conn:
        # Verify WCR exists and is in a valid state
        wcr = conn.execute(
            "SELECT id, status FROM weld_cert_requests WHERE wcr_number = ?",
            (wcr_number,),
        ).fetchone()

        if not wcr:
            output["errors"].append(f"WCR not found: {wcr_number}")
            return output

        if wcr["status"] not in ("approved", "testing", "results_received"):
            output["errors"].append(
                f"WCR {wcr_number} is '{wcr['status']}', must be approved/testing/results_received"
            )
            return output

        # Verify coupon exists and is pending/testing
        coupon = conn.execute(
            "SELECT id, status FROM weld_cert_request_coupons "
            "WHERE wcr_id = ? AND coupon_number = ?",
            (wcr["id"], coupon_number),
        ).fetchone()

        if not coupon:
            output["errors"].append(f"Coupon {coupon_number} not found on {wcr_number}")
            return output

        if coupon["status"] not in ("pending", "testing"):
            output["errors"].append(
                f"Coupon {coupon_number} is '{coupon['status']}', cannot enter results"
            )
            return output

        # Update coupon
        new_status = "passed" if result == "pass" else "failed"
        tested_at = test_date or date.today().isoformat()

        conn.execute(
            """UPDATE weld_cert_request_coupons
               SET test_result = ?, status = ?, tested_at = ?, tested_by = ?,
                   visual_result = ?, bend_result = ?, rt_result = ?,
                   failure_reason = ?, notes = ?,
                   updated_at = datetime('now')
               WHERE id = ?""",
            (
                result, new_status, tested_at, tested_by,
                visual_result, bend_result, rt_result,
                failure_reason, notes,
                coupon["id"],
            ),
        )

        # Update WCR status
        wcr_status = _update_wcr_status(conn, wcr["id"])
        conn.commit()

        output["status"] = new_status
        output["wcr_status"] = wcr_status

    logger.info(
        "Coupon result: %s #%d = %s (WCR status: %s)",
        wcr_number, coupon_number, result, output["wcr_status"],
    )
    return output


# ---------------------------------------------------------------------------
# WPQ Assignment
# ---------------------------------------------------------------------------

def assign_wpq_from_coupon(
    wcr_number: str,
    coupon_number: int,
    expiration_months: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Create a WPQ record from a passed coupon.

    Args:
        wcr_number: WCR number
        coupon_number: Coupon number
        expiration_months: Months until expiration (default from config)

    Returns:
        Dict with: wpq_id, wpq_number, expiration_date, errors
    """
    output: Dict[str, Any] = {
        "wpq_id": None,
        "wpq_number": None,
        "expiration_date": None,
        "errors": [],
    }

    if expiration_months is None:
        expiration_months = get_config_value(
            "welding", "cert_requests", "default_wpq_expiration_months", default=6
        )

    with get_db() as conn:
        # Get WCR and coupon
        wcr = conn.execute(
            "SELECT * FROM weld_cert_requests WHERE wcr_number = ?",
            (wcr_number,),
        ).fetchone()

        if not wcr:
            output["errors"].append(f"WCR not found: {wcr_number}")
            return output

        coupon = conn.execute(
            "SELECT * FROM weld_cert_request_coupons "
            "WHERE wcr_id = ? AND coupon_number = ?",
            (wcr["id"], coupon_number),
        ).fetchone()

        if not coupon:
            output["errors"].append(f"Coupon {coupon_number} not found on {wcr_number}")
            return output

        if coupon["status"] != "passed":
            output["errors"].append(
                f"Coupon {coupon_number} is '{coupon['status']}', must be 'passed'"
            )
            return output

        # Build WPQ
        stamp = wcr["welder_stamp"] or "UNKNOWN"
        process = coupon["process"] or "UNKNOWN"
        test_dt_str = coupon["tested_at"] or date.today().isoformat()
        try:
            test_dt = date.fromisoformat(test_dt_str[:10])
        except ValueError:
            test_dt = date.today()
        expiration_dt = test_dt + timedelta(days=expiration_months * 30)

        coupon_wps = coupon["wps_number"]
        if coupon_wps:
            wpq_number = f"{stamp}-{coupon_wps}"
            # Append sequence suffix if this WPQ already exists (re-qualification)
            existing_dup = conn.execute(
                "SELECT id FROM weld_wpq WHERE wpq_number = ?", (wpq_number,)
            ).fetchone()
            if existing_dup:
                seq = 2
                while True:
                    candidate = f"{wpq_number}-{seq}"
                    if not conn.execute(
                        "SELECT id FROM weld_wpq WHERE wpq_number = ?", (candidate,)
                    ).fetchone():
                        wpq_number = candidate
                        break
                    seq += 1
        else:
            wpq_number = f"{stamp}-{wcr_number}-C{coupon_number}-{process}"

        # Check uniqueness
        existing = conn.execute(
            "SELECT id FROM weld_wpq WHERE wpq_number = ?", (wpq_number,)
        ).fetchone()
        if existing:
            output["errors"].append(f"WPQ '{wpq_number}' already exists")
            return output

        cursor = conn.execute(
            """INSERT INTO weld_wpq (
                   wpq_number, welder_id, welder_stamp, wps_number,
                   process_type, p_number_base,
                   groove_positions_qualified, test_date,
                   initial_expiration_date, current_expiration_date,
                   status, notes
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?)""",
            (
                wpq_number,
                wcr["welder_id"],
                stamp,
                coupon["wps_number"],
                process,
                None,  # p_number determined from base_material lookup if needed
                coupon["position"],
                test_dt.isoformat(),
                expiration_dt.isoformat(),
                expiration_dt.isoformat(),
                f"Created from {wcr_number} coupon {coupon_number}",
            ),
        )
        wpq_id = cursor.lastrowid

        # Update coupon
        conn.execute(
            """UPDATE weld_cert_request_coupons
               SET wpq_id = ?, status = 'wpq_assigned', updated_at = datetime('now')
               WHERE id = ?""",
            (wpq_id, coupon["id"]),
        )

        # Recalculate WCR status
        _update_wcr_status(conn, wcr["id"])
        conn.commit()

        output["wpq_id"] = wpq_id
        output["wpq_number"] = wpq_number
        output["expiration_date"] = expiration_dt.isoformat()

    logger.info(
        "Assigned WPQ %s from %s coupon %d (expires: %s)",
        wpq_number, wcr_number, coupon_number, expiration_dt,
    )
    return output


# ---------------------------------------------------------------------------
# Retest Scheduling
# ---------------------------------------------------------------------------

def schedule_retest(
    wcr_number: str,
    coupon_number: int,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Schedule a retest for a failed coupon by creating a new WCR.

    Args:
        wcr_number: Original WCR number
        coupon_number: Failed coupon number

    Returns:
        Dict with: new_wcr_number, errors
    """
    output: Dict[str, Any] = {
        "new_wcr_number": None,
        "errors": [],
    }

    with get_db() as conn:
        wcr = conn.execute(
            "SELECT * FROM weld_cert_requests WHERE wcr_number = ?",
            (wcr_number,),
        ).fetchone()

        if not wcr:
            output["errors"].append(f"WCR not found: {wcr_number}")
            return output

        coupon = conn.execute(
            "SELECT * FROM weld_cert_request_coupons "
            "WHERE wcr_id = ? AND coupon_number = ?",
            (wcr["id"], coupon_number),
        ).fetchone()

        if not coupon:
            output["errors"].append(f"Coupon {coupon_number} not found on {wcr_number}")
            return output

        if coupon["status"] != "failed":
            output["errors"].append(
                f"Coupon {coupon_number} is '{coupon['status']}', must be 'failed'"
            )
            return output

        # Create new WCR with single coupon
        new_wcr_number = get_next_wcr_number(conn)

        conn.execute(
            """INSERT INTO weld_cert_requests (
                   wcr_number, welder_id, employee_number, welder_name,
                   welder_stamp, project_number, project_name,
                   request_date, submitted_by, submitted_at,
                   status, is_new_welder, notes
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending_approval', 0, ?)""",
            (
                new_wcr_number,
                wcr["welder_id"],
                wcr["employee_number"],
                wcr["welder_name"],
                wcr["welder_stamp"],
                wcr["project_number"],
                wcr["project_name"],
                date.today().isoformat(),
                "system",
                datetime.now().isoformat(),
                f"Retest of {wcr_number} coupon {coupon_number}"
                + (f". {notes}" if notes else ""),
            ),
        )
        new_wcr_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Copy coupon data
        conn.execute(
            """INSERT INTO weld_cert_request_coupons (
                   wcr_id, coupon_number, process, position,
                   wps_number, base_material, filler_metal,
                   thickness, diameter, status
               ) VALUES (?, 1, ?, ?, ?, ?, ?, ?, ?, 'pending')""",
            (
                new_wcr_id,
                coupon["process"],
                coupon["position"],
                coupon["wps_number"],
                coupon["base_material"],
                coupon["filler_metal"],
                coupon["thickness"],
                coupon["diameter"],
            ),
        )

        # Mark original coupon as retest_scheduled
        conn.execute(
            """UPDATE weld_cert_request_coupons
               SET retest_wcr_id = ?, status = 'retest_scheduled',
                   updated_at = datetime('now')
               WHERE id = ?""",
            (new_wcr_id, coupon["id"]),
        )

        _update_wcr_status(conn, wcr["id"])
        conn.commit()

        output["new_wcr_number"] = new_wcr_number

    logger.info(
        "Scheduled retest %s for %s coupon %d",
        new_wcr_number, wcr_number, coupon_number,
    )
    return output


# ---------------------------------------------------------------------------
# Status Engine
# ---------------------------------------------------------------------------

def _update_wcr_status(conn: sqlite3.Connection, wcr_id: int) -> str:
    """
    Recalculate WCR status based on coupon statuses.

    Rules:
      - All coupons passed/wpq_assigned → completed
      - Any coupon pending → testing (if WCR was approved)
      - Mix of results → results_received
      - All failed/retest_scheduled → results_received
    """
    coupons = conn.execute(
        "SELECT status FROM weld_cert_request_coupons WHERE wcr_id = ?",
        (wcr_id,),
    ).fetchall()

    if not coupons:
        return "pending_approval"

    statuses = {c["status"] for c in coupons}

    terminal = {"passed", "wpq_assigned"}
    if statuses <= terminal:
        new_status = "completed"
    elif statuses <= {"pending"}:
        # All pending — keep current status
        current = conn.execute(
            "SELECT status FROM weld_cert_requests WHERE id = ?", (wcr_id,)
        ).fetchone()
        return current["status"] if current else "pending_approval"
    elif "pending" in statuses or "testing" in statuses:
        new_status = "testing"
    else:
        new_status = "results_received"

    conn.execute(
        "UPDATE weld_cert_requests SET status = ?, updated_at = datetime('now') WHERE id = ?",
        (new_status, wcr_id),
    )
    return new_status


# ---------------------------------------------------------------------------
# Approval
# ---------------------------------------------------------------------------

def approve_cert_request(
    wcr_number: str,
    approved_by: str,
) -> Dict[str, Any]:
    """Approve a pending cert request."""
    output: Dict[str, Any] = {"wcr_number": wcr_number, "status": None, "errors": []}

    with get_db() as conn:
        wcr = conn.execute(
            "SELECT id, status FROM weld_cert_requests WHERE wcr_number = ?",
            (wcr_number,),
        ).fetchone()

        if not wcr:
            output["errors"].append(f"WCR not found: {wcr_number}")
            return output

        if wcr["status"] != "pending_approval":
            output["errors"].append(
                f"WCR is '{wcr['status']}', can only approve 'pending_approval'"
            )
            return output

        conn.execute(
            """UPDATE weld_cert_requests
               SET status = 'approved', approved_by = ?, approved_at = datetime('now'),
                   updated_at = datetime('now')
               WHERE id = ?""",
            (approved_by, wcr["id"]),
        )
        conn.commit()

        output["status"] = "approved"

    logger.info("Approved %s by %s", wcr_number, approved_by)
    return output


# ---------------------------------------------------------------------------
# Handler registration for automation dispatcher
# ---------------------------------------------------------------------------

def _handle_cert_request(json_path: Path) -> Dict[str, Any]:
    """Handler called by the automation dispatcher."""
    return process_cert_request(json_path)


try:
    from qms.automation.dispatcher import register_handler
    register_handler("weld_cert_request", _handle_cert_request, "welding")
except ImportError:
    pass
