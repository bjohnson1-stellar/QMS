---
phase: 01-quality-issues-foundation
plan: 01
subsystem: database
tags: [sqlite, schema, quality-issues, normalization, audit-trail]

# Dependency graph
requires:
  - phase: none
    provides: first phase — no dependencies
provides:
  - Unified quality issues schema (8 tables)
  - Root cause taxonomy (8 categories)
  - Normalization config for trades, statuses, types
  - Audit trail infrastructure
  - Issue linking and tagging system
affects: [phase-02-procore-import, phase-03-dashboard, phase-04-mobile-capture]

# Tech tracking
tech-stack:
  added: []
  patterns: [quality module registration, normalization config pattern]

key-files:
  created: [quality/__init__.py, quality/schema.sql, quality/db.py]
  modified: [core/db.py, config.yaml, tests/test_conftest_schemas.py, tests/test_core_db.py]

key-decisions:
  - "migrate_all() not init_db() — QMS uses migrate_all() to apply schemas"
  - "SCHEMA_ORDER index 5 — after projects (FK deps), before timetracker"
  - "8 root causes seeded via INSERT OR IGNORE — idempotent on re-init"

patterns-established:
  - "Quality module follows existing QMS module pattern: __init__.py + schema.sql + db.py"
  - "Normalization config in config.yaml quality.normalize section"

# Metrics
duration: ~15min
started: 2026-02-25T00:00:00Z
completed: 2026-02-25T00:00:00Z
---

# Phase 1 Plan 01: Quality Issues Foundation Summary

**Unified quality issues schema with 8 tables, root cause taxonomy, normalization config, and audit trail — foundation for cross-project quality intelligence.**

## Performance

| Metric | Value |
|--------|-------|
| Duration | ~15 min |
| Tasks | 3 completed |
| Files created | 3 |
| Files modified | 4 |

## Acceptance Criteria Results

| Criterion | Status | Notes |
|-----------|--------|-------|
| AC-1: Quality Issues Schema Created | Pass | 8 tables: quality_issues, quality_issue_attachments, quality_issue_history, quality_issue_links, quality_issue_tags, tags, corrective_actions, root_causes |
| AC-2: Foreign Keys Link to Existing Entities | Pass | FKs resolve to projects, business_units, employees |
| AC-3: Module Registered in SCHEMA_ORDER | Pass | Index 5, after projects, before timetracker |
| AC-4: Normalization Config Present | Pass | Trades, statuses, and types mappings in config.yaml |
| AC-5: Root Causes Seeded | Pass | 8 root causes: Workmanship, Materials, Design/Engineering, Environmental, Procedural, Subcontractor, Equipment/Tools, Other |
| AC-6: All Existing Tests Pass | Pass | 480 tests, 0 failures |

## Accomplishments

- Created unified quality issues schema supporting observations, NCRs, CARs, deficiencies, punch items, and other issue types
- Built audit trail infrastructure (quality_issue_history) for full change tracking from day one
- Established issue linking system (related, duplicate, caused_by, parent_child) for graph-level analysis
- Seeded root cause taxonomy with 8 categories across execution, supply, design, process, and external domains

## Task Commits

All tasks committed atomically in a single commit:

| Task | Commit | Type | Description |
|------|--------|------|-------------|
| Task 1: Create quality module with schema | `16933a0` | feat | 3 new files: __init__.py, schema.sql, db.py with 8 tables |
| Task 2: Register module and update config | `16933a0` | feat | SCHEMA_ORDER + normalization config |
| Task 3: Verify integration and run tests | `16933a0` | test | 480 tests passing, all AC verified |

## Files Created/Modified

| File | Change | Purpose |
|------|--------|---------|
| `quality/__init__.py` | Created | Empty module init |
| `quality/schema.sql` | Created | 8 tables with indexes, seed data |
| `quality/db.py` | Created | Helper functions: get_root_causes, get_tags, normalize_trade, normalize_status, log_issue_change |
| `core/db.py` | Modified | Added "quality" to SCHEMA_ORDER at index 5 |
| `config.yaml` | Modified | Added quality section with normalization mappings |
| `tests/test_conftest_schemas.py` | Modified | Updated hardcoded SCHEMA_ORDER count (13 to 14) |
| `tests/test_core_db.py` | Modified | Updated hardcoded SCHEMA_ORDER count (13 to 14) |

## Decisions Made

| Decision | Rationale | Impact |
|----------|-----------|--------|
| Single commit for all 3 tasks | Schema + registration + config are tightly coupled | Clean git history |
| SCHEMA_ORDER index 5 | FK deps on projects (index 4), no downstream deps yet | Future modules can depend on quality |
| INSERT OR IGNORE for seeds | Idempotent — safe to re-run migrate_all() | No duplicate root causes |

## Deviations from Plan

### Summary

| Type | Count | Impact |
|------|-------|--------|
| Auto-fixed | 1 | Essential — prevented test failures |
| Scope additions | 0 | None |
| Deferred | 0 | None |

**Total impact:** Minimal — one essential test fix

### Auto-fixed Issues

**1. Test hardcoded SCHEMA_ORDER count**
- **Found during:** Task 3 (verification)
- **Issue:** Two test files hardcoded SCHEMA_ORDER length as 13
- **Fix:** Updated to 14 in both `tests/test_conftest_schemas.py` and `tests/test_core_db.py`
- **Verification:** All 480 tests pass
- **Commit:** `16933a0` (part of main commit)

### Deferred Items

None.

## Skill Audit

No required skills for this plan. `/frontend-design` was optional and correctly not invoked (no UI work).

## Issues Encountered

None.

## Next Phase Readiness

**Ready:**
- Quality issues schema fully operational in quality.db
- Normalization config ready for import pipeline
- Root cause taxonomy seeded for classification
- Audit trail infrastructure in place

**Concerns:**
- Procore API access status unknown — affects Phase 2 import approach

**Blockers:**
- None

---
*Phase: 01-quality-issues-foundation, Plan: 01*
*Completed: 2026-02-25*
