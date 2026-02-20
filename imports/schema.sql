-- =============================================================================
-- QMS Import Infrastructure Schema
-- Tracks import sessions and per-row action plans
-- =============================================================================

CREATE TABLE IF NOT EXISTS import_sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    module TEXT NOT NULL,
    spec_name TEXT NOT NULL,
    filename TEXT NOT NULL,
    file_hash TEXT,
    total_rows INTEGER NOT NULL DEFAULT 0,
    column_mapping TEXT,
    status TEXT NOT NULL DEFAULT 'mapping'
        CHECK(status IN ('mapping','review','executing','completed','cancelled','error')),
    result_summary TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    completed_at TEXT,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS import_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES import_sessions(id),
    row_index INTEGER NOT NULL,
    action_type TEXT NOT NULL
        CHECK(action_type IN ('insert','update','skip','flag','separate','reactivate')),
    record_data TEXT NOT NULL,
    existing_data TEXT,
    match_method TEXT,
    changes TEXT,
    reason TEXT,
    approved INTEGER,
    executed INTEGER DEFAULT 0,
    execution_error TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
