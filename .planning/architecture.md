# QMS Architecture Reference

> System map for the Quality Management System. Updated 2026-02-23.

## Directory Structure

```
D:\qms\                              # Repo root = package root
├── .git/, .gitignore, CLAUDE.md
├── pyproject.toml                   # Package metadata + optional [web] extra
├── config.yaml                      # All settings (relative paths)
├── SIS QMS.url                      # Desktop shortcut (hostname-based)
├── .planning/                       # Architecture docs, roadmap, planning
│
├── data/                            # Runtime data (git-ignored)
│   ├── quality.db                   # SQLite database (source of truth)
│   ├── inbox/                       # Unified document intake
│   │   ├── NEEDS-REVIEW/
│   │   ├── CONFLICTS/
│   │   └── DUPLICATES/
│   ├── projects/                    # Engineering drawings by project
│   ├── quality-documents/           # QM procedures, forms, references
│   └── vectordb/                    # ChromaDB semantic search
│
├── core/                            # Shared services
│   ├── db.py                        # get_db(), migrate_all(), SCHEMA_ORDER
│   ├── config.py                    # get_config(), get_branding(), get_web_modules(), QMS_PATHS
│   ├── logging.py                   # get_logger()
│   └── paths.py, output.py
│
├── auth/                            # Local email+password auth + roles
│   ├── schema.sql, db.py, decorators.py, migrations.py, cli.py
│
├── api/                             # Flask web backend (11 files)
│   ├── __init__.py                  # App factory (create_app), home dashboard
│   ├── auth.py                      # Blueprint: /auth/*
│   ├── projects.py                  # Blueprint: /projects/*
│   ├── timetracker.py               # Blueprint: /timetracker/* (admin-only)
│   ├── welding.py                   # Blueprint: /welding/*
│   ├── pipeline.py                  # Blueprint: /pipeline/*
│   ├── automation.py                # Blueprint: /automation/*
│   ├── blog.py                      # Blueprint: /blog/*
│   ├── settings.py                  # Blueprint: /settings/* (9 tabs)
│   ├── workforce.py                 # Blueprint: /workforce/*
│   └── qualitydocs.py               # Blueprint: /qualitydocs/*
│
├── frontend/
│   ├── templates/
│   │   ├── base.html                # Shared layout (sidebar nav)
│   │   ├── home.html                # Dashboard home
│   │   ├── admin/                   # Admin-only pages (system-map)
│   │   ├── auth/                    # Login, profile
│   │   ├── automation/              # Automation request preview
│   │   ├── blog/                    # Blog list + detail
│   │   ├── pipeline/                # Drawing intake dashboard
│   │   ├── projects/                # Project pages + hub detail
│   │   ├── qualitydocs/             # Quality manual viewer
│   │   ├── settings/                # Settings UI (9 tabs)
│   │   ├── timetracker/             # Projections + transactions
│   │   ├── welding/                 # 8 templates (dashboard, forms, welders)
│   │   └── workforce/               # Employee management + import wizard
│   └── static/
│       ├── style.css                # Shared CSS
│       ├── dark.css                 # Dark mode styles
│       ├── brand-fonts.css          # Brand font definitions
│       ├── favicon.ico              # Multi-size ICO favicon
│       └── mascot.svg               # SIS mascot graphic
│
├── engineering/                     # Calculation library + design verification
│   ├── refrig_calc/                 # Vendored refrig_calc (20 modules, zero deps)
│   ├── refrigeration.py             # RefrigerationCalculator (ABC impl)
│   ├── validators.py                # Drawing vs calculation validation
│   ├── db.py, output.py, base.py, cli.py
│
├── imports/                         # Shared import infrastructure
│   ├── specs.py                     # Dataclasses: ImportSpec, ColumnDef, ActionItem, ActionPlan
│   ├── engine.py                    # Parse, map, plan, execute, session CRUD
│   └── schema.sql                   # import_sessions + import_actions tables
│
├── welding/                         # WPS/WPQ/continuity + forms pipeline
│   ├── forms/, extraction/, generation/  # Form pipeline (28 files)
│   └── cli.py                       # 18 commands
├── projects/                        # Project scanner + budget tracking
│   ├── budget.py                    # Per-BU allocations, hub data, rollup sync
│   ├── excel_io.py, procore_io.py   # Import/export
│   ├── migrations.py, migrate_timetracker.py
├── timetracker/                     # Time tracking & projections (admin-only)
│   ├── projections.py, transactions.py, timecard.py, cli.py
├── workforce/                       # Employee management
│   ├── employees.py                 # CRUD, duplicate detection, certifications
│   └── import_specs.py              # 15-column spec, 4-level match
├── automation/                      # JSON request dispatcher (Power Automate)
├── blog/                            # The Observatory (scheduled publishing)
│   ├── schema.sql, db.py, migrations.py
├── qualitydocs/                     # Quality manual loader
├── references/                      # Reference standard extraction
├── pipeline/                        # Drawing intake pipeline
├── vectordb/                        # Semantic search (ChromaDB)
├── reporting/                       # Reports (system command)
├── cli/main.py                      # Typer CLI entrypoint
└── tests/                           # Test suite (480+ tests)
```

## Database

Single SQLite database at `data/quality.db`.

| Fact | Value |
|------|-------|
| Tables | 263 (including FTS virtual tables) |
| Schema files | 13 (`core`, `auth`, `imports`, `workforce`, `projects`, `timetracker`, `qualitydocs`, `references`, `welding`, `pipeline`, `engineering`, `automation`, `blog`) |
| FK chain | Controlled by `SCHEMA_ORDER` in `core/db.py` |
| Shared table | `business_units` — used by projects, welding, pipeline |

**Budget model** (three-tier):
`projects` (5-digit base) → `project_allocations` (per-BU breakdown) → `project_budgets` (rollup total)
`sync_budget_rollup()` keeps `project_budgets.total_budget = SUM(project_allocations.allocated_budget)`.

## Web Architecture

`qms serve` → Waitress on `0.0.0.0:5000` (8 threads, LAN-accessible).
`qms serve --debug` → Flask dev server on `127.0.0.1:5000` (auto-reload).

**Key rule:** Business logic stays in module files — NO Flask imports in `projects/budget.py`, `workforce/employees.py`, etc. The API layer wraps results in Flask responses.

```
api/__init__.py       → create_app(), blueprint registration, home dashboard
api/auth.py           → /auth/* — login/logout/users/employee-link
api/projects.py       → /projects/* — project hub + budget APIs
api/timetracker.py    → /timetracker/* — projections + transactions (admin-only)
api/welding.py        → /welding/* — dashboard/forms/welders
api/pipeline.py       → /pipeline/* — intake dashboard
api/automation.py     → /automation/* — request preview
api/blog.py           → /blog/* — The Observatory + admin API
api/settings.py       → /settings/* — 9-tab settings UI (incl. BU CRUD)
api/workforce.py      → /workforce/* — employee CRUD + import wizard
api/qualitydocs.py    → /qualitydocs/* — quality manual viewer
```

## Config-Driven Module Registry

Single source of truth: `config.yaml` → `web_modules:` section.

- `get_web_modules()` in `core/config.py` reads module list with defaults fallback
- Adding a web module = 3 lines in config.yaml (no code changes, no migrations)
- `api/__init__.py` builds `_BLUEPRINT_MODULE`, `_MODULE_DEFAULTS`, `accessible` set from config
- `base.html` nav tabs loop over `web_modules` context variable

## Auth System

| Aspect | Detail |
|--------|--------|
| Provider | Local email + password |
| Flow | POST /auth/login → validate → session cookie |
| Roles | `admin \| user \| viewer` in `users` table |
| Module access | `user_module_access` table — per-module `admin \| editor \| viewer` |
| BU access | `user_business_units` table — restricts visible BUs/projects |
| Dev bypass | `auth.dev_bypass: true` in config auto-creates admin session |
| Gate | `before_request` in app factory; admins bypass module checks |

## Theming

- **Branding**: `config.yaml` → `branding:` section (colors, fonts, app_name)
- **get_branding()** in `core/config.py` merges config with defaults
- **Dark mode**: `localStorage('qms-theme-mode')` + `data-theme="dark"` on `<html>`
- **Cascade order**: style.css → brand `<style>` block → dark.css

## Module Overview

| Module | Schema | API Blueprint | Templates | CLI |
|--------|--------|---------------|-----------|-----|
| core | core/schema.sql | — | — | version, migrate, serve |
| auth | auth/schema.sql | auth.py | auth/ | 5 commands |
| engineering | engineering/schema.sql | — | — | 8 commands |
| welding | welding/schema.sql | welding.py | welding/ | 18 commands |
| projects | projects/schema.sql | projects.py | projects/ | 4 commands |
| timetracker | timetracker/schema.sql | timetracker.py | timetracker/ | 2 commands |
| workforce | workforce/schema.sql | workforce.py | workforce/ | 4 commands |
| qualitydocs | qualitydocs/schema.sql | qualitydocs.py | qualitydocs/ | 4 commands |
| references | references/schema.sql | — | — | 4 commands |
| pipeline | pipeline/schema.sql | pipeline.py | pipeline/ | 6 commands |
| automation | automation/schema.sql | automation.py | automation/ | 2 commands |
| blog | blog/schema.sql | blog.py | blog/ | — (web-only) |
| imports | imports/schema.sql | — | — | — (web-only wizard) |
| reporting | — | — | — | 1 command |
| vectordb | — | — | — | 4 commands |
| settings | — | settings.py | settings/ | — |
| admin | — | — | admin/ | — |
