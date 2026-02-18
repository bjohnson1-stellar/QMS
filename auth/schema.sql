-- Auth module schema: local user records synced from Entra ID

CREATE TABLE IF NOT EXISTS users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    entra_oid   TEXT UNIQUE,                    -- Entra Object ID (immutable identifier)
    email       TEXT NOT NULL,
    display_name TEXT NOT NULL,
    role        TEXT NOT NULL DEFAULT 'user'     -- admin | user | viewer
                CHECK (role IN ('admin', 'user', 'viewer')),
    is_active   INTEGER NOT NULL DEFAULT 1,
    first_login TEXT NOT NULL DEFAULT (datetime('now')),
    last_login  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_entra_oid ON users(entra_oid);
