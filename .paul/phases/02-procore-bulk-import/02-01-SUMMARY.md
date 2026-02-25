---
phase: 02-procore-bulk-import
plan: 01
subsystem: api
tags: [csv-import, normalization, dedup, cli, quality-issues]

# Dependency graph
requires:
  - phase: 01-quality-issues-foundation
    provides: quality_issues schema, normalization functions, root_causes seed data
provides:
  - CSV import engine for quality issues (import_quality_csv)
  - Header auto-mapping (40+ aliases → 13 canonical fields)
  - Dedup via source+source_id unique index
  - CLI commands: qms quality import-csv, qms quality summary
  - 26 new tests
affects: [phase-02-02-procore-extraction, phase-02-03-attachments, phase-03-dashboard]

# Tech tracking
tech-stack:
  added: []
  patterns: [CSV import engine pattern, header auto-mapping]

key-files:
  created: [quality/import_engine.py, quality/cli.py, tests/test_quality_import.py]
  modified: [cli/main.py]

key-decisions:
  - "Data-source-agnostic engine — CSV in, quality_issues out, regardless of extraction method"
  - "assigned_to stored as text — employee FK resolution deferred to Phase 3"
  - "Reuse normalize_trade/status/type from quality/db.py — no logic duplication"

patterns-established:
  - "Header auto-mapping with alias lists for flexible CSV ingestion"
  - "Procore import pattern: parse → validate → normalize → dedup → upsert"

# Metrics
duration: ~10min
started: 2026-02-25T00:00:00Z
completed: 2026-02-25T00:00:00Z
---

# Phase 2 Plan 01: Quality Issue Import Engine Summary

**CSV import engine with header auto-mapping, normalization via config, source_id dedup, dry-run mode, and CLI commands — data-source-agnostic backbone for Procore bulk import.**

## Performance

| Metric | Value |
|--------|-------|
| Duration | ~10 min |
| Tasks | 3 completed |
| Files created | 3 |
| Files modified | 1 |
| New tests | 26 |
| Total tests | 506 (480 existing + 26 new) |

## Acceptance Criteria Results

| Criterion | Status | Notes |
|-----------|--------|-------|
| AC-1: CSV Import Parses and Inserts | Pass | 3-row CSV → 3 quality_issues rows with all fields mapped |
| AC-2: Field Normalization Applied | Pass | HVAC→Mechanical, Ready for Review→in_review, Safety→observation |
| AC-3: Dedup via source_id | Pass | Second import updates (not duplicates), correct insert/update counts |
| AC-4: Dry-Run Mode | Pass | Returns counts, 0 rows written to DB |
| AC-5: CLI Command Functional | Pass | `qms quality import-csv` and `qms quality summary` both work |
| AC-6: All Existing Tests Pass | Pass | 506 tests, 0 failures |

## Accomplishments

- Built data-source-agnostic CSV import engine with 13 canonical fields and 40+ header aliases
- Integrated with Phase 1 normalization functions (no logic duplication)
- Implemented idempotent dedup via source+source_id unique index
- Added CLI module with import-csv (dry-run support) and summary commands
- 26 comprehensive tests covering parsing, normalization, dedup, dry-run, error handling

## Task Commits

All tasks committed in a single commit:

| Task | Commit | Type | Description |
|------|--------|------|-------------|
| Task 1: Create quality import engine | `3bf6242` | feat | import_engine.py with CSV parser, normalizer, dedup |
| Task 2: CLI commands + module registration | `3bf6242` | feat | cli.py + main.py registration |
| Task 3: Write tests and verify | `3bf6242` | test | 26 tests, 506 total passing |

## Files Created/Modified

| File | Change | Purpose |
|------|--------|---------|
| `quality/import_engine.py` | Created | CSV parser, header mapper, normalizer, dedup inserter (~280 lines) |
| `quality/cli.py` | Created | Typer CLI: import-csv + summary commands (~100 lines) |
| `tests/test_quality_import.py` | Created | 26 tests across 7 test classes (~260 lines) |
| `cli/main.py` | Modified | Added quality module to CLI registry |

## Decisions Made

| Decision | Rationale | Impact |
|----------|-----------|--------|
| Data-source-agnostic engine | Decouples "how to get data" from "how to load data" | 02-02 can pipe any format through same engine |
| assigned_to as text | Employee FK resolution needs matching logic (name/email) | Phase 3 enrichment concern |
| Single commit for all tasks | Tightly coupled changes (engine + CLI + tests) | Clean git history |

## Deviations from Plan

### Summary

| Type | Count | Impact |
|------|-------|--------|
| Auto-fixed | 1 | Minimal — Python deprecation fix |
| Scope additions | 0 | None |
| Deferred | 0 | None |

**Total impact:** Minimal — one deprecation fix

### Auto-fixed Issues

**1. datetime.utcnow() deprecation**
- **Found during:** Task 3 (test run showed DeprecationWarning)
- **Issue:** `datetime.utcnow()` is deprecated in Python 3.12+
- **Fix:** Changed to `datetime.now(timezone.utc)`
- **Verification:** Warning gone, all tests pass
- **Commit:** `3bf6242`

### Deferred Items

None.

## Skill Audit

No required skills for this plan. `/frontend-design` was optional and correctly not invoked (no UI work).

## Issues Encountered

None.

## Next Phase Readiness

**Ready:**
- Import engine ready to consume CSV from any Procore extraction method
- CLI commands available for manual import testing
- Header auto-mapping handles varied CSV column names

**Concerns:**
- Procore API access status still unknown — affects 02-02 approach
- Photo/attachment download not yet implemented — 02-03

**Blockers:**
- None

---
*Phase: 02-procore-bulk-import, Plan: 01*
*Completed: 2026-02-25*
