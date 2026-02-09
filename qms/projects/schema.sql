-- =============================================================================
-- QMS Projects Schema
-- Projects, customers, jobs
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

-- Projects
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY,
    number TEXT UNIQUE,
    name TEXT NOT NULL,
    client TEXT,
    path TEXT,
    status TEXT DEFAULT 'active',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    customer_id INTEGER REFERENCES customers(id),
    street TEXT,
    city TEXT,
    state TEXT,
    zip TEXT,
    pm TEXT,
    pm_employee_id TEXT REFERENCES employees(id)
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
    department_id INTEGER NOT NULL REFERENCES departments(id),
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
