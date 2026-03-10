---
phase: 14-schema-api-foundation
plan: 01
subsystem: database
tags: [sqlite, qualitydocs, schema, m3-programs, m4-sops, crud]

requires:
  - phase: 13-cross-module-credentials
    provides: completed v0.2, clean baseline for v0.3
provides:
  - M3 programs schema (qm_programs)
  - M4 categories + SOPs schema (qm_categories, qm_sops, 5 supporting tables)
  - qualitydocs/db.py CRUD module with full lifecycle functions
  - 15 seeded M4 categories from Category Roadmap
affects: [14-02 API endpoints, 15 tabbed UI, 16 M3 UI, 17 M4 UI, 18 SOP intake]

tech-stack:
  added: []
  patterns: [with-get_db context manager, JSON scope_tags, sop-history audit trail, seed_categories idempotent seeder]

key-files:
  created: [qualitydocs/db.py]
  modified: [qualitydocs/schema.sql, qualitydocs/__init__.py]

key-decisions:
  - "scope_tags stored as JSON array TEXT with LIKE filter (not json_each)"
  - "Internal _add_sop_history_internal for separate transaction from create/approve/publish"
  - "seed_categories links parent_program_id only if programs already seeded"

patterns-established:
  - "SOP lifecycle: draft → under_review → approved → published → superseded → obsolete"
  - "History auto-recording on create_sop, approve_sop, publish_sop"
  - "Pagination dict: {items, total, page, per_page, pages}"

duration: ~15min
started: 2026-03-10T14:40:00Z
completed: 2026-03-10T14:55:00Z
---

# Phase 14 Plan 01: Schema & DB Functions Summary

**Extended qualitydocs with 7 new tables for M3 programs and M4 SOPs, plus a full CRUD module with lifecycle management, history tracking, and intake pipeline.**

## Performance

| Metric | Value |
|--------|-------|
| Duration | ~15min |
| Started | 2026-03-10T14:40Z |
| Completed | 2026-03-10T14:55Z |
| Tasks | 3 completed |
| Files modified | 3 |

## Acceptance Criteria Results

| Criterion | Status | Notes |
|-----------|--------|-------|
| AC-1: M3 Programs Schema | Pass | qm_programs with program_id, status lifecycle, primary_codes JSON |
| AC-2: M4 Categories and SOPs Schema | Pass | qm_categories + qm_sops with all specified columns |
| AC-3: Scope Tags and Program-SOP Linkage | Pass | scope_tags as JSON array, qm_program_sops junction table |
| AC-4: DB Functions Module | Pass | All functions importable and tested end-to-end |
| AC-5: Existing Schema Unbroken | Pass | M1/M2 modules intact, get_manual_summary works |

## Accomplishments

- 7 new tables added to qualitydocs/schema.sql (programs, categories, SOPs, linkage, code refs, intake, history)
- qualitydocs/db.py with 22 functions covering programs, categories, SOPs, history, and intake
- 15 M4 categories seeded from Category Roadmap with parent program linkage
- Full SOP lifecycle verified: draft → approved → published with automatic history recording

## Files Created/Modified

| File | Change | Purpose |
|------|--------|---------|
| `qualitydocs/schema.sql` | Modified | 7 new M3/M4 tables appended after existing DDL |
| `qualitydocs/db.py` | Created | CRUD module: programs, categories, SOPs, history, intake |
| `qualitydocs/__init__.py` | Modified | Exports for all new public functions from db.py |

## Decisions Made

| Decision | Rationale | Impact |
|----------|-----------|--------|
| LIKE filter for scope_tags instead of json_each | Simpler, works on all SQLite versions | Slightly less precise but adequate for known scope values |
| Separate transactions for history writes | Avoids nested context manager issues with get_db() generator | History always records even if caller transaction pattern varies |
| FTS extension deferred to Phase 18 | Phase 18 handles AI classification and search | Comment added in schema.sql noting the plan |

## Deviations from Plan

### Summary

| Type | Count | Impact |
|------|-------|--------|
| Auto-fixed | 1 | Essential fix, no scope change |

**Total impact:** Minimal — one pattern fix required.

### Auto-fixed Issues

**1. get_db() context manager pattern**
- **Found during:** Task 2 (DB functions)
- **Issue:** Initial implementation called `get_db()` without `with` statement — get_db is a generator context manager
- **Fix:** Rewrote all functions to use `with get_db() as conn:` pattern matching existing loader.py
- **Verification:** All functions passed end-to-end testing after fix

## Issues Encountered

| Issue | Resolution |
|-------|------------|
| Task 2 verification ran before Task 3 migration | Reordered: ran migration first, then verified Tasks 2+3 together |

## Next Phase Readiness

**Ready:**
- Schema foundation complete for all M3/M4 features
- DB functions ready for API layer (Plan 14-02)
- 15 categories seeded, ready for UI display
- History tracking in place for approval workflows

**Concerns:**
- None

**Blockers:**
- None

---
*Phase: 14-schema-api-foundation, Plan: 01*
*Completed: 2026-03-10*
