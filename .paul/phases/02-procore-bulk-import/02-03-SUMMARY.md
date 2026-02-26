---
phase: 02-procore-bulk-import
plan: 03
subsystem: api
tags: [attachments, vector-indexing, chromadb, quality-issues, semantic-search]

# Dependency graph
requires:
  - phase: 02-procore-bulk-import
    provides: import_quality_csv(), import_batch(), quality_issue_attachments table
provides:
  - Attachment URL capture during CSV import (_insert_attachments)
  - Quality issues vector indexing (index_quality_issues)
  - "quality_issues" ChromaDB collection for semantic search
  - CLI command: `qms quality index`
  - 7 new tests (44 total in test_quality_import.py)
affects: [phase-03-dashboard, phase-04-mobile-capture]

# Tech tracking
tech-stack:
  added: []
  patterns: [attachment claim-check (URL now, download later), vectordb indexer per content type]

key-files:
  created: []
  modified: [quality/import_engine.py, quality/cli.py, vectordb/indexer.py, vectordb/__init__.py, tests/test_quality_import.py]

key-decisions:
  - "URL-only attachment recording — no file download in this plan (deferred to Phase 4)"
  - "Semicolon-separated URL splitting for multi-attachment CSV fields"

patterns-established:
  - "Attachment claim-check: store source_url with empty filepath, download later"
  - "index_quality_issues() follows same structure as all other vectordb indexers"

# Metrics
duration: ~8min
started: 2026-02-26T00:00:00Z
completed: 2026-02-26T00:00:00Z
---

# Phase 2 Plan 03: Attachments + Vector Indexing Summary

**Attachment URL capture during CSV import and quality issues vector indexing via ChromaDB, completing the Phase 2 bulk import pipeline.**

## Performance

| Metric | Value |
|--------|-------|
| Duration | ~8 min |
| Tasks | 3 completed |
| Files modified | 5 |
| New tests | 7 (44 total in quality import suite) |
| Total tests | 534 passing |

## Acceptance Criteria Results

| Criterion | Status | Notes |
|-----------|--------|-------|
| AC-1: Attachment URLs Captured During Import | Pass | Semicolon-split URLs → quality_issue_attachments rows with source_url, filename, file_type |
| AC-2: Quality Issues Vector Indexed | Pass | index_quality_issues() creates "quality_issues" collection with title+description+location |
| AC-3: CLI Index Command | Pass | `qms quality index [--rebuild]` registered and functional |
| AC-4: All Tests Pass | Pass | 44 quality tests + 534 total, 0 failures |

## Accomplishments

- Added attachment URL extraction to import engine — CSV "Attachments"/"Photos" columns split on semicolons, each URL stored in quality_issue_attachments with derived filename
- Built index_quality_issues() vectordb indexer following established pattern — queries quality_issues table, indexes title+description+location with project/type/status/severity metadata
- Added `qms quality index` CLI command with --rebuild flag and graceful chromadb ImportError handling

## Task Commits

Work applied in this session, committed with UNIFY.

| Task | Status | Description |
|------|--------|-------------|
| Task 1: Attachment URL extraction | PASS | _COLUMN_ALIASES + _insert_attachments + _filename_from_url in import_engine.py |
| Task 2: Vector indexer + CLI | PASS | index_quality_issues in indexer.py, export in __init__.py, `index` command in cli.py |
| Task 3: Tests + regression | PASS | 5 attachment tests + 2 indexer tests, 534 total passing |

## Files Created/Modified

| File | Change | Purpose |
|------|--------|---------|
| `quality/import_engine.py` | Modified | Added "attachments" column aliases, _filename_from_url(), _insert_attachments(), attachments_recorded counter |
| `quality/cli.py` | Modified | Added `index` command (~20 lines) |
| `vectordb/indexer.py` | Modified | Added "quality_issues" collection, index_quality_issues() (~65 lines), wired into index_all() |
| `vectordb/__init__.py` | Modified | Added index_quality_issues to imports and __all__ |
| `tests/test_quality_import.py` | Modified | Added TestAttachmentImport (5 tests), TestIndexQualityIssues (2 tests) |

## Decisions Made

| Decision | Rationale | Impact |
|----------|-----------|--------|
| URL-only attachment recording | Download is expensive and can fail — claim-check pattern captures URLs now, downloads later | Phase 4 can scan for filepath='' to find pending downloads |
| Semicolon as URL delimiter | Procore exports use semicolons for multi-value fields; consistent with CSV conventions | Simple split, no regex needed |

## Deviations from Plan

### Summary

| Type | Count | Impact |
|------|-------|--------|
| Auto-fixed | 0 | None |
| Scope additions | 0 | None |
| Deferred | 0 | None |

**Total impact:** None — plan executed as written.

### Deferred Items

None.

## Skill Audit

No required skills for this plan. `/frontend-design` was optional and correctly not invoked (no UI work).

## Issues Encountered

| Issue | Resolution |
|-------|------------|
| torchvision crash on vectordb import test | Known machine issue — does not affect test results (534 pass) |

## Next Phase Readiness

**Ready:**
- Full import pipeline operational: single CSV, batch, auto-resolve, attachment URLs, dry-run
- Quality issues indexable into ChromaDB for semantic search
- Pipeline classifier configured for observation CSV detection
- CLI covers all import + indexing workflows
- Phase 2 complete — all 3 plans executed and unified

**Concerns:**
- Procore API access still unknown — manual CSV export works but doesn't scale
- Attachment files not yet downloaded (URLs only) — Phase 4 dependency

**Blockers:**
- None

---
*Phase: 02-procore-bulk-import, Plan: 03*
*Completed: 2026-02-26*
