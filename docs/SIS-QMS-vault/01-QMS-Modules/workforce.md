---
module: workforce
cli_name: workforce
status: Complete
commands: [list, import-csv, import-from-sis, bulk-update]
depends_on: [core]
depended_by: [projects, welding, pipeline]
tables: [departments, roles, permissions, role_permissions, employees, employee_contacts, employment_history, employee_certifications, employee_quality_documents, employee_permissions]
api_blueprint: "-"
source_dir: workforce/
schema_file: workforce/schema.sql
tags: [qms-module, hr, employees]
created: 2026-02-10
updated: 2026-02-10
---

# Workforce

Manages the **employee registry** — the people side of the quality system. Tracks employees, subcontractors, certifications, employment history, roles, and permissions. Second in the schema dependency chain after [[core]].

## Architecture

- Employee IDs are **TEXT UUIDs** (not auto-increment integers)
- Dual identity: employees can be `is_employee=1` and/or `is_subcontractor=1`
- Auto-generated employee numbers (`E-XXXX`) and subcontractor numbers (`S-XXXX`)
- RBAC model: `roles` → `role_permissions` → `permissions`, with per-employee overrides
- Self-referencing supervisor hierarchy in `employees` table
- `departments` table is **legacy** — being replaced by `business_units` from [[projects]]

## CLI Commands

| Command | Description |
|---------|-------------|
| `qms workforce list [--active-only]` | List employees |
| `qms workforce import-csv <file>` | Import employees from CSV |
| `qms workforce import-from-sis <file>` | Import employees from SIS workbook |
| `qms workforce bulk-update <file>` | Bulk-update employee records from CSV |

## Database Tables (10 total)

| Table | Purpose |
|-------|---------|
| `departments` | **Legacy** — being replaced by `business_units` |
| `roles` | Role definitions with hierarchy levels |
| `permissions` | Permission codes by module/category |
| `role_permissions` | Role ↔ Permission mapping |
| `employees` | Employee master (UUID id, employee_number, supervisor FK, role FK) |
| `employee_contacts` | Additional contacts (work, personal, emergency) |
| `employment_history` | Hire/rehire/promotion/transfer/separation events |
| `employee_certifications` | Certifications with expiry tracking |
| `employee_quality_documents` | Quality docs (WPQ, Cert, Test, Qualification) |
| `employee_permissions` | Individual permission overrides |

## Key Functions

| Function | Location | Description |
|----------|----------|-------------|
| `create_employee()` | `workforce/` | Create employee record |
| `find_employee_by_number()` | `workforce/` | Lookup by employee number |
| `find_employee_by_name()` | `workforce/` | Lookup by name |
| `terminate_employee()` | `workforce/` | Record separation |
| `rehire_employee()` | `workforce/` | Rehire terminated employee |
| `import_from_csv()` | `workforce/` | CSV import with duplicate detection |
| `import_employees_from_sis()` | `workforce/` | SIS workbook import |
| `add_certification()` | `workforce/` | Add certification with expiry |
| `get_expiring_certifications()` | `workforce/` | Find expiring certifications |
| `grant_permission()` | `workforce/` | Grant permission override |
| `get_employee_permissions()` | `workforce/` | Get effective permissions (role + overrides) |

## Dependencies

### Depends On
- [[core]] — Database, logging

### Depended By
- [[projects]] — `employees` table for PM linkages (`pm_employee_id`)
- [[welding]] — `employees` table for welder linkages (`employee_id`)
- [[pipeline]] — Employee import from SIS sheets

## Related Notes
- [[projects]] — PM assignment, shared `business_units` replacing `departments`
- [[welding]] — Welder ↔ Employee linkage
