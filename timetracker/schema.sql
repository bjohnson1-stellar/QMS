-- =============================================================================
-- QMS Time Tracker Schema
-- Transactions, budget settings, projection periods & snapshots
-- =============================================================================

-- Project spending ledger
CREATE TABLE IF NOT EXISTS project_transactions (
    id INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    transaction_date TEXT NOT NULL,
    transaction_type TEXT NOT NULL CHECK (
        transaction_type IN ('Time', 'Travel', 'Materials', 'Other')
    ),
    description TEXT NOT NULL,
    amount REAL NOT NULL,
    hours REAL,
    rate REAL,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Singleton budget configuration
CREATE TABLE IF NOT EXISTS budget_settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    company_name TEXT DEFAULT 'My Company',
    default_hourly_rate REAL DEFAULT 150.0,
    working_hours_per_month INTEGER DEFAULT 176,
    fiscal_year_start_month INTEGER DEFAULT 1,
    gmp_weight_multiplier REAL NOT NULL DEFAULT 1.5,
    max_hours_per_week REAL NOT NULL DEFAULT 40.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =============================================================================
-- Projection Tables (monthly hour forecasting)
-- =============================================================================

-- Monthly periods for projection planning
CREATE TABLE IF NOT EXISTS projection_periods (
    id INTEGER PRIMARY KEY,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    working_days INTEGER NOT NULL,
    total_hours INTEGER NOT NULL,
    is_locked INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(year, month)
);

-- Versioned projection snapshots per period
CREATE TABLE IF NOT EXISTS projection_snapshots (
    id INTEGER PRIMARY KEY,
    period_id INTEGER NOT NULL REFERENCES projection_periods(id) ON DELETE CASCADE,
    version INTEGER NOT NULL DEFAULT 1,
    name TEXT,
    description TEXT,
    hourly_rate REAL NOT NULL,
    total_hours INTEGER NOT NULL,
    total_projected_cost REAL NOT NULL,
    status TEXT DEFAULT 'Draft' CHECK (status IN ('Draft', 'Committed', 'Superseded')),
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    committed_at TEXT,
    finalized_at TEXT,
    UNIQUE(period_id, version)
);

-- Per-project allocations within a snapshot
CREATE TABLE IF NOT EXISTS projection_entries (
    id INTEGER PRIMARY KEY,
    snapshot_id INTEGER NOT NULL REFERENCES projection_snapshots(id) ON DELETE CASCADE,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    allocated_hours REAL NOT NULL CHECK (allocated_hours >= 0),
    projected_cost REAL NOT NULL,
    weight_used REAL,
    remaining_budget_at_time REAL,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(snapshot_id, project_id)
);

-- Per-period job selection (which eligible jobs to include in this month)
CREATE TABLE IF NOT EXISTS projection_period_jobs (
    id INTEGER PRIMARY KEY,
    period_id INTEGER NOT NULL REFERENCES projection_periods(id) ON DELETE CASCADE,
    allocation_id INTEGER NOT NULL REFERENCES project_allocations(id) ON DELETE CASCADE,
    included INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(period_id, allocation_id)
);

-- Job-level detail under project-level projection_entries
CREATE TABLE IF NOT EXISTS projection_entry_details (
    id INTEGER PRIMARY KEY,
    entry_id INTEGER NOT NULL REFERENCES projection_entries(id) ON DELETE CASCADE,
    allocation_id INTEGER NOT NULL REFERENCES project_allocations(id),
    job_code TEXT NOT NULL,
    allocated_hours REAL NOT NULL DEFAULT 0,
    projected_cost REAL NOT NULL DEFAULT 0,
    weight_used REAL,
    is_manual_override INTEGER NOT NULL DEFAULT 0,
    notes TEXT,
    UNIQUE(entry_id, allocation_id)
);
