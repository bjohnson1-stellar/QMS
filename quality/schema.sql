-- =============================================================================
-- QMS Quality Issues Schema
-- Unified quality issue tracking: observations, NCRs, CARs, deficiencies,
-- punch items. Supports audit trail, issue linking, tagging, corrective
-- actions, and cross-project analytics.
-- =============================================================================

-- Root cause taxonomy (lookup table)
CREATE TABLE IF NOT EXISTS root_causes (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    category TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Seed standard root causes
INSERT OR IGNORE INTO root_causes (name, description, category) VALUES
    ('Workmanship', 'Quality of work performed by trades or subcontractors', 'execution'),
    ('Materials', 'Defective, incorrect, or substandard materials', 'supply'),
    ('Design/Engineering', 'Design errors, omissions, or conflicts in drawings/specs', 'design'),
    ('Environmental', 'Weather, site conditions, or environmental factors', 'external'),
    ('Procedural', 'Failure to follow established procedures or specifications', 'process'),
    ('Subcontractor', 'Subcontractor performance, coordination, or compliance', 'execution'),
    ('Equipment/Tools', 'Equipment malfunction, improper tools, or calibration issues', 'supply'),
    ('Other', 'Root cause does not fit standard categories', 'other');

-- Flexible tag definitions
CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    color TEXT,
    description TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Quality issues (main table — all issue types)
CREATE TABLE IF NOT EXISTS quality_issues (
    id INTEGER PRIMARY KEY,
    type TEXT NOT NULL CHECK (type IN ('observation', 'ncr', 'car', 'deficiency', 'punch', 'other')),
    title TEXT NOT NULL,
    description TEXT,
    project_id INTEGER REFERENCES projects(id),
    business_unit_id INTEGER REFERENCES business_units(id),
    location TEXT,
    trade TEXT,
    severity TEXT CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    priority TEXT CHECK (priority IN ('low', 'medium', 'high', 'urgent')),
    status TEXT DEFAULT 'open' CHECK (status IN ('open', 'in_review', 'in_progress', 'resolved', 'closed', 'deferred')),
    root_cause_id INTEGER REFERENCES root_causes(id),
    assigned_to TEXT REFERENCES employees(id),
    reported_by TEXT,
    due_date TEXT,
    resolved_by TEXT REFERENCES employees(id),
    resolved_at TEXT,
    resolution_notes TEXT,
    estimated_cost REAL,
    source TEXT DEFAULT 'manual' CHECK (source IN ('manual', 'procore', 'mobile', 'import')),
    source_id TEXT,
    source_project_id TEXT,
    source_url TEXT,
    source_synced_at TEXT,
    metadata TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_qi_project ON quality_issues(project_id);
CREATE INDEX IF NOT EXISTS idx_qi_bu ON quality_issues(business_unit_id);
CREATE INDEX IF NOT EXISTS idx_qi_type ON quality_issues(type);
CREATE INDEX IF NOT EXISTS idx_qi_status ON quality_issues(status);
CREATE INDEX IF NOT EXISTS idx_qi_trade ON quality_issues(trade);
CREATE INDEX IF NOT EXISTS idx_qi_severity ON quality_issues(severity);
CREATE UNIQUE INDEX IF NOT EXISTS idx_qi_source_dedup ON quality_issues(source, source_id)
    WHERE source_id IS NOT NULL;

-- Quality issue attachments (photos, documents, voice notes)
CREATE TABLE IF NOT EXISTS quality_issue_attachments (
    id INTEGER PRIMARY KEY,
    issue_id INTEGER NOT NULL REFERENCES quality_issues(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    filepath TEXT NOT NULL,
    file_type TEXT CHECK (file_type IN ('image', 'document', 'video', 'audio')),
    file_size INTEGER,
    description TEXT,
    source_url TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_qia_issue ON quality_issue_attachments(issue_id);

-- Quality issue audit trail (every field change logged)
CREATE TABLE IF NOT EXISTS quality_issue_history (
    id INTEGER PRIMARY KEY,
    issue_id INTEGER NOT NULL REFERENCES quality_issues(id) ON DELETE CASCADE,
    field_changed TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    changed_by TEXT REFERENCES employees(id),
    changed_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_qih_issue ON quality_issue_history(issue_id);
CREATE INDEX IF NOT EXISTS idx_qih_changed_at ON quality_issue_history(changed_at);

-- Quality issue relationships (related, duplicate, caused_by, parent_child)
CREATE TABLE IF NOT EXISTS quality_issue_links (
    id INTEGER PRIMARY KEY,
    issue_id_a INTEGER NOT NULL REFERENCES quality_issues(id) ON DELETE CASCADE,
    issue_id_b INTEGER NOT NULL REFERENCES quality_issues(id) ON DELETE CASCADE,
    link_type TEXT NOT NULL CHECK (link_type IN ('related', 'duplicate', 'caused_by', 'parent_child')),
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(issue_id_a, issue_id_b, link_type)
);

-- Quality issue tags (many-to-many junction)
CREATE TABLE IF NOT EXISTS quality_issue_tags (
    id INTEGER PRIMARY KEY,
    issue_id INTEGER NOT NULL REFERENCES quality_issues(id) ON DELETE CASCADE,
    tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(issue_id, tag_id)
);

-- Corrective actions (CAPA — corrective, preventive, containment)
CREATE TABLE IF NOT EXISTS corrective_actions (
    id INTEGER PRIMARY KEY,
    issue_id INTEGER NOT NULL REFERENCES quality_issues(id) ON DELETE CASCADE,
    action_type TEXT DEFAULT 'corrective' CHECK (action_type IN ('corrective', 'preventive', 'containment')),
    description TEXT NOT NULL,
    assigned_to TEXT REFERENCES employees(id),
    status TEXT DEFAULT 'open' CHECK (status IN ('open', 'in_progress', 'completed', 'verified', 'ineffective')),
    due_date TEXT,
    completed_at TEXT,
    verified_by TEXT REFERENCES employees(id),
    verified_at TEXT,
    effectiveness_notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ca_issue ON corrective_actions(issue_id);
CREATE INDEX IF NOT EXISTS idx_ca_status ON corrective_actions(status);

-- Mobile capture processing log (tracks processed photos/voice notes)
CREATE TABLE IF NOT EXISTS capture_log (
    id INTEGER PRIMARY KEY,
    filename TEXT NOT NULL,
    filepath TEXT NOT NULL,
    file_hash TEXT,
    status TEXT DEFAULT 'processed' CHECK (status IN ('processed', 'failed', 'skipped')),
    issue_id INTEGER REFERENCES quality_issues(id),
    error_message TEXT,
    processed_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(filepath)
);
