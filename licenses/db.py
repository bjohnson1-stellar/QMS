"""
State Licenses CRUD — pure Python, no Flask dependency.

Handles company contractor licenses and employee professional licenses.
"""

import sqlite3
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional


def generate_uuid() -> str:
    return str(uuid.uuid4())


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
) -> List[Dict[str, Any]]:
    """List licenses with optional filters. Includes days_until_expiry."""
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
    rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


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

    updates["updated_at"] = datetime.utcnow().isoformat()
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    params = list(updates.values()) + [license_id]

    conn.execute(
        f"UPDATE state_licenses SET {set_clause} WHERE id = ?", params
    )
    conn.commit()
    return get_license(conn, license_id)


def delete_license(conn: sqlite3.Connection, license_id: str) -> bool:
    """Hard delete a license. Returns True if a row was deleted."""
    cursor = conn.execute(
        "DELETE FROM state_licenses WHERE id = ?", (license_id,)
    )
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
               (state_code, board_name, website_url, phone, notes, updated_at, updated_by)
           VALUES (?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(state_code) DO UPDATE SET
               board_name = excluded.board_name,
               website_url = excluded.website_url,
               phone = excluded.phone,
               notes = excluded.notes,
               updated_at = excluded.updated_at,
               updated_by = excluded.updated_by""",
        (
            state_code,
            fields.get("board_name", ""),
            fields.get("website_url"),
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

    updates["updated_at"] = datetime.utcnow().isoformat()
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    params = list(updates.values()) + [req_id]
    conn.execute(f"UPDATE ce_requirements SET {set_clause} WHERE id = ?", params)
    conn.commit()
    row = conn.execute(
        "SELECT * FROM ce_requirements WHERE id = ?", (req_id,)
    ).fetchone()
    return dict(row) if row else None


def delete_ce_requirement(conn: sqlite3.Connection, req_id: str) -> bool:
    """Hard delete a CE requirement."""
    cur = conn.execute("DELETE FROM ce_requirements WHERE id = ?", (req_id,))
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

    updates["updated_at"] = datetime.utcnow().isoformat()
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    params = list(updates.values()) + [credit_id]
    conn.execute(f"UPDATE ce_credits SET {set_clause} WHERE id = ?", params)
    conn.commit()
    row = conn.execute(
        "SELECT * FROM ce_credits WHERE id = ?", (credit_id,)
    ).fetchone()
    return dict(row) if row else None


def delete_ce_credit(conn: sqlite3.Connection, credit_id: str) -> bool:
    """Hard delete a CE credit."""
    cur = conn.execute("DELETE FROM ce_credits WHERE id = ?", (credit_id,))
    conn.commit()
    return cur.rowcount > 0


def get_ce_summary(
    conn: sqlite3.Connection, license_id: str
) -> Dict[str, Any]:
    """CE progress summary for a license: hours earned vs required."""
    # Get the license to find state_code + license_type
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

    # Sum approved credits
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
        WHERE pa.status = 'active' AND p.state IS NOT NULL
          AND pa.scope_name IS NOT NULL
        EXCEPT
        SELECT sl.state_code AS project_state,
               sc.name AS project_scope
        FROM state_licenses sl
        JOIN license_scope_map lsm ON lsm.license_id = sl.id
        JOIN scope_categories sc ON sc.id = lsm.scope_id
        WHERE sl.status = 'active'
    """).fetchall()
    return [dict(r) for r in rows]


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
