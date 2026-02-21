-- =============================================================================
-- QMS Customer Profile Schema
-- Requirements, specifications, quality preferences, and interaction history
-- =============================================================================

-- Customer engineering requirements (corporate-level standards)
-- e.g., "All welding must conform to AWS D1.1", "Require 100% RT on pressure welds"
CREATE TABLE IF NOT EXISTS customer_requirements (
    id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    category TEXT NOT NULL CHECK (
        category IN (
            'welding', 'inspection', 'testing', 'documentation',
            'materials', 'safety', 'general'
        )
    ),
    title TEXT NOT NULL,
    description TEXT,
    reference_code TEXT,
    mandatory INTEGER NOT NULL DEFAULT 1,
    applies_to TEXT DEFAULT 'all_projects',
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_cr_customer ON customer_requirements(customer_id);
CREATE INDEX IF NOT EXISTS idx_cr_category ON customer_requirements(category);

-- Customer specifications (corporate standards, project templates, preferred specs)
-- e.g., "Freshpet Corporate Piping Spec Rev 3", "Lineage Refrigeration Design Standard"
CREATE TABLE IF NOT EXISTS customer_specifications (
    id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    spec_type TEXT NOT NULL CHECK (
        spec_type IN (
            'corporate_standard', 'project_template',
            'quality_requirement', 'design_standard', 'test_procedure'
        )
    ),
    spec_number TEXT,
    title TEXT NOT NULL,
    description TEXT,
    revision TEXT,
    document_path TEXT,
    discipline TEXT,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'superseded', 'archived')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_cs_customer ON customer_specifications(customer_id);
CREATE INDEX IF NOT EXISTS idx_cs_type ON customer_specifications(spec_type);

-- Customer quality preferences (how they want documents handled)
-- Key-value pairs grouped by type for flexibility
-- e.g., type='submittal_format', key='drawing_format', value='PDF with bookmarks'
-- e.g., type='naming_convention', key='drawing_prefix', value='{PROJECT}-{DISC}-{SEQ}'
CREATE TABLE IF NOT EXISTS customer_quality_preferences (
    id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    preference_type TEXT NOT NULL CHECK (
        preference_type IN (
            'document_format', 'naming_convention', 'delivery_method',
            'review_process', 'submittal_format', 'retention'
        )
    ),
    preference_key TEXT NOT NULL,
    preference_value TEXT NOT NULL,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(customer_id, preference_type, preference_key)
);
CREATE INDEX IF NOT EXISTS idx_cqp_customer ON customer_quality_preferences(customer_id);

-- Customer history / interaction log (lessons learned, feedback, issues)
CREATE TABLE IF NOT EXISTS customer_history (
    id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    project_id INTEGER REFERENCES projects(id),
    entry_type TEXT NOT NULL CHECK (
        entry_type IN (
            'lesson_learned', 'feedback', 'issue',
            'success', 'note', 'requirement_change'
        )
    ),
    title TEXT NOT NULL,
    description TEXT,
    recorded_by INTEGER REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_ch_customer ON customer_history(customer_id);
CREATE INDEX IF NOT EXISTS idx_ch_project ON customer_history(project_id);
CREATE INDEX IF NOT EXISTS idx_ch_type ON customer_history(entry_type);
