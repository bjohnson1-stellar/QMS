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
    last_login           TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- Module-level access: controls which modules a non-admin user can reach
-- Module validation is handled in Python via get_web_modules() — no CHECK constraint
CREATE TABLE IF NOT EXISTS user_module_access (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    module   TEXT NOT NULL,
    role     TEXT NOT NULL DEFAULT 'viewer'
             CHECK (role IN ('admin', 'editor', 'viewer')),
    UNIQUE(user_id, module)
);

CREATE INDEX IF NOT EXISTS idx_uma_user ON user_module_access(user_id);

-- Business unit access: controls which BUs a non-admin user can see in projects
-- No entries = unrestricted (sees all BUs). Admins always bypass.
CREATE TABLE IF NOT EXISTS user_business_units (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id           INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    business_unit_id  INTEGER NOT NULL REFERENCES business_units(id) ON DELETE CASCADE,
    UNIQUE(user_id, business_unit_id)
);

CREATE INDEX IF NOT EXISTS idx_ubu_user ON user_business_units(user_id);
