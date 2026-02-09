"""
Employee/Subcontractor Management

Core CRUD operations for employee tracking with UUID primary keys,
multi-level duplicate prevention, certification management, and permissions.
"""

import csv
import uuid
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


def generate_uuid() -> str:
    """Generate UUID v4 for primary keys."""
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Lookups
# ---------------------------------------------------------------------------

def find_employee_by_number(
    conn: sqlite3.Connection,
    employee_number: Optional[str] = None,
    subcontractor_number: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Find employee by employee_number or subcontractor_number."""
    if employee_number:
        row = conn.execute(
            "SELECT * FROM employees WHERE employee_number = ?", (employee_number,)
        ).fetchone()
        if row:
            return dict(row)

    if subcontractor_number:
        row = conn.execute(
            "SELECT * FROM employees WHERE subcontractor_number = ?", (subcontractor_number,)
        ).fetchone()
        if row:
            return dict(row)

    return None


def find_employee_by_email(conn: sqlite3.Connection, email: str) -> Optional[Dict[str, Any]]:
    row = conn.execute(
        "SELECT * FROM employees WHERE LOWER(TRIM(email)) = LOWER(TRIM(?))", (email,)
    ).fetchone()
    return dict(row) if row else None


def find_employee_by_phone(conn: sqlite3.Connection, phone: str) -> Optional[Dict[str, Any]]:
    clean_phone = "".join(c for c in phone if c.isdigit())
    row = conn.execute(
        "SELECT * FROM employees "
        "WHERE REPLACE(REPLACE(REPLACE(phone, '-', ''), '(', ''), ')', '') = ?",
        (clean_phone,),
    ).fetchone()
    return dict(row) if row else None


def find_employee_by_name(
    conn: sqlite3.Connection, last_name: str, first_name: str
) -> List[Dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM employees "
        "WHERE LOWER(last_name) = LOWER(?) AND LOWER(first_name) = LOWER(?)",
        (last_name, first_name),
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Auto-numbering
# ---------------------------------------------------------------------------

def get_next_employee_number(conn: sqlite3.Connection) -> str:
    row = conn.execute(
        "SELECT COALESCE(MAX(CAST(SUBSTR(employee_number, 5) AS INTEGER)), 0) + 1 AS n "
        "FROM employees WHERE employee_number LIKE 'EMP-%'"
    ).fetchone()
    return f"EMP-{row['n']:04d}"


def get_next_subcontractor_number(conn: sqlite3.Connection) -> str:
    row = conn.execute(
        "SELECT COALESCE(MAX(CAST(SUBSTR(subcontractor_number, 5) AS INTEGER)), 0) + 1 AS n "
        "FROM employees WHERE subcontractor_number LIKE 'SUB-%'"
    ).fetchone()
    return f"SUB-{row['n']:04d}"


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

def create_employee(
    conn: sqlite3.Connection,
    last_name: str,
    first_name: str,
    is_employee: bool = True,
    is_subcontractor: bool = False,
    current_hire_date: Optional[str] = None,
    position: Optional[str] = None,
    department_id: Optional[int] = None,
    job_id: Optional[int] = None,
    role_id: Optional[int] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    created_by: str = "SYSTEM",
    **kwargs,
) -> str:
    """Create new employee. Returns employee UUID."""
    employee_id = generate_uuid()
    employee_number = get_next_employee_number(conn) if is_employee else None
    subcontractor_number = get_next_subcontractor_number(conn) if is_subcontractor else None

    if current_hire_date is None and (is_employee or is_subcontractor):
        current_hire_date = datetime.now().strftime("%Y-%m-%d")

    original_hire_date = kwargs.get("original_hire_date", current_hire_date)

    conn.execute(
        """INSERT INTO employees (
            id, employee_number, subcontractor_number,
            last_name, first_name, middle_initial, preferred_name,
            is_employee, is_subcontractor, is_active,
            original_hire_date, current_hire_date, separation_date,
            department_id, job_id, position, supervisor_id, role_id,
            email, phone, preferred_contact_method,
            ssn_last_four, status, status_reason, notes, created_by
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            employee_id, employee_number, subcontractor_number,
            last_name, first_name, kwargs.get("middle_initial"), kwargs.get("preferred_name"),
            1 if is_employee else 0, 1 if is_subcontractor else 0, kwargs.get("is_active", 1),
            original_hire_date, current_hire_date, kwargs.get("separation_date"),
            department_id, job_id, position, kwargs.get("supervisor_id"), role_id,
            email, phone, kwargs.get("preferred_contact_method", "email"),
            kwargs.get("ssn_last_four"), kwargs.get("status", "active"),
            kwargs.get("status_reason"), kwargs.get("notes"), created_by,
        ),
    )
    conn.commit()
    return employee_id


def update_employee(conn: sqlite3.Connection, employee_id: str, **updates) -> bool:
    """Update employee record by UUID."""
    allowed = {
        "last_name", "first_name", "middle_initial", "preferred_name",
        "is_employee", "is_subcontractor", "is_active",
        "current_hire_date", "separation_date",
        "department_id", "job_id", "position", "supervisor_id", "role_id",
        "email", "phone", "preferred_contact_method",
        "ssn_last_four", "status", "status_reason", "notes",
    }
    fields = {k: v for k, v in updates.items() if k in allowed}
    if not fields:
        return False

    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [employee_id]
    conn.execute(f"UPDATE employees SET {set_clause} WHERE id = ?", values)
    conn.commit()
    return True


def terminate_employee(
    conn: sqlite3.Connection,
    employee_id: str,
    separation_date: Optional[str] = None,
    status_reason: Optional[str] = None,
) -> bool:
    if separation_date is None:
        separation_date = datetime.now().strftime("%Y-%m-%d")
    conn.execute(
        "UPDATE employees SET status='terminated', is_active=0, separation_date=?, status_reason=? WHERE id=?",
        (separation_date, status_reason, employee_id),
    )
    conn.commit()
    return True


# ---------------------------------------------------------------------------
# Weekly import with duplicate prevention
# ---------------------------------------------------------------------------

def import_weekly_personnel(
    conn: sqlite3.Connection,
    import_records: List[Dict[str, Any]],
    created_by: str = "IMPORT-SYSTEM",
) -> Dict[str, Any]:
    """Import personnel with multi-level duplicate prevention."""
    log = []
    flagged = []

    for record in import_records:
        existing = find_employee_by_number(
            conn, record.get("employee_number"), record.get("subcontractor_number")
        )
        match_method = None

        if existing:
            match_method = "employee_number" if record.get("employee_number") else "subcontractor_number"

        if not existing and record.get("email"):
            existing = find_employee_by_email(conn, record["email"])
            if existing:
                match_method = "email"

        if not existing and record.get("phone"):
            existing = find_employee_by_phone(conn, record["phone"])
            if existing:
                match_method = "phone"

        if not existing and record.get("last_name") and record.get("first_name"):
            candidates = find_employee_by_name(conn, record["last_name"], record["first_name"])
            if len(candidates) == 1:
                existing = candidates[0]
                match_method = "name_fuzzy"
                flagged.append({"record": record, "match": existing, "reason": "Name match — verify"})
            elif len(candidates) > 1:
                flagged.append({"record": record, "matches": candidates, "reason": "Multiple name matches"})
                continue

        if existing:
            update_employee(conn, existing["id"], **{
                k: record.get(k, existing.get(k))
                for k in ["last_name", "first_name", "position", "department_id", "job_id", "email", "phone"]
            })
            log.append({"action": "UPDATE", "id": existing["id"], "match": match_method})
        else:
            new_id = create_employee(
                conn,
                last_name=record["last_name"],
                first_name=record["first_name"],
                is_employee=record.get("is_employee", True),
                is_subcontractor=record.get("is_subcontractor", False),
                current_hire_date=record.get("hire_date"),
                position=record.get("position"),
                department_id=record.get("department_id"),
                job_id=record.get("job_id"),
                email=record.get("email"),
                phone=record.get("phone"),
                created_by=created_by,
            )
            log.append({"action": "INSERT", "id": new_id, "match": "new_record"})

    return {
        "imported": len(log),
        "updated": sum(1 for x in log if x["action"] == "UPDATE"),
        "inserted": sum(1 for x in log if x["action"] == "INSERT"),
        "flagged_for_review": len(flagged),
        "log": log,
        "duplicates": flagged,
    }


def import_from_csv(csv_path: str, created_by: str = "CSV-IMPORT") -> Dict[str, Any]:
    """Import personnel from CSV file."""
    from qms.core.db import get_db

    records = []
    with open(csv_path, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if "is_employee" in row:
                row["is_employee"] = row["is_employee"].lower() in ("1", "true", "yes")
            if "is_subcontractor" in row:
                row["is_subcontractor"] = row["is_subcontractor"].lower() in ("1", "true", "yes")
            if "department_id" in row and row["department_id"]:
                row["department_id"] = int(row["department_id"])
            if "job_id" in row and row["job_id"]:
                row["job_id"] = int(row["job_id"])
            records.append(row)

    with get_db() as conn:
        return import_weekly_personnel(conn, records, created_by)


# ---------------------------------------------------------------------------
# Certifications
# ---------------------------------------------------------------------------

def add_certification(
    conn: sqlite3.Connection,
    employee_id: str,
    certification_type: str,
    certification_number: Optional[str] = None,
    issuing_organization: Optional[str] = None,
    issue_date: Optional[str] = None,
    expiry_date: Optional[str] = None,
    renewal_reminder_days: int = 90,
    certificate_file_path: Optional[str] = None,
    notes: Optional[str] = None,
    created_by: str = "SYSTEM",
) -> str:
    """Add certification to employee. Returns certification UUID."""
    cert_id = generate_uuid()
    conn.execute(
        """INSERT INTO employee_certifications (
            id, employee_id, certification_type, certification_number,
            issuing_organization, issue_date, expiry_date, renewal_reminder_days,
            status, certificate_file_path, notes, created_by
        ) VALUES (?,?,?,?,?,?,?,?,'active',?,?,?)""",
        (
            cert_id, employee_id, certification_type, certification_number,
            issuing_organization, issue_date, expiry_date, renewal_reminder_days,
            certificate_file_path, notes, created_by,
        ),
    )
    conn.commit()
    return cert_id


def get_expiring_certifications(conn: sqlite3.Connection, days_ahead: int = 90) -> List[Dict]:
    rows = conn.execute(
        "SELECT * FROM v_expiring_certifications WHERE days_until_expiry <= ? ORDER BY days_until_expiry",
        (days_ahead,),
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Rehire
# ---------------------------------------------------------------------------

def rehire_employee(
    conn: sqlite3.Connection,
    employee_id: str,
    new_hire_date: Optional[str] = None,
    reason: Optional[str] = None,
) -> bool:
    """Rehire a former employee and create a new employment_history record.

    Reactivates the employee record, clears separation_date, and logs
    a 'rehire' transition in employment_history.

    Returns True on success.
    """
    if new_hire_date is None:
        new_hire_date = datetime.now().strftime("%Y-%m-%d")

    conn.execute(
        "UPDATE employees SET status='active', is_active=1, "
        "current_hire_date=?, separation_date=NULL WHERE id=?",
        (new_hire_date, employee_id),
    )

    emp = conn.execute(
        "SELECT is_employee, is_subcontractor FROM employees WHERE id = ?",
        (employee_id,),
    ).fetchone()

    if emp["is_employee"] and emp["is_subcontractor"]:
        employment_type = "both"
    elif emp["is_employee"]:
        employment_type = "employee"
    else:
        employment_type = "subcontractor"

    conn.execute(
        """INSERT INTO employment_history (
            id, employee_id, start_date, employment_type,
            transition_type, reason_for_change, created_by
        ) VALUES (?, ?, ?, ?, 'rehire', ?, 'SYSTEM')""",
        (generate_uuid(), employee_id, new_hire_date, employment_type, reason),
    )

    conn.commit()
    return True


# ---------------------------------------------------------------------------
# Permission management
# ---------------------------------------------------------------------------

def grant_permission(
    conn: sqlite3.Connection,
    employee_id: str,
    permission_code: str,
    granted_by: str,
    reason: Optional[str] = None,
) -> str:
    """Grant an individual permission to an employee.

    Looks up the permission by its code and creates (or replaces) an
    employee_permissions row with ``is_granted=1``.

    Returns the employee_permissions UUID.

    Raises:
        ValueError: If *permission_code* does not exist.
    """
    perm = conn.execute(
        "SELECT id FROM permissions WHERE permission_code = ?", (permission_code,)
    ).fetchone()
    if not perm:
        raise ValueError(f"Permission code '{permission_code}' not found")

    perm_id = generate_uuid()
    conn.execute(
        """INSERT OR REPLACE INTO employee_permissions (
            id, employee_id, permission_id, is_granted, granted_by, reason
        ) VALUES (?, ?, ?, 1, ?, ?)""",
        (perm_id, employee_id, perm["id"], granted_by, reason),
    )
    conn.commit()
    return perm_id


def revoke_permission(
    conn: sqlite3.Connection,
    employee_id: str,
    permission_code: str,
    granted_by: str,
    reason: Optional[str] = None,
) -> bool:
    """Revoke a permission from an employee.

    Creates an override row with ``is_granted=0`` and sets the revoked_date.

    Returns True on success.

    Raises:
        ValueError: If *permission_code* does not exist.
    """
    perm = conn.execute(
        "SELECT id FROM permissions WHERE permission_code = ?", (permission_code,)
    ).fetchone()
    if not perm:
        raise ValueError(f"Permission code '{permission_code}' not found")

    conn.execute(
        """INSERT OR REPLACE INTO employee_permissions (
            id, employee_id, permission_id, is_granted, granted_by, reason, revoked_date
        ) VALUES (?, ?, ?, 0, ?, ?, datetime('now'))""",
        (generate_uuid(), employee_id, perm["id"], granted_by, reason),
    )
    conn.commit()
    return True


def get_employee_permissions(
    conn: sqlite3.Connection, employee_id: str
) -> List[Dict[str, Any]]:
    """Return effective permissions for an employee.

    Queries the ``v_employee_permissions`` view and returns only rows
    where ``has_permission = 1``, ordered by module then permission name.
    """
    rows = conn.execute(
        "SELECT * FROM v_employee_permissions "
        "WHERE employee_id = ? AND has_permission = 1 "
        "ORDER BY module, permission_name",
        (employee_id,),
    ).fetchall()
    return [dict(r) for r in rows]
