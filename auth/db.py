"""
User CRUD operations for QMS auth — local email + password.

Pure business logic — no Flask imports.
"""

import sqlite3

from werkzeug.security import check_password_hash, generate_password_hash


def create_user(
    conn: sqlite3.Connection,
    email: str,
    display_name: str,
    password: str,
    role: str = "user",
    must_change_password: bool = True,
) -> dict:
    """
    Create a new local user with a hashed password.

    Returns the created user dict.
    Raises sqlite3.IntegrityError if email already exists.
    """
    if role not in ("admin", "user", "viewer"):
        raise ValueError(f"Invalid role: {role}")

    password_hash = generate_password_hash(password)
    cursor = conn.execute(
        """INSERT INTO users (email, display_name, password_hash, role, must_change_password)
           VALUES (?, ?, ?, ?, ?)""",
        (email, display_name, password_hash, role, int(must_change_password)),
    )
    conn.commit()

    return {
        "id": cursor.lastrowid,
        "email": email,
        "display_name": display_name,
        "role": role,
        "is_active": True,
        "must_change_password": must_change_password,
    }


def authenticate(conn: sqlite3.Connection, email: str, password: str) -> dict | None:
    """
    Validate email + password. Returns user dict on success, None on failure.

    Also updates last_login timestamp on success.
    """
    row = conn.execute(
        "SELECT * FROM users WHERE email = ? AND is_active = 1",
        (email,),
    ).fetchone()

    if not row:
        return None

    if not row["password_hash"]:
        return None

    if not check_password_hash(row["password_hash"], password):
        return None

    # Update last_login
    conn.execute(
        "UPDATE users SET last_login = datetime('now') WHERE id = ?",
        (row["id"],),
    )
    conn.commit()

    return dict(row)


def get_user(conn: sqlite3.Connection, user_id: int) -> dict | None:
    """Fetch a user by ID."""
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


def get_user_by_email(conn: sqlite3.Connection, email: str) -> dict | None:
    """Fetch a user by email address."""
    row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    return dict(row) if row else None


def list_users(conn: sqlite3.Connection) -> list[dict]:
    """List all users, ordered by display name."""
    rows = conn.execute(
        "SELECT id, email, display_name, role, is_active, must_change_password, "
        "first_login, last_login FROM users ORDER BY display_name"
    ).fetchall()
    return [dict(r) for r in rows]


def set_password(
    conn: sqlite3.Connection,
    user_id: int,
    new_password: str,
    must_change: bool = False,
) -> bool:
    """Set a user's password (admin reset). Returns True if user was found."""
    password_hash = generate_password_hash(new_password)
    cursor = conn.execute(
        "UPDATE users SET password_hash = ?, must_change_password = ? WHERE id = ?",
        (password_hash, int(must_change), user_id),
    )
    conn.commit()
    return cursor.rowcount > 0


def change_password(
    conn: sqlite3.Connection,
    user_id: int,
    current_password: str,
    new_password: str,
) -> tuple[bool, str]:
    """
    Change a user's own password (requires current password).

    Returns (success, message).
    """
    row = conn.execute(
        "SELECT password_hash FROM users WHERE id = ?", (user_id,)
    ).fetchone()

    if not row:
        return False, "User not found"

    if not row["password_hash"] or not check_password_hash(row["password_hash"], current_password):
        return False, "Current password is incorrect"

    password_hash = generate_password_hash(new_password)
    conn.execute(
        "UPDATE users SET password_hash = ?, must_change_password = 0 WHERE id = ?",
        (password_hash, user_id),
    )
    conn.commit()
    return True, "Password changed successfully"


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
