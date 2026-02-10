-- =============================================================================
-- QMS Engineering Schema
-- Calculation history and design validation records
-- =============================================================================

-- Calculation log
CREATE TABLE IF NOT EXISTS eng_calculations (
    id INTEGER PRIMARY KEY,
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
    discipline TEXT NOT NULL,
    calculation_type TEXT NOT NULL,
    input_json TEXT,
    output_json TEXT,
    project_id INTEGER REFERENCES projects(id),
    sheet_id INTEGER REFERENCES sheets(id),
    equipment_tag TEXT,
    line_number TEXT,
    notes TEXT
);

-- Validation results (drawing vs calculation)
CREATE TABLE IF NOT EXISTS eng_validations (
    id INTEGER PRIMARY KEY,
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
    calculation_id INTEGER REFERENCES eng_calculations(id),
    project_id INTEGER REFERENCES projects(id),
    sheet_id INTEGER REFERENCES sheets(id),
    item_type TEXT,
    item_tag TEXT,
    extracted_value TEXT,
    calculated_value TEXT,
    tolerance_pct REAL,
    deviation_pct REAL,
    status TEXT,
    notes TEXT
);
