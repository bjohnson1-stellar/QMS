---
tags: [api, overview, flask]
created: 2026-02-10
---

# API Overview

> **Base URL:** `http://localhost:5000`
> **Launch:** `qms serve`
> **App factory:** `api/__init__.py`

## Root Route
| Method | URL | Action |
|--------|-----|--------|
| GET | `/` | Redirects to `/projects/` |

## Projects Blueprint (`/projects`)

### Page Routes (HTML)
| Method | URL | Template | Description |
|--------|-----|----------|-------------|
| GET | `/projects/` | `dashboard.html` | Dashboard with stats and monthly allocation |
| GET | `/projects/manage` | `projects.html` | Project CRUD with BU allocations |
| GET | `/projects/business-units` | `business_units.html` | Business unit management |
| GET | `/projects/transactions` | `transactions.html` | Spending ledger |
| GET | `/projects/settings` | `settings.html` | Application settings |
| GET | `/projects/projections` | `projections.html` | Monthly projection system |

### Projects API
| Method | URL | Description |
|--------|-----|-------------|
| GET | `/projects/api/projects` | List all projects with budgets |
| POST | `/projects/api/projects` | Create project (validates number format, checks duplicates) |
| PUT | `/projects/api/projects/<id>` | Update project |
| DELETE | `/projects/api/projects/<id>` | Delete project (cascades to budget/allocations; blocked if committed projections exist) |

### Allocations API
| Method | URL | Description |
|--------|-----|-------------|
| GET | `/projects/api/projects/<pid>/allocations` | Get BU allocations for project |
| POST | `/projects/api/projects/<pid>/allocations` | Upsert allocation (buCode, subjob, budget, weight) |
| DELETE | `/projects/api/projects/<pid>/allocations/<aid>` | Delete allocation |
| PATCH | `/projects/api/allocations/<aid>/gmp` | Toggle GMP flag on allocation (`{isGmp: bool}`) |
| PATCH | `/projects/api/allocations/bulk` | Bulk update allocations (`{ids, action, value}`). Actions: `set_stage`, `set_projection`, `set_gmp`, `set_weight` (0.00–5.00), `delete` |

### Business Units API
| Method | URL | Description |
|--------|-----|-------------|
| GET | `/projects/api/business-units` | List all business units |
| POST | `/projects/api/business-units` | Create BU (code must be 3 digits) |
| PUT | `/projects/api/business-units/<id>` | Update BU |
| DELETE | `/projects/api/business-units/<id>` | Delete BU (fails if in use) |

### Transactions API
| Method | URL | Description |
|--------|-----|-------------|
| GET | `/projects/api/transactions` | List (filters: project_id, type) |
| GET | `/projects/api/transactions/<id>` | Get single transaction |
| POST | `/projects/api/transactions` | Create (auto-calculates amount for Time type) |
| PUT | `/projects/api/transactions/<id>` | Update transaction |
| DELETE | `/projects/api/transactions/<id>` | Delete transaction |

### Settings API
| Method | URL | Description |
|--------|-----|-------------|
| GET | `/projects/api/settings` | Get settings (company, rate, hours, fiscal year, GMP multiplier) |
| PUT | `/projects/api/settings` | Update settings (includes `gmpWeightMultiplier`) |

### Projection Periods API
| Method | URL | Description |
|--------|-----|-------------|
| GET | `/projects/api/projection-periods` | List all periods |
| POST | `/projects/api/projection-periods` | Create period (validates year 2020-2100, month 1-12) |
| GET | `/projects/api/projection-periods/<id>` | Get single period |
| PUT | `/projects/api/projection-periods/<id>/lock` | Toggle period lock |

### Projection Period Jobs API
| Method | URL | Description |
|--------|-----|-------------|
| GET | `/projects/api/projection-periods/<pid>/jobs` | List eligible jobs for period (auto-populates on first access) |
| PATCH | `/projects/api/projection-periods/<pid>/jobs/<aid>/toggle` | Toggle single job inclusion (`{included: bool}`) |
| PATCH | `/projects/api/projection-periods/<pid>/jobs/bulk-toggle` | Bulk toggle jobs (`{allocation_ids, included}`) |

### Projections API
| Method | URL | Description |
|--------|-----|-------------|
| POST | `/projects/api/projections/calculate` | Calculate job-level projection for period (GMP-weighted, respects period job toggles) |
| GET | `/projects/api/projections/<pid>` | Get active projection snapshot for period |
| POST | `/projects/api/projections/<pid>` | Create snapshot with job-level details (fails if locked) |
| GET | `/projects/api/projections/period/<pid>/snapshots` | List all snapshots for a period |
| GET | `/projects/api/projections/snapshot/<sid>` | Get snapshot with project-level entries and nested job details |
| PUT | `/projects/api/projections/snapshot/<sid>/activate` | Set snapshot as active (Draft only) |
| PUT | `/projects/api/projections/snapshot/<sid>/commit` | Commit snapshot: lock period, record costs, supersede others |
| PUT | `/projects/api/projections/snapshot/<sid>/uncommit` | Revert committed snapshot to Draft, unlock period |

### Budget Summary API
| Method | URL | Description |
|--------|-----|-------------|
| GET | `/projects/api/projects/budget-summary` | Projects with committed + projected costs and remaining budget |

### Excel Import/Export
| Method | URL | Description |
|--------|-----|-------------|
| GET | `/projects/api/projects/template` | Download Excel import template |
| POST | `/projects/api/projects/import` | Import projects from Excel |

## Transaction Types
- **Time** — Auto-calculated: hours × hourly rate
- **Travel** — Manual amount
- **Materials** — Manual amount
- **Other** — Manual amount

## Project Stages
Archive, Bidding, Construction and Bidding, Course of Construction, Lost Proposal, Post-Construction, Pre-Construction, Proposal, Warranty

## Related Notes
- [[web]] — Web module documentation
- [[projects]] — Business logic layer
- [[Architecture Overview]] — Request flow diagrams
