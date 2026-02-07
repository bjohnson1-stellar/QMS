-- SIS Quality - Specification Schema Extension
-- For importing and comparing piping/material specifications across projects
-- Run: sqlite3 D:\quality.db < schema-specs.sql

-------------------------------------------------
-- SPECIFICATION DOCUMENTS
-------------------------------------------------

-- Individual spec documents (PDFs imported)
CREATE TABLE IF NOT EXISTS specifications (
    id INTEGER PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id),
    spec_number TEXT NOT NULL,           -- e.g., "15A01", "Spec-001"
    title TEXT,                          -- "Carbon Steel Piping Spec"
    spec_type TEXT,                      -- piping, valve, instrument, insulation, paint
    revision TEXT,
    revision_date TEXT,
    file_name TEXT,
    file_path TEXT,
    page_count INTEGER,
    imported_at TEXT DEFAULT CURRENT_TIMESTAMP,
    extraction_model TEXT,
    quality_score REAL,
    UNIQUE(project_id, spec_number, revision)
);

-------------------------------------------------
-- SPEC SECTIONS & ITEMS
-------------------------------------------------

-- Sections within a spec (e.g., "Materials", "Valves", "Flanges", "Testing")
CREATE TABLE IF NOT EXISTS spec_sections (
    id INTEGER PRIMARY KEY,
    spec_id INTEGER REFERENCES specifications(id),
    section_number TEXT,                 -- "3.1", "4.2.1"
    section_title TEXT,                  -- "Pipe Materials"
    page_number INTEGER,
    extracted_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Individual requirements/items within sections
CREATE TABLE IF NOT EXISTS spec_items (
    id INTEGER PRIMARY KEY,
    section_id INTEGER REFERENCES spec_sections(id),
    spec_id INTEGER REFERENCES specifications(id),
    item_type TEXT NOT NULL,             -- material, valve, flange, fitting, gasket, bolt, test_req, pressure_rating
    item_key TEXT NOT NULL,              -- Normalized key: "pipe_cs_sch40", "valve_gate_150"

    -- Core properties (varies by item_type)
    size_range TEXT,                     -- "1/2\" - 24\""
    material TEXT,                       -- "ASTM A106 Gr B"
    material_grade TEXT,                 -- "Gr B", "316L"
    schedule TEXT,                       -- "SCH 40", "STD"
    rating TEXT,                         -- "150#", "300#", "Class 150"
    end_connection TEXT,                 -- "BW", "SW", "THD", "RF"

    -- Full details as JSON for complex specs
    details TEXT,                        -- JSON: {"seamless": true, "wall_thickness": "0.237"}

    -- Source tracking
    raw_text TEXT,                       -- Original text from spec
    page_number INTEGER,
    confidence REAL DEFAULT 1.0,

    UNIQUE(spec_id, item_type, item_key)
);

-------------------------------------------------
-- MASTER SPEC (Cross-Project Reference)
-------------------------------------------------

-- Aggregated "baseline" spec built from all projects
-- Items that appear consistently across projects
CREATE TABLE IF NOT EXISTS master_spec_items (
    id INTEGER PRIMARY KEY,
    item_type TEXT NOT NULL,             -- material, valve, flange, etc.
    item_key TEXT NOT NULL,              -- Normalized key

    -- Consensus values (most common across projects)
    material TEXT,
    material_grade TEXT,
    schedule TEXT,
    rating TEXT,
    end_connection TEXT,
    size_range TEXT,
    details TEXT,                        -- JSON

    -- Statistics
    project_count INTEGER DEFAULT 1,     -- How many projects have this item
    first_seen_project INTEGER REFERENCES projects(id),
    last_updated TEXT DEFAULT CURRENT_TIMESTAMP,

    -- Confidence based on consistency
    consistency_score REAL DEFAULT 1.0,  -- 1.0 = all projects agree, 0.5 = 50% agree

    UNIQUE(item_type, item_key)
);

-- Variations from master spec (per-project differences)
CREATE TABLE IF NOT EXISTS spec_variations (
    id INTEGER PRIMARY KEY,
    master_item_id INTEGER REFERENCES master_spec_items(id),
    project_id INTEGER REFERENCES projects(id),
    spec_id INTEGER REFERENCES specifications(id),

    -- What's different
    field_name TEXT NOT NULL,            -- "material", "schedule", "rating"
    master_value TEXT,                   -- What master says
    project_value TEXT,                  -- What this project says

    -- Classification
    variation_type TEXT,                 -- upgrade, downgrade, alternative, missing
    significance TEXT,                   -- critical, high, medium, low
    notes TEXT,

    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(master_item_id, project_id, field_name)
);

-------------------------------------------------
-- SPEC INTAKE LOG
-------------------------------------------------

CREATE TABLE IF NOT EXISTS spec_intake_log (
    id INTEGER PRIMARY KEY,
    file_name TEXT NOT NULL,
    source_path TEXT,
    destination_path TEXT,
    action TEXT,                         -- imported, duplicate, needs_review, failed
    project_id INTEGER REFERENCES projects(id),
    spec_id INTEGER REFERENCES specifications(id),
    detected_project_number TEXT,        -- What was read from the page
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-------------------------------------------------
-- INDEXES
-------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_specifications_project ON specifications(project_id);
CREATE INDEX IF NOT EXISTS idx_specifications_type ON specifications(spec_type);
CREATE INDEX IF NOT EXISTS idx_spec_items_type ON spec_items(item_type);
CREATE INDEX IF NOT EXISTS idx_spec_items_key ON spec_items(item_key);
CREATE INDEX IF NOT EXISTS idx_master_spec_key ON master_spec_items(item_type, item_key);
CREATE INDEX IF NOT EXISTS idx_spec_variations_project ON spec_variations(project_id);

-------------------------------------------------
-- VIEWS
-------------------------------------------------

-- Master spec summary
CREATE VIEW IF NOT EXISTS v_master_spec_summary AS
SELECT
    item_type,
    COUNT(*) AS items,
    ROUND(AVG(consistency_score), 2) AS avg_consistency,
    AVG(project_count) AS avg_projects
FROM master_spec_items
GROUP BY item_type;

-- Variations by project
CREATE VIEW IF NOT EXISTS v_project_spec_variations AS
SELECT
    p.number AS project,
    p.name AS project_name,
    sv.field_name,
    sv.master_value,
    sv.project_value,
    sv.variation_type,
    sv.significance,
    msi.item_type,
    msi.item_key
FROM spec_variations sv
JOIN master_spec_items msi ON sv.master_item_id = msi.id
JOIN projects p ON sv.project_id = p.id
ORDER BY p.number, sv.significance DESC;

-- Items unique to specific projects (not in master)
CREATE VIEW IF NOT EXISTS v_project_unique_items AS
SELECT
    p.number AS project,
    si.item_type,
    si.item_key,
    si.material,
    si.rating,
    s.spec_number
FROM spec_items si
JOIN specifications s ON si.spec_id = s.id
JOIN projects p ON s.project_id = p.id
LEFT JOIN master_spec_items msi ON si.item_type = msi.item_type AND si.item_key = msi.item_key
WHERE msi.id IS NULL;

-- Spec comparison across projects
CREATE VIEW IF NOT EXISTS v_spec_comparison AS
SELECT
    msi.item_type,
    msi.item_key,
    msi.material AS master_material,
    msi.rating AS master_rating,
    msi.schedule AS master_schedule,
    msi.project_count,
    msi.consistency_score,
    GROUP_CONCAT(DISTINCT p.number) AS projects_with_variations
FROM master_spec_items msi
LEFT JOIN spec_variations sv ON msi.id = sv.master_item_id
LEFT JOIN projects p ON sv.project_id = p.id
GROUP BY msi.id
ORDER BY msi.consistency_score ASC;  -- Show least consistent first

-- Recent spec imports
CREATE VIEW IF NOT EXISTS v_recent_spec_imports AS
SELECT
    sil.*,
    p.name AS project_name,
    s.title AS spec_title
FROM spec_intake_log sil
LEFT JOIN projects p ON sil.project_id = p.id
LEFT JOIN specifications s ON sil.spec_id = s.id
WHERE sil.created_at > datetime('now', '-7 days')
ORDER BY sil.created_at DESC;
