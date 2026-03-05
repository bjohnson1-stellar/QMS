-- State Licenses — company and employee license tracking
-- FK: employees.id (optional employee link)

CREATE TABLE IF NOT EXISTS state_licenses (
    id              TEXT PRIMARY KEY,
    holder_type     TEXT,                 -- legacy; nullable for backward compat
    employee_id     TEXT,
    business_entity TEXT,                 -- company / business entity name
    state_code      TEXT NOT NULL,        -- 2-letter state abbreviation
    license_type    TEXT NOT NULL,         -- e.g. 'Contractor', 'Journeyman Plumber'
    license_number  TEXT NOT NULL,
    holder_name     TEXT NOT NULL,         -- company name or employee name
    issued_date     TEXT,                  -- ISO 8601
    expiration_date TEXT,                  -- ISO 8601 (NULL = no expiry)
    reciprocal_state TEXT,                 -- 2-letter code of reciprocal state (NULL = none)
    association_date TEXT,                 -- ISO 8601 — when holder became associated
    disassociation_date TEXT,              -- ISO 8601 — when holder disassociated
    status          TEXT NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active', 'expired', 'pending', 'revoked', 'disassociation')),
    notes           TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
    created_by      TEXT,
    FOREIGN KEY (employee_id) REFERENCES employees(id)
);

CREATE INDEX IF NOT EXISTS idx_state_licenses_holder_type
    ON state_licenses(holder_type);
CREATE INDEX IF NOT EXISTS idx_state_licenses_state_code
    ON state_licenses(state_code);
CREATE INDEX IF NOT EXISTS idx_state_licenses_status
    ON state_licenses(status);
CREATE INDEX IF NOT EXISTS idx_state_licenses_expiration
    ON state_licenses(expiration_date);

-- State licensing board reference data
CREATE TABLE IF NOT EXISTS state_license_boards (
    state_code  TEXT PRIMARY KEY,   -- 2-letter
    board_name  TEXT NOT NULL,
    website_url TEXT,
    phone       TEXT,
    notes       TEXT,
    updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by  TEXT
);

-- Scope categories (construction disciplines)
CREATE TABLE IF NOT EXISTS scope_categories (
    id         TEXT PRIMARY KEY,
    name       TEXT NOT NULL UNIQUE,
    sort_order INTEGER DEFAULT 0
);

-- Junction: which scopes a license covers
CREATE TABLE IF NOT EXISTS license_scope_map (
    license_id TEXT NOT NULL,
    scope_id   TEXT NOT NULL,
    PRIMARY KEY (license_id, scope_id),
    FOREIGN KEY (license_id) REFERENCES state_licenses(id) ON DELETE CASCADE,
    FOREIGN KEY (scope_id) REFERENCES scope_categories(id) ON DELETE CASCADE
);

-- Per-state CE requirements by license type
CREATE TABLE IF NOT EXISTS ce_requirements (
    id                    TEXT PRIMARY KEY,
    state_code            TEXT NOT NULL,
    license_type          TEXT NOT NULL,
    hours_required        REAL NOT NULL,
    period_months         INTEGER NOT NULL,
    provider_requirements TEXT,
    notes                 TEXT,
    created_at            TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at            TEXT NOT NULL DEFAULT (datetime('now')),
    created_by            TEXT,
    UNIQUE(state_code, license_type)
);

-- Individual CE credit records
CREATE TABLE IF NOT EXISTS ce_credits (
    id               TEXT PRIMARY KEY,
    employee_id      TEXT NOT NULL,
    license_id       TEXT NOT NULL,
    provider         TEXT,
    course_name      TEXT NOT NULL,
    hours            REAL NOT NULL,
    completion_date  TEXT NOT NULL,
    certificate_file TEXT,
    status           TEXT NOT NULL DEFAULT 'approved'
                     CHECK (status IN ('approved', 'pending', 'rejected')),
    notes            TEXT,
    created_at       TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at       TEXT NOT NULL DEFAULT (datetime('now')),
    created_by       TEXT,
    FOREIGN KEY (employee_id) REFERENCES employees(id),
    FOREIGN KEY (license_id) REFERENCES state_licenses(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_ce_credits_license ON ce_credits(license_id);
CREATE INDEX IF NOT EXISTS idx_ce_credits_employee ON ce_credits(employee_id);
CREATE INDEX IF NOT EXISTS idx_ce_requirements_state ON ce_requirements(state_code);

-- Pre-computed expiry view for dashboard queries
CREATE VIEW IF NOT EXISTS v_expiring_licenses AS
SELECT
    sl.*,
    CASE
        WHEN sl.expiration_date IS NULL THEN NULL
        ELSE CAST(julianday(sl.expiration_date) - julianday('now') AS INTEGER)
    END AS days_until_expiry
FROM state_licenses sl
WHERE sl.status = 'active';
