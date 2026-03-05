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
