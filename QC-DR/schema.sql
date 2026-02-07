-- SIS Quality Database Schema
-- Includes extraction data + validation tracking
-- Init: sqlite3 D:\quality.db < schema.sql

-------------------------------------------------
-- PROJECTS
-------------------------------------------------

CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY,
    number TEXT UNIQUE,
    name TEXT NOT NULL,
    client TEXT,
    path TEXT,
    status TEXT DEFAULT 'active',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS project_codes (
    id INTEGER PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id),
    code_name TEXT,
    code_year TEXT,
    UNIQUE(project_id, code_name)
);

-------------------------------------------------
-- SHEETS
-------------------------------------------------

CREATE TABLE IF NOT EXISTS sheets (
    id INTEGER PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id),
    discipline TEXT,              -- Mechanical, Structural, Electrical, etc.
    file_name TEXT,
    file_path TEXT,               -- Relative path within project
    drawing_number TEXT,
    title TEXT,
    revision TEXT,
    revision_sequence INTEGER DEFAULT 1,
    is_current INTEGER DEFAULT 1,
    supersedes INTEGER REFERENCES sheets(id),
    superseded_by INTEGER REFERENCES sheets(id),
    drawing_type TEXT,            -- pid, isometric, plan, section, detail, etc.
    complexity TEXT,              -- simple, complex
    extracted_at TEXT,
    extraction_model TEXT,
    quality_score REAL,
    UNIQUE(project_id, drawing_number, revision)
);

-- Standard discipline prefixes (defaults, can be overridden per project)
CREATE TABLE IF NOT EXISTS discipline_defaults (
    id INTEGER PRIMARY KEY,
    name TEXT,                    -- "Mechanical", "Structural", etc.
    common_names TEXT,            -- JSON: ["Mechanical", "Mech", "Process"]
    drawing_prefixes TEXT         -- JSON: ["P-", "ISO-", "M-"]
);

-- Default discipline mappings
INSERT OR IGNORE INTO discipline_defaults (name, common_names, drawing_prefixes) VALUES
    ('Mechanical', '["Mechanical", "Mech", "Process", "Piping"]', '["P-", "PID-", "PFD-", "ISO-", "M-"]'),
    ('Structural', '["Structural", "Struct", "Steel"]', '["S-", "ST-", "SF-"]'),
    ('Electrical', '["Electrical", "Elec", "Power"]', '["E-", "EL-", "EP-"]'),
    ('Civil', '["Civil", "Site"]', '["C-", "CW-", "CG-"]'),
    ('Architectural', '["Architectural", "Arch", "Architecture"]', '["A-", "AR-", "AD-"]'),
    ('Plumbing', '["Plumbing", "Plumb"]', '["PL-", "P-"]'),
    ('Fire-Protection', '["Fire-Protection", "Fire Protection", "FP", "Sprinkler"]', '["FP-", "FS-"]'),
    ('Refrigeration', '["Refrigeration", "Refrig", "HVAC", "Mechanical-HVAC"]', '["R-", "RF-", "H-", "HVAC-"]'),
    ('Refrigeration-Controls', '["Refrigeration-Controls", "Refrig Controls", "Controls"]', '["RC-", "IC-"]'),
    ('Instrumentation', '["Instrumentation", "Inst", "Controls", "I&C"]', '["I-", "IN-", "IL-", "IC-"]'),
    ('Utilities', '["Utilities", "Utility", "Util"]', '["U-", "UT-"]'),
    ('General', '["General", "Gen", "Misc"]', '["G-", "GA-", "GN-", "D-"]');

-- Actual disciplines discovered per project (from folder scan)
CREATE TABLE IF NOT EXISTS disciplines (
    id INTEGER PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id),
    name TEXT NOT NULL,           -- Actual folder name: "Refrigeration-Controls"
    folder_path TEXT,             -- Full path: "07600-Rosina/Refrigeration-Controls"
    normalized_name TEXT,         -- Mapped name: "Refrigeration-Controls"
    sheet_count INTEGER DEFAULT 0,
    processed_count INTEGER DEFAULT 0,
    UNIQUE(project_id, name)
);

-------------------------------------------------
-- EXTRACTED DATA
-------------------------------------------------

CREATE TABLE IF NOT EXISTS lines (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER REFERENCES sheets(id),
    line_number TEXT NOT NULL,
    size TEXT,
    material TEXT,
    spec_class TEXT,
    from_location TEXT,
    to_location TEXT,
    service TEXT,
    confidence REAL DEFAULT 1.0
);

CREATE TABLE IF NOT EXISTS equipment (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER REFERENCES sheets(id),
    tag TEXT NOT NULL,
    description TEXT,
    equipment_type TEXT,
    confidence REAL DEFAULT 1.0
);

CREATE TABLE IF NOT EXISTS instruments (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER REFERENCES sheets(id),
    tag TEXT NOT NULL,
    instrument_type TEXT,
    loop_number TEXT,
    confidence REAL DEFAULT 1.0
);

CREATE TABLE IF NOT EXISTS welds (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER REFERENCES sheets(id),
    weld_id TEXT,
    weld_type TEXT,
    size TEXT,
    joint_type TEXT,
    nde_required TEXT,
    confidence REAL DEFAULT 1.0
);

-------------------------------------------------
-- FLAGS AND CONFLICTS
-------------------------------------------------

CREATE TABLE IF NOT EXISTS extraction_flags (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER REFERENCES sheets(id),
    field TEXT,
    issue TEXT,
    severity TEXT,
    resolved INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS conflicts (
    id INTEGER PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id),
    conflict_type TEXT,
    severity TEXT,
    item TEXT,
    details TEXT,
    resolved INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-------------------------------------------------
-- VALIDATION & MODEL TRACKING
-------------------------------------------------

-- Every extraction run logged
CREATE TABLE IF NOT EXISTS model_runs (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER REFERENCES sheets(id),
    model TEXT NOT NULL,           -- haiku, sonnet, opus
    run_type TEXT,                 -- extraction, validation, shadow
    items_extracted INTEGER,
    flags_raised INTEGER,
    duration_ms INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Misses found by validation
CREATE TABLE IF NOT EXISTS extraction_misses (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER REFERENCES sheets(id),
    extraction_model TEXT,         -- Model that missed it
    found_by TEXT,                 -- opus-review, human, cross-checker
    missed_item_type TEXT,         -- line, equipment, instrument, weld
    missed_item TEXT,              -- Description of what was missed
    severity TEXT,                 -- high, medium, low
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Shadow review results
CREATE TABLE IF NOT EXISTS shadow_reviews (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER REFERENCES sheets(id),
    extraction_model TEXT,         -- Model being reviewed
    review_model TEXT DEFAULT 'opus',
    items_checked INTEGER,
    items_correct INTEGER,
    items_missed INTEGER,
    items_wrong INTEGER,
    accuracy REAL,
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Gold standard verified extractions
CREATE TABLE IF NOT EXISTS gold_standard (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER REFERENCES sheets(id),
    drawing_type TEXT,
    complexity TEXT,
    verified_extraction TEXT,      -- JSON of verified data
    verified_by TEXT,              -- human, opus-verified
    verified_at TEXT,
    UNIQUE(sheet_id)
);

-- Model accuracy over time
CREATE TABLE IF NOT EXISTS accuracy_log (
    id INTEGER PRIMARY KEY,
    model TEXT,
    drawing_type TEXT,
    period_start TEXT,
    period_end TEXT,
    sheets_checked INTEGER,
    accuracy REAL,
    miss_rate REAL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Routing adjustments made by system
CREATE TABLE IF NOT EXISTS routing_changes (
    id INTEGER PRIMARY KEY,
    drawing_type TEXT,
    old_model TEXT,
    new_model TEXT,
    reason TEXT,
    accuracy_before REAL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-------------------------------------------------
-- INTAKE & REVISION TRACKING
-------------------------------------------------

-- Processing queue for async work
CREATE TABLE IF NOT EXISTS processing_queue (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER REFERENCES sheets(id),
    project_id INTEGER REFERENCES projects(id),
    task TEXT NOT NULL,            -- extract, revision_diff, cross_check, etc.
    priority TEXT DEFAULT 'normal', -- high, normal, low
    status TEXT DEFAULT 'pending',  -- pending, processing, complete, failed
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    started_at TEXT,
    completed_at TEXT,
    error TEXT
);

-- Intake log
CREATE TABLE IF NOT EXISTS intake_log (
    id INTEGER PRIMARY KEY,
    file_name TEXT NOT NULL,
    source_path TEXT,
    destination_path TEXT,
    action TEXT,                   -- routed, revision_update, new_project, needs_review, skipped
    project_id INTEGER REFERENCES projects(id),
    sheet_id INTEGER REFERENCES sheets(id),
    old_revision TEXT,
    new_revision TEXT,
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Revision deltas (what changed between revisions)
CREATE TABLE IF NOT EXISTS revision_deltas (
    id INTEGER PRIMARY KEY,
    old_sheet_id INTEGER REFERENCES sheets(id),
    new_sheet_id INTEGER REFERENCES sheets(id),
    delta_type TEXT,               -- added, removed, changed
    item_type TEXT,                -- line, equipment, instrument, weld
    item_id TEXT,                  -- Line number or tag
    old_value TEXT,                -- JSON of old item
    new_value TEXT,                -- JSON of new item
    significance TEXT,             -- high, medium, low
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Project flags for items needing attention
CREATE TABLE IF NOT EXISTS project_flags (
    id INTEGER PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id),
    flag TEXT,                     -- needs_setup, needs_review, stale, etc.
    message TEXT,
    resolved INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    resolved_at TEXT
);

-- Drawing number patterns for project matching
CREATE TABLE IF NOT EXISTS project_patterns (
    id INTEGER PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id),
    pattern_type TEXT,             -- prefix, regex, client_name
    pattern TEXT,                  -- e.g., "P-1", "^ISO-1\d{3}$", "Acme"
    confidence REAL DEFAULT 1.0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(project_id, pattern_type, pattern)
);

-------------------------------------------------
-- INDEXES
-------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_sheets_project ON sheets(project_id);
CREATE INDEX IF NOT EXISTS idx_sheets_type ON sheets(drawing_type);
CREATE INDEX IF NOT EXISTS idx_lines_number ON lines(line_number);
CREATE INDEX IF NOT EXISTS idx_equipment_tag ON equipment(tag);
CREATE INDEX IF NOT EXISTS idx_model_runs_sheet ON model_runs(sheet_id);
CREATE INDEX IF NOT EXISTS idx_shadow_reviews_sheet ON shadow_reviews(sheet_id);
CREATE INDEX IF NOT EXISTS idx_extraction_misses_model ON extraction_misses(extraction_model);

-------------------------------------------------
-- VIEWS
-------------------------------------------------

-- Project summary
CREATE VIEW IF NOT EXISTS v_project_summary AS
SELECT 
    p.number,
    p.name,
    p.status,
    COUNT(DISTINCT s.id) AS total_sheets,
    SUM(CASE WHEN s.extracted_at IS NOT NULL THEN 1 ELSE 0 END) AS processed,
    COUNT(DISTINCT c.id) AS open_conflicts
FROM projects p
LEFT JOIN sheets s ON s.project_id = p.id
LEFT JOIN conflicts c ON c.project_id = p.id AND c.resolved = 0
GROUP BY p.id;

-- Material conflicts
CREATE VIEW IF NOT EXISTS v_material_conflicts AS
SELECT 
    p.number AS project,
    l1.line_number,
    s1.drawing_number AS drawing1,
    l1.material AS material1,
    s2.drawing_number AS drawing2,
    l2.material AS material2
FROM lines l1
JOIN lines l2 ON l1.line_number = l2.line_number AND l1.id < l2.id
JOIN sheets s1 ON l1.sheet_id = s1.id
JOIN sheets s2 ON l2.sheet_id = s2.id
JOIN projects p ON s1.project_id = p.id
WHERE l1.material != l2.material
  AND s1.project_id = s2.project_id;

-- Model accuracy by drawing type
CREATE VIEW IF NOT EXISTS v_model_accuracy AS
SELECT 
    s.drawing_type,
    s.extraction_model AS model,
    COUNT(DISTINCT s.id) AS sheets,
    ROUND(AVG(sr.accuracy), 3) AS avg_accuracy,
    COUNT(DISTINCT em.id) AS total_misses,
    ROUND(COUNT(DISTINCT em.id) * 1.0 / COUNT(DISTINCT s.id), 3) AS miss_rate
FROM sheets s
LEFT JOIN shadow_reviews sr ON s.id = sr.sheet_id
LEFT JOIN extraction_misses em ON s.id = em.sheet_id
WHERE s.extracted_at IS NOT NULL
GROUP BY s.drawing_type, s.extraction_model;

-- Unprocessed sheets
CREATE VIEW IF NOT EXISTS v_unprocessed AS
SELECT p.number AS project, s.file_name, s.drawing_number, s.drawing_type
FROM sheets s
JOIN projects p ON s.project_id = p.id
WHERE s.extracted_at IS NULL;

-- Recent misses (last 7 days)
CREATE VIEW IF NOT EXISTS v_recent_misses AS
SELECT 
    em.extraction_model,
    s.drawing_type,
    em.missed_item_type,
    em.missed_item,
    em.severity,
    p.number AS project,
    s.drawing_number,
    em.created_at
FROM extraction_misses em
JOIN sheets s ON em.sheet_id = s.id
JOIN projects p ON s.project_id = p.id
WHERE em.created_at > datetime('now', '-7 days')
ORDER BY em.created_at DESC;

-- Accuracy alerts (below 95%)
CREATE VIEW IF NOT EXISTS v_accuracy_alerts AS
SELECT 
    drawing_type,
    model,
    sheets,
    avg_accuracy,
    miss_rate,
    CASE 
        WHEN avg_accuracy < 0.90 THEN 'CRITICAL'
        WHEN avg_accuracy < 0.95 THEN 'WARNING'
        ELSE 'OK'
    END AS status
FROM v_model_accuracy
WHERE avg_accuracy < 0.95 OR miss_rate > 0.05;

-- Sheets needing shadow review (not yet reviewed)
CREATE VIEW IF NOT EXISTS v_needs_shadow AS
SELECT s.id, p.number AS project, s.drawing_number, s.drawing_type, s.extraction_model
FROM sheets s
JOIN projects p ON s.project_id = p.id
LEFT JOIN shadow_reviews sr ON s.id = sr.sheet_id
WHERE s.extracted_at IS NOT NULL
  AND s.is_current = 1
  AND sr.id IS NULL
ORDER BY RANDOM()
LIMIT 10;

-- Revision history
CREATE VIEW IF NOT EXISTS v_revision_history AS
SELECT 
    p.number AS project,
    s.drawing_number,
    s.revision,
    s.revision_sequence,
    s.is_current,
    s.file_name,
    s.extracted_at,
    prev.revision AS previous_revision,
    (SELECT COUNT(*) FROM revision_deltas WHERE new_sheet_id = s.id) AS changes_from_prev
FROM sheets s
JOIN projects p ON s.project_id = p.id
LEFT JOIN sheets prev ON s.supersedes = prev.id
ORDER BY p.number, s.drawing_number, s.revision_sequence;

-- Current sheets only (for cross-checking)
CREATE VIEW IF NOT EXISTS v_current_sheets AS
SELECT s.*, p.number AS project
FROM sheets s
JOIN projects p ON s.project_id = p.id
WHERE s.is_current = 1;

-- Pending queue items
CREATE VIEW IF NOT EXISTS v_pending_queue AS
SELECT 
    q.*,
    p.number AS project,
    s.drawing_number,
    s.revision
FROM processing_queue q
LEFT JOIN projects p ON q.project_id = p.id
LEFT JOIN sheets s ON q.sheet_id = s.id
WHERE q.status = 'pending'
ORDER BY 
    CASE q.priority WHEN 'high' THEN 1 WHEN 'normal' THEN 2 ELSE 3 END,
    q.created_at;

-- Recent intake activity
CREATE VIEW IF NOT EXISTS v_recent_intake AS
SELECT 
    i.*,
    p.name AS project_name
FROM intake_log i
LEFT JOIN projects p ON i.project_id = p.id
WHERE i.created_at > datetime('now', '-7 days')
ORDER BY i.created_at DESC;

-- Projects needing attention
CREATE VIEW IF NOT EXISTS v_project_alerts AS
SELECT 
    p.number,
    p.name,
    pf.flag,
    pf.message,
    pf.created_at
FROM project_flags pf
JOIN projects p ON pf.project_id = p.id
WHERE pf.resolved = 0
ORDER BY pf.created_at DESC;

-- Discipline summary for a project
CREATE VIEW IF NOT EXISTS v_discipline_summary AS
SELECT 
    p.number AS project,
    s.discipline,
    COUNT(DISTINCT s.id) AS sheets,
    SUM(CASE WHEN s.extracted_at IS NOT NULL THEN 1 ELSE 0 END) AS processed,
    COUNT(DISTINCT c.id) AS conflicts
FROM sheets s
JOIN projects p ON s.project_id = p.id
LEFT JOIN conflicts c ON c.project_id = p.id 
    AND c.item IN (SELECT line_number FROM lines WHERE sheet_id = s.id)
WHERE s.is_current = 1
GROUP BY p.id, s.discipline;

-- Cross-discipline conflicts (most valuable!)
CREATE VIEW IF NOT EXISTS v_cross_discipline_conflicts AS
SELECT 
    p.number AS project,
    s1.discipline AS discipline1,
    s1.drawing_number AS drawing1,
    s2.discipline AS discipline2,
    s2.drawing_number AS drawing2,
    l1.line_number,
    l1.material AS material1,
    l2.material AS material2,
    'material_mismatch' AS conflict_type
FROM lines l1
JOIN lines l2 ON l1.line_number = l2.line_number AND l1.id < l2.id
JOIN sheets s1 ON l1.sheet_id = s1.id
JOIN sheets s2 ON l2.sheet_id = s2.id
JOIN projects p ON s1.project_id = p.id
WHERE s1.discipline != s2.discipline
  AND s1.is_current = 1 AND s2.is_current = 1
  AND l1.material != l2.material
  AND s1.project_id = s2.project_id;

-- Equipment appearing across disciplines
CREATE VIEW IF NOT EXISTS v_equipment_by_discipline AS
SELECT 
    p.number AS project,
    e.tag,
    GROUP_CONCAT(DISTINCT s.discipline) AS disciplines,
    COUNT(DISTINCT s.discipline) AS discipline_count,
    GROUP_CONCAT(DISTINCT s.drawing_number) AS drawings
FROM equipment e
JOIN sheets s ON e.sheet_id = s.id
JOIN projects p ON s.project_id = p.id
WHERE s.is_current = 1
GROUP BY p.id, e.tag
HAVING COUNT(DISTINCT s.discipline) > 1;
