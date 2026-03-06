"""
State Licenses CRUD — pure Python, no Flask dependency.

Handles company contractor licenses and employee professional licenses.
"""

import base64
import hashlib
import json
import math
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
        "disassociation_date", "status", "notes",
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
        f"""SELECT lsm.license_id, sc.id, sc.name, sc.description, sc.sort_order
            FROM license_scope_map lsm
            JOIN scope_categories sc ON lsm.scope_id = sc.id
            WHERE lsm.license_id IN ({placeholders})
            ORDER BY sc.sort_order, sc.name""",
        license_ids,
    ).fetchall()
    for r in rows:
        result[r["license_id"]].append({
            "id": r["id"], "name": r["name"],
            "description": r["description"], "sort_order": r["sort_order"],
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
    """List CE credits, optionally filtered."""
    clauses: list = []
    params: list = []
    if license_id:
        clauses.append("license_id = ?")
        params.append(license_id)
    if employee_id:
        clauses.append("employee_id = ?")
        params.append(employee_id)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    rows = conn.execute(
        f"SELECT * FROM ce_credits{where} ORDER BY completion_date DESC", params
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
