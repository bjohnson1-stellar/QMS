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
    website_url TEXT,               -- main portal
    lookup_url  TEXT,               -- license verification/search URL
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

-- Per-user portal credentials for license management
CREATE TABLE IF NOT EXISTS license_portal_credentials (
    id          TEXT PRIMARY KEY,
    license_id  TEXT NOT NULL,
    user_id     TEXT NOT NULL,
    portal_url  TEXT,                -- override per-license portal URL
    username    TEXT NOT NULL,
    password_enc TEXT NOT NULL,       -- Fernet-encrypted password
    notes       TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(license_id, user_id),
    FOREIGN KEY (license_id) REFERENCES state_licenses(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_portal_creds_user ON license_portal_credentials(user_id);

-- License event history (renewal, amendment, suspension, etc.)
CREATE TABLE IF NOT EXISTS license_events (
    id              TEXT PRIMARY KEY,
    license_id      TEXT NOT NULL,
    event_type      TEXT NOT NULL
                    CHECK (event_type IN ('issued','renewed','amended','suspended','revoked','expired','reinstated')),
    event_date      TEXT NOT NULL,        -- ISO 8601 (YYYY-MM-DD)
    notes           TEXT,
    fee_amount      REAL,
    fee_type        TEXT
                    CHECK (fee_type IS NULL OR fee_type IN ('application','renewal','amendment','late_fee','other')),
    created_by      TEXT DEFAULT 'system',
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (license_id) REFERENCES state_licenses(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_license_events_license ON license_events(license_id);
CREATE INDEX IF NOT EXISTS idx_license_events_type ON license_events(event_type);

-- Notification rules — configurable alert triggers
CREATE TABLE IF NOT EXISTS license_notification_rules (
    id              INTEGER PRIMARY KEY,
    rule_name       TEXT UNIQUE NOT NULL,
    notification_type TEXT NOT NULL,          -- expiration_warning, ce_deadline, renewal_reminder
    entity_type     TEXT NOT NULL,            -- license, ce_credit
    days_before     INTEGER NOT NULL,
    priority        TEXT DEFAULT 'normal',    -- urgent, high, normal, low
    repeat_interval_days INTEGER,
    is_active       INTEGER DEFAULT 1,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Generated notifications (alerts)
CREATE TABLE IF NOT EXISTS license_notifications (
    id              INTEGER PRIMARY KEY,
    notification_type TEXT NOT NULL,
    entity_type     TEXT NOT NULL,
    entity_id       TEXT NOT NULL,            -- UUID (matches state_licenses.id)
    rule_id         INTEGER REFERENCES license_notification_rules(id),
    priority        TEXT DEFAULT 'normal',
    due_date        TEXT,                     -- ISO 8601
    days_until_due  INTEGER,
    title           TEXT NOT NULL,
    message         TEXT NOT NULL,
    status          TEXT DEFAULT 'active',    -- active, acknowledged, resolved, auto_resolved
    acknowledged_by TEXT,
    acknowledged_at TEXT,
    resolved_by     TEXT,
    resolved_at     TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(entity_type, entity_id, rule_id, status)
);

CREATE INDEX IF NOT EXISTS idx_license_notifications_status ON license_notifications(status);
CREATE INDEX IF NOT EXISTS idx_license_notifications_type ON license_notifications(notification_type);
CREATE INDEX IF NOT EXISTS idx_license_notifications_entity ON license_notifications(entity_type, entity_id);

-- Documents attached to licenses (certificates, applications, bonds, etc.)
CREATE TABLE IF NOT EXISTS license_documents (
    id                TEXT PRIMARY KEY,
    license_id        TEXT NOT NULL,
    doc_type          TEXT NOT NULL
                      CHECK (doc_type IN ('certificate','application','correspondence','receipt','bond','insurance','other')),
    filename          TEXT NOT NULL,        -- sanitized filename on disk
    original_filename TEXT NOT NULL,        -- user's original filename
    file_size         INTEGER,             -- bytes
    mime_type         TEXT,
    description       TEXT,
    uploaded_by       TEXT DEFAULT 'system',
    uploaded_at       TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (license_id) REFERENCES state_licenses(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_license_documents_license ON license_documents(license_id);
CREATE INDEX IF NOT EXISTS idx_license_documents_type ON license_documents(doc_type);

-- Timestamped text notes per license
CREATE TABLE IF NOT EXISTS license_notes (
    id          TEXT PRIMARY KEY,
    license_id  TEXT NOT NULL,
    note_text   TEXT NOT NULL,
    created_by  TEXT DEFAULT 'system',
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (license_id) REFERENCES state_licenses(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_license_notes_license ON license_notes(license_id);

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
