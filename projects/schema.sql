-- =============================================================================
-- QMS Projects Schema
-- Projects, customers, jobs, business units, budgets, projections
-- =============================================================================

-- Customers
CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    contact_name TEXT,
    contact_email TEXT,
    contact_phone TEXT,
    billing_street TEXT,
    billing_city TEXT,
    billing_state TEXT,
    billing_zip TEXT,
    status TEXT DEFAULT 'active',
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Business Units (unified department/BU table)
-- Replaces the former inline 'departments' table from pipeline/processor.py.
-- Shared by projects (jobs FK), welding (welder registry FK), and pipeline.
CREATE TABLE IF NOT EXISTS business_units (
    id INTEGER PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    full_name TEXT,
    description TEXT,
    manager TEXT,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_bu_code CHECK (code GLOB '[0-9][0-9][0-9]')
);
CREATE INDEX IF NOT EXISTS idx_bu_code ON business_units(code);

-- Projects
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY,
    number TEXT UNIQUE,
    name TEXT NOT NULL,
    client TEXT,
    path TEXT,
    status TEXT DEFAULT 'active',
    stage TEXT DEFAULT 'Proposal' CHECK (
        stage IN (
            'Archive', 'Bidding', 'Construction and Bidding',
            'Course of Construction', 'Lost Proposal',
            'Post-Construction', 'Pre-Construction', 'Proposal', 'Warranty'
        )
    ),
    start_date TEXT,
    end_date TEXT,
    notes TEXT,
    description TEXT,
    project_type TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    customer_id INTEGER REFERENCES customers(id),
    street TEXT,
    city TEXT,
    state TEXT,
    zip TEXT,
    pm TEXT,
    pm_employee_id TEXT REFERENCES employees(id),
    is_gmp INTEGER NOT NULL DEFAULT 0
);

-- Project identification codes
CREATE TABLE IF NOT EXISTS project_codes (
    id INTEGER PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id),
    code_name TEXT,
    code_year TEXT,
    UNIQUE(project_id, code_name)
);

-- Pattern matching rules for intake routing
CREATE TABLE IF NOT EXISTS project_patterns (
    id INTEGER PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id),
    pattern_type TEXT,
    pattern TEXT,
    confidence REAL DEFAULT 1.0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(project_id, pattern_type, pattern)
);

-- Project-level flags
CREATE TABLE IF NOT EXISTS project_flags (
    id INTEGER PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id),
    flag TEXT,
    message TEXT,
    resolved INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    resolved_at TEXT
);

-- Jobs (department-scoped work within a project)
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY,
    job_number TEXT UNIQUE NOT NULL,
    project_id INTEGER NOT NULL REFERENCES projects(id),
    department_id INTEGER NOT NULL REFERENCES business_units(id),
    project_number TEXT NOT NULL,
    department_number TEXT NOT NULL,
    suffix TEXT NOT NULL,
    scope_name TEXT NOT NULL,
    pm TEXT,
    status TEXT DEFAULT 'active',
    last_updated DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    pm_employee_id TEXT REFERENCES employees(id)
);

-- =============================================================================
-- Budget & Time Tracking Tables (from Time Tracker integration)
-- =============================================================================

-- Project budgets (1:1 with projects, budget-specific fields)
CREATE TABLE IF NOT EXISTS project_budgets (
    id INTEGER PRIMARY KEY,
    project_id INTEGER UNIQUE NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    total_budget REAL NOT NULL DEFAULT 0,
    weight_adjustment REAL NOT NULL DEFAULT 1.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Per-business-unit budget allocations within a project
CREATE TABLE IF NOT EXISTS project_allocations (
    id INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    business_unit_id INTEGER NOT NULL REFERENCES business_units(id),
    subjob TEXT NOT NULL DEFAULT '00',
    job_code TEXT NOT NULL,
    allocated_budget REAL NOT NULL DEFAULT 0,
    weight_adjustment REAL NOT NULL DEFAULT 1.0,
    notes TEXT,
    stage TEXT DEFAULT 'Course of Construction',
    projection_enabled INTEGER DEFAULT 1,
    scope_name TEXT,
    pm TEXT,
    job_id INTEGER REFERENCES jobs(id),
    is_gmp INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(project_id, business_unit_id, subjob)
);
CREATE INDEX IF NOT EXISTS idx_pa_project ON project_allocations(project_id);
CREATE INDEX IF NOT EXISTS idx_pa_bu ON project_allocations(business_unit_id);

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
