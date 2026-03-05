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
            "(sl.holder_name LIKE ? OR sl.license_number LIKE ? "
            "OR sl.license_type LIKE ? OR sl.state_code LIKE ?)"
        )
        term = f"%{search}%"
        params.extend([term, term, term, term])

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
           (id, holder_type, employee_id, state_code, license_type,
            license_number, holder_name, issued_date, expiration_date,
            status, notes, created_at, updated_at, created_by)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            license_id,
            fields["holder_type"],
            fields.get("employee_id"),
            fields["state_code"],
            fields["license_type"],
            fields["license_number"],
            fields["holder_name"],
            fields.get("issued_date"),
            fields.get("expiration_date"),
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
        "holder_type", "employee_id", "state_code", "license_type",
        "license_number", "holder_name", "issued_date", "expiration_date",
        "status", "notes",
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
            SUM(CASE WHEN holder_type = 'company' THEN 1 ELSE 0 END) AS company,
            SUM(CASE WHEN holder_type = 'employee' THEN 1 ELSE 0 END) AS employee
        FROM state_licenses
    """).fetchone()
    return dict(row)
