-- SIS Quality - Quality Management Documents Schema Extension
-- For tracking procedures, forms, templates, and records
-- Run: sqlite3 D:\quality.db < schema-qm-docs.sql

-------------------------------------------------
-- PROCEDURES TABLE
-- SOPs, Work Instructions, Policies
-------------------------------------------------

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

-------------------------------------------------
-- FORMS REGISTRY
-- Blank forms and templates
-------------------------------------------------

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

-------------------------------------------------
-- RECORDS TABLE
-- Completed forms, audit evidence, signed documents
-------------------------------------------------

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

-------------------------------------------------
-- DOCUMENT REVISION HISTORY
-- Tracks all changes across document types
-------------------------------------------------

CREATE TABLE IF NOT EXISTS qm_document_history (
    id INTEGER PRIMARY KEY,
    document_type TEXT NOT NULL,  -- MODULE, PROCEDURE, FORM, RECORD
    document_id INTEGER NOT NULL,
    revision TEXT NOT NULL,
    change_summary TEXT,
    changed_by TEXT,
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    previous_file_hash TEXT,
    new_file_hash TEXT
);

-------------------------------------------------
-- TEMPLATES TABLE
-- Document templates (not forms - blank starting points)
-------------------------------------------------

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

-------------------------------------------------
-- UNIFIED INTAKE LOG FOR QM DOCUMENTS
-------------------------------------------------

CREATE TABLE IF NOT EXISTS qm_intake_log (
    id INTEGER PRIMARY KEY,
    file_name TEXT NOT NULL,
    source_path TEXT,
    destination_path TEXT,
    document_type TEXT,  -- MODULE, PROCEDURE, FORM, TEMPLATE, RECORD
    action TEXT,         -- routed, duplicate, needs_review, failed
    document_id INTEGER, -- ID in target table
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-------------------------------------------------
-- INDEXES
-------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_procedures_number ON qm_procedures(procedure_number);
CREATE INDEX IF NOT EXISTS idx_procedures_status ON qm_procedures(status);
CREATE INDEX IF NOT EXISTS idx_procedures_type ON qm_procedures(document_type);

CREATE INDEX IF NOT EXISTS idx_forms_number ON qm_forms(form_number);
CREATE INDEX IF NOT EXISTS idx_forms_status ON qm_forms(status);
CREATE INDEX IF NOT EXISTS idx_forms_procedure ON qm_forms(associated_procedure_id);
CREATE INDEX IF NOT EXISTS idx_forms_module ON qm_forms(associated_module_id);

CREATE INDEX IF NOT EXISTS idx_records_project ON qm_records(project_id);
CREATE INDEX IF NOT EXISTS idx_records_type ON qm_records(record_type);
CREATE INDEX IF NOT EXISTS idx_records_date ON qm_records(record_date);
CREATE INDEX IF NOT EXISTS idx_records_form ON qm_records(form_id);

CREATE INDEX IF NOT EXISTS idx_doc_history_type ON qm_document_history(document_type, document_id);
CREATE INDEX IF NOT EXISTS idx_doc_history_date ON qm_document_history(changed_at);

CREATE INDEX IF NOT EXISTS idx_templates_number ON qm_templates(template_number);
CREATE INDEX IF NOT EXISTS idx_templates_type ON qm_templates(template_type);

CREATE INDEX IF NOT EXISTS idx_qm_intake_log_date ON qm_intake_log(created_at);
CREATE INDEX IF NOT EXISTS idx_qm_intake_log_type ON qm_intake_log(document_type);

-------------------------------------------------
-- VIEWS
-------------------------------------------------

-- Procedures by status
CREATE VIEW IF NOT EXISTS v_procedures_by_status AS
SELECT
    status,
    document_type,
    COUNT(*) AS count,
    GROUP_CONCAT(procedure_number) AS numbers
FROM qm_procedures
GROUP BY status, document_type
ORDER BY status, document_type;

-- Forms with associated procedures
CREATE VIEW IF NOT EXISTS v_forms_with_procedures AS
SELECT
    f.form_number,
    f.title AS form_title,
    f.revision AS form_revision,
    f.status AS form_status,
    p.procedure_number,
    p.title AS procedure_title
FROM qm_forms f
LEFT JOIN qm_procedures p ON f.associated_procedure_id = p.id
ORDER BY f.form_number;

-- Records by project
CREATE VIEW IF NOT EXISTS v_records_by_project AS
SELECT
    p.number AS project_number,
    p.name AS project_name,
    r.record_type,
    COUNT(*) AS record_count,
    MIN(r.record_date) AS earliest,
    MAX(r.record_date) AS latest
FROM qm_records r
LEFT JOIN projects p ON r.project_id = p.id
GROUP BY r.project_id, r.record_type
ORDER BY p.number, r.record_type;

-- Recent document changes
CREATE VIEW IF NOT EXISTS v_recent_qm_changes AS
SELECT
    document_type,
    document_id,
    revision,
    change_summary,
    changed_by,
    changed_at
FROM qm_document_history
ORDER BY changed_at DESC
LIMIT 50;

-- QM documents summary
CREATE VIEW IF NOT EXISTS v_qm_summary AS
SELECT 'Procedures' AS type, COUNT(*) AS count FROM qm_procedures WHERE status != 'OBSOLETE'
UNION ALL
SELECT 'Forms', COUNT(*) FROM qm_forms WHERE status != 'OBSOLETE'
UNION ALL
SELECT 'Templates', COUNT(*) FROM qm_templates WHERE status = 'ACTIVE'
UNION ALL
SELECT 'Records', COUNT(*) FROM qm_records
UNION ALL
SELECT 'Modules', COUNT(*) FROM qm_modules WHERE status = 'Approved';
