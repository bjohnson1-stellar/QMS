"""
Incremental migrations for the auth module.

Adds password_hash and must_change_password columns to the users table
for local email+password authentication (replacing Entra ID SSO).
"""

import sqlite3

from qms.core.logging import get_logger

logger = get_logger("qms.auth.migrations")


def run_auth_migrations(conn: sqlite3.Connection) -> None:
    """Run all auth schema migrations (idempotent)."""
    _add_password_columns(conn)
    _ensure_unique_email(conn)
    _create_module_access_table(conn)
    _drop_module_check_constraint(conn)
    _drop_entra_oid(conn)
    _create_business_unit_access_table(conn)
    _fix_module_access_fk(conn)
    _add_employee_link(conn)


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    cols = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(c["name"] == column for c in cols)


def _add_password_columns(conn: sqlite3.Connection) -> None:
    """Add password_hash and must_change_password if missing."""
    if not _column_exists(conn, "users", "password_hash"):
        logger.info("Adding password_hash column to users")
        conn.execute("ALTER TABLE users ADD COLUMN password_hash TEXT")

    if not _column_exists(conn, "users", "must_change_password"):
        logger.info("Adding must_change_password column to users")
        conn.execute(
            "ALTER TABLE users ADD COLUMN must_change_password INTEGER NOT NULL DEFAULT 1"
        )

    conn.commit()


def _create_module_access_table(conn: sqlite3.Connection) -> None:
    """Create user_module_access table if it doesn't exist."""
    existing = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='user_module_access'"
    ).fetchone()
    if not existing:
        logger.info("Creating user_module_access table")
        conn.execute("""
            CREATE TABLE user_module_access (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                module   TEXT NOT NULL,
                role     TEXT NOT NULL DEFAULT 'viewer'
                         CHECK (role IN ('admin', 'editor', 'viewer')),
                UNIQUE(user_id, module)
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_uma_user ON user_module_access(user_id)"
        )
        conn.commit()


def _ensure_unique_email(conn: sqlite3.Connection) -> None:
    """Create a unique index on email if it doesn't exist."""
    # Check if unique index already exists
    indexes = conn.execute(
        "SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name='users'"
    ).fetchall()

    has_unique_email = any(
        idx["sql"] and "UNIQUE" in idx["sql"] and "email" in idx["sql"]
        for idx in indexes
    )

    if not has_unique_email:
        logger.info("Creating unique index on users.email")
        # Drop the old non-unique index first
        conn.execute("DROP INDEX IF EXISTS idx_users_email")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email)")
        conn.commit()


def _drop_module_check_constraint(conn: sqlite3.Connection) -> None:
    """
    Recreate user_module_access without the CHECK constraint on module.

    Module validation is now handled in Python via get_web_modules(),
    so the CHECK constraint is no longer needed (and blocks adding new modules).
    """
    # Check if the table has a CHECK constraint on module
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='user_module_access'"
    ).fetchone()

    if not row or not row["sql"]:
        return

    # If there's no CHECK on module, nothing to do
    if "CHECK" not in row["sql"] or "module" not in row["sql"]:
        return

    # Only proceed if the CHECK actually constrains the module column
    ddl = row["sql"]
    if "CHECK (module IN" not in ddl and "CHECK(module IN" not in ddl:
        return

    logger.info("Recreating user_module_access without module CHECK constraint")

    conn.execute("ALTER TABLE user_module_access RENAME TO _uma_old")
    conn.execute("""
        CREATE TABLE user_module_access (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            module   TEXT NOT NULL,
            role     TEXT NOT NULL DEFAULT 'viewer'
                     CHECK (role IN ('admin', 'editor', 'viewer')),
            UNIQUE(user_id, module)
        )
    """)
    conn.execute("""
        INSERT INTO user_module_access (id, user_id, module, role)
        SELECT id, user_id, module, role FROM _uma_old
    """)
    conn.execute("DROP TABLE _uma_old")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_uma_user ON user_module_access(user_id)"
    )
    conn.commit()


def _create_business_unit_access_table(conn: sqlite3.Connection) -> None:
    """Create user_business_units table if it doesn't exist."""
    existing = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='user_business_units'"
    ).fetchone()
    if not existing:
        logger.info("Creating user_business_units table")
        conn.execute("""
            CREATE TABLE user_business_units (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id           INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                business_unit_id  INTEGER NOT NULL REFERENCES business_units(id) ON DELETE CASCADE,
                UNIQUE(user_id, business_unit_id)
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ubu_user ON user_business_units(user_id)"
        )
        conn.commit()


def _drop_entra_oid(conn: sqlite3.Connection) -> None:
    """Drop the legacy entra_oid column from users (table rebuild)."""
    if not _column_exists(conn, "users", "entra_oid"):
        return

    logger.info("Dropping legacy entra_oid column from users")

    conn.execute("DROP INDEX IF EXISTS idx_users_entra_oid")
    conn.execute("ALTER TABLE users RENAME TO _users_old")
    conn.execute("""
        CREATE TABLE users (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            email                TEXT NOT NULL,
            display_name         TEXT NOT NULL,
            password_hash        TEXT,
            role                 TEXT NOT NULL DEFAULT 'user'
                                 CHECK (role IN ('admin', 'user', 'viewer')),
            is_active            INTEGER NOT NULL DEFAULT 1,
            must_change_password INTEGER NOT NULL DEFAULT 1,
            first_login          TEXT NOT NULL DEFAULT (datetime('now')),
            last_login           TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        INSERT INTO users (id, email, display_name, password_hash, role,
                           is_active, must_change_password, first_login, last_login)
        SELECT id, email, display_name, password_hash, role,
               is_active, must_change_password, first_login, last_login
        FROM _users_old
    """)
    conn.execute("DROP TABLE _users_old")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email)")
    conn.commit()


def _fix_module_access_fk(conn: sqlite3.Connection) -> None:
    """
    Rebuild user_module_access if its FK points to a stale table name.

    The _drop_entra_oid migration renamed `users` → `_users_old`, which
    caused SQLite to rewrite the FK in user_module_access from users(id)
    to _users_old(id).  This migration detects the stale reference and
    rebuilds the table with the correct FK.
    """
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='user_module_access'"
    ).fetchone()

    if not row or not row["sql"]:
        return

    # Only rebuild if the FK is pointing at the wrong table
    if "_users_old" not in row["sql"]:
        return

    logger.info("Fixing user_module_access FK (was pointing to _users_old)")

    conn.execute("ALTER TABLE user_module_access RENAME TO _uma_fix")
    conn.execute("""
        CREATE TABLE user_module_access (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            module   TEXT NOT NULL,
            role     TEXT NOT NULL DEFAULT 'viewer'
                     CHECK (role IN ('admin', 'editor', 'viewer')),
            UNIQUE(user_id, module)
        )
    """)
    conn.execute("""
        INSERT INTO user_module_access (id, user_id, module, role)
        SELECT id, user_id, module, role FROM _uma_fix
    """)
    conn.execute("DROP TABLE _uma_fix")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_uma_user ON user_module_access(user_id)"
    )
    conn.commit()


def _add_employee_link(conn: sqlite3.Connection) -> None:
    """Add employee_id FK column to users table (links auth → workforce)."""
    if _column_exists(conn, "users", "employee_id"):
        return
    logger.info("Adding employee_id column to users")
    conn.execute(
        "ALTER TABLE users ADD COLUMN employee_id TEXT REFERENCES employees(id)"
    )
    conn.commit()
