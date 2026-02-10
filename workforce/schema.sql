-- =============================================================================
-- QMS Workforce Schema
-- Employees, departments, roles, permissions, certifications
-- =============================================================================

-- Departments
CREATE TABLE IF NOT EXISTS departments (
    id INTEGER PRIMARY KEY,
    department_number TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    full_name TEXT,
    manager TEXT,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Roles
CREATE TABLE IF NOT EXISTS roles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role_name TEXT NOT NULL UNIQUE,
    role_code TEXT NOT NULL UNIQUE,
    description TEXT,
    hierarchy_level INTEGER,
    status TEXT DEFAULT 'active' CHECK(status IN ('active', 'inactive')),
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    created_by TEXT
);

-- Permissions
CREATE TABLE IF NOT EXISTS permissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    permission_code TEXT NOT NULL UNIQUE,
    permission_name TEXT NOT NULL,
    description TEXT,
    module TEXT,
    category TEXT,
    status TEXT DEFAULT 'active' CHECK(status IN ('active', 'inactive')),
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    created_by TEXT
);

-- Role-permission mapping
CREATE TABLE IF NOT EXISTS role_permissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role_id INTEGER NOT NULL REFERENCES roles(id),
    permission_id INTEGER NOT NULL REFERENCES permissions(id),
    created_at TEXT DEFAULT (datetime('now')),
    created_by TEXT,
    UNIQUE(role_id, permission_id)
);

-- Employees
CREATE TABLE IF NOT EXISTS employees (
    id TEXT PRIMARY KEY,
    employee_number TEXT UNIQUE,
    subcontractor_number TEXT UNIQUE,
    last_name TEXT NOT NULL,
    first_name TEXT NOT NULL,
    middle_initial TEXT,
    preferred_name TEXT,
    is_employee INTEGER DEFAULT 0 CHECK(is_employee IN (0, 1)),
    is_subcontractor INTEGER DEFAULT 0 CHECK(is_subcontractor IN (0, 1)),
    is_active INTEGER DEFAULT 1 CHECK(is_active IN (0, 1)),
    original_hire_date TEXT,
    current_hire_date TEXT,
    separation_date TEXT,
    department_id INTEGER REFERENCES departments(id),
    job_id INTEGER,
    position TEXT,
    supervisor_id TEXT REFERENCES employees(id),
    role_id INTEGER REFERENCES roles(id),
    email TEXT,
    phone TEXT,
    preferred_contact_method TEXT DEFAULT 'email' CHECK(preferred_contact_method IN ('email', 'phone', 'text', 'any')),
    ssn_last_four TEXT,
    status TEXT DEFAULT 'active' CHECK(status IN ('active', 'inactive', 'on_leave', 'terminated')),
    status_reason TEXT,
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    created_by TEXT,
    CHECK(is_employee = 1 OR is_subcontractor = 1)
);

-- Employee contacts (additional)
CREATE TABLE IF NOT EXISTS employee_contacts (
    id TEXT PRIMARY KEY,
    employee_id TEXT NOT NULL REFERENCES employees(id),
    contact_type TEXT CHECK(contact_type IN ('work', 'personal', 'emergency', 'other')),
    contact_method TEXT CHECK(contact_method IN ('phone', 'email', 'mobile', 'fax')),
    contact_value TEXT NOT NULL,
    is_primary INTEGER DEFAULT 0 CHECK(is_primary IN (0, 1)),
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    created_by TEXT
);

-- Employment history
CREATE TABLE IF NOT EXISTS employment_history (
    id TEXT PRIMARY KEY,
    employee_id TEXT NOT NULL REFERENCES employees(id),
    start_date TEXT NOT NULL,
    end_date TEXT,
    employment_type TEXT CHECK(employment_type IN ('employee', 'subcontractor', 'both')),
    position TEXT,
    department_id INTEGER REFERENCES departments(id),
    job_id INTEGER,
    supervisor_id TEXT REFERENCES employees(id),
    transition_type TEXT CHECK(transition_type IN ('hire', 'rehire', 'promotion', 'transfer', 'separation', 'termination')),
    reason_for_change TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    created_by TEXT
);

-- Certifications (all trades)
CREATE TABLE IF NOT EXISTS employee_certifications (
    id TEXT PRIMARY KEY,
    employee_id TEXT NOT NULL REFERENCES employees(id),
    certification_type TEXT NOT NULL,
    certification_number TEXT,
    issuing_organization TEXT,
    issue_date TEXT,
    expiry_date TEXT,
    renewal_required INTEGER DEFAULT 1 CHECK(renewal_required IN (0, 1)),
    renewal_reminder_days INTEGER DEFAULT 90,
    status TEXT DEFAULT 'active' CHECK(status IN ('active', 'expired', 'revoked', 'pending')),
    certificate_file_path TEXT,
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    created_by TEXT
);

-- Quality documents linked to employees
CREATE TABLE IF NOT EXISTS employee_quality_documents (
    id TEXT PRIMARY KEY,
    employee_id TEXT NOT NULL REFERENCES employees(id),
    document_type TEXT CHECK(document_type IN ('WPQ', 'Cert', 'Test', 'Qualification', 'Other')),
    document_number TEXT,
    document_title TEXT,
    issued_date TEXT,
    expiry_date TEXT,
    file_path TEXT,
    related_standard TEXT,
    status TEXT DEFAULT 'active' CHECK(status IN ('active', 'expired', 'superseded')),
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    created_by TEXT
);

-- Individual permission overrides
CREATE TABLE IF NOT EXISTS employee_permissions (
    id TEXT PRIMARY KEY,
    employee_id TEXT NOT NULL REFERENCES employees(id),
    permission_id INTEGER NOT NULL REFERENCES permissions(id),
    is_granted INTEGER NOT NULL CHECK(is_granted IN (0, 1)),
    granted_by TEXT,
    granted_date TEXT DEFAULT (datetime('now')),
    revoked_date TEXT,
    reason TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    UNIQUE(employee_id, permission_id)
);
