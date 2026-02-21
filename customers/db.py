"""
Customer profile business logic — pure Python, no Flask imports.

Provides CRUD for customer profiles, requirements, specifications,
quality preferences, and interaction history.  Designed to support
repeat-business workflows where customer-specific standards carry
across projects.
"""

import sqlite3
from typing import Optional


# =============================================================================
# Customer profiles (extends base customers table from projects/schema.sql)
# =============================================================================

def list_customers(
    conn: sqlite3.Connection,
    status: str = "active",
    tier: Optional[str] = None,
) -> list:
    """List customers with project counts and latest activity."""
    where = ["c.status = ?"]
    params: list = [status]
    if tier:
        where.append("c.tier = ?")
        params.append(tier)

    sql = f"""
        SELECT c.*,
               COUNT(DISTINCT p.id) AS project_count,
               MAX(p.updated_at) AS last_project_activity,
               (SELECT COUNT(*) FROM customer_requirements cr
                WHERE cr.customer_id = c.id AND cr.status = 'active') AS requirement_count,
               (SELECT COUNT(*) FROM customer_specifications cs
                WHERE cs.customer_id = c.id AND cs.status = 'active') AS spec_count,
               e.first_name || ' ' || e.last_name AS account_manager_name
        FROM customers c
        LEFT JOIN projects p ON p.customer_id = c.id
        LEFT JOIN employees e ON e.id = c.account_manager_id
        WHERE {' AND '.join(where)}
        GROUP BY c.id
        ORDER BY c.name
    """
    return conn.execute(sql, params).fetchall()


def get_customer(conn: sqlite3.Connection, customer_id: int) -> Optional[sqlite3.Row]:
    """Get a single customer profile with aggregated stats."""
    return conn.execute(
        """SELECT c.*,
                  COUNT(DISTINCT p.id) AS project_count,
                  (SELECT COUNT(*) FROM customer_requirements cr
                   WHERE cr.customer_id = c.id AND cr.status = 'active') AS requirement_count,
                  (SELECT COUNT(*) FROM customer_specifications cs
                   WHERE cs.customer_id = c.id AND cs.status = 'active') AS spec_count,
                  (SELECT COUNT(*) FROM customer_quality_preferences cqp
                   WHERE cqp.customer_id = c.id) AS preference_count,
                  e.first_name || ' ' || e.last_name AS account_manager_name
           FROM customers c
           LEFT JOIN projects p ON p.customer_id = c.id
           LEFT JOIN employees e ON e.id = c.account_manager_id
           WHERE c.id = ?
           GROUP BY c.id""",
        (customer_id,),
    ).fetchone()


def create_customer(conn: sqlite3.Connection, **fields) -> int:
    """Create a new customer. Returns the customer ID."""
    allowed = {
        "name", "contact_name", "contact_email", "contact_phone",
        "billing_street", "billing_city", "billing_state", "billing_zip",
        "status", "notes", "industry", "territory", "tier", "website",
        "account_manager_id",
    }
    data = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if "name" not in data:
        raise ValueError("Customer name is required")

    cols = ", ".join(data.keys())
    placeholders = ", ".join("?" for _ in data)
    cur = conn.execute(
        f"INSERT INTO customers ({cols}) VALUES ({placeholders})",
        list(data.values()),
    )
    conn.commit()
    return cur.lastrowid


def update_customer(conn: sqlite3.Connection, customer_id: int, **fields) -> bool:
    """Partial update of a customer profile."""
    allowed = {
        "name", "contact_name", "contact_email", "contact_phone",
        "billing_street", "billing_city", "billing_state", "billing_zip",
        "status", "notes", "industry", "territory", "tier", "website",
        "account_manager_id", "onboarding_complete",
    }
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return False

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    set_clause += ", updated_at = datetime('now')"
    values = list(updates.values()) + [customer_id]

    conn.execute(
        f"UPDATE customers SET {set_clause} WHERE id = ?",
        values,
    )
    conn.commit()
    return True


# =============================================================================
# Customer requirements
# =============================================================================

def list_requirements(
    conn: sqlite3.Connection,
    customer_id: int,
    category: Optional[str] = None,
    status: str = "active",
) -> list:
    """List engineering requirements for a customer."""
    where = ["customer_id = ?", "status = ?"]
    params: list = [customer_id, status]
    if category:
        where.append("category = ?")
        params.append(category)
    return conn.execute(
        f"""SELECT * FROM customer_requirements
            WHERE {' AND '.join(where)}
            ORDER BY category, title""",
        params,
    ).fetchall()


def create_requirement(conn: sqlite3.Connection, customer_id: int, **fields) -> int:
    """Add an engineering requirement. Returns requirement ID."""
    allowed = {
        "category", "title", "description", "reference_code",
        "mandatory", "applies_to",
    }
    data = {k: v for k, v in fields.items() if k in allowed and v is not None}
    data["customer_id"] = customer_id

    if "category" not in data or "title" not in data:
        raise ValueError("category and title are required")

    cols = ", ".join(data.keys())
    placeholders = ", ".join("?" for _ in data)
    cur = conn.execute(
        f"INSERT INTO customer_requirements ({cols}) VALUES ({placeholders})",
        list(data.values()),
    )
    conn.commit()
    return cur.lastrowid


def update_requirement(conn: sqlite3.Connection, req_id: int, **fields) -> bool:
    """Update a requirement."""
    allowed = {
        "category", "title", "description", "reference_code",
        "mandatory", "applies_to", "status",
    }
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return False

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    set_clause += ", updated_at = datetime('now')"
    values = list(updates.values()) + [req_id]
    conn.execute(
        f"UPDATE customer_requirements SET {set_clause} WHERE id = ?",
        values,
    )
    conn.commit()
    return True


def delete_requirement(conn: sqlite3.Connection, req_id: int) -> bool:
    """Delete a requirement."""
    cur = conn.execute("DELETE FROM customer_requirements WHERE id = ?", (req_id,))
    conn.commit()
    return cur.rowcount > 0


# =============================================================================
# Customer specifications
# =============================================================================

def list_specifications(
    conn: sqlite3.Connection,
    customer_id: int,
    spec_type: Optional[str] = None,
    status: str = "active",
) -> list:
    """List specifications for a customer."""
    where = ["customer_id = ?", "status = ?"]
    params: list = [customer_id, status]
    if spec_type:
        where.append("spec_type = ?")
        params.append(spec_type)
    return conn.execute(
        f"""SELECT * FROM customer_specifications
            WHERE {' AND '.join(where)}
            ORDER BY spec_type, title""",
        params,
    ).fetchall()


def create_specification(conn: sqlite3.Connection, customer_id: int, **fields) -> int:
    """Add a specification. Returns spec ID."""
    allowed = {
        "spec_type", "spec_number", "title", "description",
        "revision", "document_path", "discipline",
    }
    data = {k: v for k, v in fields.items() if k in allowed and v is not None}
    data["customer_id"] = customer_id

    if "spec_type" not in data or "title" not in data:
        raise ValueError("spec_type and title are required")

    cols = ", ".join(data.keys())
    placeholders = ", ".join("?" for _ in data)
    cur = conn.execute(
        f"INSERT INTO customer_specifications ({cols}) VALUES ({placeholders})",
        list(data.values()),
    )
    conn.commit()
    return cur.lastrowid


def update_specification(conn: sqlite3.Connection, spec_id: int, **fields) -> bool:
    """Update a specification."""
    allowed = {
        "spec_type", "spec_number", "title", "description",
        "revision", "document_path", "discipline", "status",
    }
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return False

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    set_clause += ", updated_at = datetime('now')"
    values = list(updates.values()) + [spec_id]
    conn.execute(
        f"UPDATE customer_specifications SET {set_clause} WHERE id = ?",
        values,
    )
    conn.commit()
    return True


def delete_specification(conn: sqlite3.Connection, spec_id: int) -> bool:
    """Delete a specification."""
    cur = conn.execute("DELETE FROM customer_specifications WHERE id = ?", (spec_id,))
    conn.commit()
    return cur.rowcount > 0


# =============================================================================
# Customer quality preferences
# =============================================================================

def list_preferences(
    conn: sqlite3.Connection,
    customer_id: int,
    preference_type: Optional[str] = None,
) -> list:
    """List quality preferences for a customer."""
    where = ["customer_id = ?"]
    params: list = [customer_id]
    if preference_type:
        where.append("preference_type = ?")
        params.append(preference_type)
    return conn.execute(
        f"""SELECT * FROM customer_quality_preferences
            WHERE {' AND '.join(where)}
            ORDER BY preference_type, preference_key""",
        params,
    ).fetchall()


def set_preference(
    conn: sqlite3.Connection,
    customer_id: int,
    preference_type: str,
    preference_key: str,
    preference_value: str,
    notes: Optional[str] = None,
) -> int:
    """Upsert a quality preference. Returns the preference ID."""
    conn.execute(
        """INSERT INTO customer_quality_preferences
           (customer_id, preference_type, preference_key, preference_value, notes)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(customer_id, preference_type, preference_key)
           DO UPDATE SET preference_value = excluded.preference_value,
                         notes = excluded.notes,
                         updated_at = datetime('now')""",
        (customer_id, preference_type, preference_key, preference_value, notes),
    )
    conn.commit()
    row = conn.execute(
        """SELECT id FROM customer_quality_preferences
           WHERE customer_id = ? AND preference_type = ? AND preference_key = ?""",
        (customer_id, preference_type, preference_key),
    ).fetchone()
    return row["id"]


def delete_preference(conn: sqlite3.Connection, pref_id: int) -> bool:
    """Delete a quality preference."""
    cur = conn.execute(
        "DELETE FROM customer_quality_preferences WHERE id = ?", (pref_id,)
    )
    conn.commit()
    return cur.rowcount > 0


# =============================================================================
# Customer history / interaction log
# =============================================================================

def list_history(
    conn: sqlite3.Connection,
    customer_id: int,
    entry_type: Optional[str] = None,
    limit: int = 50,
) -> list:
    """List interaction history for a customer, newest first."""
    where = ["ch.customer_id = ?"]
    params: list = [customer_id]
    if entry_type:
        where.append("ch.entry_type = ?")
        params.append(entry_type)
    params.append(limit)
    return conn.execute(
        f"""SELECT ch.*, p.number AS project_number, p.name AS project_name,
                   u.display_name AS recorded_by_name
            FROM customer_history ch
            LEFT JOIN projects p ON p.id = ch.project_id
            LEFT JOIN users u ON u.id = ch.recorded_by
            WHERE {' AND '.join(where)}
            ORDER BY ch.created_at DESC
            LIMIT ?""",
        params,
    ).fetchall()


def add_history_entry(
    conn: sqlite3.Connection,
    customer_id: int,
    entry_type: str,
    title: str,
    description: Optional[str] = None,
    project_id: Optional[int] = None,
    recorded_by: Optional[int] = None,
) -> int:
    """Add a history entry. Returns the entry ID."""
    cur = conn.execute(
        """INSERT INTO customer_history
           (customer_id, entry_type, title, description, project_id, recorded_by)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (customer_id, entry_type, title, description, project_id, recorded_by),
    )
    conn.commit()
    return cur.lastrowid


# =============================================================================
# Cross-module helpers
# =============================================================================

def get_customer_projects(conn: sqlite3.Connection, customer_id: int) -> list:
    """List all projects for a customer."""
    return conn.execute(
        """SELECT p.id, p.number, p.name, p.stage, p.status,
                  p.start_date, p.end_date, p.pm,
                  f.name AS facility_name
           FROM projects p
           LEFT JOIN facilities f ON f.id = p.facility_id
           WHERE p.customer_id = ?
           ORDER BY p.created_at DESC""",
        (customer_id,),
    ).fetchall()


def get_customer_facilities(conn: sqlite3.Connection, customer_id: int) -> list:
    """List all facilities for a customer."""
    return conn.execute(
        """SELECT f.*,
                  (SELECT COUNT(*) FROM projects p WHERE p.facility_id = f.id) AS project_count
           FROM facilities f
           WHERE f.customer_id = ?
           ORDER BY f.name""",
        (customer_id,),
    ).fetchall()


def get_customer_contacts(conn: sqlite3.Connection, customer_id: int) -> list:
    """List all contacts for a customer (corporate, facility, project-level)."""
    return conn.execute(
        """SELECT pc.*,
                  f.name AS facility_name,
                  p.number AS project_number, p.name AS project_name
           FROM project_contacts pc
           LEFT JOIN facilities f ON f.id = pc.facility_id
           LEFT JOIN projects p ON p.id = pc.project_id
           WHERE pc.customer_id = ?
           ORDER BY pc.is_primary DESC, pc.name""",
        (customer_id,),
    ).fetchall()


def get_customer_summary(conn: sqlite3.Connection, customer_id: int) -> Optional[dict]:
    """Get a full customer profile summary for the detail page."""
    customer = get_customer(conn, customer_id)
    if not customer:
        return None

    return {
        "customer": dict(customer),
        "projects": [dict(r) for r in get_customer_projects(conn, customer_id)],
        "facilities": [dict(r) for r in get_customer_facilities(conn, customer_id)],
        "contacts": [dict(r) for r in get_customer_contacts(conn, customer_id)],
        "requirements": [dict(r) for r in list_requirements(conn, customer_id)],
        "specifications": [dict(r) for r in list_specifications(conn, customer_id)],
        "preferences": [dict(r) for r in list_preferences(conn, customer_id)],
        "history": [dict(r) for r in list_history(conn, customer_id, limit=20)],
    }
