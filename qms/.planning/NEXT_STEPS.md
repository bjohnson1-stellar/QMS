# QMS Next Steps — Execution Plan

**Context**: 142 tests passing across 16 files. conftest.py loads all 8 schemas.
Test infrastructure is solid. This plan covers the 5 next priorities.

---

## Task 1: Fix Phone Lookup Bug

**Priority**: High — real data-matching bug
**Effort**: ~15 minutes
**Files**: `qms/workforce/employees.py`, `qms/tests/test_workforce_employees.py`

### Problem
`find_employee_by_phone()` (line 55-62) uses SQL REPLACE to strip `- ( )` from stored phone numbers, but does NOT strip spaces. A phone stored as `(555) 123-4567` becomes `555 1234567` in SQL, while Python strips to `5551234567`. They don't match.

### Fix
In `qms/workforce/employees.py` line 59, add a REPLACE for spaces:
```python
# BEFORE:
"WHERE REPLACE(REPLACE(REPLACE(phone, '-', ''), '(', ''), ')', '') = ?",

# AFTER:
"WHERE REPLACE(REPLACE(REPLACE(REPLACE(phone, '-', ''), '(', ''), ')', ''), ' ', '') = ?",
```

### Test Update
In `qms/tests/test_workforce_employees.py`, update `test_by_phone` to use the format that was originally broken:
```python
def test_by_phone(self, memory_db):
    create_employee(memory_db, "Smith", "Jane", phone="(555) 123-4567")
    found = find_employee_by_phone(memory_db, "5551234567")
    assert found is not None
```

Also add a second test with the no-space format to cover both:
```python
def test_by_phone_no_spaces(self, memory_db):
    create_employee(memory_db, "Smith", "Jane", phone="555-123-4567")
    found = find_employee_by_phone(memory_db, "5551234567")
    assert found is not None
```

### Also Check
`qms/workforce/sis_import.py` line 43-59 `find_existing_employee()` calls `find_employee_by_phone()` — it inherits the fix automatically, no change needed there.

---

## Task 2: Build Reporting Module

**Priority**: Medium — listed as "not started" in planning docs
**Effort**: ~1–2 hours
**Files**: `qms/reporting/cli.py` (rewrite), `qms/reporting/queries.py` (new), `qms/tests/test_reporting.py` (new)

### Current State
`reporting/cli.py` has a single `system` command (24 lines) that counts active projects/employees/sheets/conflicts. No `__init__.py` exports. No query helpers.

### Planning Doc Requirements (from `.planning/RESTRUCTURE_PLANNING_PROMPT.md` lines 152-156)
- Conflict reports, extraction accuracy
- Quality dashboards
- Compliance matrices
- Expiration tracking across all modules

### Implementation Plan

**`qms/reporting/queries.py`** — query functions (each returns a dict or list):
```
system_dashboard(conn) -> dict
    Active projects, employees, sheets, open conflicts (already in cli.py, extract it)

engineering_summary(conn, project_id=None) -> dict
    Calculations by type, validations by status (PASS/FAIL/WARNING/REVIEW),
    most recent calculations
    Tables: eng_calculations, eng_validations

welding_dashboard(conn) -> dict
    Active welders, WPS/WPQ/PQR counts, expiring continuity, overdue notifications
    Tables: weld_welder_registry, weld_wps, weld_wpq, weld_pqr,
            weld_continuity_log, weld_notifications

workforce_report(conn) -> dict
    Active/inactive/terminated counts, expiring certifications,
    employees by department
    Tables: employees, employee_certifications, departments

pipeline_status(conn) -> dict
    Queue depth by status, recent imports, extraction accuracy
    Tables: processing_queue, sheets, conflicts

expiring_items(conn, days_ahead=90) -> list
    Union query across: employee_certifications (expiry_date),
    weld_continuity_log (last_weld_date + 180 days), weld_wpq (expiry)
    Returns list of {module, item_type, name, expires_on, days_remaining}
```

**`qms/reporting/cli.py`** — 5 commands:
```
qms report system          — system-wide dashboard (rewrite existing)
qms report engineering     — eng calc/validation summary, optional --project filter
qms report welding         — welding program status with expiry warnings
qms report workforce       — employee/cert status
qms report expiring        — cross-module expiration tracking, --days option
```

All commands should:
- Use `mock_db`-compatible `get_db(readonly=True)` pattern
- Support `--format json|human|markdown` via the existing `core/output.py` formatters
- Default to human-readable output

**`qms/tests/test_reporting.py`** — tests using `mock_db` with seed data:
```
test_system_dashboard_empty(mock_db)
test_system_dashboard_with_data(mock_db, seed_project)
test_engineering_summary_empty(mock_db)
test_welding_dashboard_empty(mock_db)
test_workforce_report_with_employees(mock_db)
test_expiring_items_empty(mock_db)
test_cli_system_command(cli_runner, mock_db)
test_cli_engineering_command(cli_runner, mock_db)
```

### Important
- `reporting/cli.py` currently imports `get_db` from `qms.core` — when adding tests, `mock_db` needs to also patch `qms.reporting.queries.get_db` (or import it inside functions).
- Add `qms.reporting.queries` to `__init__.py` exports.

---

## Task 3: Pipeline Process — Non-AI Fallback

**Priority**: Medium — the process command is a no-op stub
**Effort**: ~2 hours
**Files**: `qms/pipeline/cli.py` (modify process command), `qms/pipeline/processor.py` (add extraction functions), `qms/tests/test_pipeline_processor.py` (new)

### Current State
`pipeline/cli.py:316` marks processing_queue items as "completed" without doing anything. The TODO says "when AI extraction is integrated."

### What the Process Command Should Do
For each queued item in `processing_queue`:
1. Load the file from disk (path is in the queue record)
2. Extract metadata using regex/pattern matching (non-AI fallback)
3. Create/update records in the appropriate tables
4. Update queue status

### Non-AI Fallback Extraction Strategy

**`qms/pipeline/processor.py`** — add these functions:

```
extract_from_filename(filename: str) -> dict
    Parse: project number, discipline, drawing number, revision
    Patterns already exist in pipeline/common.py:
    - extract_project_number(filename) — line exists
    - extract_department_number(filename) — line exists
    - Revision pattern: r'Rev[_\s-]?([A-Z0-9]+)'
    - Drawing number: r'([A-Z]{1,2}-\d{2,4})'

classify_document(filename: str, config: dict) -> str
    Use document_types patterns from config.yaml to classify:
    drawings, specifications, procedures, forms, QM modules
    Config already has regex patterns for each type.

process_queue_item(conn, item: dict) -> dict
    1. Get filepath from item
    2. extract_from_filename()
    3. classify_document()
    4. If drawing: upsert into sheets table
    5. If spec: upsert into specifications table
    6. Update processing_queue status
    Returns: {status, extracted_fields, classification}
```

### Tables Updated by Processing
- `sheets` — drawing records (project_id, drawing_number, discipline, revision, file_path)
- `specifications` — spec documents
- `processing_queue` — status, completed_at, error

### Test Plan (`qms/tests/test_pipeline_processor.py`)
```
test_extract_from_filename_drawing()
    "07645-P-101_Rev_B.pdf" -> project="07645", discipline="piping", drawing="P-101", rev="B"

test_extract_from_filename_spec()
    "242300-Refrigeration_Rev_01.pdf" -> project=None, spec_section="242300"

test_classify_document_drawing()
test_classify_document_procedure()
test_process_queue_item(mock_db, seed_project)
```

### Important
- `pipeline/common.py` already has `extract_project_number()`, `extract_department_number()`, `normalize_job_numbers()` — reuse these.
- The AI extraction path should remain as a future enhancement. The non-AI path gives immediate value for filename-based metadata.

---

## Task 4: `qms init` Command

**Priority**: Medium — fresh clone experience
**Effort**: ~30 minutes
**Files**: `qms/cli/main.py` (add command), `qms/tests/test_cli_main.py` (add test)

### Problem
A fresh clone has no `data/` directory. `qms migrate` creates the DB file but doesn't create `inbox/`, `projects/`, `quality-documents/`, `vectordb/`, or their subdirectories.

### Implementation
Add an `init` command to `qms/cli/main.py`:

```python
@app.command()
def init():
    """Initialize QMS data directories and run database migrations."""
    from qms.core.config import QMS_PATHS
    from qms.core.paths import ensure_directory
    from qms.core.db import migrate_all

    # Create all data directories
    dirs = [
        QMS_PATHS.inbox,
        QMS_PATHS.needs_review,
        QMS_PATHS.conflicts,
        QMS_PATHS.duplicates,
        QMS_PATHS.projects,
        QMS_PATHS.quality_documents,
        QMS_PATHS.vector_database,
    ]
    for d in dirs:
        ensure_directory(d)
        typer.echo(f"  Created: {d.relative_to(QMS_PATHS.config_dir)}")

    # Run migrations
    migrate_all()
    typer.echo("QMS initialized successfully.")
```

### Test
```python
def test_init_command(cli_runner, mock_db, tmp_path):
    # Would need to mock QMS_PATHS to point at tmp_path
    # Then verify directories were created
```

### Important
- This must be idempotent — safe to run on an existing installation.
- `ensure_directory` already uses `mkdir(parents=True, exist_ok=True)`, so it's safe.
- The `migrate` command should remain as-is (just runs schemas). `init` does dirs + migrate.

---

## Task 5: Expand Test Coverage (Testable Without External Deps)

**Priority**: Low — incremental improvement
**Effort**: ~1–2 hours
**Files**: New test files for welding, projects, pipeline common

### What's Testable Now

**`qms/tests/test_pipeline_common.py`** — pure parsing functions in `pipeline/common.py`:
```
test_extract_project_number("07645-P-101.pdf") == "07645"
test_extract_project_number("no-project.pdf") == None
test_extract_department_number("D04-whatever") == "04"
test_extract_date_from_filename("SIS_2026-02-09.xlsx") == date(2026, 2, 9)
test_normalize_job_numbers(["07645-D04", "07645D04"]) — consistent output
test_parse_address("123 Main St, City, ST 12345") — structured result
test_strip_city_state("Anytown, OH") — returns ("Anytown", "OH")
test_extract_suffix("EMP-0001-A") — returns "A"
```

**`qms/tests/test_projects_scanner.py`** — helpers in `projects/scanner.py`:
```
test_get_file_hash(tmp_path) — create a file, hash it, verify deterministic
test_get_page_count_no_fitz() — should return None gracefully (no PyMuPDF)
```

**`qms/tests/test_welding_intake.py`** — dashboard query in `welding/intake.py`:
```
test_get_dashboard_data(mock_db) — returns dict with expected keys, all zeros on empty DB
```

**`qms/tests/test_workforce_sis_import.py`** — functions in `workforce/sis_import.py`:
```
test_parse_name_from_record() — with mock record object
test_find_existing_employee_by_number(memory_db)
test_find_existing_employee_by_phone(memory_db)
test_find_existing_employee_by_name(memory_db)
test_find_existing_employee_not_found(memory_db)
```

### What Still Needs External Deps (defer)
- Welding importer: needs openpyxl Excel test fixtures
- Pipeline importer: needs openpyxl Excel test fixtures
- Quality docs loader: needs XML test fixtures
- References extractor: needs PDF test fixtures (PyMuPDF)
- VectorDB: needs chromadb

---

## Execution Order

1. **Task 1** (phone bug) — quick win, merge immediately
2. **Task 4** (qms init) — quick win, unblocks fresh clone workflow
3. **Task 2** (reporting) — fills the biggest module gap
4. **Task 3** (pipeline process) — gives the process command real functionality
5. **Task 5** (expand tests) — incremental, do alongside other work

Each task is independent and can be done in a separate PR/session.
