# QMS Development Guide

> Conventions, patterns, and how to build. Updated 2026-02-23.

## Installation

```bash
pip install -e D:\qms            # Core (CLI, database, all modules)
pip install -e "D:\qms[web]"     # + Flask web UI
```

## Import Patterns

```python
# Core services
from qms.core import get_db, get_config, get_logger, QMS_PATHS

# Engineering
from qms.engineering.refrigeration import RefrigerationCalculator, run_line_sizing
from qms.engineering.refrig_calc import NH3Properties, LineSizing

# Database access
from qms.core import get_db
with get_db() as conn:
    rows = conn.execute("SELECT * FROM projects").fetchall()
```

## Database Conventions

- Single SQLite DB at `QMS_PATHS.database` (= `data/quality.db`)
- Schema files live in each module directory: `{module}/schema.sql`
- FK dependency chain controlled by `SCHEMA_ORDER` in `core/db.py`
- Incremental migrations go in `{module}/migrations.py`, wired into `core/db.py`
- `business_units` is a shared table — used by projects, welding, pipeline

## Web Architecture

### Layer separation (mandatory)

Business logic stays in module files. **NO Flask imports** in files like `projects/budget.py`, `workforce/employees.py`, etc. The API blueprint wraps module functions in Flask responses.

```
Module layer:   projects/budget.py      → pure Python, returns dicts/tuples
API layer:      api/projects.py         → imports budget.py, returns jsonify()
Template layer: templates/projects/     → Jinja2, consumes context from API
```

### Adding a new web module

1. Add 3 lines to `config.yaml` under `web_modules:`
2. Create API blueprint in `api/{module}.py`
3. Create templates in `frontend/templates/{module}/`
4. Register blueprint in `api/__init__.py`

No database migrations needed for the module registry itself.

### Template conventions

- All templates extend `base.html`
- Sidebar nav is auto-generated from `web_modules` context variable
- Brand color `<style>` block loads BETWEEN `style.css` and `dark.css` (cascade order matters)

## Import Infrastructure

Shared engine in `imports/` package for CSV/Excel file imports:

| Component | Purpose |
|-----------|---------|
| `imports/specs.py` | Dataclasses: `ImportSpec`, `ColumnDef`, `ActionItem`, `ActionPlan` |
| `imports/engine.py` | Parse, map, plan, execute, session CRUD |
| `imports/schema.sql` | `import_sessions` + `import_actions` tables |

**Spec pattern:** Each module provides an `ImportSpec` with `match_fn`, `categorize_fn`, `detect_missing_fn`, `execute_fn`.

**Action types:** `insert`, `update`, `skip`, `flag`, `separate`, `reactivate`

**Example:** `workforce/import_specs.py` — 15 columns, 4-level match (emp# → phone → name → email)

## Model Routing

| Model | Tasks |
|-------|-------|
| Haiku | File routing, pattern matching, title block reading |
| Sonnet | Full extraction, conflict detection, report generation |
| Opus | Shadow review (10%), critical decisions, ambiguous routing |

## Testing

```bash
# Run all tests (exclude vectordb — torchvision crash on this machine)
pytest tests/ --ignore=tests/test_vectordb.py

# Run specific module tests
pytest tests/test_welding.py
pytest tests/test_projects.py
```

480+ tests currently passing.

## Config System

All settings in `config.yaml` at package root. Paths are **relative**, resolved by `QMS_PATHS._resolve()` against `_PACKAGE_DIR`.

Key config sections:
- `paths:` — database, inbox, projects, quality-documents, vectordb
- `web_modules:` — module registry (drives nav, access control)
- `branding:` — colors, fonts, app_name (drives theming)
- `auth:` — dev_bypass, session settings
- `pipeline:` — classifier patterns, routing rules

## Blog / The Observatory

- Three states: Draft → Scheduled → Published
- Auto-publish: lazy on read — `_auto_publish_scheduled()` runs inside `list_posts()`
- Schema: `blog_posts` table with `publish_at TEXT DEFAULT NULL`
- Editor: Settings UI → Observatory tab
- Routes: `/blog/` (public list), `/blog/<slug>` (public detail), `/blog/api/posts` (CRUD)

## Welding Form Pipeline

- **Registry:** `get_form_definition("wps")` — 6 form types
- **Extraction:** Dual Sonnet + Opus shadow review
- **Qualification Engine:** Plugin ABC with ASME IX + AWS D1.1 codes
- **Web UI:** `/welding/` — dashboard, form lists, welder profiles

## Server Configuration

| Mode | Command | Host | Notes |
|------|---------|------|-------|
| Production | `qms serve` | `0.0.0.0:5000` | Waitress, 8 threads, LAN-accessible |
| Development | `qms serve --debug` | `127.0.0.1:5000` | Flask dev server, auto-reload |

LAN URL: `http://L004470-CAD:5000`
