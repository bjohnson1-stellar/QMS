---
module: web
cli_name: serve
status: Complete
commands: [serve]
depends_on: [core, projects]
depended_by: []
tables: []
api_blueprint: api/__init__.py
source_dir: api/
template_dir: frontend/templates/
static_dir: frontend/static/
tags: [qms-module, flask, web-ui]
created: 2026-02-10
updated: 2026-02-11
---

# Web (Flask UI)

The **web interface** for QMS — a Flask app serving project management pages with a REST API backend. Launched via `qms serve` at `http://localhost:5000`.

## Architecture

- **Flask app factory** in `api/__init__.py`
- Module blueprints registered in `api/` (currently: projects)
- **Clean separation:** API routes are thin wrappers calling business logic in `projects/budget.py`
- Jinja2 templates extend `frontend/templates/base.html` (shared sidebar layout)
- Static assets in `frontend/static/style.css`
- Optional dependency: `pip install -e ".[web]"` for Flask

```
Browser → Flask Routes (api/projects.py) → Business Logic (projects/budget.py) → SQLite (core/db.py)
```

## Pages

| Page | URL | Template | Description |
|------|-----|----------|-------------|
| Dashboard | `/projects/` | `projects/dashboard.html` | Stats, monthly allocation, active projects |
| Projects | `/projects/manage` | `projects/projects.html` | Full CRUD with BU allocations, Excel I/O. Filters: stage, search, projection-enabled toggle. Views: By Project (hierarchical) / By BU (flat). Weight sliders with scroll-wheel support. |
| Business Units | `/projects/business-units` | `projects/business_units.html` | 3-digit BU code management |
| Transactions | `/projects/transactions` | `projects/transactions.html` | Spending ledger (Time, Travel, Materials, Other) |
| Settings | `/projects/settings` | `projects/settings.html` | Hourly rate, working hours, fiscal year |
| Projections | `/projects/projections` | `projects/projections.html` | 4-card layout: period selector, per-period job toggles, editable results with manual hour overrides, snapshot history with commit/uncommit workflow |

## API Endpoints (30+)

See [[API Overview]] for the full REST API reference.

### Summary by Resource
| Resource | Endpoints | Methods |
|----------|-----------|---------|
| Projects | 4 | GET, POST, PUT, DELETE |
| Allocations | 3 | GET, POST, DELETE |
| Business Units | 4 | GET, POST, PUT, DELETE |
| Transactions | 5 | GET, POST, PUT, DELETE |
| Settings | 2 | GET, PUT |
| Projection Periods | 5 | GET, POST, PUT, PATCH |
| Projections | 8 | GET, POST, PUT |
| Budget Summary | 1 | GET |
| Excel I/O | 2 | GET, POST |

## Key Files

| File | Purpose |
|------|---------|
| `api/__init__.py` | Flask app factory, blueprint registration |
| `api/projects.py` | Projects blueprint (all routes) |
| `frontend/templates/base.html` | Shared layout with sidebar |
| `frontend/templates/projects/*.html` | 6 page templates |
| `frontend/static/style.css` | Shared CSS |
| `cli/main.py` | `qms serve` command definition |

## Dependencies

### Depends On
- [[core]] — Database
- [[projects]] — All business logic via `projects/budget.py` and `projects/excel_io.py`
- Flask, Jinja2 (optional `[web]` dependency)

### Depended By
None — end-user delivery layer.

## Related Notes
- [[projects]] — Business logic layer
- [[API Overview]] — Full endpoint reference
- [[Architecture Overview]] — Web architecture diagram
