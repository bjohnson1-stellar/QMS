-- Migration 004: Parallel Reference Extraction Support
-- Adds tables and columns for parallelized agent-based extraction

-- =============================================================================
-- NEW TABLE: Track section files and extraction status
-- =============================================================================
CREATE TABLE IF NOT EXISTS ref_sections (
    id INTEGER PRIMARY KEY,
    reference_id INTEGER NOT NULL REFERENCES qm_references(id) ON DELETE CASCADE,
    section_number TEXT NOT NULL,              -- '01', '02', etc. for sequencing
    section_title TEXT,                        -- 'Part QG - General Requirements'
    section_type TEXT,                         -- 'Part', 'Article', 'Chapter', 'Annex'
    file_path TEXT,                            -- Path to split PDF section
    file_hash TEXT,                            -- MD5 for integrity check
    start_page INTEGER NOT NULL,               -- 1-based page number in original
    end_page INTEGER NOT NULL,                 -- Inclusive end page
    status TEXT DEFAULT 'pending' CHECK(status IN (
        'pending',      -- Not yet processed
        'splitting',    -- Being split from source PDF
        'split',        -- PDF section created, awaiting extraction
        'extracting',   -- Extraction in progress
        'extracted',    -- Extraction complete
        'merging',      -- Being merged/deduplicated
        'validated',    -- Passed validation
        'failed',       -- Extraction failed
        'skipped'       -- Intentionally skipped (e.g., blank pages)
    )),
    extraction_model TEXT,                     -- Model used: 'haiku', 'sonnet', 'opus'
    extraction_started_at TIMESTAMP,
    extraction_completed_at TIMESTAMP,
    clauses_extracted INTEGER DEFAULT 0,
    content_blocks_extracted INTEGER DEFAULT 0,
    avg_confidence REAL,
    error_message TEXT,                        -- Last error if failed
    retry_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(reference_id, section_number)
);

CREATE INDEX IF NOT EXISTS idx_ref_sections_reference ON ref_sections(reference_id);
CREATE INDEX IF NOT EXISTS idx_ref_sections_status ON ref_sections(status);

-- =============================================================================
-- NEW TABLE: Audit trail for extraction operations
-- =============================================================================
CREATE TABLE IF NOT EXISTS ref_extraction_log (
    id INTEGER PRIMARY KEY,
    reference_id INTEGER NOT NULL REFERENCES qm_references(id),
    section_id INTEGER REFERENCES ref_sections(id),
    operation TEXT NOT NULL,                   -- 'split_start', 'split_complete', 'extract_start', etc.
    agent_name TEXT,                           -- 'ref-section-splitter', 'ref-section-extractor', etc.
    model_used TEXT,                           -- 'haiku', 'sonnet', 'opus'
    details TEXT,                              -- JSON with additional info
    items_processed INTEGER,                   -- Clauses, blocks, pages processed
    duration_ms INTEGER,                       -- Operation duration in milliseconds
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ref_extraction_log_reference ON ref_extraction_log(reference_id);
CREATE INDEX IF NOT EXISTS idx_ref_extraction_log_section ON ref_extraction_log(section_id);
CREATE INDEX IF NOT EXISTS idx_ref_extraction_log_operation ON ref_extraction_log(operation);

-- =============================================================================
-- MODIFY EXISTING TABLES
-- =============================================================================

-- Add section_id to ref_clauses for tracking which section extracted each clause
-- This enables deduplication during merge phase
ALTER TABLE ref_clauses ADD COLUMN section_id INTEGER REFERENCES ref_sections(id);

-- Add extraction confidence to ref_clauses
ALTER TABLE ref_clauses ADD COLUMN extraction_confidence REAL DEFAULT 1.0;

-- Add parallel extraction tracking to qm_references
ALTER TABLE qm_references ADD COLUMN section_count INTEGER DEFAULT 0;
ALTER TABLE qm_references ADD COLUMN extraction_status TEXT DEFAULT 'not_started' CHECK(extraction_status IN (
    'not_started',
    'splitting',
    'split_complete',
    'extracting',
    'extracted',
    'merging',
    'merged',
    'validating',
    'complete',
    'failed'
));

-- =============================================================================
-- PROGRESS VIEW: See extraction status at a glance
-- =============================================================================
CREATE VIEW IF NOT EXISTS v_ref_extraction_progress AS
SELECT
    r.id AS reference_id,
    r.standard_id,
    r.title,
    r.page_count,
    r.extraction_status,
    r.section_count,
    COUNT(s.id) AS total_sections,
    SUM(CASE WHEN s.status = 'pending' THEN 1 ELSE 0 END) AS pending_sections,
    SUM(CASE WHEN s.status = 'extracting' THEN 1 ELSE 0 END) AS extracting_sections,
    SUM(CASE WHEN s.status IN ('extracted', 'validated') THEN 1 ELSE 0 END) AS completed_sections,
    SUM(CASE WHEN s.status = 'failed' THEN 1 ELSE 0 END) AS failed_sections,
    SUM(COALESCE(s.clauses_extracted, 0)) AS total_clauses,
    SUM(COALESCE(s.content_blocks_extracted, 0)) AS total_blocks,
    AVG(s.avg_confidence) AS overall_confidence,
    MIN(s.extraction_started_at) AS extraction_started,
    MAX(s.extraction_completed_at) AS last_section_completed
FROM qm_references r
LEFT JOIN ref_sections s ON s.reference_id = r.id
GROUP BY r.id;

-- =============================================================================
-- SECTION WORK QUEUE VIEW: Find sections ready for extraction
-- =============================================================================
CREATE VIEW IF NOT EXISTS v_ref_section_queue AS
SELECT
    s.id AS section_id,
    s.reference_id,
    r.standard_id,
    s.section_number,
    s.section_title,
    s.section_type,
    s.file_path,
    s.start_page,
    s.end_page,
    (s.end_page - s.start_page + 1) AS page_count,
    s.status,
    s.retry_count
FROM ref_sections s
JOIN qm_references r ON r.id = s.reference_id
WHERE s.status IN ('split', 'failed')
  AND s.retry_count < 3
ORDER BY
    s.retry_count ASC,  -- Prioritize fresh attempts
    r.id ASC,           -- Process by reference order
    CAST(s.section_number AS INTEGER) ASC;  -- Then by section order
