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

-- Business entities (parent companies, subsidiaries, DBAs)
CREATE TABLE IF NOT EXISTS business_entities (
    id                      TEXT PRIMARY KEY,
    name                    TEXT NOT NULL,
    entity_type             TEXT NOT NULL DEFAULT 'corporation'
                            CHECK (entity_type IN ('corporation','llc','partnership','sole_proprietorship','subsidiary','dba','branch')),
    parent_id               TEXT,
    ein                     TEXT,
    state_of_incorporation  TEXT,
    address                 TEXT,
    city                    TEXT,
    state_code              TEXT,
    zip_code                TEXT,
    phone                   TEXT,
    website                 TEXT,
    notes                   TEXT,
    status                  TEXT NOT NULL DEFAULT 'active'
                            CHECK (status IN ('active','inactive','dissolved')),
    created_at              TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at              TEXT NOT NULL DEFAULT (datetime('now')),
    created_by              TEXT,
    FOREIGN KEY (parent_id) REFERENCES business_entities(id)
);

CREATE INDEX IF NOT EXISTS idx_business_entities_parent ON business_entities(parent_id);
CREATE INDEX IF NOT EXISTS idx_business_entities_type ON business_entities(entity_type);
CREATE INDEX IF NOT EXISTS idx_business_entities_status ON business_entities(status);
CREATE INDEX IF NOT EXISTS idx_business_entities_state ON business_entities(state_of_incorporation);

-- Entity registrations (SoS filings, DBE certs, minority certs, etc.)
CREATE TABLE IF NOT EXISTS entity_registrations (
    id                  TEXT PRIMARY KEY,
    entity_id           TEXT NOT NULL,
    registration_type   TEXT NOT NULL
                        CHECK (registration_type IN ('secretary_of_state','dbe','mbe','wbe','sbe','hub','sdvosb','other')),
    state_code          TEXT NOT NULL,
    registration_number TEXT,
    issuing_authority   TEXT,
    issued_date         TEXT,
    expiration_date     TEXT,
    status              TEXT NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active','expired','pending','revoked','suspended')),
    filing_frequency    TEXT
                        CHECK (filing_frequency IS NULL OR filing_frequency IN ('annual','biennial','triennial','one_time')),
    next_filing_date    TEXT,
    fee_amount          REAL,
    notes               TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now')),
    created_by          TEXT,
    UNIQUE(entity_id, registration_type, state_code),
    FOREIGN KEY (entity_id) REFERENCES business_entities(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_entity_registrations_entity ON entity_registrations(entity_id);
CREATE INDEX IF NOT EXISTS idx_entity_registrations_type ON entity_registrations(registration_type);
CREATE INDEX IF NOT EXISTS idx_entity_registrations_state ON entity_registrations(state_code);
CREATE INDEX IF NOT EXISTS idx_entity_registrations_status ON entity_registrations(status);
CREATE INDEX IF NOT EXISTS idx_entity_registrations_expiration ON entity_registrations(expiration_date);

-- State regulatory requirements (fee schedules, compliance rules per state/license type)
CREATE TABLE IF NOT EXISTS state_requirements (
    id                    TEXT PRIMARY KEY,
    state_code            TEXT NOT NULL,        -- 2-letter state abbreviation
    license_type          TEXT NOT NULL,        -- e.g. 'Contractor', 'Master Plumber'
    requirement_type      TEXT NOT NULL
                          CHECK (requirement_type IN (
                              'initial_application','renewal','ce_requirement',
                              'bond','insurance','exam','background_check','fingerprinting')),
    description           TEXT,
    fee_amount            REAL,
    fee_frequency         TEXT
                          CHECK (fee_frequency IS NULL OR fee_frequency IN (
                              'one_time','annual','biennial','triennial','per_renewal')),
    renewal_period_months INTEGER,              -- how often this requirement recurs
    authority_name        TEXT,                 -- issuing/enforcing authority
    authority_url         TEXT,                 -- link to authority website
    effective_date        TEXT,                 -- when this requirement became effective
    notes                 TEXT,
    created_at            TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at            TEXT NOT NULL DEFAULT (datetime('now')),
    created_by            TEXT,
    UNIQUE(state_code, license_type, requirement_type)
);

CREATE INDEX IF NOT EXISTS idx_state_requirements_state ON state_requirements(state_code);
CREATE INDEX IF NOT EXISTS idx_state_requirements_type ON state_requirements(requirement_type);
CREATE INDEX IF NOT EXISTS idx_state_requirements_license_type ON state_requirements(license_type);

-- CE providers — organizations offering continuing education
CREATE TABLE IF NOT EXISTS ce_providers (
    id                    TEXT PRIMARY KEY,
    name                  TEXT NOT NULL UNIQUE,
    accreditation_body    TEXT,
    accreditation_number  TEXT,
    contact_email         TEXT,
    contact_phone         TEXT,
    website               TEXT,
    notes                 TEXT,
    is_active             INTEGER NOT NULL DEFAULT 1,
    created_at            TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at            TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_ce_providers_active ON ce_providers(is_active);

-- CE courses — catalog of available courses from providers
CREATE TABLE IF NOT EXISTS ce_courses (
    id                TEXT PRIMARY KEY,
    provider_id       TEXT REFERENCES ce_providers(id),
    title             TEXT NOT NULL,
    description       TEXT,
    hours             REAL NOT NULL,
    format            TEXT CHECK (format IS NULL OR format IN (
                          'online','classroom','self_study','webinar','conference','other')),
    states_accepted   TEXT NOT NULL DEFAULT '[]',   -- JSON array of state codes
    license_types     TEXT NOT NULL DEFAULT '[]',   -- JSON array of license types
    url               TEXT,
    is_active         INTEGER NOT NULL DEFAULT 1,
    created_at        TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at        TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(provider_id, title)
);

CREATE INDEX IF NOT EXISTS idx_ce_courses_provider ON ce_courses(provider_id);
CREATE INDEX IF NOT EXISTS idx_ce_courses_active ON ce_courses(is_active);

-- Junction: link CE credits to catalog courses
CREATE TABLE IF NOT EXISTS ce_credit_courses (
    credit_id TEXT NOT NULL REFERENCES ce_credits(id) ON DELETE CASCADE,
    course_id TEXT NOT NULL REFERENCES ce_courses(id) ON DELETE CASCADE,
    PRIMARY KEY (credit_id, course_id)
);

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
