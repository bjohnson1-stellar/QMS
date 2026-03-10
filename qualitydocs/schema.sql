-- =============================================================================
-- QMS Quality Documents Schema
-- Quality manual CMS, procedures, forms, templates, records
-- =============================================================================

-- Quality manual modules
CREATE TABLE IF NOT EXISTS qm_modules (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    module_number   INTEGER UNIQUE NOT NULL,
    version         TEXT,
    effective_date  TEXT,
    status          TEXT CHECK(status IN ('Draft','UnderReview','Approved','Superseded','Obsolete')),
    title           TEXT,
    description     TEXT,
    xml_source      TEXT,
    loaded_at       TEXT DEFAULT (datetime('now'))
);

-- Module sections
CREATE TABLE IF NOT EXISTS qm_sections (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    module_id         INTEGER NOT NULL REFERENCES qm_modules(id) ON DELETE CASCADE,
    section_number    TEXT NOT NULL,
    title             TEXT,
    display_order     INTEGER,
    related_sections  TEXT,
    related_modules   TEXT,
    UNIQUE(module_id, section_number)
);

-- Section subsections
CREATE TABLE IF NOT EXISTS qm_subsections (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    section_id       INTEGER NOT NULL REFERENCES qm_sections(id) ON DELETE CASCADE,
    letter           TEXT NOT NULL,
    title            TEXT,
    subsection_type  TEXT CHECK(subsection_type IN (
        'PurposeAndScope','Requirements','Procedures',
        'Responsibilities','Documentation',
        'VerificationAndCompliance','General'
    )),
    display_order    INTEGER,
    full_ref         TEXT,
    UNIQUE(section_id, letter)
);

-- Content blocks within subsections
CREATE TABLE IF NOT EXISTS qm_content_blocks (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    subsection_id   INTEGER NOT NULL REFERENCES qm_subsections(id) ON DELETE CASCADE,
    block_type      TEXT NOT NULL CHECK(block_type IN (
        'HeadingParagraph','Paragraph','SubHeading',
        'BulletList','NumberedList','Table','Note',
        'ResponsibilityBlock'
    )),
    content         TEXT,
    level           INTEGER,
    display_order   INTEGER,
    xml_fragment    TEXT
);

-- Cross-references between modules/sections
CREATE TABLE IF NOT EXISTS qm_cross_references (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    source_module_id       INTEGER REFERENCES qm_modules(id),
    source_subsection_id   INTEGER REFERENCES qm_subsections(id),
    source_content_id      INTEGER REFERENCES qm_content_blocks(id),
    target_module          INTEGER,
    target_section         TEXT,
    target_subsection      TEXT,
    ref_type               TEXT CHECK(ref_type IN ('internal','external','code','standard')),
    detection_method       TEXT CHECK(detection_method IN ('explicit','prose_detected')),
    original_text          TEXT,
    is_valid               INTEGER DEFAULT 0
);

-- Code/standard references found in content
CREATE TABLE IF NOT EXISTS qm_code_references (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    subsection_id     INTEGER REFERENCES qm_subsections(id),
    content_block_id  INTEGER REFERENCES qm_content_blocks(id),
    code              TEXT NOT NULL,
    organization      TEXT,
    code_section      TEXT,
    original_text     TEXT,
    detection_method  TEXT CHECK(detection_method IN ('explicit','prose_detected'))
);

-- Responsibility assignments
CREATE TABLE IF NOT EXISTS qm_responsibility_assignments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    subsection_id   INTEGER REFERENCES qm_subsections(id),
    role            TEXT NOT NULL,
    responsibility  TEXT,
    display_order   INTEGER
);

-- Full-text search for QM content
CREATE VIRTUAL TABLE IF NOT EXISTS qm_content_fts USING fts5(
    module_number,
    section_number,
    subsection_ref,
    subsection_type,
    block_type,
    content,
    tokenize='porter unicode61'
);

-- Procedures (SOP, WI, Policy)
CREATE TABLE IF NOT EXISTS qm_procedures (
    id INTEGER PRIMARY KEY,
    procedure_number TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    revision TEXT DEFAULT 'A',
    revision_date DATE,
    effective_date DATE,
    document_type TEXT CHECK(document_type IN ('SOP', 'WI', 'POLICY', 'PROCEDURE')),
    department TEXT,
    owner TEXT,
    file_path TEXT,
    file_hash TEXT,
    page_count INTEGER,
    status TEXT DEFAULT 'DRAFT' CHECK(status IN ('DRAFT', 'REVIEW', 'APPROVED', 'SUPERSEDED', 'OBSOLETE')),
    supersedes_id INTEGER REFERENCES qm_procedures(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Forms
CREATE TABLE IF NOT EXISTS qm_forms (
    id INTEGER PRIMARY KEY,
    form_number TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    revision TEXT DEFAULT 'A',
    revision_date DATE,
    associated_procedure_id INTEGER REFERENCES qm_procedures(id),
    associated_module_id INTEGER REFERENCES qm_modules(id),
    file_path TEXT,
    file_hash TEXT,
    status TEXT DEFAULT 'ACTIVE' CHECK(status IN ('DRAFT', 'ACTIVE', 'SUPERSEDED', 'OBSOLETE')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Quality records
CREATE TABLE IF NOT EXISTS qm_records (
    id INTEGER PRIMARY KEY,
    record_type TEXT NOT NULL,
    form_id INTEGER REFERENCES qm_forms(id),
    project_id INTEGER REFERENCES projects(id),
    record_date DATE NOT NULL,
    description TEXT,
    file_path TEXT,
    file_hash TEXT,
    retention_years INTEGER DEFAULT 7,
    retention_expires DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Templates
CREATE TABLE IF NOT EXISTS qm_templates (
    id INTEGER PRIMARY KEY,
    template_number TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    revision TEXT DEFAULT 'A',
    revision_date DATE,
    template_type TEXT CHECK(template_type IN ('PROCEDURE', 'FORM', 'REPORT', 'CHECKLIST', 'OTHER')),
    file_path TEXT,
    file_hash TEXT,
    status TEXT DEFAULT 'ACTIVE',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Document revision history
CREATE TABLE IF NOT EXISTS qm_document_history (
    id INTEGER PRIMARY KEY,
    document_type TEXT NOT NULL,
    document_id INTEGER NOT NULL,
    revision TEXT NOT NULL,
    change_summary TEXT,
    changed_by TEXT,
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    previous_file_hash TEXT,
    new_file_hash TEXT
);

-- QM intake log
CREATE TABLE IF NOT EXISTS qm_intake_log (
    id INTEGER PRIMARY KEY,
    file_name TEXT NOT NULL,
    source_path TEXT,
    destination_path TEXT,
    document_type TEXT,
    action TEXT,
    document_id INTEGER,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =============================================================================
-- M3 Quality Programs & M4 SOPs (v0.3)
-- =============================================================================

-- M3 Quality Programs
CREATE TABLE IF NOT EXISTS qm_programs (
    id                        INTEGER PRIMARY KEY AUTOINCREMENT,
    program_id                TEXT UNIQUE NOT NULL,
    title                     TEXT NOT NULL,
    description               TEXT,
    primary_codes             TEXT,
    qualification_requirements TEXT,
    status                    TEXT CHECK(status IN ('draft','under_review','approved','published','superseded','obsolete')) DEFAULT 'draft',
    version                   TEXT DEFAULT '1.0',
    created_at                TEXT DEFAULT (datetime('now')),
    updated_at                TEXT DEFAULT (datetime('now'))
);

-- M4 SOP Categories
CREATE TABLE IF NOT EXISTS qm_categories (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    category_code     TEXT UNIQUE NOT NULL,
    module_number     INTEGER DEFAULT 4,
    name              TEXT NOT NULL,
    description       TEXT,
    parent_program_id INTEGER REFERENCES qm_programs(id) ON DELETE SET NULL,
    display_order     INTEGER,
    created_at        TEXT DEFAULT (datetime('now'))
);

-- M4 Standard Operating Procedures
CREATE TABLE IF NOT EXISTS qm_sops (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id         TEXT UNIQUE NOT NULL,
    title               TEXT NOT NULL,
    category_id         INTEGER NOT NULL REFERENCES qm_categories(id),
    status              TEXT CHECK(status IN ('draft','under_review','approved','published','superseded','obsolete')) DEFAULT 'draft',
    scope_tags          TEXT DEFAULT '[]',
    version             TEXT DEFAULT '1.0',
    revision            TEXT DEFAULT 'A',
    file_path           TEXT,
    file_hash           TEXT,
    content_text        TEXT,
    summary             TEXT,
    approved_by         TEXT,
    approved_at         TEXT,
    effective_date      TEXT,
    review_cycle_months INTEGER DEFAULT 24,
    created_at          TEXT DEFAULT (datetime('now')),
    updated_at          TEXT DEFAULT (datetime('now'))
);

-- M3-M4 linkage (many-to-many)
CREATE TABLE IF NOT EXISTS qm_program_sops (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    program_id INTEGER NOT NULL REFERENCES qm_programs(id) ON DELETE CASCADE,
    sop_id     INTEGER NOT NULL REFERENCES qm_sops(id) ON DELETE CASCADE,
    UNIQUE(program_id, sop_id)
);

-- Code references detected in SOPs
CREATE TABLE IF NOT EXISTS qm_sop_code_references (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    sop_id           INTEGER NOT NULL REFERENCES qm_sops(id) ON DELETE CASCADE,
    code             TEXT NOT NULL,
    organization     TEXT,
    code_section     TEXT,
    original_text    TEXT,
    detection_method TEXT CHECK(detection_method IN ('explicit','ai_detected','prose_detected'))
);

-- SOP intake/classification pipeline tracking
CREATE TABLE IF NOT EXISTS qm_sop_intake (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    file_name              TEXT NOT NULL,
    file_path              TEXT,
    file_hash              TEXT,
    status                 TEXT CHECK(status IN ('pending','analyzing','classified','approved','rejected','error')) DEFAULT 'pending',
    ai_classification      TEXT,
    suggested_category_id  INTEGER REFERENCES qm_categories(id),
    suggested_scope_tags   TEXT,
    suggested_program_ids  TEXT,
    suggested_document_id  TEXT,
    user_overrides         TEXT,
    final_sop_id           INTEGER REFERENCES qm_sops(id),
    error_message          TEXT,
    created_at             TEXT DEFAULT (datetime('now')),
    processed_at           TEXT
);

-- SOP revision/approval history
CREATE TABLE IF NOT EXISTS qm_sop_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    sop_id          INTEGER NOT NULL REFERENCES qm_sops(id) ON DELETE CASCADE,
    action          TEXT NOT NULL CHECK(action IN ('created','submitted','approved','rejected','published','revised','superseded')),
    actor           TEXT,
    notes           TEXT,
    previous_status TEXT,
    new_status      TEXT,
    created_at      TEXT DEFAULT (datetime('now'))
);

-- NOTE: FTS extension for SOP content planned for Phase 18 (rebuild qm_content_fts to include qm_sops.content_text)
