-- Equipment Registry Schema
-- Part of v0.4 Equipment-Centric Platform (Phase 19)
-- Extends pipeline module with unified equipment tracking across disciplines

-- Equipment type catalog (product definitions, shared by instances)
CREATE TABLE IF NOT EXISTS equipment_types (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    manufacturer TEXT,
    model_base TEXT,
    masterformat_section TEXT,
    expected_disciplines TEXT,              -- JSON array: ["Electrical","Mechanical","Structural"]
    default_document_requirements TEXT,     -- JSON: {"submitted":["submittal"],"installed":["inspection"],...}
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Configuration variants (left/right hand, voltage options, etc.)
CREATE TABLE IF NOT EXISTS equipment_variants (
    id INTEGER PRIMARY KEY,
    type_id INTEGER NOT NULL REFERENCES equipment_types(id),
    variant_code TEXT NOT NULL,
    variant_description TEXT,
    model_number TEXT,
    distinguishing_attributes TEXT,         -- JSON: {"hand":"left","connections":"left side"}
    UNIQUE(type_id, variant_code)
);

-- Individual installed equipment instances (the core registry)
CREATE TABLE IF NOT EXISTS equipment_instances (
    id INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id),
    type_id INTEGER REFERENCES equipment_types(id),
    variant_id INTEGER REFERENCES equipment_variants(id),
    tag TEXT NOT NULL,
    serial_number TEXT,
    system_id INTEGER REFERENCES equipment_systems(id),
    discipline_primary TEXT,
    location_area TEXT,
    location_room TEXT,
    hp REAL,
    voltage TEXT,
    amperage REAL,
    weight_lbs REAL,
    pipe_size TEXT,
    attributes TEXT,                        -- JSON overflow for type-specific attrs
    lifecycle_stage TEXT DEFAULT 'design',
    stage_updated_at TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(project_id, tag)
);

CREATE INDEX IF NOT EXISTS idx_equipment_instances_project_tag
    ON equipment_instances(project_id, tag);
CREATE INDEX IF NOT EXISTS idx_equipment_instances_system
    ON equipment_instances(system_id);
CREATE INDEX IF NOT EXISTS idx_equipment_instances_type
    ON equipment_instances(type_id);

-- System groupings (Refrigeration System 1, Electrical Service 2, etc.)
CREATE TABLE IF NOT EXISTS equipment_systems (
    id INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id),
    system_tag TEXT NOT NULL,
    system_name TEXT NOT NULL,
    system_category TEXT,                   -- HVAC, Refrigeration, Electrical, Plumbing, etc.
    discipline TEXT,
    description TEXT,
    cx_required INTEGER DEFAULT 0,
    cx_priority INTEGER,
    parent_system_id INTEGER REFERENCES equipment_systems(id),
    UNIQUE(project_id, system_tag)
);

-- Cross-discipline appearances (where each equipment shows up on drawings)
CREATE TABLE IF NOT EXISTS equipment_appearances (
    id INTEGER PRIMARY KEY,
    instance_id INTEGER NOT NULL REFERENCES equipment_instances(id),
    discipline TEXT NOT NULL,
    sheet_id INTEGER REFERENCES sheets(id),
    drawing_number TEXT,
    attributes_on_sheet TEXT,               -- JSON: what this discipline says about the equipment
    source_table TEXT,                      -- which extraction table the data came from
    source_id INTEGER,                      -- row id in that table
    extracted_at TEXT,
    UNIQUE(instance_id, discipline, sheet_id)
);

CREATE INDEX IF NOT EXISTS idx_equipment_appearances_instance
    ON equipment_appearances(instance_id);

-- Equipment relationship graph (feeds, serves, connects_to, etc.)
CREATE TABLE IF NOT EXISTS equipment_relationships (
    id INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id),
    source_tag TEXT NOT NULL,
    target_tag TEXT NOT NULL,
    relationship_type TEXT NOT NULL,        -- feeds, serves, connects_to, mounted_on, controlled_by
    discipline TEXT,
    drawing_number TEXT,
    attributes TEXT,                        -- JSON: {"pipe_size":"3in","wire_size":"#4/0","breaker":"300AT"}
    UNIQUE(project_id, source_tag, target_tag, relationship_type)
);

CREATE INDEX IF NOT EXISTS idx_equipment_relationships_source
    ON equipment_relationships(project_id, source_tag);
CREATE INDEX IF NOT EXISTS idx_equipment_relationships_target
    ON equipment_relationships(project_id, target_tag);

-- Document linking (type, variant, or instance level)
CREATE TABLE IF NOT EXISTS equipment_documents (
    id INTEGER PRIMARY KEY,
    link_level TEXT NOT NULL CHECK(link_level IN ('type', 'variant', 'instance')),
    link_id INTEGER NOT NULL,
    document_type TEXT NOT NULL,
    document_ref_type TEXT,                 -- submittal, shop_drawing, test_report, inspection, etc.
    document_ref_id INTEGER,               -- FK to actual document (nullable until received)
    status TEXT DEFAULT 'required' CHECK(status IN ('required','submitted','approved','rejected','waived')),
    due_date TEXT,
    received_date TEXT,
    reviewed_by INTEGER,
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Lifecycle stage history (audit trail of stage transitions)
CREATE TABLE IF NOT EXISTS equipment_stage_history (
    id INTEGER PRIMARY KEY,
    instance_id INTEGER NOT NULL REFERENCES equipment_instances(id),
    from_stage TEXT,
    to_stage TEXT NOT NULL,
    changed_at TEXT DEFAULT CURRENT_TIMESTAMP,
    changed_by INTEGER,
    evidence_document_id INTEGER,
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_equipment_stage_history_instance
    ON equipment_stage_history(instance_id);

-- Attribute change log (for conflict resolution audit trail)
CREATE TABLE IF NOT EXISTS equipment_attribute_log (
    id INTEGER PRIMARY KEY,
    instance_id INTEGER NOT NULL REFERENCES equipment_instances(id),
    attribute_name TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    source_discipline TEXT,
    source_drawing TEXT,
    changed_at TEXT DEFAULT CURRENT_TIMESTAMP,
    changed_by INTEGER,
    reason TEXT
);

-- Conflict detection rules (configurable per project)
CREATE TABLE IF NOT EXISTS conflict_rules (
    id INTEGER PRIMARY KEY,
    attribute_name TEXT NOT NULL,
    comparison_type TEXT NOT NULL CHECK(comparison_type IN (
        'exact', 'numeric_tolerance', 'range_contains', 'unit_convert', 'derived', 'presence'
    )),
    tolerance_value REAL,
    tolerance_type TEXT CHECK(tolerance_type IN ('absolute', 'percent')),
    severity TEXT DEFAULT 'warning' CHECK(severity IN ('critical', 'warning', 'info')),
    description TEXT,
    active INTEGER DEFAULT 1
);

-- Detected conflicts (populated by conflict scanner)
CREATE TABLE IF NOT EXISTS equipment_conflicts (
    id INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id),
    equipment_tag TEXT NOT NULL,
    conflict_type TEXT NOT NULL CHECK(conflict_type IN (
        'attribute', 'missing_discipline', 'spec_violation'
    )),
    attribute_name TEXT,
    discipline_a TEXT,
    drawing_a TEXT,
    value_a TEXT,
    discipline_b TEXT,
    drawing_b TEXT,
    value_b TEXT,
    rule_id INTEGER REFERENCES conflict_rules(id),
    severity TEXT DEFAULT 'warning',
    status TEXT DEFAULT 'new' CHECK(status IN (
        'new', 'confirmed', 'assigned', 'resolved', 'false_positive'
    )),
    assigned_to INTEGER,
    rfi_id INTEGER,
    resolution_note TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    resolved_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_equipment_conflicts_project
    ON equipment_conflicts(project_id, status);

-- Seed default conflict rules
INSERT OR IGNORE INTO conflict_rules (attribute_name, comparison_type, tolerance_value, tolerance_type, severity, description) VALUES
    ('hp', 'numeric_tolerance', 10, 'percent', 'warning', 'Horsepower mismatch >10% between disciplines'),
    ('voltage', 'exact', NULL, NULL, 'critical', 'Voltage mismatch between disciplines — wrong voltage = wrong equipment'),
    ('amperage', 'numeric_tolerance', 15, 'percent', 'warning', 'Amperage mismatch >15% between disciplines'),
    ('weight_lbs', 'numeric_tolerance', 20, 'percent', 'warning', 'Weight mismatch >20% — affects structural support design'),
    ('pipe_size', 'exact', NULL, NULL, 'warning', 'Pipe size mismatch between disciplines'),
    ('refrigerant', 'exact', NULL, NULL, 'critical', 'Refrigerant type mismatch — different piping materials and safety requirements');
