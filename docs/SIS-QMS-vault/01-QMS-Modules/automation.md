---
module: automation
cli_name: automation
status: Complete
commands: [process, status]
depends_on: [core]
depended_by: [welding]
tables: [automation_processing_log]
api_blueprint: "-"
source_dir: automation/
schema_file: automation/schema.sql
tags: [qms-module, automation]
created: 2026-02-11
updated: 2026-02-11
---

# Automation

A **generic JSON-based request processing dispatcher** that scans an incoming directory for JSON files, routes each file by its `"type"` field to a registered handler, logs results, and moves processed files to `processed/` or `failed/`.

Designed as the intake gateway for Power Automate and other external systems that produce structured JSON requests.

## Architecture

- **Handler registry pattern:** Modules register handler functions at import time via `register_handler(type_name, handler_fn, module_name)`. The dispatcher looks up the handler by the `"type"` field in each JSON file.
- **File lifecycle:** `incoming/` -> parse -> route -> handler -> `processed/` (success) or `failed/` (error). Files are moved with a timestamp prefix to avoid collisions.
- **Audit log:** Every processing attempt is recorded in `automation_processing_log` with status, source JSON, result summary, and error details.
- **Dry-run support:** Both `process_file()` and `process_all()` accept `dry_run=True` to preview without executing handlers or moving files.
- Directory paths are configurable in `config.yaml` under `automation:`.

### Directory Structure

```
data/automation/
  incoming/    # Drop JSON request files here
  processed/   # Successfully handled files (timestamped)
  failed/      # Invalid or handler-error files (timestamped)
```

### Handler Registration Flow

```
Module imports at CLI time
  -> calls register_handler("weld_cert_request", handler_fn, "welding")
  -> dispatcher stores in _HANDLERS dict
  -> process_all() iterates incoming/*.json
  -> reads "type" field from each JSON
  -> looks up _HANDLERS[type]
  -> calls handler_fn(json_path) -> result dict
  -> logs to automation_processing_log
  -> moves file to processed/ or failed/
```

Currently registered handlers:

| Type | Handler Module | Handler Function |
|------|---------------|------------------|
| `weld_cert_request` | [[welding]] | `cert_requests._handle_cert_request()` |

## CLI Commands

| Command | Description |
|---------|-------------|
| `qms automation process [file]` | Process all JSON files in incoming dir, or a single file. Supports `--dry-run`. |
| `qms automation status` | Show automation processing log. Supports `--limit`, `--type`, `--status` filters. |

## Database Tables

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `automation_processing_log` | Audit trail for every processing attempt | file_name, request_type, status, handler_module, result_summary, error_message, source_json, processed_at |

### `automation_processing_log` Schema

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Auto-increment |
| file_name | TEXT NOT NULL | Original JSON filename |
| request_type | TEXT NOT NULL | Value of the `"type"` field (or "unknown") |
| status | TEXT NOT NULL | `pending`, `processing`, `success`, `failed` |
| handler_module | TEXT | Module that handled the request (e.g., "welding") |
| result_summary | TEXT | Handler return summary on success |
| error_message | TEXT | Error details on failure |
| source_json | TEXT | Full JSON content of the request file |
| processed_at | TEXT | ISO timestamp when processing completed |
| created_at | TEXT | Row creation timestamp (auto) |

## Key Functions

| Function | Location | Description |
|----------|----------|-------------|
| `register_handler(type, fn, module)` | `automation/dispatcher.py` | Register a handler for a request type |
| `process_file(path, dry_run)` | `automation/dispatcher.py` | Process a single JSON request file |
| `process_all(dry_run)` | `automation/dispatcher.py` | Scan incoming dir and process all JSON files |
| `get_processing_log(limit, status, type)` | `automation/dispatcher.py` | Query the processing log with optional filters |

## Dependencies

### Depends On
- [[core]] -- Database (`get_db`), logging, config (`QMS_PATHS`, `get_config_value`)

### Depended By
- [[welding]] -- Registers `weld_cert_request` handler; `process-requests` CLI command delegates to automation dispatcher

## Related Notes
- [[welding]] -- First consumer (weld cert request intake)
- [[Database Overview]] -- Full schema map
