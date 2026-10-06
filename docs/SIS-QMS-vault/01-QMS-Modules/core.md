---
module: core
cli_name: "-"
status: Complete
commands: [version, migrate]
depends_on: []
depended_by: [engineering, welding, qualitydocs, references, projects, pipeline, workforce, vectordb, reporting, web]
tables: [audit_log, attachments, notes]
api_blueprint: "-"
source_dir: core/
schema_file: core/schema.sql
tags: [qms-module, foundation]
created: 2026-02-10
updated: 2026-02-10
---

# Core

The **foundational module** — every other QMS module depends on it. Provides database connectivity, configuration management, logging, and shared utility tables.

## Architecture

Core follows a **singleton pattern** for configuration and path resolution:
- `config.yaml` uses **relative paths**, resolved at runtime by `QMS_PATHS._resolve()`
- `get_db()` is a context manager yielding SQLite connections with WAL mode
- `SCHEMA_ORDER` in `db.py` controls the FK dependency chain for migrations

```
SCHEMA_ORDER: core → workforce → projects → qualitydocs → references → welding → pipeline → engineering
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `qms version` | Show QMS version and module status |
| `qms migrate` | Run database schema migrations for all modules in SCHEMA_ORDER |

## Database Tables

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `audit_log` | Activity audit logging | entity_type, entity_id, action, changed_by, old_values, new_values |
| `attachments` | File attachments (polymorphic) | entity_type, entity_id, file_path, mime_type |
| `notes` | Generic notes/comments (polymorphic) | entity_type, entity_id, content, created_by |

> **Pattern:** `audit_log`, `attachments`, and `notes` use **polymorphic associations** — `entity_type` + `entity_id` can reference any row in any table.

## Key Functions

| Function | Location | Description |
|----------|----------|-------------|
| `get_db(readonly=False)` | `core/db.py` | Context manager for SQLite connections |
| `execute_query(query, params, readonly)` | `core/db.py` | Execute query, return results as dicts |
| `migrate_all()` | `core/db.py` | Run all module schemas in dependency order |
| `get_config()` | `core/config.py` | Get configuration singleton |
| `get_config_value(key, default)` | `core/config.py` | Get specific config value |
| `get_logger(name)` | `core/logging.py` | Get module logger instance |
| `QMS_PATHS` | `core/config.py` | Path resolver singleton |

## Dependencies

### Depends On
None — this is the foundation.

### Depended By
**Every module**: [[engineering]], [[welding]], [[qualitydocs]], [[references]], [[projects]], [[pipeline]], [[workforce]], [[vectordb]], [[reporting]], [[web]]

## Related Notes
- [[Architecture Overview]] — System-wide architecture
- [[Database Overview]] — Full schema map
- [[ADR-001 Single Database Design]] — Why one SQLite file
