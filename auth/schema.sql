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

-- Module-level access: controls which modules a non-admin user can reach
CREATE TABLE IF NOT EXISTS user_module_access (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    module   TEXT NOT NULL
             CHECK (module IN ('projects', 'welding', 'pipeline', 'automation')),
    role     TEXT NOT NULL DEFAULT 'viewer'
             CHECK (role IN ('admin', 'editor', 'viewer')),
    UNIQUE(user_id, module)
);

CREATE INDEX IF NOT EXISTS idx_uma_user ON user_module_access(user_id);
