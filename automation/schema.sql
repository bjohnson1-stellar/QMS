-- =============================================================================
-- QMS Automation Schema
-- Generic request processing audit log
-- =============================================================================

CREATE TABLE IF NOT EXISTS automation_processing_log (
    id              INTEGER PRIMARY KEY,
    file_name       TEXT NOT NULL,
    request_type    TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending',  -- processing, success, failed
    handler_module  TEXT,
    result_summary  TEXT,
    error_message   TEXT,
    source_json     TEXT,
    processed_at    TEXT,
    created_at      TEXT DEFAULT (datetime('now'))
);
