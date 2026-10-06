---
module: projects
cli_name: projects
status: Complete
commands: [scan, list, summary, migrate-timetracker, export-timecard]
depends_on: [core, workforce]
depended_by: [engineering, welding, pipeline, qualitydocs, web]
tables: [customers, business_units, projects, project_codes, project_patterns, project_flags, jobs, project_budgets, project_allocations, project_transactions, budget_settings, projection_periods, projection_snapshots, projection_entries, projection_period_jobs, projection_entry_details]
api_blueprint: api/projects.py
source_dir: projects/
schema_file: projects/schema.sql
tags: [qms-module, project-management, budget]
created: 2026-02-10
updated: 2026-02-11
---

# Projects

The **central hub** of QMS — manages projects, jobs, budgets, allocations, transactions, and projections. Defines the shared `business_units` table used across multiple modules.

## Architecture

- **3-tier budget model:** `projects` → `project_allocations` (per-BU) → `project_budgets` (rollup)
- `business_units` is a **shared table** used by [[welding]] and [[pipeline]]
- `jobs` = department-scoped work (job_number = project + BU code + suffix)
- **GMP (Guaranteed Maximum Price):** Per-job flag on `project_allocations.is_gmp` — GMP jobs receive a configurable weight multiplier in projections
- **Weight adjustment:** Per-allocation multiplier on hour share (range 0.00–5.00, step 0.05). Formula: `weight = effective_budget × weight_adjustment × gmp_factor`. Scroll-wheel adjustable on sliders.
- **Two-tier projection filtering:** Global `projection_enabled` flag (Projects page) gates eligibility; per-period `included` toggle (Projections page) controls monthly inclusion
- **Job-level projections:** `calculate_projection()` allocates hours per-job (not per-project), pro-rating remaining budget from project-level spending
- 9 project stages: Archive, Bidding, Construction and Bidding, Course of Construction, Lost Proposal, Post-Construction, Pre-Construction, Proposal, Warranty
- Business logic in `projects/budget.py` — **NO Flask imports** (clean separation)
- Incremental migrations in `projects/migrations.py` for ALTER TABLE operations

## CLI Commands

| Command | Description |
|---------|-------------|
| `qms projects scan [project]` | Scan project directories and update database |
| `qms projects list [--stage]` | List all projects |
| `qms projects summary <project>` | Show project summary with discipline breakdown |
| `qms projects migrate-timetracker [db_path]` | One-time import from Time Tracker DB |
| `qms projects export-timecard <period>` | Export UKG timecard for a period (cross-month support) |

## Database Tables (16 total)

### Project Registry
| Table | Purpose |
|-------|---------|
| `customers` | Customer registry |
| `business_units` | **Shared:** 3-digit BU codes (used by [[welding]], [[pipeline]]) |
| `projects` | Project master (number, name, stage, PM, dates) |
| `project_codes` | Project identification codes |
| `project_patterns` | Pattern matching rules for intake routing |
| `project_flags` | Project-level flags |
| `jobs` | Department-scoped work within projects |

### Budget & Finance
| Table | Purpose |
|-------|---------|
| `project_budgets` | 1:1 with projects (total_budget rollup) |
| `project_allocations` | Per-BU budget allocations (weight adjustments, GMP flag) |
| `project_transactions` | Spending ledger (Time, Travel, Materials, Other) |
| `budget_settings` | Singleton config (hourly rate, working hours, fiscal year, GMP multiplier) |

### Projections
| Table | Purpose |
|-------|---------|
| `projection_periods` | Monthly periods (lockable) |
| `projection_snapshots` | Versioned projection snapshots (Draft → Committed → Superseded) |
| `projection_entries` | Per-project allocations within snapshots (aggregated from job-level) |
| `projection_period_jobs` | **NEW:** Per-period job selection toggles (included/excluded per month) |
| `projection_entry_details` | **NEW:** Job-level detail under project-level entries |

## Key Functions

| Function | Location | Description |
|----------|----------|-------------|
| `list_projects_with_budgets()` | `projects/budget.py` | All projects with budget info |
| `create_project_with_budget()` | `projects/budget.py` | Create project + budget + allocations |
| `sync_budget_rollup()` | `projects/budget.py` | Sync total = SUM(allocations) |
| `calculate_projection()` | `projects/budget.py` | Job-level hour allocation with GMP weighting (uses period_jobs) |
| `load_period_jobs()` | `projects/budget.py` | Load/auto-populate per-period job selection |
| `toggle_period_job()` | `projects/budget.py` | Toggle job inclusion for a specific period |
| `list_snapshots()` | `projects/budget.py` | List all snapshots for a period |
| `get_snapshot_with_details()` | `projects/budget.py` | Snapshot metadata + entries with nested job details |
| `commit_snapshot()` | `projects/budget.py` | Commit snapshot: lock period, record costs |
| `uncommit_snapshot()` | `projects/budget.py` | Revert committed snapshot back to Draft |
| `has_committed_projections()` | `projects/budget.py` | Check if project has committed projection costs |
| `get_budget_summary()` | `projects/budget.py` | Extended budget listing with committed + projected costs |
| `update_allocation_field()` | `projects/budget.py` | Update single field on allocation (incl. is_gmp) |
| `bulk_update_allocations()` | `projects/budget.py` | Bulk set stage/projection/gmp/weight or delete |
| `scan_and_sync_project()` | `projects/scanner.py` | Scan directory, sync to DB |
| `import_projects_from_excel()` | `projects/excel_io.py` | Bulk import from Excel |
| `run_all_migrations()` | `projects/migrations.py` | Incremental schema migrations (includes GMP) |
| `migrate()` | `projects/timetracker.py` | One-time Time Tracker import |

## Dependencies

### Depends On
- [[core]] — Database, logging, config
- [[workforce]] — `employees` table for PM linkages

### Depended By
- [[engineering]] — Project lookups for validation
- [[welding]] — Shared `business_units` table
- [[pipeline]] — Project lookups, shared `business_units`
- [[qualitydocs]] — `qm_records` links to projects
- [[web]] — API blueprint for web UI

## Related Notes
- [[web]] — Flask API blueprint for project management UI
- [[Business Units]] — Shared table documentation
- [[Database Overview]] — FK dependency map
