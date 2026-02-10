-- =============================================================================
-- QMS References Schema
-- Reference standards registry, clause extraction, full-text search
-- =============================================================================

-- Reference standards registry
CREATE TABLE IF NOT EXISTS qm_references (
    id INTEGER PRIMARY KEY,
    standard_id TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    edition TEXT,
    publisher TEXT,
    category TEXT,
    file_path TEXT,
    file_hash TEXT,
    page_count INTEGER,
    scope_notes TEXT,
    status TEXT DEFAULT 'CURRENT' CHECK(status IN ('CURRENT', 'SUPERSEDED', 'WITHDRAWN')),
    superseded_by TEXT,
    effective_date DATE,
    review_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    content_extracted INTEGER DEFAULT 0,
    extraction_date TIMESTAMP,
    extraction_method TEXT,
    section_count INTEGER DEFAULT 0,
    extraction_status TEXT DEFAULT 'not_started' CHECK(extraction_status IN (
        'not_started', 'splitting', 'split_complete', 'extracting',
        'extracted', 'merging', 'merged', 'validating', 'complete', 'failed'
    ))
);

-- Extracted clauses
CREATE TABLE IF NOT EXISTS ref_clauses (
    id INTEGER PRIMARY KEY,
    reference_id INTEGER NOT NULL REFERENCES qm_references(id) ON DELETE CASCADE,
    clause_number TEXT NOT NULL,
    clause_title TEXT,
    parent_clause_id INTEGER REFERENCES ref_clauses(id),
    requirement_summary TEXT,
    applicability TEXT,
    verification_method TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    section_id INTEGER REFERENCES ref_sections(id),
    extraction_confidence REAL DEFAULT 1.0,
    UNIQUE(reference_id, clause_number)
);

-- Content blocks within clauses
CREATE TABLE IF NOT EXISTS ref_content_blocks (
    id INTEGER PRIMARY KEY,
    clause_id INTEGER NOT NULL REFERENCES ref_clauses(id) ON DELETE CASCADE,
    block_type TEXT NOT NULL CHECK(block_type IN (
        'Heading', 'Paragraph', 'Note', 'Warning', 'Caution',
        'BulletList', 'NumberedList', 'Table', 'Figure', 'Equation',
        'Example', 'Definition', 'Requirement', 'Informative'
    )),
    content TEXT NOT NULL,
    page_number INTEGER,
    display_order INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Links between reference clauses and internal procedures
CREATE TABLE IF NOT EXISTS ref_procedure_links (
    id INTEGER PRIMARY KEY,
    clause_id INTEGER NOT NULL REFERENCES ref_clauses(id) ON DELETE CASCADE,
    procedure_id INTEGER REFERENCES qm_procedures(id),
    procedure_number TEXT,
    link_type TEXT DEFAULT 'IMPLEMENTS' CHECK(link_type IN (
        'IMPLEMENTS', 'REFERENCES', 'PARTIAL', 'EXCLUDES'
    )),
    notes TEXT,
    verified_date DATE,
    verified_by TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- PDF sections (for parallel extraction)
CREATE TABLE IF NOT EXISTS ref_sections (
    id INTEGER PRIMARY KEY,
    reference_id INTEGER NOT NULL REFERENCES qm_references(id) ON DELETE CASCADE,
    section_number TEXT NOT NULL,
    section_title TEXT,
    section_type TEXT,
    file_path TEXT,
    file_hash TEXT,
    start_page INTEGER NOT NULL,
    end_page INTEGER NOT NULL,
    status TEXT DEFAULT 'pending' CHECK(status IN (
        'pending', 'splitting', 'split', 'extracting',
        'extracted', 'merging', 'validated', 'failed', 'skipped'
    )),
    extraction_model TEXT,
    extraction_started_at TIMESTAMP,
    extraction_completed_at TIMESTAMP,
    clauses_extracted INTEGER DEFAULT 0,
    content_blocks_extracted INTEGER DEFAULT 0,
    avg_confidence REAL,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(reference_id, section_number)
);

-- Extraction operation log
CREATE TABLE IF NOT EXISTS ref_extraction_log (
    id INTEGER PRIMARY KEY,
    reference_id INTEGER NOT NULL REFERENCES qm_references(id),
    section_id INTEGER REFERENCES ref_sections(id),
    operation TEXT NOT NULL,
    agent_name TEXT,
    model_used TEXT,
    details TEXT,
    items_processed INTEGER,
    duration_ms INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Full-text search for reference clauses
CREATE VIRTUAL TABLE IF NOT EXISTS ref_clauses_fts USING fts5(
    standard_id,
    clause_number,
    clause_title,
    requirement_summary,
    applicability,
    tokenize='porter unicode61'
);

-- Full-text search for reference content blocks
CREATE VIRTUAL TABLE IF NOT EXISTS ref_content_fts USING fts5(
    standard_id,
    clause_number,
    clause_title,
    block_type,
    content,
    tokenize='porter unicode61'
);
