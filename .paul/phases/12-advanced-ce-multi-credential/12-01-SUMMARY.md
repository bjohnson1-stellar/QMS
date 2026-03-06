---
phase: 12-advanced-ce-multi-credential
plan: 01
subsystem: database, api
tags: [sqlite, ce-providers, ce-courses, json-each, cross-state, catalog]

requires:
  - phase: 11-regulatory-intelligence
    provides: state_requirements table, compliance scoring (context for CE catalog)
provides:
  - ce_providers table with full CRUD (soft-delete)
  - ce_courses table with cross-state applicability via JSON states_accepted
  - ce_credit_courses junction table for credit-to-course linking
  - 13 new API endpoints for providers, courses, and credit-course linking
  - Auto-populate course_name/provider on credit creation from catalog
affects: [12-02-ui, 13-integrations]

tech-stack:
  added: []
  patterns: [json_each() for cross-state course filtering, soft-delete for catalog entities, credit-course junction linking]

key-files:
  modified:
    - licenses/schema.sql
    - licenses/migrations.py
    - licenses/db.py
    - api/licenses.py

key-decisions:
  - "Soft-delete for providers and courses (is_active flag) — preserves referential integrity"
  - "JSON arrays for states_accepted and license_types — flexible, filterable via json_each()"
  - "Backward compatible — existing free-text provider/course_name on ce_credits unchanged"
  - "Auto-populate from catalog optional — course_id param on credit creation fills course_name/provider"

patterns-established:
  - "CE catalog soft-delete pattern: is_active=0, not hard delete"
  - "JSON array filtering via json_each() EXISTS subquery"
  - "Credit-course junction table for many-to-many linking"

duration: ~8min
completed: 2026-03-06T21:30:00Z
---

# Phase 12 Plan 01: CE Provider & Course Catalog Backend

**CE provider and course catalog with cross-state credit mapping, 3 new tables, 15 DB functions, and 13 API endpoints.**

## Performance

| Metric | Value |
|--------|-------|
| Duration | ~8min |
| Tasks | 3 completed |
| Files modified | 4 |

## Acceptance Criteria Results

| Criterion | Status | Notes |
|-----------|--------|-------|
| AC-1: CE Providers CRUD | Pass | Full CRUD with soft-delete, audit logging, search/filter |
| AC-2: CE Courses CRUD with Cross-State Mapping | Pass | json_each() filtering on states_accepted works for state_code and license_type |
| AC-3: Credit-Course Linking | Pass | Junction table, auto-populate on credit creation, list_ce_credits includes catalog info via LEFT JOIN |

## Accomplishments

- Created 3 new tables: ce_providers, ce_courses, ce_credit_courses with migration
- Built 15 DB functions: provider CRUD (5), course CRUD (5), credit-course linking (3), plus updated list_ce_credits with catalog JOIN
- Added 13 API endpoints: providers (5 routes), courses (5 routes), credit-course linking (3 routes)
- Cross-state course filtering operational via json_each() on states_accepted JSON array
- Modified credit creation endpoint to auto-populate course_name/provider from catalog when course_id provided

## Files Created/Modified

| File | Change | Purpose |
|------|--------|---------|
| `licenses/schema.sql` | Modified | Added ce_providers, ce_courses, ce_credit_courses table definitions + indexes |
| `licenses/migrations.py` | Modified | Added _create_ce_catalog_tables() migration function |
| `licenses/db.py` | Modified | Added 15 functions: provider CRUD, course CRUD, credit-course linking; updated list_ce_credits with catalog JOIN |
| `api/licenses.py` | Modified | Added 13 API routes for providers, courses, linking; updated credit creation for auto-populate |

## Decisions Made

| Decision | Rationale | Impact |
|----------|-----------|--------|
| Soft-delete for providers/courses | Preserves FK integrity with ce_credit_courses; courses referenced by credits shouldn't vanish | Active filtering default on list endpoints |
| JSON arrays for multi-state/type | Flexible, no junction tables needed; SQLite json_each() performs well | Clean API: pass arrays, filter by single value |
| Keep free-text fields on ce_credits | Backward compatible; existing credits don't need migration | course_id linking is additive, not required |
| Auto-populate optional on credit creation | Reduces friction; can still manually enter course_name/provider | course_id param triggers catalog lookup |

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

| Issue | Resolution |
|-------|------------|
| Auth redirect in test client | Used forced session for integration testing; dev_bypass requires page hit first |

## Next Phase Readiness

**Ready:**
- Full backend API available for Plan 02 UI development
- Provider and course catalog functional for CRUD operations
- Cross-state filtering ready for UI course browser
- Credit-course linking ready for enhanced credit entry form

**Concerns:**
- No seed data for providers/courses yet (empty catalog until user populates or Plan 02 adds seed)

**Blockers:**
- None

---
*Phase: 12-advanced-ce-multi-credential, Plan: 01*
*Completed: 2026-03-06*
