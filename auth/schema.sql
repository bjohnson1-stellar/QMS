-- Auth module schema: local user accounts with email + password

CREATE TABLE IF NOT EXISTS users (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    email                TEXT NOT NULL,
    display_name         TEXT NOT NULL,
    password_hash        TEXT,                              -- NULL until password is set
    role                 TEXT NOT NULL DEFAULT 'user'
                         CHECK (role IN ('admin', 'user', 'viewer')),
    is_active            INTEGER NOT NULL DEFAULT 1,
    must_change_password INTEGER NOT NULL DEFAULT 1,
    first_login          TEXT NOT NULL DEFAULT (datetime('now')),
    last_login           TEXT NOT NULL DEFAULT (datetime('now')),
    entra_oid            TEXT                               -- Legacy: nullable, kept for migration
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_entra_oid ON users(entra_oid);
