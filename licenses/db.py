"""
State Licenses CRUD — pure Python, no Flask dependency.

Handles company contractor licenses and employee professional licenses.
"""

import base64
import hashlib
import json
import math
import mimetypes
import os
import sqlite3
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from cryptography.fernet import Fernet, InvalidToken


def generate_uuid() -> str:
    return str(uuid.uuid4())


def _audit(
    conn: sqlite3.Connection,
    entity_type: str,
    entity_id: str,
    action: str,
    old_values: Optional[Dict] = None,
    new_values: Optional[Dict] = None,
    changed_by: str = "system",
) -> None:
    """Insert an audit_log row for a license module mutation."""
    conn.execute(
        """INSERT INTO audit_log (entity_type, entity_id, action, changed_by, old_values, new_values)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            entity_type,
            entity_id,
            action,
            changed_by,
            json.dumps(old_values) if old_values else None,
            json.dumps(new_values) if new_values else None,
        ),
    )


# ---------------------------------------------------------------------------
# List / Get
# ---------------------------------------------------------------------------

def list_licenses(
    conn: sqlite3.Connection,
    *,
    holder_type: Optional[str] = None,
    state_code: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    page: int = 0,
    per_page: int = 0,
) -> Dict[str, Any]:
    """List licenses with optional filters, pagination, and days_until_expiry.

    Returns {items: [...], total, page, per_page, pages}.
    When per_page=0 (default), returns all rows with pages=1.
    """
    clauses = []
    params: list = []

    if holder_type:
        clauses.append("sl.holder_type = ?")
        params.append(holder_type)
    if state_code:
        clauses.append("sl.state_code = ?")
        params.append(state_code)
    if status:
        clauses.append("sl.status = ?")
        params.append(status)
    if search:
        clauses.append(
            "(sl.holder_name LIKE ? OR sl.business_entity LIKE ? "
            "OR sl.license_number LIKE ? "
            "OR sl.license_type LIKE ? OR sl.state_code LIKE ?)"
        )
        term = f"%{search}%"
        params.extend([term, term, term, term, term])

    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""

    # Get total count (same WHERE, no LIMIT)
    total = conn.execute(
        f"SELECT COUNT(*) FROM state_licenses sl{where}", params
    ).fetchone()[0]

    sql = f"""
        SELECT sl.*,
               CASE
                   WHEN sl.expiration_date IS NULL THEN NULL
                   ELSE CAST(julianday(sl.expiration_date)
                             - julianday('now') AS INTEGER)
               END AS days_until_expiry
        FROM state_licenses sl
        {where}
        ORDER BY sl.expiration_date ASC NULLS LAST, sl.holder_name
    """

    # Apply pagination if per_page > 0
    per_page = min(per_page, 200) if per_page > 0 else 0
    if per_page > 0:
        page = max(page, 1)
        offset = (page - 1) * per_page
        sql += " LIMIT ? OFFSET ?"
        params.extend([per_page, offset])
        pages = math.ceil(total / per_page) if per_page else 1
    else:
        page = 1
        pages = 1

    rows = conn.execute(sql, params).fetchall()
    return {
        "items": [dict(r) for r in rows],
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": pages,
    }


def get_license(conn: sqlite3.Connection, license_id: str) -> Optional[Dict[str, Any]]:
    """Get a single license by ID."""
    row = conn.execute(
        """SELECT sl.*,
                  CASE
                      WHEN sl.expiration_date IS NULL THEN NULL
                      ELSE CAST(julianday(sl.expiration_date)
                                - julianday('now') AS INTEGER)
                  END AS days_until_expiry
           FROM state_licenses sl WHERE sl.id = ?""",
        (license_id,),
    ).fetchone()
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# Create / Update / Delete
# ---------------------------------------------------------------------------

def create_license(conn: sqlite3.Connection, **fields) -> Dict[str, Any]:
    """Insert a new license record. Returns the created row."""
    license_id = generate_uuid()
    now = datetime.utcnow().isoformat()

    conn.execute(
        """INSERT INTO state_licenses
           (id, holder_type, employee_id, business_entity, state_code,
            license_type, license_number, holder_name, issued_date,
            expiration_date, reciprocal_state, association_date,
            disassociation_date, status, notes, created_at, updated_at,
            created_by)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            license_id,
            fields.get("holder_type") or "company",
            fields.get("employee_id"),
            fields.get("business_entity"),
            fields["state_code"],
            fields["license_type"],
            fields["license_number"],
            fields.get("holder_name") or fields.get("business_entity", ""),
            fields.get("issued_date"),
            fields.get("expiration_date"),
            fields.get("reciprocal_state"),
            fields.get("association_date"),
            fields.get("disassociation_date"),
            fields.get("status", "active"),
            fields.get("notes"),
            now,
            now,
            fields.get("created_by"),
        ),
    )
    _audit(conn, "license", license_id, "created",
           new_values=fields, changed_by=fields.get("created_by", "system"))
    conn.commit()
    return get_license(conn, license_id)


def update_license(
    conn: sqlite3.Connection, license_id: str, **fields
) -> Optional[Dict[str, Any]]:
    """Partial update — only provided fields are changed."""
    allowed = {
        "holder_type", "employee_id", "business_entity", "state_code",
        "license_type", "license_number", "holder_name", "issued_date",
        "expiration_date", "reciprocal_state", "association_date",
        "disassociation_date", "status", "notes", "entity_id",
    }
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return get_license(conn, license_id)

    # Capture old values before mutation
    old = get_license(conn, license_id)
    if not old:
        return None
    old_snapshot = {k: old[k] for k in updates if k in old}

    updates["updated_at"] = datetime.utcnow().isoformat()
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    params = list(updates.values()) + [license_id]

    conn.execute(
        f"UPDATE state_licenses SET {set_clause} WHERE id = ?", params
    )
    _audit(conn, "license", license_id, "updated",
           old_values=old_snapshot, new_values={k: v for k, v in updates.items() if k != "updated_at"},
           changed_by=fields.get("changed_by", "system"))
    conn.commit()
    return get_license(conn, license_id)


def delete_license(conn: sqlite3.Connection, license_id: str, changed_by: str = "system") -> bool:
    """Hard delete a license. Returns True if a row was deleted."""
    old = get_license(conn, license_id)
    cursor = conn.execute(
        "DELETE FROM state_licenses WHERE id = ?", (license_id,)
    )
    if cursor.rowcount > 0 and old:
        _audit(conn, "license", license_id, "deleted",
               old_values=old, changed_by=changed_by)
    conn.commit()
    return cursor.rowcount > 0


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def get_license_stats(conn: sqlite3.Connection) -> Dict[str, int]:
    """Dashboard card counts."""
    row = conn.execute("""
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) AS active,
            SUM(CASE WHEN status = 'expired' THEN 1 ELSE 0 END) AS expired,
            SUM(CASE WHEN status = 'active'
                      AND expiration_date IS NOT NULL
                      AND julianday(expiration_date) - julianday('now') <= 90
                      AND julianday(expiration_date) - julianday('now') > 0
                 THEN 1 ELSE 0 END) AS expiring_90,
            SUM(CASE WHEN employee_id IS NOT NULL THEN 1 ELSE 0 END) AS with_employee
        FROM state_licenses
    """).fetchone()
    return dict(row)


# ---------------------------------------------------------------------------
# Dashboard queries
# ---------------------------------------------------------------------------

def get_expiring_licenses(conn: sqlite3.Connection) -> Dict[str, List[Dict[str, Any]]]:
    """Active licenses grouped by urgency band: critical (≤30d), warning (31-60d), upcoming (61-90d).

    Also includes recently expired (within -30d) in the critical band.
    """
    rows = conn.execute("""
        SELECT sl.*,
               CAST(julianday(sl.expiration_date) - julianday('now') AS INTEGER)
                   AS days_until_expiry
        FROM state_licenses sl
        WHERE sl.expiration_date IS NOT NULL
          AND julianday(sl.expiration_date) - julianday('now') BETWEEN -30 AND 90
          AND sl.status IN ('active', 'expired')
        ORDER BY sl.expiration_date ASC
    """).fetchall()

    bands: Dict[str, List[Dict[str, Any]]] = {
        "critical": [],
        "warning": [],
        "upcoming": [],
    }
    for r in rows:
        d = dict(r)
        days = d["days_until_expiry"]
        if days <= 30:
            bands["critical"].append(d)
        elif days <= 60:
            bands["warning"].append(d)
        else:
            bands["upcoming"].append(d)

    return bands


def get_state_map_data(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Per-state aggregation for the SVG map.

    Returns list of {state_code, total, active, expiring_90, expired}.
    """
    rows = conn.execute("""
        SELECT
            state_code,
            COUNT(*) AS total,
            SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) AS active,
            SUM(CASE WHEN status = 'active'
                      AND expiration_date IS NOT NULL
                      AND julianday(expiration_date) - julianday('now') <= 90
                      AND julianday(expiration_date) - julianday('now') > 0
                 THEN 1 ELSE 0 END) AS expiring_90,
            SUM(CASE WHEN status = 'expired' THEN 1 ELSE 0 END) AS expired
        FROM state_licenses
        GROUP BY state_code
        ORDER BY state_code
    """).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# State License Boards
# ---------------------------------------------------------------------------

def get_license_board(
    conn: sqlite3.Connection, state_code: str
) -> Optional[Dict[str, Any]]:
    """Get licensing board info for a state."""
    row = conn.execute(
        "SELECT * FROM state_license_boards WHERE state_code = ?",
        (state_code,),
    ).fetchone()
    return dict(row) if row else None


def upsert_license_board(
    conn: sqlite3.Connection, state_code: str, **fields
) -> Dict[str, Any]:
    """Insert or update a state licensing board record."""
    now = datetime.utcnow().isoformat()
    conn.execute(
        """INSERT INTO state_license_boards
               (state_code, board_name, website_url, lookup_url, phone, notes,
                updated_at, updated_by)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(state_code) DO UPDATE SET
               board_name = excluded.board_name,
               website_url = excluded.website_url,
               lookup_url = excluded.lookup_url,
               phone = excluded.phone,
               notes = excluded.notes,
               updated_at = excluded.updated_at,
               updated_by = excluded.updated_by""",
        (
            state_code,
            fields.get("board_name", ""),
            fields.get("website_url"),
            fields.get("lookup_url"),
            fields.get("phone"),
            fields.get("notes"),
            now,
            fields.get("updated_by"),
        ),
    )
    conn.commit()
    return get_license_board(conn, state_code)


# ---------------------------------------------------------------------------
# Scope Categories
# ---------------------------------------------------------------------------

def list_scope_categories(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """All scope categories sorted by sort_order."""
    rows = conn.execute(
        "SELECT * FROM scope_categories ORDER BY sort_order, name"
    ).fetchall()
    return [dict(r) for r in rows]


def create_scope_category(
    conn: sqlite3.Connection, name: str
) -> Dict[str, Any]:
    """Create a new scope category."""
    cat_id = generate_uuid()
    max_order = conn.execute(
        "SELECT COALESCE(MAX(sort_order), 0) FROM scope_categories"
    ).fetchone()[0]
    conn.execute(
        "INSERT INTO scope_categories (id, name, sort_order) VALUES (?, ?, ?)",
        (cat_id, name, max_order + 1),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM scope_categories WHERE id = ?", (cat_id,)
    ).fetchone()
    return dict(row)


def batch_get_license_scopes(
    conn: sqlite3.Connection, license_ids: List[str]
) -> Dict[str, List[Dict[str, Any]]]:
    """Get scope categories for multiple licenses in a single query.

    Returns {license_id: [scope_dicts]} — empty list for licenses with no scopes.
    """
    if not license_ids:
        return {}
    result: Dict[str, List[Dict[str, Any]]] = {lid: [] for lid in license_ids}
    placeholders = ",".join("?" for _ in license_ids)
    rows = conn.execute(
        f"""SELECT lsm.license_id, sc.id, sc.name, sc.sort_order
            FROM license_scope_map lsm
            JOIN scope_categories sc ON lsm.scope_id = sc.id
            WHERE lsm.license_id IN ({placeholders})
            ORDER BY sc.sort_order, sc.name""",
        license_ids,
    ).fetchall()
    for r in rows:
        result[r["license_id"]].append({
            "id": r["id"], "name": r["name"],
            "sort_order": r["sort_order"],
        })
    return result


def get_license_scopes(
    conn: sqlite3.Connection, license_id: str
) -> List[Dict[str, Any]]:
    """Get scope categories linked to a license."""
    rows = conn.execute(
        """SELECT sc.* FROM scope_categories sc
           JOIN license_scope_map lsm ON lsm.scope_id = sc.id
           WHERE lsm.license_id = ?
           ORDER BY sc.sort_order, sc.name""",
        (license_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def set_license_scopes(
    conn: sqlite3.Connection, license_id: str, scope_ids: List[str]
) -> List[Dict[str, Any]]:
    """Replace all scope mappings for a license."""
    conn.execute(
        "DELETE FROM license_scope_map WHERE license_id = ?", (license_id,)
    )
    for sid in scope_ids:
        conn.execute(
            "INSERT OR IGNORE INTO license_scope_map (license_id, scope_id) VALUES (?, ?)",
            (license_id, sid),
        )
    conn.commit()
    return get_license_scopes(conn, license_id)


# ---------------------------------------------------------------------------
# CE Requirements
# ---------------------------------------------------------------------------

def list_ce_requirements(
    conn: sqlite3.Connection, state_code: Optional[str] = None
) -> List[Dict[str, Any]]:
    """List CE requirements, optionally filtered by state."""
    if state_code:
        rows = conn.execute(
            "SELECT * FROM ce_requirements WHERE state_code = ? ORDER BY license_type",
            (state_code,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM ce_requirements ORDER BY state_code, license_type"
        ).fetchall()
    return [dict(r) for r in rows]


def create_ce_requirement(conn: sqlite3.Connection, **fields) -> Dict[str, Any]:
    """Create a new CE requirement."""
    req_id = generate_uuid()
    now = datetime.utcnow().isoformat()
    conn.execute(
        """INSERT INTO ce_requirements
               (id, state_code, license_type, hours_required, period_months,
                provider_requirements, notes, created_at, updated_at, created_by)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            req_id,
            fields["state_code"],
            fields["license_type"],
            fields["hours_required"],
            fields["period_months"],
            fields.get("provider_requirements"),
            fields.get("notes"),
            now, now,
            fields.get("created_by"),
        ),
    )
    _audit(conn, "ce_requirement", req_id, "created",
           new_values=fields, changed_by=fields.get("created_by", "system"))
    conn.commit()
    row = conn.execute(
        "SELECT * FROM ce_requirements WHERE id = ?", (req_id,)
    ).fetchone()
    return dict(row)


def update_ce_requirement(
    conn: sqlite3.Connection, req_id: str, **fields
) -> Optional[Dict[str, Any]]:
    """Partial update of a CE requirement."""
    allowed = {
        "state_code", "license_type", "hours_required", "period_months",
        "provider_requirements", "notes",
    }
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        row = conn.execute(
            "SELECT * FROM ce_requirements WHERE id = ?", (req_id,)
        ).fetchone()
        return dict(row) if row else None

    # Capture old values before mutation
    old_row = conn.execute(
        "SELECT * FROM ce_requirements WHERE id = ?", (req_id,)
    ).fetchone()
    if not old_row:
        return None
    old_snapshot = {k: dict(old_row)[k] for k in updates if k in dict(old_row)}

    updates["updated_at"] = datetime.utcnow().isoformat()
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    params = list(updates.values()) + [req_id]
    conn.execute(f"UPDATE ce_requirements SET {set_clause} WHERE id = ?", params)
    _audit(conn, "ce_requirement", req_id, "updated",
           old_values=old_snapshot, new_values={k: v for k, v in updates.items() if k != "updated_at"},
           changed_by=fields.get("changed_by", "system"))
    conn.commit()
    row = conn.execute(
        "SELECT * FROM ce_requirements WHERE id = ?", (req_id,)
    ).fetchone()
    return dict(row) if row else None


def delete_ce_requirement(conn: sqlite3.Connection, req_id: str, changed_by: str = "system") -> bool:
    """Hard delete a CE requirement."""
    old_row = conn.execute("SELECT * FROM ce_requirements WHERE id = ?", (req_id,)).fetchone()
    cur = conn.execute("DELETE FROM ce_requirements WHERE id = ?", (req_id,))
    if cur.rowcount > 0 and old_row:
        _audit(conn, "ce_requirement", req_id, "deleted",
               old_values=dict(old_row), changed_by=changed_by)
    conn.commit()
    return cur.rowcount > 0


# ---------------------------------------------------------------------------
# CE Credits
# ---------------------------------------------------------------------------

def list_ce_credits(
    conn: sqlite3.Connection,
    license_id: Optional[str] = None,
    employee_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """List CE credits, optionally filtered. Includes linked course/provider info."""
    clauses: list = []
    params: list = []
    if license_id:
        clauses.append("cr.license_id = ?")
        params.append(license_id)
    if employee_id:
        clauses.append("cr.employee_id = ?")
        params.append(employee_id)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    rows = conn.execute(
        f"""SELECT cr.*,
                   co.id AS catalog_course_id,
                   co.title AS catalog_course_title,
                   co.hours AS catalog_course_hours,
                   cp.id AS catalog_provider_id,
                   cp.name AS catalog_provider_name
            FROM ce_credits cr
            LEFT JOIN ce_credit_courses cc ON cc.credit_id = cr.id
            LEFT JOIN ce_courses co ON co.id = cc.course_id
            LEFT JOIN ce_providers cp ON cp.id = co.provider_id
            {where}
            ORDER BY cr.completion_date DESC""",
        params,
    ).fetchall()
    return [dict(r) for r in rows]


def create_ce_credit(conn: sqlite3.Connection, **fields) -> Dict[str, Any]:
    """Create a new CE credit record."""
    credit_id = generate_uuid()
    now = datetime.utcnow().isoformat()
    conn.execute(
        """INSERT INTO ce_credits
               (id, employee_id, license_id, provider, course_name, hours,
                completion_date, certificate_file, status, notes,
                created_at, updated_at, created_by)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            credit_id,
            fields["employee_id"],
            fields["license_id"],
            fields.get("provider"),
            fields["course_name"],
            fields["hours"],
            fields["completion_date"],
            fields.get("certificate_file"),
            fields.get("status", "approved"),
            fields.get("notes"),
            now, now,
            fields.get("created_by"),
        ),
    )
    _audit(conn, "ce_credit", credit_id, "created",
           new_values=fields, changed_by=fields.get("created_by", "system"))
    conn.commit()
    row = conn.execute(
        "SELECT * FROM ce_credits WHERE id = ?", (credit_id,)
    ).fetchone()
    return dict(row)


def update_ce_credit(
    conn: sqlite3.Connection, credit_id: str, **fields
) -> Optional[Dict[str, Any]]:
    """Partial update of a CE credit."""
    allowed = {
        "provider", "course_name", "hours", "completion_date",
        "certificate_file", "status", "notes",
    }
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        row = conn.execute(
            "SELECT * FROM ce_credits WHERE id = ?", (credit_id,)
        ).fetchone()
        return dict(row) if row else None

    # Capture old values before mutation
    old_row = conn.execute(
        "SELECT * FROM ce_credits WHERE id = ?", (credit_id,)
    ).fetchone()
    if not old_row:
        return None
    old_snapshot = {k: dict(old_row)[k] for k in updates if k in dict(old_row)}

    updates["updated_at"] = datetime.utcnow().isoformat()
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    params = list(updates.values()) + [credit_id]
    conn.execute(f"UPDATE ce_credits SET {set_clause} WHERE id = ?", params)
    _audit(conn, "ce_credit", credit_id, "updated",
           old_values=old_snapshot, new_values={k: v for k, v in updates.items() if k != "updated_at"},
           changed_by=fields.get("changed_by", "system"))
    conn.commit()
    row = conn.execute(
        "SELECT * FROM ce_credits WHERE id = ?", (credit_id,)
    ).fetchone()
    return dict(row) if row else None


def delete_ce_credit(conn: sqlite3.Connection, credit_id: str, changed_by: str = "system") -> bool:
    """Hard delete a CE credit."""
    old_row = conn.execute("SELECT * FROM ce_credits WHERE id = ?", (credit_id,)).fetchone()
    cur = conn.execute("DELETE FROM ce_credits WHERE id = ?", (credit_id,))
    if cur.rowcount > 0 and old_row:
        _audit(conn, "ce_credit", credit_id, "deleted",
               old_values=dict(old_row), changed_by=changed_by)
    conn.commit()
    return cur.rowcount > 0


def get_ce_summary(
    conn: sqlite3.Connection, license_id: str
) -> Dict[str, Any]:
    """CE progress summary for a license: hours earned vs required.

    Period-aware: only counts credits within the current renewal window
    (expiration_date - period_months → expiration_date).  Falls back to
    counting all credits if no expiration date is set.
    """
    lic = get_license(conn, license_id)
    if not lic:
        return {"hours_earned": 0, "hours_required": 0, "period_months": 0, "pct_complete": 0}

    # Find matching CE requirement
    req = conn.execute(
        "SELECT hours_required, period_months FROM ce_requirements "
        "WHERE state_code = ? AND license_type = ?",
        (lic["state_code"], lic["license_type"]),
    ).fetchone()

    hours_required = req["hours_required"] if req else 0
    period_months = req["period_months"] if req else 0

    # Sum approved credits — scoped to renewal period when possible
    if lic.get("expiration_date") and period_months > 0:
        row = conn.execute(
            """SELECT COALESCE(SUM(hours), 0) AS total FROM ce_credits
               WHERE license_id = ? AND status = 'approved'
                 AND completion_date >= date(?, '-' || ? || ' months')
                 AND completion_date <= ?""",
            (license_id, lic["expiration_date"], period_months,
             lic["expiration_date"]),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT COALESCE(SUM(hours), 0) AS total FROM ce_credits "
            "WHERE license_id = ? AND status = 'approved'",
            (license_id,),
        ).fetchone()
    hours_earned = row["total"]

    pct = round((hours_earned / hours_required * 100), 1) if hours_required > 0 else 0

    return {
        "hours_earned": hours_earned,
        "hours_required": hours_required,
        "period_months": period_months,
        "pct_complete": min(pct, 100),
    }


def get_ce_compliance_report(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """All licenses with CE requirements — progress and compliance status.

    Status logic:
    - compliant: ≥100% hours
    - at_risk:   50-99% hours AND within 90 days of expiration
    - non_compliant: <50% hours OR overdue (past expiration)
    """
    rows = conn.execute("""
        SELECT sl.id, sl.state_code, sl.license_type, sl.license_number,
               sl.expiration_date, sl.status AS license_status,
               sl.business_entity, sl.holder_name, sl.employee_id,
               e.first_name || ' ' || e.last_name AS qualifying_party,
               cr.hours_required, cr.period_months
        FROM state_licenses sl
        JOIN ce_requirements cr
            ON cr.state_code = sl.state_code AND cr.license_type = sl.license_type
        LEFT JOIN employees e ON e.id = sl.employee_id
        WHERE sl.status IN ('active', 'expired')
        ORDER BY sl.state_code, sl.license_type
    """).fetchall()

    # Batch-load all approved CE credits grouped by license_id
    # We need two maps: one for period-scoped, one for all-time (fallback)
    license_ids = [dict(r)["id"] for r in rows]
    # Re-fetch rows as dicts (cursor consumed above)
    rows_list = [dict(r) for r in rows]

    # All-time approved credits per license
    if license_ids:
        ph = ",".join("?" for _ in license_ids)
        alltime_rows = conn.execute(
            f"""SELECT license_id, COALESCE(SUM(hours), 0) AS total
                FROM ce_credits WHERE status='approved'
                AND license_id IN ({ph}) GROUP BY license_id""",
            license_ids,
        ).fetchall()
        alltime_map = {r["license_id"]: r["total"] for r in alltime_rows}
    else:
        alltime_map = {}

    # Period-scoped credits: build per-license using their specific windows
    # Group licenses by (expiration_date, period_months) to batch where possible
    period_map: Dict[str, float] = {}
    need_period: List[Dict[str, Any]] = []
    for d in rows_list:
        if d["expiration_date"] and d["period_months"]:
            need_period.append(d)

    # For period-scoped, we still need per-window queries, but we can batch
    # licenses sharing the same (expiration_date, period_months) window
    from collections import defaultdict
    window_groups: Dict[tuple, List[str]] = defaultdict(list)
    for d in need_period:
        key = (d["expiration_date"], d["period_months"])
        window_groups[key].append(d["id"])

    for (exp, period), ids in window_groups.items():
        ph = ",".join("?" for _ in ids)
        period_rows = conn.execute(
            f"""SELECT license_id, COALESCE(SUM(hours), 0) AS total
                FROM ce_credits
                WHERE status='approved'
                  AND completion_date >= date(?, '-' || ? || ' months')
                  AND completion_date <= ?
                  AND license_id IN ({ph})
                GROUP BY license_id""",
            [exp, period, exp] + ids,
        ).fetchall()
        for pr in period_rows:
            period_map[pr["license_id"]] = pr["total"]

    results = []
    for d in rows_list:
        exp = d["expiration_date"]
        period = d["period_months"]

        # Use period-scoped credits if available, else all-time
        if exp and period:
            earned = period_map.get(d["id"], 0)
        else:
            earned = alltime_map.get(d["id"], 0)

        req = d["hours_required"]
        pct = round(earned / req * 100, 1) if req > 0 else 0

        # Days until expiry
        days_row = conn.execute(
            "SELECT CAST(julianday(?) - julianday('now') AS INTEGER) AS d",
            (exp,),
        ).fetchone() if exp else None
        days_left = days_row["d"] if days_row else None

        # Determine status
        if pct >= 100:
            ce_status = "compliant"
        elif days_left is not None and days_left < 0:
            ce_status = "non_compliant"
        elif pct < 50:
            ce_status = "non_compliant"
        elif days_left is not None and days_left <= 90:
            ce_status = "at_risk"
        else:
            ce_status = "compliant" if pct >= 100 else "at_risk"

        d["hours_earned"] = earned
        d["pct_complete"] = min(pct, 100)
        d["days_until_expiry"] = days_left
        d["ce_status"] = ce_status
        results.append(d)

    return results


def get_compliance_dashboard_data(conn: sqlite3.Connection) -> Dict[str, Any]:
    """Aggregate compliance data for the main licenses page dashboard.

    Returns {health, action_items, ce_by_state}.
    """
    report = get_ce_compliance_report(conn)

    # Health counts
    health = {"compliant": 0, "at_risk": 0, "non_compliant": 0}
    for r in report:
        health[r["ce_status"]] += 1

    # CE by state
    state_map: Dict[str, Dict[str, int]] = {}
    for r in report:
        st = r["state_code"]
        if st not in state_map:
            state_map[st] = {"compliant": 0, "at_risk": 0, "non_compliant": 0}
        state_map[st][r["ce_status"]] += 1
    ce_by_state = [
        {"state": st, **counts}
        for st, counts in sorted(state_map.items())
    ]

    # Action items
    action_items: List[Dict[str, Any]] = []

    # 1) Licenses expiring within 90 days
    expiring = conn.execute("""
        SELECT id, state_code, license_type, license_number, business_entity,
               CAST(julianday(expiration_date) - julianday('now') AS INTEGER) AS days_left
        FROM state_licenses
        WHERE status = 'active'
          AND expiration_date IS NOT NULL
          AND julianday(expiration_date) - julianday('now') BETWEEN 0 AND 90
        ORDER BY expiration_date
    """).fetchall()
    for row in expiring:
        d = dict(row)
        action_items.append({
            "type": "expiring",
            "message": f"{d['state_code']} {d['license_type']} #{d['license_number']} expires in {d['days_left']} days",
            "link": f"/licenses/{d['id']}",
        })

    # 2) CE credits below 50% with upcoming renewal
    for r in report:
        if r["pct_complete"] < 50 and r["hours_required"] > 0:
            days = r.get("days_until_expiry")
            if days is not None and 0 < days <= 180:
                action_items.append({
                    "type": "ce_low",
                    "message": f"{r['state_code']} {r['license_type']} — only {r['pct_complete']}% CE hours ({r['hours_earned']}/{r['hours_required']})",
                    "link": f"/licenses/{r['id']}",
                })

    # 3) Coverage gaps
    gaps = get_scope_coverage_gaps(conn)
    for g in gaps:
        action_items.append({
            "type": "coverage_gap",
            "message": f"No active {g['project_scope']} license in {g['project_state']}",
            "link": f"/licenses/state/{g['project_state']}",
        })

    return {
        "health": health,
        "action_items": action_items,
        "ce_by_state": ce_by_state,
    }


# ---------------------------------------------------------------------------
# Detail Page Helpers
# ---------------------------------------------------------------------------

def get_state_license_summary(
    conn: sqlite3.Connection, state_code: str
) -> Dict[str, Any]:
    """Aggregate stats for a single state."""
    row = conn.execute("""
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) AS active,
            SUM(CASE WHEN status = 'expired' THEN 1 ELSE 0 END) AS expired,
            SUM(CASE WHEN status = 'active'
                      AND expiration_date IS NOT NULL
                      AND julianday(expiration_date) - julianday('now') <= 90
                      AND julianday(expiration_date) - julianday('now') > 0
                 THEN 1 ELSE 0 END) AS expiring_90
        FROM state_licenses
        WHERE state_code = ?
    """, (state_code,)).fetchone()
    return dict(row) if row else {"total": 0, "active": 0, "expired": 0, "expiring_90": 0}


def list_licenses_for_state(
    conn: sqlite3.Connection, state_code: str
) -> List[Dict[str, Any]]:
    """Licenses for a state with qualifying party name joined."""
    rows = conn.execute("""
        SELECT sl.*,
               e.first_name || ' ' || e.last_name AS qualifying_party_name,
               CASE
                   WHEN sl.expiration_date IS NULL THEN NULL
                   ELSE CAST(julianday(sl.expiration_date)
                             - julianday('now') AS INTEGER)
               END AS days_until_expiry
        FROM state_licenses sl
        LEFT JOIN employees e ON e.id = sl.employee_id
        WHERE sl.state_code = ?
        ORDER BY sl.license_type, sl.expiration_date ASC NULLS LAST
    """, (state_code,)).fetchall()
    return [dict(r) for r in rows]


def get_scope_coverage_gaps(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Find (project_state, scope) pairs without matching active licenses.

    Compares active project allocations against licenses linked via scope_categories.
    """
    # Check if project_allocations table exists
    table_check = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='project_allocations'"
    ).fetchone()
    if not table_check:
        return []

    rows = conn.execute("""
        SELECT DISTINCT p.state AS project_state,
               pa.scope_name AS project_scope
        FROM project_allocations pa
        JOIN projects p ON pa.project_id = p.id
        WHERE p.state IS NOT NULL
          AND pa.scope_name IS NOT NULL
          AND pa.stage NOT IN ('closed', 'cancelled')
        EXCEPT
        SELECT sl.state_code AS project_state,
               sc.name AS project_scope
        FROM state_licenses sl
        JOIN license_scope_map lsm ON lsm.license_id = sl.id
        JOIN scope_categories sc ON sc.id = lsm.scope_id
        WHERE sl.status = 'active'
    """).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Portal Credential Encryption
# ---------------------------------------------------------------------------

def _get_fernet(secret_key: str) -> Fernet:
    """Derive a Fernet key from the app secret key via PBKDF2."""
    dk = hashlib.pbkdf2_hmac("sha256", secret_key.encode(), b"qms-license-creds", 100_000)
    return Fernet(base64.urlsafe_b64encode(dk[:32]))


def _encrypt(secret_key: str, plaintext: str) -> str:
    """Encrypt a string and return base64 token."""
    return _get_fernet(secret_key).encrypt(plaintext.encode()).decode()


def _decrypt(secret_key: str, token: str) -> str:
    """Decrypt a Fernet token back to plaintext."""
    try:
        return _get_fernet(secret_key).decrypt(token.encode()).decode()
    except InvalidToken:
        return "••••••••"


# ---------------------------------------------------------------------------
# Portal Credentials CRUD
# ---------------------------------------------------------------------------

def get_portal_credential(
    conn: sqlite3.Connection, license_id: str, user_id: str, secret_key: str
) -> Optional[Dict[str, Any]]:
    """Get a user's portal credentials for a license (decrypted)."""
    row = conn.execute(
        "SELECT * FROM license_portal_credentials WHERE license_id = ? AND user_id = ?",
        (license_id, user_id),
    ).fetchone()
    if not row:
        return None
    d = dict(row)
    d["password"] = _decrypt(secret_key, d.pop("password_enc"))
    return d


def upsert_portal_credential(
    conn: sqlite3.Connection,
    license_id: str,
    user_id: str,
    secret_key: str,
    **fields,
) -> Dict[str, Any]:
    """Create or update portal credentials for a user+license."""
    now = datetime.utcnow().isoformat()
    cred_id = generate_uuid()
    encrypted_pw = _encrypt(secret_key, fields["password"])

    conn.execute(
        """INSERT INTO license_portal_credentials
               (id, license_id, user_id, portal_url, username, password_enc, notes,
                created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(license_id, user_id) DO UPDATE SET
               portal_url = excluded.portal_url,
               username = excluded.username,
               password_enc = excluded.password_enc,
               notes = excluded.notes,
               updated_at = excluded.updated_at""",
        (
            cred_id,
            license_id,
            user_id,
            fields.get("portal_url"),
            fields["username"],
            encrypted_pw,
            fields.get("notes"),
            now,
            now,
        ),
    )
    conn.commit()
    return get_portal_credential(conn, license_id, user_id, secret_key)


def delete_portal_credential(
    conn: sqlite3.Connection, license_id: str, user_id: str
) -> bool:
    """Delete a user's portal credentials for a license."""
    cur = conn.execute(
        "DELETE FROM license_portal_credentials WHERE license_id = ? AND user_id = ?",
        (license_id, user_id),
    )
    conn.commit()
    return cur.rowcount > 0


# ---------------------------------------------------------------------------
# Certificate File Storage
# ---------------------------------------------------------------------------

def save_certificate_file(
    license_id: str, filename: str, file_data: bytes
) -> str:
    """Save a CE certificate file to data/certificates/<license_id>/.

    Returns the relative path (for storing in ce_credits.certificate_file).
    """
    import os
    from qms.core.config import QMS_PATHS

    base = os.path.join(QMS_PATHS.data_dir, "certificates", license_id)
    os.makedirs(base, exist_ok=True)

    # Sanitise filename
    safe_name = "".join(
        c if c.isalnum() or c in "._- " else "_" for c in filename
    ).strip()
    if not safe_name:
        safe_name = f"certificate_{generate_uuid()[:8]}"

    path = os.path.join(base, safe_name)
    with open(path, "wb") as f:
        f.write(file_data)

    return f"certificates/{license_id}/{safe_name}"


def get_certificate_path(
    conn: sqlite3.Connection, credit_id: str
) -> Optional[str]:
    """Resolve full filesystem path for a CE credit's certificate file."""
    import os
    from qms.core.config import QMS_PATHS

    row = conn.execute(
        "SELECT certificate_file FROM ce_credits WHERE id = ?",
        (credit_id,),
    ).fetchone()
    if not row or not row["certificate_file"]:
        return None

    full = os.path.join(QMS_PATHS.data_dir, row["certificate_file"])
    return full if os.path.isfile(full) else None


# ---------------------------------------------------------------------------
# License Events
# ---------------------------------------------------------------------------

VALID_EVENT_TYPES = {"issued", "renewed", "amended", "suspended", "revoked", "expired", "reinstated"}
VALID_FEE_TYPES = {"application", "renewal", "amendment", "late_fee", "other"}


def create_event(
    conn: sqlite3.Connection,
    license_id: str,
    event_type: str,
    event_date: str,
    notes: Optional[str] = None,
    fee_amount: Optional[float] = None,
    fee_type: Optional[str] = None,
    created_by: str = "system",
) -> Optional[Dict[str, Any]]:
    """Record a license event (renewal, amendment, suspension, etc.).

    Returns the new event dict, or None if license_id doesn't exist.
    """
    # Verify license exists
    row = conn.execute("SELECT 1 FROM state_licenses WHERE id = ?", (license_id,)).fetchone()
    if not row:
        return None

    event_id = generate_uuid()
    conn.execute(
        """INSERT INTO license_events
               (id, license_id, event_type, event_date, notes, fee_amount, fee_type, created_by)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (event_id, license_id, event_type, event_date, notes, fee_amount, fee_type, created_by),
    )
    _audit(conn, "license_event", event_id, "created",
           new_values={"license_id": license_id, "event_type": event_type,
                       "event_date": event_date, "fee_amount": fee_amount,
                       "fee_type": fee_type},
           changed_by=created_by)
    conn.commit()

    return get_event(conn, event_id)


def get_event(conn: sqlite3.Connection, event_id: str) -> Optional[Dict[str, Any]]:
    """Fetch a single event by ID."""
    row = conn.execute("SELECT * FROM license_events WHERE id = ?", (event_id,)).fetchone()
    return dict(row) if row else None


def get_license_events(
    conn: sqlite3.Connection, license_id: str, limit: int = 50
) -> List[Dict[str, Any]]:
    """List events for a license, newest first."""
    rows = conn.execute(
        """SELECT * FROM license_events
           WHERE license_id = ?
           ORDER BY event_date DESC, created_at DESC
           LIMIT ?""",
        (license_id, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def auto_expire_licenses(
    conn: sqlite3.Connection, dry_run: bool = False
) -> Dict[str, Any]:
    """Mark active licenses past their expiration_date as expired.

    Creates an 'expired' event for each. Returns {expired_count, licenses}.
    In dry_run mode, returns what WOULD expire without making changes.
    """
    today = datetime.utcnow().strftime("%Y-%m-%d")
    rows = conn.execute(
        """SELECT id, holder_name, license_number, state_code, expiration_date
           FROM state_licenses
           WHERE status = 'active'
             AND expiration_date IS NOT NULL
             AND expiration_date < ?""",
        (today,),
    ).fetchall()
    licenses = [dict(r) for r in rows]

    if dry_run or not licenses:
        return {"expired_count": len(licenses), "licenses": licenses}

    for lic in licenses:
        conn.execute(
            "UPDATE state_licenses SET status = 'expired', updated_at = ? WHERE id = ?",
            (datetime.utcnow().isoformat(), lic["id"]),
        )
        _audit(conn, "license", lic["id"], "updated",
               old_values={"status": "active"},
               new_values={"status": "expired"},
               changed_by="auto-expire")
        # Create expired event
        event_id = generate_uuid()
        conn.execute(
            """INSERT INTO license_events
                   (id, license_id, event_type, event_date, notes, created_by)
               VALUES (?, ?, 'expired', ?, 'Auto-expired: past expiration date', 'auto-expire')""",
            (event_id, lic["id"], today),
        )
    conn.commit()
    return {"expired_count": len(licenses), "licenses": licenses}


def renew_license(
    conn: sqlite3.Connection,
    license_id: str,
    new_expiration_date: str,
    fee_amount: Optional[float] = None,
    fee_type: Optional[str] = None,
    notes: Optional[str] = None,
    created_by: str = "system",
) -> Optional[Dict[str, Any]]:
    """Renew a license: update expiration_date, create 'renewed' event.

    If the license was expired, also creates a 'reinstated' event and
    sets status back to 'active'.
    Returns the updated license dict, or None if not found.
    """
    current = get_license(conn, license_id)
    if not current:
        return None

    now = datetime.utcnow().isoformat()

    # If expired, reinstate first
    if current["status"] == "expired":
        conn.execute(
            "UPDATE state_licenses SET status = 'active', updated_at = ? WHERE id = ?",
            (now, license_id),
        )
        _audit(conn, "license", license_id, "updated",
               old_values={"status": "expired"},
               new_values={"status": "active"},
               changed_by=created_by)
        reinstate_id = generate_uuid()
        conn.execute(
            """INSERT INTO license_events
                   (id, license_id, event_type, event_date, notes, created_by)
               VALUES (?, ?, 'reinstated', ?, ?, ?)""",
            (reinstate_id, license_id, new_expiration_date, "Reinstated during renewal", created_by),
        )

    # Update expiration date
    old_exp = current.get("expiration_date")
    conn.execute(
        "UPDATE state_licenses SET expiration_date = ?, updated_at = ? WHERE id = ?",
        (new_expiration_date, now, license_id),
    )
    _audit(conn, "license", license_id, "updated",
           old_values={"expiration_date": old_exp},
           new_values={"expiration_date": new_expiration_date},
           changed_by=created_by)

    # Create renewed event
    create_event(conn, license_id, "renewed", new_expiration_date,
                 notes=notes, fee_amount=fee_amount, fee_type=fee_type,
                 created_by=created_by)

    return get_license(conn, license_id)


def get_renewal_timeline(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Monthly renewal counts for the next 12 months.

    Returns list of {month, with_employee, without_employee} sorted chronologically.
    """
    rows = conn.execute("""
        SELECT
            strftime('%%Y-%%m', expiration_date) AS month,
            SUM(CASE WHEN employee_id IS NOT NULL THEN 1 ELSE 0 END) AS with_employee,
            SUM(CASE WHEN employee_id IS NULL THEN 1 ELSE 0 END) AS without_employee,
            COUNT(*) AS total
        FROM state_licenses
        WHERE expiration_date IS NOT NULL
          AND expiration_date >= date('now')
          AND expiration_date < date('now', '+12 months')
          AND status = 'active'
        GROUP BY strftime('%%Y-%%m', expiration_date)
        ORDER BY month
    """).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------

def save_document_file(
    license_id: str, filename: str, file_data: bytes
) -> str:
    """Save a license document to data/license-documents/<license_id>/.

    Returns the relative path (for storing in license_documents.filename).
    """
    from qms.core.config import QMS_PATHS

    base = os.path.join(QMS_PATHS.data_dir, "license-documents", license_id)
    os.makedirs(base, exist_ok=True)

    # Sanitise filename
    safe_name = "".join(
        c if c.isalnum() or c in "._- " else "_" for c in filename
    ).strip()
    if not safe_name:
        safe_name = f"document_{generate_uuid()[:8]}"

    path = os.path.join(base, safe_name)
    with open(path, "wb") as f:
        f.write(file_data)

    return f"license-documents/{license_id}/{safe_name}"


def get_document_path(
    conn: sqlite3.Connection, doc_id: str
) -> Optional[str]:
    """Resolve full filesystem path for a license document."""
    from qms.core.config import QMS_PATHS

    row = conn.execute(
        "SELECT filename FROM license_documents WHERE id = ?",
        (doc_id,),
    ).fetchone()
    if not row or not row["filename"]:
        return None

    full = os.path.join(QMS_PATHS.data_dir, row["filename"])
    return full if os.path.isfile(full) else None


def create_document(
    conn: sqlite3.Connection,
    license_id: str,
    doc_type: str,
    filename: str,
    original_filename: str,
    file_size: int = 0,
    mime_type: Optional[str] = None,
    description: Optional[str] = None,
    uploaded_by: str = "system",
) -> Dict[str, Any]:
    """Create a license_documents record."""
    doc_id = generate_uuid()
    conn.execute(
        """INSERT INTO license_documents
           (id, license_id, doc_type, filename, original_filename,
            file_size, mime_type, description, uploaded_by)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (doc_id, license_id, doc_type, filename, original_filename,
         file_size, mime_type, description, uploaded_by),
    )
    _audit(conn, "license_documents", doc_id, "INSERT", changed_by=uploaded_by)
    return get_document(conn, doc_id)


def get_document(
    conn: sqlite3.Connection, doc_id: str
) -> Optional[Dict[str, Any]]:
    """Fetch a single document by ID."""
    row = conn.execute(
        "SELECT * FROM license_documents WHERE id = ?", (doc_id,)
    ).fetchone()
    return dict(row) if row else None


def list_documents(
    conn: sqlite3.Connection, license_id: str
) -> List[Dict[str, Any]]:
    """List all documents for a license, newest first."""
    rows = conn.execute(
        "SELECT * FROM license_documents WHERE license_id = ? ORDER BY uploaded_at DESC",
        (license_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def delete_document(
    conn: sqlite3.Connection, doc_id: str, deleted_by: str = "system"
) -> bool:
    """Delete a document record and its file on disk."""
    from qms.core.config import QMS_PATHS

    row = conn.execute(
        "SELECT * FROM license_documents WHERE id = ?", (doc_id,)
    ).fetchone()
    if not row:
        return False

    # Remove file from disk
    full_path = os.path.join(QMS_PATHS.data_dir, row["filename"])
    if os.path.isfile(full_path):
        os.remove(full_path)

    conn.execute("DELETE FROM license_documents WHERE id = ?", (doc_id,))
    _audit(conn, "license_documents", doc_id, "DELETE",
           old_values=dict(row), changed_by=deleted_by)
    return True


# ---------------------------------------------------------------------------
# Notes
# ---------------------------------------------------------------------------

def create_note(
    conn: sqlite3.Connection,
    license_id: str,
    note_text: str,
    created_by: str = "system",
) -> Dict[str, Any]:
    """Create a license note."""
    note_id = generate_uuid()
    conn.execute(
        """INSERT INTO license_notes (id, license_id, note_text, created_by)
           VALUES (?, ?, ?, ?)""",
        (note_id, license_id, note_text, created_by),
    )
    _audit(conn, "license_notes", note_id, "INSERT", changed_by=created_by)
    row = conn.execute(
        "SELECT * FROM license_notes WHERE id = ?", (note_id,)
    ).fetchone()
    return dict(row)


def list_notes(
    conn: sqlite3.Connection, license_id: str
) -> List[Dict[str, Any]]:
    """List all notes for a license, newest first."""
    rows = conn.execute(
        "SELECT * FROM license_notes WHERE license_id = ? ORDER BY created_at DESC",
        (license_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def delete_note(
    conn: sqlite3.Connection, note_id: str, deleted_by: str = "system"
) -> bool:
    """Delete a note by ID."""
    row = conn.execute(
        "SELECT * FROM license_notes WHERE id = ?", (note_id,)
    ).fetchone()
    if not row:
        return False
    conn.execute("DELETE FROM license_notes WHERE id = ?", (note_id,))
    _audit(conn, "license_notes", note_id, "DELETE",
           old_values=dict(row), changed_by=deleted_by)
    return True


# ---------------------------------------------------------------------------
# Activity Feed
# ---------------------------------------------------------------------------

def get_activity_feed(
    conn: sqlite3.Connection, license_id: str, limit: int = 50
) -> List[Dict[str, Any]]:
    """Unified activity feed merging events, notes, and documents.

    Returns list of dicts sorted by timestamp descending.
    """
    rows = conn.execute("""
        SELECT
            'event' AS activity_type,
            created_at AS timestamp,
            event_type || COALESCE(': ' || notes, '') AS description,
            created_by,
            id AS source_id
        FROM license_events
        WHERE license_id = ?

        UNION ALL

        SELECT
            'note' AS activity_type,
            created_at AS timestamp,
            CASE WHEN LENGTH(note_text) > 200
                 THEN SUBSTR(note_text, 1, 200) || '...'
                 ELSE note_text END AS description,
            created_by,
            id AS source_id
        FROM license_notes
        WHERE license_id = ?

        UNION ALL

        SELECT
            'document' AS activity_type,
            uploaded_at AS timestamp,
            'Uploaded ' || doc_type || ': ' || original_filename AS description,
            uploaded_by AS created_by,
            id AS source_id
        FROM license_documents
        WHERE license_id = ?

        ORDER BY timestamp DESC
        LIMIT ?
    """, (license_id, license_id, license_id, limit)).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Business Entities
# ---------------------------------------------------------------------------

VALID_ENTITY_TYPES = {
    "corporation", "llc", "partnership", "sole_proprietorship",
    "subsidiary", "dba", "branch",
}
VALID_ENTITY_STATUSES = {"active", "inactive", "dissolved"}


def list_entities(
    conn: sqlite3.Connection,
    *,
    search: Optional[str] = None,
    entity_type: Optional[str] = None,
    status: Optional[str] = None,
    parent_id: Optional[str] = None,
    page: int = 1,
    per_page: int = 25,
) -> Dict[str, Any]:
    """List business entities with counts. Returns paginated dict."""
    clauses: list = []
    params: list = []

    if search:
        clauses.append("(be.name LIKE ? OR be.ein LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])
    if entity_type:
        clauses.append("be.entity_type = ?")
        params.append(entity_type)
    if status:
        clauses.append("be.status = ?")
        params.append(status)
    if parent_id is not None:
        if parent_id == "":
            clauses.append("be.parent_id IS NULL")
        else:
            clauses.append("be.parent_id = ?")
            params.append(parent_id)

    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""

    total = conn.execute(
        f"SELECT COUNT(*) FROM business_entities be{where}", params
    ).fetchone()[0]

    pages = max(1, math.ceil(total / per_page)) if per_page > 0 else 1
    offset = (page - 1) * per_page if per_page > 0 else 0

    rows = conn.execute(f"""
        SELECT be.*,
            (SELECT COUNT(*) FROM business_entities c WHERE c.parent_id = be.id) AS child_count,
            (SELECT COUNT(*) FROM state_licenses sl WHERE sl.entity_id = be.id) AS license_count,
            (SELECT COUNT(*) FROM entity_registrations er WHERE er.entity_id = be.id) AS registration_count
        FROM business_entities be
        {where}
        ORDER BY be.name
        LIMIT ? OFFSET ?
    """, params + [per_page, offset]).fetchall()

    return {
        "items": [dict(r) for r in rows],
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": pages,
    }


def get_entity(conn: sqlite3.Connection, entity_id: str) -> Optional[Dict[str, Any]]:
    """Get a single entity with children, registrations, and linked licenses."""
    row = conn.execute(
        "SELECT * FROM business_entities WHERE id = ?", (entity_id,)
    ).fetchone()
    if not row:
        return None

    entity = dict(row)

    # Children
    children = conn.execute(
        "SELECT id, name, entity_type, status FROM business_entities WHERE parent_id = ? ORDER BY name",
        (entity_id,),
    ).fetchall()
    entity["children"] = [dict(c) for c in children]

    # Registrations with days_until_expiry
    regs = conn.execute("""
        SELECT er.*,
            CASE
                WHEN er.expiration_date IS NULL THEN NULL
                ELSE CAST(julianday(er.expiration_date) - julianday('now') AS INTEGER)
            END AS days_until_expiry
        FROM entity_registrations er
        WHERE er.entity_id = ?
        ORDER BY er.state_code, er.registration_type
    """, (entity_id,)).fetchall()
    entity["registrations"] = [dict(r) for r in regs]

    # Linked licenses (summary)
    licenses = conn.execute("""
        SELECT id, license_type, license_number, state_code, holder_name, status, expiration_date
        FROM state_licenses
        WHERE entity_id = ?
        ORDER BY state_code, license_type
    """, (entity_id,)).fetchall()
    entity["licenses"] = [dict(l) for l in licenses]

    # Parent info
    if entity.get("parent_id"):
        parent = conn.execute(
            "SELECT id, name, entity_type FROM business_entities WHERE id = ?",
            (entity["parent_id"],),
        ).fetchone()
        entity["parent"] = dict(parent) if parent else None
    else:
        entity["parent"] = None

    return entity


def create_entity(
    conn: sqlite3.Connection,
    name: str,
    entity_type: str = "corporation",
    parent_id: Optional[str] = None,
    changed_by: str = "system",
    **kwargs,
) -> Dict[str, Any]:
    """Create a new business entity."""
    entity_id = generate_uuid()
    now = datetime.utcnow().isoformat()

    if parent_id:
        parent = conn.execute(
            "SELECT id FROM business_entities WHERE id = ?", (parent_id,)
        ).fetchone()
        if not parent:
            raise ValueError(f"Parent entity {parent_id} not found")

    conn.execute(
        """INSERT INTO business_entities
           (id, name, entity_type, parent_id, ein, state_of_incorporation,
            address, city, state_code, zip_code, phone, website, notes,
            status, created_at, updated_at, created_by)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            entity_id, name.strip(), entity_type, parent_id,
            kwargs.get("ein"), kwargs.get("state_of_incorporation"),
            kwargs.get("address"), kwargs.get("city"),
            kwargs.get("state_code"), kwargs.get("zip_code"),
            kwargs.get("phone"), kwargs.get("website"),
            kwargs.get("notes"),
            kwargs.get("status", "active"),
            now, now, changed_by,
        ),
    )
    _audit(conn, "business_entity", entity_id, "created",
           new_values={"name": name, "entity_type": entity_type},
           changed_by=changed_by)
    conn.commit()
    return get_entity(conn, entity_id)


def update_entity(
    conn: sqlite3.Connection, entity_id: str, changed_by: str = "system", **kwargs
) -> Optional[Dict[str, Any]]:
    """Partial update of a business entity."""
    allowed = {
        "name", "entity_type", "parent_id", "ein", "state_of_incorporation",
        "address", "city", "state_code", "zip_code", "phone", "website",
        "notes", "status",
    }
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return get_entity(conn, entity_id)

    old = conn.execute(
        "SELECT * FROM business_entities WHERE id = ?", (entity_id,)
    ).fetchone()
    if not old:
        return None
    old_dict = dict(old)
    old_snapshot = {k: old_dict.get(k) for k in updates}

    updates["updated_at"] = datetime.utcnow().isoformat()
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    params = list(updates.values()) + [entity_id]

    conn.execute(f"UPDATE business_entities SET {set_clause} WHERE id = ?", params)
    _audit(conn, "business_entity", entity_id, "updated",
           old_values=old_snapshot,
           new_values={k: v for k, v in updates.items() if k != "updated_at"},
           changed_by=changed_by)
    conn.commit()
    return get_entity(conn, entity_id)


def delete_entity(
    conn: sqlite3.Connection, entity_id: str, changed_by: str = "system"
) -> bool:
    """Delete a business entity. Unlinks licenses first, cascades registrations."""
    old = conn.execute(
        "SELECT * FROM business_entities WHERE id = ?", (entity_id,)
    ).fetchone()
    if not old:
        return False

    # Unlink licenses (set entity_id = NULL, don't delete them)
    conn.execute(
        "UPDATE state_licenses SET entity_id = NULL WHERE entity_id = ?",
        (entity_id,),
    )
    # Reparent children to this entity's parent
    parent_id = dict(old).get("parent_id")
    conn.execute(
        "UPDATE business_entities SET parent_id = ? WHERE parent_id = ?",
        (parent_id, entity_id),
    )

    cursor = conn.execute("DELETE FROM business_entities WHERE id = ?", (entity_id,))
    if cursor.rowcount > 0:
        _audit(conn, "business_entity", entity_id, "deleted",
               old_values=dict(old), changed_by=changed_by)
    conn.commit()
    return cursor.rowcount > 0


def get_entity_hierarchy(
    conn: sqlite3.Connection, entity_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Get entity hierarchy tree.

    If entity_id given: returns that entity + all descendants.
    If None: returns all top-level entities with nested children.
    """
    if entity_id:
        rows = conn.execute("""
            WITH RECURSIVE tree AS (
                SELECT *, 0 AS depth FROM business_entities WHERE id = ?
                UNION ALL
                SELECT be.*, tree.depth + 1
                FROM business_entities be
                JOIN tree ON be.parent_id = tree.id
            )
            SELECT * FROM tree ORDER BY depth, name
        """, (entity_id,)).fetchall()
        return [dict(r) for r in rows]

    # All top-level with child counts
    rows = conn.execute("""
        SELECT be.*,
            (SELECT COUNT(*) FROM business_entities c WHERE c.parent_id = be.id) AS child_count,
            (SELECT COUNT(*) FROM state_licenses sl WHERE sl.entity_id = be.id) AS license_count,
            (SELECT COUNT(*) FROM entity_registrations er WHERE er.entity_id = be.id) AS registration_count
        FROM business_entities be
        WHERE be.parent_id IS NULL
        ORDER BY be.name
    """).fetchall()
    return [dict(r) for r in rows]


def get_entity_summary(conn: sqlite3.Connection) -> Dict[str, Any]:
    """Summary stats for entities dashboard."""
    total = conn.execute("SELECT COUNT(*) FROM business_entities").fetchone()[0]
    by_type = conn.execute(
        "SELECT entity_type, COUNT(*) as cnt FROM business_entities GROUP BY entity_type ORDER BY cnt DESC"
    ).fetchall()
    active_regs = conn.execute(
        "SELECT COUNT(*) FROM entity_registrations WHERE status = 'active'"
    ).fetchone()[0]
    expiring_regs = conn.execute("""
        SELECT COUNT(*) FROM entity_registrations
        WHERE status = 'active' AND expiration_date IS NOT NULL
          AND julianday(expiration_date) - julianday('now') <= 90
    """).fetchone()[0]

    return {
        "total_entities": total,
        "by_type": {r["entity_type"]: r["cnt"] for r in by_type},
        "active_registrations": active_regs,
        "expiring_registrations_90d": expiring_regs,
    }


# ---------------------------------------------------------------------------
# Entity Registrations
# ---------------------------------------------------------------------------

VALID_REGISTRATION_TYPES = {
    "secretary_of_state", "dbe", "mbe", "wbe", "sbe", "hub", "sdvosb", "other",
}
VALID_REGISTRATION_STATUSES = {"active", "expired", "pending", "revoked", "suspended"}
VALID_FILING_FREQUENCIES = {"annual", "biennial", "triennial", "one_time"}


def list_registrations(
    conn: sqlite3.Connection,
    *,
    entity_id: Optional[str] = None,
    registration_type: Optional[str] = None,
    state_code: Optional[str] = None,
    status: Optional[str] = None,
    expiring_days: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """List entity registrations with optional filters."""
    clauses: list = []
    params: list = []

    if entity_id:
        clauses.append("er.entity_id = ?")
        params.append(entity_id)
    if registration_type:
        clauses.append("er.registration_type = ?")
        params.append(registration_type)
    if state_code:
        clauses.append("er.state_code = ?")
        params.append(state_code)
    if status:
        clauses.append("er.status = ?")
        params.append(status)
    if expiring_days is not None:
        clauses.append(
            "er.status = 'active' AND er.expiration_date IS NOT NULL "
            "AND julianday(er.expiration_date) - julianday('now') <= ?"
        )
        params.append(expiring_days)

    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""

    rows = conn.execute(f"""
        SELECT er.*,
            be.name AS entity_name,
            CASE
                WHEN er.expiration_date IS NULL THEN NULL
                ELSE CAST(julianday(er.expiration_date) - julianday('now') AS INTEGER)
            END AS days_until_expiry
        FROM entity_registrations er
        JOIN business_entities be ON be.id = er.entity_id
        {where}
        ORDER BY er.state_code, er.registration_type
    """, params).fetchall()
    return [dict(r) for r in rows]


def get_registration(
    conn: sqlite3.Connection, registration_id: str
) -> Optional[Dict[str, Any]]:
    """Get a single registration with entity name."""
    row = conn.execute("""
        SELECT er.*,
            be.name AS entity_name,
            CASE
                WHEN er.expiration_date IS NULL THEN NULL
                ELSE CAST(julianday(er.expiration_date) - julianday('now') AS INTEGER)
            END AS days_until_expiry
        FROM entity_registrations er
        JOIN business_entities be ON be.id = er.entity_id
        WHERE er.id = ?
    """, (registration_id,)).fetchone()
    return dict(row) if row else None


def create_registration(
    conn: sqlite3.Connection,
    entity_id: str,
    registration_type: str,
    state_code: str,
    changed_by: str = "system",
    **kwargs,
) -> Dict[str, Any]:
    """Create a new entity registration."""
    # Validate entity exists
    entity = conn.execute(
        "SELECT id FROM business_entities WHERE id = ?", (entity_id,)
    ).fetchone()
    if not entity:
        raise ValueError(f"Entity {entity_id} not found")

    reg_id = generate_uuid()
    now = datetime.utcnow().isoformat()

    conn.execute(
        """INSERT INTO entity_registrations
           (id, entity_id, registration_type, state_code, registration_number,
            issuing_authority, issued_date, expiration_date, status,
            filing_frequency, next_filing_date, fee_amount, notes,
            created_at, updated_at, created_by)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            reg_id, entity_id, registration_type, state_code.upper(),
            kwargs.get("registration_number"),
            kwargs.get("issuing_authority"),
            kwargs.get("issued_date"),
            kwargs.get("expiration_date"),
            kwargs.get("status", "active"),
            kwargs.get("filing_frequency"),
            kwargs.get("next_filing_date"),
            kwargs.get("fee_amount"),
            kwargs.get("notes"),
            now, now, changed_by,
        ),
    )
    _audit(conn, "entity_registration", reg_id, "created",
           new_values={"entity_id": entity_id, "registration_type": registration_type,
                       "state_code": state_code},
           changed_by=changed_by)
    conn.commit()
    return get_registration(conn, reg_id)


def update_registration(
    conn: sqlite3.Connection, registration_id: str, changed_by: str = "system", **kwargs
) -> Optional[Dict[str, Any]]:
    """Partial update of an entity registration."""
    allowed = {
        "registration_type", "state_code", "registration_number",
        "issuing_authority", "issued_date", "expiration_date", "status",
        "filing_frequency", "next_filing_date", "fee_amount", "notes",
    }
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return get_registration(conn, registration_id)

    old = conn.execute(
        "SELECT * FROM entity_registrations WHERE id = ?", (registration_id,)
    ).fetchone()
    if not old:
        return None
    old_dict = dict(old)
    old_snapshot = {k: old_dict.get(k) for k in updates}

    updates["updated_at"] = datetime.utcnow().isoformat()
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    params = list(updates.values()) + [registration_id]

    conn.execute(f"UPDATE entity_registrations SET {set_clause} WHERE id = ?", params)
    _audit(conn, "entity_registration", registration_id, "updated",
           old_values=old_snapshot,
           new_values={k: v for k, v in updates.items() if k != "updated_at"},
           changed_by=changed_by)
    conn.commit()
    return get_registration(conn, registration_id)


def delete_registration(
    conn: sqlite3.Connection, registration_id: str, changed_by: str = "system"
) -> bool:
    """Delete an entity registration."""
    old = conn.execute(
        "SELECT * FROM entity_registrations WHERE id = ?", (registration_id,)
    ).fetchone()
    cursor = conn.execute(
        "DELETE FROM entity_registrations WHERE id = ?", (registration_id,)
    )
    if cursor.rowcount > 0 and old:
        _audit(conn, "entity_registration", registration_id, "deleted",
               old_values=dict(old), changed_by=changed_by)
    conn.commit()
    return cursor.rowcount > 0


# ---------------------------------------------------------------------------
# Phase 11 — State Regulatory Requirements
# ---------------------------------------------------------------------------

def list_requirements(
    conn: sqlite3.Connection,
    *,
    state_code: Optional[str] = None,
    license_type: Optional[str] = None,
    requirement_type: Optional[str] = None,
    page: int = 0,
    per_page: int = 0,
) -> Dict[str, Any]:
    """List state requirements with optional filters and pagination.

    Returns {items, total, page, per_page, pages}.
    """
    clauses: List[str] = []
    params: list = []

    if state_code:
        clauses.append("sr.state_code = ?")
        params.append(state_code)
    if license_type:
        clauses.append("sr.license_type = ?")
        params.append(license_type)
    if requirement_type:
        clauses.append("sr.requirement_type = ?")
        params.append(requirement_type)

    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""

    total = conn.execute(
        f"SELECT COUNT(*) FROM state_requirements sr{where}", params
    ).fetchone()[0]

    sql = f"""
        SELECT sr.*
        FROM state_requirements sr
        {where}
        ORDER BY sr.state_code, sr.license_type, sr.requirement_type
    """

    per_page = min(per_page, 200) if per_page > 0 else 0
    if per_page > 0:
        page = max(page, 1)
        offset = (page - 1) * per_page
        sql += " LIMIT ? OFFSET ?"
        params.extend([per_page, offset])
        pages = math.ceil(total / per_page) if per_page else 1
    else:
        page = 1
        pages = 1

    rows = conn.execute(sql, params).fetchall()
    return {
        "items": [dict(r) for r in rows],
        "total": total,
        "page": page,
        "per_page": per_page or total,
        "pages": pages,
    }


def get_requirement(
    conn: sqlite3.Connection, requirement_id: str
) -> Optional[Dict[str, Any]]:
    """Get a single state requirement by ID."""
    row = conn.execute(
        "SELECT * FROM state_requirements WHERE id = ?", (requirement_id,)
    ).fetchone()
    return dict(row) if row else None


def create_requirement(
    conn: sqlite3.Connection, data: Dict[str, Any], created_by: str = "system"
) -> Dict[str, Any]:
    """Create a state requirement. Returns the new record."""
    req_id = generate_uuid()
    now = datetime.utcnow().isoformat()
    conn.execute(
        """INSERT INTO state_requirements
               (id, state_code, license_type, requirement_type, description,
                fee_amount, fee_frequency, renewal_period_months,
                authority_name, authority_url, effective_date, notes,
                created_at, updated_at, created_by)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            req_id,
            data["state_code"],
            data["license_type"],
            data["requirement_type"],
            data.get("description"),
            data.get("fee_amount"),
            data.get("fee_frequency"),
            data.get("renewal_period_months"),
            data.get("authority_name"),
            data.get("authority_url"),
            data.get("effective_date"),
            data.get("notes"),
            now, now, created_by,
        ),
    )
    _audit(conn, "state_requirement", req_id, "created",
           new_values=data, changed_by=created_by)
    conn.commit()
    return get_requirement(conn, req_id)  # type: ignore


def update_requirement(
    conn: sqlite3.Connection,
    requirement_id: str,
    data: Dict[str, Any],
    changed_by: str = "system",
) -> Optional[Dict[str, Any]]:
    """Update a state requirement. Returns updated record or None."""
    old = get_requirement(conn, requirement_id)
    if not old:
        return None

    allowed = {
        "state_code", "license_type", "requirement_type", "description",
        "fee_amount", "fee_frequency", "renewal_period_months",
        "authority_name", "authority_url", "effective_date", "notes",
    }
    sets: List[str] = []
    params: list = []
    for key, val in data.items():
        if key in allowed:
            sets.append(f"{key} = ?")
            params.append(val)
    if not sets:
        return old

    sets.append("updated_at = ?")
    params.append(datetime.utcnow().isoformat())
    params.append(requirement_id)

    conn.execute(
        f"UPDATE state_requirements SET {', '.join(sets)} WHERE id = ?", params
    )
    _audit(conn, "state_requirement", requirement_id, "updated",
           old_values=old, new_values=data, changed_by=changed_by)
    conn.commit()
    return get_requirement(conn, requirement_id)


def delete_requirement(
    conn: sqlite3.Connection, requirement_id: str, deleted_by: str = "system"
) -> bool:
    """Delete a state requirement."""
    old = conn.execute(
        "SELECT * FROM state_requirements WHERE id = ?", (requirement_id,)
    ).fetchone()
    cursor = conn.execute(
        "DELETE FROM state_requirements WHERE id = ?", (requirement_id,)
    )
    if cursor.rowcount > 0 and old:
        _audit(conn, "state_requirement", requirement_id, "deleted",
               old_values=dict(old), changed_by=deleted_by)
    conn.commit()
    return cursor.rowcount > 0


def get_requirements_for_license(
    conn: sqlite3.Connection, state_code: str, license_type: str
) -> List[Dict[str, Any]]:
    """Get all requirements for a specific state/license_type combo."""
    rows = conn.execute(
        """SELECT * FROM state_requirements
           WHERE state_code = ? AND license_type = ?
           ORDER BY requirement_type""",
        (state_code, license_type),
    ).fetchall()
    return [dict(r) for r in rows]


def calculate_compliance_score(
    conn: sqlite3.Connection, license_id: str
) -> Dict[str, Any]:
    """Calculate compliance score for a single license.

    Returns {score, total_requirements, met_count, met: [...], unmet: [...]}.
    Each requirement is evaluated against available evidence.
    """
    lic = conn.execute(
        "SELECT * FROM state_licenses WHERE id = ?", (license_id,)
    ).fetchone()
    if not lic:
        return {"score": 0, "total_requirements": 0, "met_count": 0,
                "met": [], "unmet": [], "error": "License not found"}

    lic = dict(lic)
    reqs = get_requirements_for_license(conn, lic["state_code"], lic["license_type"])

    if not reqs:
        return {"score": 100, "total_requirements": 0, "met_count": 0,
                "met": [], "unmet": [], "license_id": license_id,
                "state_code": lic["state_code"], "license_type": lic["license_type"]}

    met: List[Dict[str, Any]] = []
    unmet: List[Dict[str, Any]] = []

    for req in reqs:
        rt = req["requirement_type"]
        entry = {
            "requirement_id": req["id"],
            "requirement_type": rt,
            "description": req.get("description") or rt.replace("_", " ").title(),
        }

        if rt == "initial_application":
            # Always met for existing licenses (they were issued)
            entry["evidence"] = "License exists — application was approved"
            met.append(entry)

        elif rt == "renewal":
            # Met if status is active and not expired
            if lic["status"] == "active":
                exp = lic.get("expiration_date")
                if exp and exp >= datetime.utcnow().strftime("%Y-%m-%d"):
                    entry["evidence"] = f"Active, expires {exp}"
                    met.append(entry)
                elif exp:
                    entry["reason"] = f"Expired on {exp}"
                    unmet.append(entry)
                else:
                    entry["evidence"] = "Active, no expiration"
                    met.append(entry)
            else:
                entry["reason"] = f"Status is {lic['status']}"
                unmet.append(entry)

        elif rt == "ce_requirement":
            # Met if CE credits >= required hours from ce_requirements table
            ce_req = conn.execute(
                """SELECT hours_required, period_months FROM ce_requirements
                   WHERE state_code = ? AND license_type = ?""",
                (lic["state_code"], lic["license_type"]),
            ).fetchone()
            if ce_req:
                hours_req = ce_req[0]
                earned = conn.execute(
                    """SELECT COALESCE(SUM(hours), 0) FROM ce_credits
                       WHERE license_id = ? AND status = 'approved'""",
                    (license_id,),
                ).fetchone()[0]
                if earned >= hours_req:
                    entry["evidence"] = f"{earned}/{hours_req} CE hours"
                    met.append(entry)
                else:
                    entry["reason"] = f"Only {earned}/{hours_req} CE hours"
                    unmet.append(entry)
            else:
                # No CE requirement defined in ce_requirements — assume met
                entry["evidence"] = "No CE requirement defined for this state/type"
                met.append(entry)

        elif rt == "bond":
            # Met if a bond document exists
            bond_doc = conn.execute(
                """SELECT id FROM license_documents
                   WHERE license_id = ? AND doc_type = 'bond' LIMIT 1""",
                (license_id,),
            ).fetchone()
            if bond_doc:
                entry["evidence"] = "Bond document on file"
                met.append(entry)
            else:
                entry["reason"] = "No bond document on file"
                unmet.append(entry)

        elif rt == "insurance":
            # Met if an insurance document exists
            ins_doc = conn.execute(
                """SELECT id FROM license_documents
                   WHERE license_id = ? AND doc_type = 'insurance' LIMIT 1""",
                (license_id,),
            ).fetchone()
            if ins_doc:
                entry["evidence"] = "Insurance document on file"
                met.append(entry)
            else:
                entry["reason"] = "No insurance document on file"
                unmet.append(entry)

        elif rt in ("exam", "background_check", "fingerprinting"):
            # Met if a document or event references it
            doc = conn.execute(
                """SELECT id FROM license_documents
                   WHERE license_id = ? AND (
                       doc_type = 'certificate' OR doc_type = 'other'
                   ) LIMIT 1""",
                (license_id,),
            ).fetchone()
            event = conn.execute(
                """SELECT id FROM license_events
                   WHERE license_id = ? AND notes LIKE ?
                   LIMIT 1""",
                (license_id, f"%{rt.replace('_', ' ')}%"),
            ).fetchone()
            if doc or event:
                entry["evidence"] = "Supporting document or event on file"
                met.append(entry)
            else:
                entry["reason"] = f"No {rt.replace('_', ' ')} record found"
                unmet.append(entry)

    total = len(reqs)
    met_count = len(met)
    score = round((met_count / total) * 100) if total > 0 else 100

    return {
        "license_id": license_id,
        "state_code": lic["state_code"],
        "license_type": lic["license_type"],
        "holder_name": lic.get("holder_name", ""),
        "score": score,
        "total_requirements": total,
        "met_count": met_count,
        "met": met,
        "unmet": unmet,
    }


def get_compliance_gap_analysis(
    conn: sqlite3.Connection,
) -> List[Dict[str, Any]]:
    """Gap analysis across all active licenses with requirements defined.

    Returns list of per-license compliance summaries.
    Only includes licenses that have state_requirements entries.
    """
    # Get distinct state/license_type combos that have requirements
    req_combos = conn.execute(
        "SELECT DISTINCT state_code, license_type FROM state_requirements"
    ).fetchall()
    combo_set = {(r[0], r[1]) for r in req_combos}

    if not combo_set:
        return []

    # Get all active licenses
    licenses = conn.execute(
        "SELECT id, state_code, license_type, holder_name FROM state_licenses WHERE status = 'active'"
    ).fetchall()

    results: List[Dict[str, Any]] = []
    for lic in licenses:
        lic = dict(lic)
        if (lic["state_code"], lic["license_type"]) not in combo_set:
            continue
        score_data = calculate_compliance_score(conn, lic["id"])
        results.append({
            "license_id": lic["id"],
            "state_code": lic["state_code"],
            "license_type": lic["license_type"],
            "holder_name": lic["holder_name"],
            "score": score_data["score"],
            "total_requirements": score_data["total_requirements"],
            "met_count": score_data["met_count"],
            "unmet_list": [u["requirement_type"] for u in score_data["unmet"]],
        })

    return sorted(results, key=lambda x: (x["score"], x["state_code"]))


def get_compliance_summary_by_state(
    conn: sqlite3.Connection,
) -> Dict[str, Dict[str, Any]]:
    """Compliance summary grouped by state.

    Returns {state_code: {total_licenses, avg_score, fully_compliant, has_gaps}}.
    """
    gap_data = get_compliance_gap_analysis(conn)
    state_map: Dict[str, Dict[str, Any]] = {}

    for item in gap_data:
        st = item["state_code"]
        if st not in state_map:
            state_map[st] = {
                "total_licenses": 0,
                "scores": [],
                "fully_compliant": 0,
                "has_gaps": 0,
            }
        state_map[st]["total_licenses"] += 1
        state_map[st]["scores"].append(item["score"])
        if item["score"] == 100:
            state_map[st]["fully_compliant"] += 1
        else:
            state_map[st]["has_gaps"] += 1

    # Compute averages
    result: Dict[str, Dict[str, Any]] = {}
    for st, data in sorted(state_map.items()):
        scores = data.pop("scores")
        data["avg_score"] = round(sum(scores) / len(scores)) if scores else 0
        result[st] = data

    return result


def seed_state_requirements(
    conn: sqlite3.Connection,
    requirements_data: List[Dict[str, Any]],
    created_by: str = "system",
) -> int:
    """Seed state requirements data. Uses INSERT OR IGNORE for idempotency.

    Each item in requirements_data should have:
      state_code, license_type, requirement_type, and optionally
      description, fee_amount, fee_frequency, renewal_period_months,
      authority_name, authority_url, notes.

    Returns count of newly inserted rows.
    """
    count = 0
    for req in requirements_data:
        cursor = conn.execute(
            """INSERT OR IGNORE INTO state_requirements
                   (id, state_code, license_type, requirement_type, description,
                    fee_amount, fee_frequency, renewal_period_months,
                    authority_name, authority_url, effective_date, notes,
                    created_at, updated_at, created_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'), ?)""",
            (
                generate_uuid(),
                req["state_code"],
                req["license_type"],
                req["requirement_type"],
                req.get("description"),
                req.get("fee_amount"),
                req.get("fee_frequency"),
                req.get("renewal_period_months"),
                req.get("authority_name"),
                req.get("authority_url"),
                req.get("effective_date"),
                req.get("notes"),
                created_by,
            ),
        )
        count += cursor.rowcount
    conn.commit()
    return count


# ---------------------------------------------------------------------------
# CE Providers — catalog CRUD
# ---------------------------------------------------------------------------

VALID_COURSE_FORMATS = ("online", "classroom", "self_study", "webinar", "conference", "other")


def list_ce_providers(
    conn: sqlite3.Connection,
    active_only: bool = True,
    search: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """List CE providers with optional filters."""
    clauses: list = []
    params: list = []
    if active_only:
        clauses.append("is_active = 1")
    if search:
        clauses.append("(name LIKE ? OR accreditation_body LIKE ?)")
        term = f"%{search}%"
        params.extend([term, term])
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    rows = conn.execute(
        f"SELECT * FROM ce_providers{where} ORDER BY name", params
    ).fetchall()
    return [dict(r) for r in rows]


def get_ce_provider(
    conn: sqlite3.Connection, provider_id: str
) -> Optional[Dict[str, Any]]:
    """Get a single CE provider by ID."""
    row = conn.execute(
        "SELECT * FROM ce_providers WHERE id = ?", (provider_id,)
    ).fetchone()
    return dict(row) if row else None


def create_ce_provider(
    conn: sqlite3.Connection,
    name: str,
    accreditation_body: Optional[str] = None,
    accreditation_number: Optional[str] = None,
    contact_email: Optional[str] = None,
    contact_phone: Optional[str] = None,
    website: Optional[str] = None,
    notes: Optional[str] = None,
    changed_by: str = "system",
) -> Dict[str, Any]:
    """Create a new CE provider."""
    provider_id = generate_uuid()
    now = datetime.utcnow().isoformat()
    conn.execute(
        """INSERT INTO ce_providers
               (id, name, accreditation_body, accreditation_number,
                contact_email, contact_phone, website, notes,
                created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (provider_id, name, accreditation_body, accreditation_number,
         contact_email, contact_phone, website, notes, now, now),
    )
    _audit(conn, "ce_provider", provider_id, "created",
           new_values={"name": name}, changed_by=changed_by)
    conn.commit()
    return dict(conn.execute(
        "SELECT * FROM ce_providers WHERE id = ?", (provider_id,)
    ).fetchone())


def update_ce_provider(
    conn: sqlite3.Connection, provider_id: str, changed_by: str = "system", **fields
) -> Optional[Dict[str, Any]]:
    """Partial update of a CE provider."""
    allowed = {
        "name", "accreditation_body", "accreditation_number",
        "contact_email", "contact_phone", "website", "notes", "is_active",
    }
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return get_ce_provider(conn, provider_id)

    old_row = conn.execute(
        "SELECT * FROM ce_providers WHERE id = ?", (provider_id,)
    ).fetchone()
    if not old_row:
        return None
    old_snapshot = {k: dict(old_row)[k] for k in updates if k in dict(old_row)}

    updates["updated_at"] = datetime.utcnow().isoformat()
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    params = list(updates.values()) + [provider_id]
    conn.execute(f"UPDATE ce_providers SET {set_clause} WHERE id = ?", params)
    _audit(conn, "ce_provider", provider_id, "updated",
           old_values=old_snapshot,
           new_values={k: v for k, v in updates.items() if k != "updated_at"},
           changed_by=changed_by)
    conn.commit()
    return get_ce_provider(conn, provider_id)


def delete_ce_provider(
    conn: sqlite3.Connection, provider_id: str, changed_by: str = "system"
) -> bool:
    """Soft-delete a CE provider (set is_active=0)."""
    old_row = conn.execute(
        "SELECT * FROM ce_providers WHERE id = ?", (provider_id,)
    ).fetchone()
    if not old_row:
        return False
    conn.execute(
        "UPDATE ce_providers SET is_active = 0, updated_at = ? WHERE id = ?",
        (datetime.utcnow().isoformat(), provider_id),
    )
    _audit(conn, "ce_provider", provider_id, "soft_deleted",
           old_values={"is_active": 1}, changed_by=changed_by)
    conn.commit()
    return True


# ---------------------------------------------------------------------------
# CE Courses — catalog CRUD
# ---------------------------------------------------------------------------


def list_ce_courses(
    conn: sqlite3.Connection,
    provider_id: Optional[str] = None,
    state_code: Optional[str] = None,
    license_type: Optional[str] = None,
    active_only: bool = True,
    search: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """List CE courses with optional filters.

    Cross-state filtering uses json_each() on the states_accepted JSON array.
    """
    clauses: list = []
    params: list = []
    if active_only:
        clauses.append("c.is_active = 1")
    if provider_id:
        clauses.append("c.provider_id = ?")
        params.append(provider_id)
    if state_code:
        clauses.append(
            "EXISTS (SELECT 1 FROM json_each(c.states_accepted) WHERE value = ?)"
        )
        params.append(state_code)
    if license_type:
        clauses.append(
            "EXISTS (SELECT 1 FROM json_each(c.license_types) WHERE value = ?)"
        )
        params.append(license_type)
    if search:
        clauses.append("(c.title LIKE ? OR c.description LIKE ?)")
        term = f"%{search}%"
        params.extend([term, term])
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    rows = conn.execute(
        f"""SELECT c.*, p.name AS provider_name
            FROM ce_courses c
            LEFT JOIN ce_providers p ON p.id = c.provider_id
            {where}
            ORDER BY c.title""",
        params,
    ).fetchall()
    results = []
    for r in rows:
        d = dict(r)
        # Parse JSON arrays for the response
        for field in ("states_accepted", "license_types"):
            if isinstance(d.get(field), str):
                try:
                    d[field] = json.loads(d[field])
                except (json.JSONDecodeError, TypeError):
                    d[field] = []
        results.append(d)
    return results


# ---------------------------------------------------------------------------
# Employee Credential Portfolio
# ---------------------------------------------------------------------------


def list_employees_with_licenses(
    conn: sqlite3.Connection,
) -> List[Dict[str, Any]]:
    """Return employees who hold at least one license, with summary counts."""
    rows = conn.execute(
        """SELECT e.id, e.first_name, e.last_name, e.employee_number,
                  COUNT(sl.id) AS license_count,
                  SUM(CASE WHEN sl.status = 'active' THEN 1 ELSE 0 END) AS active_count,
                  SUM(CASE WHEN sl.status = 'expired' THEN 1 ELSE 0 END) AS expired_count
           FROM employees e
           JOIN state_licenses sl ON sl.employee_id = e.id
           GROUP BY e.id
           ORDER BY e.last_name, e.first_name"""
    ).fetchall()
    return [dict(r) for r in rows]


def get_employee_portfolio(
    conn: sqlite3.Connection, employee_id: str
) -> List[Dict[str, Any]]:
    """Return all licenses for an employee with CE progress per license."""
    rows = conn.execute(
        """SELECT sl.*,
                  COALESCE(cr_sum.hours_earned, 0) AS hours_earned,
                  ce_req.hours_required,
                  ce_req.period_months
           FROM state_licenses sl
           LEFT JOIN (
               SELECT license_id, SUM(hours) AS hours_earned
               FROM ce_credits
               WHERE status = 'approved'
               GROUP BY license_id
           ) cr_sum ON cr_sum.license_id = sl.id
           LEFT JOIN ce_requirements ce_req
               ON ce_req.state_code = sl.state_code
              AND ce_req.license_type = sl.license_type
           WHERE sl.employee_id = ?
           ORDER BY sl.expiration_date ASC NULLS LAST""",
        (employee_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_ce_course(
    conn: sqlite3.Connection, course_id: str
) -> Optional[Dict[str, Any]]:
    """Get a single CE course with provider name."""
    row = conn.execute(
        """SELECT c.*, p.name AS provider_name
           FROM ce_courses c
           LEFT JOIN ce_providers p ON p.id = c.provider_id
           WHERE c.id = ?""",
        (course_id,),
    ).fetchone()
    if not row:
        return None
    d = dict(row)
    for field in ("states_accepted", "license_types"):
        if isinstance(d.get(field), str):
            try:
                d[field] = json.loads(d[field])
            except (json.JSONDecodeError, TypeError):
                d[field] = []
    return d


def create_ce_course(
    conn: sqlite3.Connection,
    title: str,
    hours: float,
    provider_id: Optional[str] = None,
    description: Optional[str] = None,
    format: Optional[str] = None,
    states_accepted: Optional[List[str]] = None,
    license_types: Optional[List[str]] = None,
    url: Optional[str] = None,
    changed_by: str = "system",
) -> Dict[str, Any]:
    """Create a new CE course."""
    course_id = generate_uuid()
    now = datetime.utcnow().isoformat()
    sa_json = json.dumps(states_accepted or [])
    lt_json = json.dumps(license_types or [])
    conn.execute(
        """INSERT INTO ce_courses
               (id, provider_id, title, description, hours, format,
                states_accepted, license_types, url, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (course_id, provider_id, title, description, hours, format,
         sa_json, lt_json, url, now, now),
    )
    _audit(conn, "ce_course", course_id, "created",
           new_values={"title": title, "hours": hours},
           changed_by=changed_by)
    conn.commit()
    return get_ce_course(conn, course_id)


def update_ce_course(
    conn: sqlite3.Connection, course_id: str, changed_by: str = "system", **fields
) -> Optional[Dict[str, Any]]:
    """Partial update of a CE course."""
    allowed = {
        "provider_id", "title", "description", "hours", "format",
        "states_accepted", "license_types", "url", "is_active",
    }
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return get_ce_course(conn, course_id)

    old_row = conn.execute(
        "SELECT * FROM ce_courses WHERE id = ?", (course_id,)
    ).fetchone()
    if not old_row:
        return None
    old_snapshot = {k: dict(old_row)[k] for k in updates if k in dict(old_row)}

    # Serialize JSON fields
    for jf in ("states_accepted", "license_types"):
        if jf in updates and isinstance(updates[jf], list):
            updates[jf] = json.dumps(updates[jf])

    updates["updated_at"] = datetime.utcnow().isoformat()
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    params = list(updates.values()) + [course_id]
    conn.execute(f"UPDATE ce_courses SET {set_clause} WHERE id = ?", params)
    _audit(conn, "ce_course", course_id, "updated",
           old_values=old_snapshot,
           new_values={k: v for k, v in updates.items() if k != "updated_at"},
           changed_by=changed_by)
    conn.commit()
    return get_ce_course(conn, course_id)


def delete_ce_course(
    conn: sqlite3.Connection, course_id: str, changed_by: str = "system"
) -> bool:
    """Soft-delete a CE course (set is_active=0)."""
    old_row = conn.execute(
        "SELECT * FROM ce_courses WHERE id = ?", (course_id,)
    ).fetchone()
    if not old_row:
        return False
    conn.execute(
        "UPDATE ce_courses SET is_active = 0, updated_at = ? WHERE id = ?",
        (datetime.utcnow().isoformat(), course_id),
    )
    _audit(conn, "ce_course", course_id, "soft_deleted",
           old_values={"is_active": 1}, changed_by=changed_by)
    conn.commit()
    return True


# ---------------------------------------------------------------------------
# CE Credit ↔ Course linking
# ---------------------------------------------------------------------------


def link_credit_to_course(
    conn: sqlite3.Connection, credit_id: str, course_id: str
) -> bool:
    """Link a CE credit to a catalog course."""
    conn.execute(
        "INSERT OR IGNORE INTO ce_credit_courses (credit_id, course_id) VALUES (?, ?)",
        (credit_id, course_id),
    )
    conn.commit()
    return True


def unlink_credit_from_course(
    conn: sqlite3.Connection, credit_id: str, course_id: str
) -> bool:
    """Remove link between a CE credit and a catalog course."""
    cur = conn.execute(
        "DELETE FROM ce_credit_courses WHERE credit_id = ? AND course_id = ?",
        (credit_id, course_id),
    )
    conn.commit()
    return cur.rowcount > 0


def get_credit_courses(
    conn: sqlite3.Connection, credit_id: str
) -> List[Dict[str, Any]]:
    """Get all courses linked to a CE credit."""
    rows = conn.execute(
        """SELECT c.*, p.name AS provider_name
           FROM ce_credit_courses cc
           JOIN ce_courses c ON c.id = cc.course_id
           LEFT JOIN ce_providers p ON p.id = c.provider_id
           WHERE cc.credit_id = ?""",
        (credit_id,),
    ).fetchall()
    results = []
    for r in rows:
        d = dict(r)
        for field in ("states_accepted", "license_types"):
            if isinstance(d.get(field), str):
                try:
                    d[field] = json.loads(d[field])
                except (json.JSONDecodeError, TypeError):
                    d[field] = []
        results.append(d)
    return results


# ── Calendar feed ─────────────────────────────────────────────────────

def get_calendar_events(conn: sqlite3.Connection, months_ahead: int = 12) -> list:
    """Return license expirations and CE deadlines as calendar event dicts.

    Each dict has: uid, summary, description, dtstart (YYYY-MM-DD), location.
    """
    events: list = []

    # License expirations within the lookahead window
    rows = conn.execute(
        "SELECT sl.id, sl.license_type, sl.license_number, sl.state_code, "
        "       sl.holder_name, sl.expiration_date "
        "FROM state_licenses sl "
        "WHERE sl.status = 'active' "
        "  AND sl.expiration_date IS NOT NULL "
        "  AND sl.expiration_date >= date('now') "
        "  AND sl.expiration_date <= date('now', ? || ' months')",
        (str(months_ahead),),
    ).fetchall()

    for r in rows:
        r = dict(r)
        events.append({
            "uid": f"license-{r['id']}@qms",
            "summary": f"{r['license_type']} #{r['license_number']} expires ({r['state_code']})",
            "description": (
                f"Holder: {r['holder_name']}\n"
                f"State: {r['state_code']}\n"
                f"License: {r['license_type']} #{r['license_number']}\n"
                f"Action: Renew before {r['expiration_date']}"
            ),
            "dtstart": r["expiration_date"],
            "location": r["state_code"],
        })

    # CE requirement deadlines (use license expiration as period end proxy)
    ce_rows = conn.execute(
        "SELECT sl.id, sl.license_type, sl.license_number, sl.state_code, "
        "       sl.holder_name, sl.expiration_date, "
        "       cr.hours_required, cr.period_months "
        "FROM state_licenses sl "
        "JOIN ce_requirements cr ON cr.state_code = sl.state_code "
        "  AND cr.license_type = sl.license_type "
        "WHERE sl.status = 'active' "
        "  AND sl.expiration_date IS NOT NULL "
        "  AND sl.expiration_date >= date('now') "
        "  AND sl.expiration_date <= date('now', ? || ' months')",
        (str(months_ahead),),
    ).fetchall()

    for r in ce_rows:
        r = dict(r)
        events.append({
            "uid": f"ce-deadline-{r['id']}@qms",
            "summary": f"CE deadline: {r['hours_required']}hrs for {r['license_type']} ({r['state_code']})",
            "description": (
                f"Holder: {r['holder_name']}\n"
                f"Requirement: {r['hours_required']} hours every {r['period_months']} months\n"
                f"License: {r['license_type']} #{r['license_number']}\n"
                f"Complete CE credits before {r['expiration_date']}"
            ),
            "dtstart": r["expiration_date"],
            "location": r["state_code"],
        })

    return events
