# QMS — Quality Management System

Modular Python package at `D:\qms\` for construction drawing review, quality document management, and engineering calculations.

## Git Workflow (MANDATORY)

**Repository:** `https://github.com/bjohnson1-stellar/QMS.git`
**Branch:** `main`

### Auto-Commit Rule
**ALWAYS commit and push after completing a batch of work.** Do not wait to be asked.

```bash
cd D:\qms

# Stage files (exclude data/)
git add -A -- ':!data'

# Commit with descriptive message
git commit -m "description of changes

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"

# Push immediately
git push origin main
```

### What to commit
- All package code (including `.planning/`)
- `.gitignore`, `CLAUDE.md`, `pyproject.toml`, `config.yaml`

### What to NEVER commit
- `data/` — runtime data (database, projects, documents, vectordb)
- `*.db`, `*.db-shm`, `*.db-wal` — database files
- `.mcp.json` — local MCP config
- `*.egg-info/` — build artifacts

### Roadmap Maintenance
**ALWAYS update `.planning/roadmap.json` when completing or adding features.**
- When a feature is **completed**: move it to "Recently Completed" with a `"completed": "YYYY-MM-DD"` date
- When a **new feature** is started or planned: add it to "In Progress" or "Planned" with module, priority, tags
- This feeds the admin system map at `/admin/system-map`

## Quick Start

```bash
pip install -e D:\qms        # Install editable (core)
pip install -e "D:\qms[web]" # Install with web UI (Flask)
qms version                  # Show version
qms migrate                  # Run all schema migrations
qms serve                    # Launch web UI at localhost:5000
qms welding dashboard        # Welding program status
qms docs summary             # Quality manual summary
qms refs search <term>       # Search reference standards
qms projects scan            # Scan project folders
qms projects migrate-timetracker  # Import from Time Tracker DB
qms eng line-sizing          # Run pipe sizing calculation
qms eng --help               # All engineering commands
```

## Directory Structure

```
D:\qms\                          # Repo root = package root
├── .git/                        # Git repository
├── .gitignore
├── CLAUDE.md                    # This file
├── pyproject.toml
├── config.yaml                  # All settings (relative paths)
├── .planning/                   # Architecture docs
│
├── data/                        # Runtime data (git-ignored)
│   ├── quality.db               # SQLite database (source of truth)
│   ├── inbox/                   # Drop ALL documents here
│   │   ├── NEEDS-REVIEW/
│   │   ├── CONFLICTS/
│   │   └── DUPLICATES/
│   ├── projects/                # Engineering drawings by project
│   ├── quality-documents/       # QM procedures, forms, references
│   └── vectordb/                # ChromaDB semantic search
│
├── core/                        # Shared services
│   ├── db.py                    # get_db(), migrate_all()
│   ├── config.py                # get_config(), QMS_PATHS
│   ├── logging.py               # get_logger()
│   └── paths.py, output.py
│
├── auth/                        # Local email+password auth + roles
│   ├── schema.sql, db.py, decorators.py, migrations.py, cli.py
│
├── api/                         # Flask web backend
│   ├── __init__.py              # App factory (create_app)
│   ├── auth.py                  # Blueprint: /auth/* routes
│   ├── projects.py              # Blueprint: /projects/* routes
│   ├── welding.py               # Blueprint: /welding/* routes
│   ├── pipeline.py              # Blueprint: /pipeline/* routes
│   ├── automation.py            # Blueprint: /automation/* routes
│   ├── blog.py                  # Blueprint: /blog/* routes
│   └── settings.py              # Blueprint: /settings/* routes
│
├── frontend/                    # Web UI assets
│   ├── templates/
│   │   ├── base.html            # Shared layout (sidebar nav)
│   │   ├── auth/                # Login, profile templates
│   │   ├── projects/            # 5 project pages (Jinja2)
│   │   ├── welding/             # 8 welding templates
│   │   ├── settings/            # Settings UI templates
│   │   ├── automation/          # Automation templates
│   │   ├── pipeline/            # Pipeline templates
│   │   └── blog/                # Blog list + detail pages
│   └── static/
│       ├── style.css            # Shared CSS
│       ├── dark.css             # Dark mode styles
│       ├── brand-fonts.css      # Brand font definitions
│       └── favicon.ico          # Multi-size ICO favicon
│
├── engineering/                 # Calculation library + design verification
│   ├── refrig_calc/             # Vendored refrig_calc (20 modules, zero deps)
│   ├── refrigeration.py         # RefrigerationCalculator (ABC impl)
│   ├── validators.py            # Drawing vs calculation validation
│   ├── db.py                    # Calculation audit trail
│   ├── output.py                # Result formatters
│   ├── base.py                  # DisciplineCalculator ABC
│   └── cli.py                   # 8 commands
│
├── automation/                  # JSON request dispatcher (Power Automate intake)
├── blog/                        # The Observatory blog (scheduled publishing)
│   ├── schema.sql, db.py, migrations.py
├── welding/                     # WPS/WPQ/continuity tracking + forms pipeline
│   ├── forms/, extraction/, generation/  # Form pipeline (28 files)
│   └── cli.py                   # 18 commands
├── qualitydocs/                 # Quality manual loader
├── references/                  # Reference standard extraction
├── projects/                    # Project scanner + budget tracking
│   ├── budget.py                # Per-BU allocations, budget queries, rollup sync
│   ├── excel_io.py, procore_io.py  # Import/export (Excel, Procore)
│   ├── migrations.py            # Incremental schema migrations
│   └── migrate_timetracker.py   # One-time TT data migration
├── pipeline/                    # Drawing intake pipeline
├── workforce/                   # Employee management
├── vectordb/                    # Semantic search
├── reporting/                   # Reports
└── cli/main.py                  # Typer CLI entrypoint
```

## Key Paths

| Resource | Path |
|----------|------|
| Package root | `D:\qms\` |
| Config | `D:\qms\config.yaml` |
| Database | `D:\qms\data\quality.db` |
| Vector Database | `D:\qms\data\vectordb\` |
| Unified Inbox | `D:\qms\data\inbox\` |
| Projects | `D:\qms\data\projects\` |
| Quality Documents | `D:\qms\data\quality-documents\` |
| Planning docs | `D:\qms\.planning\` |

All paths in `config.yaml` are **relative** to the package root. The `QMS_PATHS` singleton resolves them automatically.

## CLI Commands (65 total)

| Module | Commands |
|--------|----------|
| `qms` (top-level) | `version`, `migrate`, `serve` |
| `qms eng` | `history`, `line-sizing`, `relief-valve`, `pump`, `ventilation`, `charge`, `validate-pipes`, `validate-relief` |
| `qms welding` | `dashboard`, `continuity`, `import-wps`, `import-weekly`, `check-notifications`, `register`, `export-lookups`, `cert-requests`, `cert-results`, `approve-wcr`, `assign-wpq`, `schedule-retest`, `process-requests`, `seed-lookups`, `extract`, `generate`, `register-template`, `derive-ranges` |
| `qms automation` | `process`, `status` |
| `qms docs` | `load-module`, `summary`, `search`, `detail` |
| `qms refs` | `extract`, `list`, `search`, `clauses` |
| `qms projects` | `scan`, `list`, `summary`, `import-procore`, `export-timecard`, `migrate-timetracker` |
| `qms pipeline` | `status`, `queue`, `import-drawing`, `import-batch`, `process`, `intake` |
| `qms workforce` | `list`, `import-csv`, `import-from-sis`, `bulk-update` |
| `qms vectordb` | `index`, `search`, `status`, `queue` |
| `qms auth` | `create-user`, `reset-password`, `grant-access`, `revoke-access`, `list-users` |
| `qms report` | `system` |

## Unified Inbox

**Drop ALL documents in `D:\qms\data\inbox\`** — the system classifies and routes automatically:

| Document Type | Example | Routes To |
|---------------|---------|-----------|
| Drawings | `P-101_Rev_B.pdf` | `data/projects/{project}/{discipline}/` |
| Specifications | `242300-Refrigeration_Rev_01.pdf` | `data/projects/{project}/{set}/Specs/` |
| Procedures | `SP-001-Welding.pdf` | `data/quality-documents/Procedures/` |
| Forms | `FM-001-Inspection.pdf` | `data/quality-documents/Forms/` |
| QM Modules | `module1.xml` | `data/quality-documents/Modules/` |

## Engineering Calculations

The `qms eng` module wraps the `refrig_calc` library for industrial refrigeration:

```bash
qms eng line-sizing --capacity-tons 200 --line-type wet
qms eng relief-valve --volume-cuft 150 --set-pressure-psig 300
qms eng pump --capacity-tons 100 --recirculation-rate 4
qms eng ventilation --length-ft 40 --width-ft 25 --height-ft 14
qms eng charge --volume-cuft 20 --temperature -20

# Validate drawings against calculations
qms eng validate-pipes 07645
qms eng validate-relief 07645
```

All calculations are saved to the `eng_calculations` audit trail.

## Development

### Imports

```python
from qms.core import get_db, get_config, get_logger, QMS_PATHS
from qms.engineering.refrigeration import RefrigerationCalculator, run_line_sizing
from qms.engineering.refrig_calc import NH3Properties, LineSizing
```

### Database

Single SQLite database at `QMS_PATHS.database` with 256 tables across 10 schema files. FK dependency chain controlled by `SCHEMA_ORDER` in `core/db.py`. The `business_units` table is shared by projects, welding, and pipeline modules.

**Budget model** (three-tier): `projects` (5-digit base) → `project_allocations` (per-BU breakdown) → `project_budgets` (rollup total). The `sync_budget_rollup()` function in `budget.py` keeps `project_budgets.total_budget = SUM(project_allocations.allocated_budget)`.

```python
from qms.core import get_db
with get_db() as conn:
    conn.execute("SELECT * FROM projects")
```

### Web Architecture

`qms serve` launches a Flask app at `http://localhost:5000`. The app factory in `api/__init__.py` registers module blueprints. Business logic stays in module files (NO Flask imports in `projects/budget.py` etc.) — the API layer wraps results in Flask responses.

```
api/__init__.py     → create_app(), registers blueprints
api/auth.py         → Blueprint /auth/*, login/logout/users
api/projects.py     → Blueprint /projects/*, calls budget.py
api/welding.py      → Blueprint /welding/*, dashboard/forms
api/pipeline.py     → Blueprint /pipeline/*, intake dashboard
api/automation.py   → Blueprint /automation/*, request preview
api/blog.py         → Blueprint /blog/*, The Observatory blog + admin API
api/settings.py     → Blueprint /settings/*, 8-tab settings UI + blog editor
projects/budget.py  → Pure business logic (allocation, queries)
frontend/templates/ → Jinja2 templates extending base.html
frontend/static/    → Shared CSS/JS (style.css, dark.css, brand-fonts.css, favicon.ico)
```

Optional dependency: `pip install -e ".[web]"` for Flask.

### Model Routing

| Model | Tasks |
|-------|-------|
| Haiku | File routing, pattern matching, title block reading |
| Sonnet | Full extraction, conflict detection, report generation |
| Opus | Shadow review (10%), critical decisions, ambiguous routing |
