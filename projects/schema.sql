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

-- Facilities (physical sites belonging to a customer)
CREATE TABLE IF NOT EXISTS facilities (
    id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    name TEXT NOT NULL,
    street TEXT,
    city TEXT,
    state TEXT,
    zip TEXT,
    status TEXT DEFAULT 'active',
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(customer_id, name)
);

-- Project contacts (corporate, site, or project-level)
CREATE TABLE IF NOT EXISTS project_contacts (
    id INTEGER PRIMARY KEY,
    customer_id INTEGER REFERENCES customers(id),
    facility_id INTEGER REFERENCES facilities(id),
    project_id INTEGER REFERENCES projects(id),
    name TEXT NOT NULL,
    role TEXT,
    email TEXT,
    phone TEXT,
    is_primary INTEGER DEFAULT 0,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_pc_customer ON project_contacts(customer_id);
CREATE INDEX IF NOT EXISTS idx_pc_facility ON project_contacts(facility_id);
CREATE INDEX IF NOT EXISTS idx_pc_project ON project_contacts(project_id);

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
    facility_id INTEGER REFERENCES facilities(id),
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
    is_gmp INTEGER NOT NULL DEFAULT 0,
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

-- NOTE: project_transactions, budget_settings, and projection tables
-- have been moved to timetracker/schema.sql
