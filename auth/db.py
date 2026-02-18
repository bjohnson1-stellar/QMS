"""
User CRUD operations for QMS auth.

Pure business logic — no Flask imports.
"""

import sqlite3


def upsert_user(
    conn: sqlite3.Connection,
    entra_oid: str,
    email: str,
    display_name: str,
    default_role: str = "user",
) -> dict:
    """
    Insert or update a user from Entra ID claims.

    On first login: creates user with default_role.
    On subsequent logins: updates email/display_name and last_login,
    but preserves the locally-assigned role.
    """
    existing = conn.execute(
        "SELECT id, role, is_active FROM users WHERE entra_oid = ?",
        (entra_oid,),
    ).fetchone()

    if existing:
        conn.execute(
            """UPDATE users
               SET email = ?, display_name = ?, last_login = datetime('now')
               WHERE entra_oid = ?""",
            (email, display_name, entra_oid),
        )
        conn.commit()
        user_id = existing["id"]
        role = existing["role"]
        is_active = existing["is_active"]
    else:
        cursor = conn.execute(
            """INSERT INTO users (entra_oid, email, display_name, role)
               VALUES (?, ?, ?, ?)""",
            (entra_oid, email, display_name, default_role),
        )
        conn.commit()
        user_id = cursor.lastrowid
        role = default_role
        is_active = 1

    return {
        "id": user_id,
        "entra_oid": entra_oid,
        "email": email,
        "display_name": display_name,
        "role": role,
        "is_active": bool(is_active),
    }


def get_user(conn: sqlite3.Connection, user_id: int) -> dict | None:
    """Fetch a user by ID."""
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


def get_user_by_oid(conn: sqlite3.Connection, entra_oid: str) -> dict | None:
    """Fetch a user by Entra Object ID."""
    row = conn.execute(
        "SELECT * FROM users WHERE entra_oid = ?", (entra_oid,)
    ).fetchone()
    return dict(row) if row else None


def list_users(conn: sqlite3.Connection) -> list[dict]:
    """List all users, ordered by display name."""
    rows = conn.execute(
        "SELECT * FROM users ORDER BY display_name"
    ).fetchall()
    return [dict(r) for r in rows]


def update_role(conn: sqlite3.Connection, user_id: int, role: str) -> bool:
    """Update a user's role. Returns True if user was found."""
    if role not in ("admin", "user", "viewer"):
        raise ValueError(f"Invalid role: {role}")
    cursor = conn.execute(
        "UPDATE users SET role = ? WHERE id = ?", (role, user_id)
    )
    conn.commit()
    return cursor.rowcount > 0


def set_active(conn: sqlite3.Connection, user_id: int, is_active: bool) -> bool:
    """Activate or deactivate a user. Returns True if user was found."""
    cursor = conn.execute(
        "UPDATE users SET is_active = ? WHERE id = ?", (int(is_active), user_id)
    )
    conn.commit()
    return cursor.rowcount > 0
