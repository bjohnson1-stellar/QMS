---
phase: 07-renewal-workflow-events
plan: 01
subsystem: api
tags: [license-events, auto-expire, renewal, fee-tracking, cli]

# Dependency graph
requires:
  - phase: 06-foundation-hardening
    provides: Audit trail (_audit function), pagination pattern, input validation pattern
provides:
  - license_events table with 7 event types and fee tracking
  - DB functions: create_event, get_event, get_license_events, auto_expire_licenses, renew_license
  - API endpoints: GET/POST events, POST renew
  - CLI command: qms licenses auto-expire --dry-run
  - Migration with backfill of issued events
affects: [phase-07-plan-02-event-timeline-ui, phase-08-notifications]

# Tech tracking
tech-stack:
  added: []
  patterns: [event-sourcing-lite, auto-expire-cli-pattern, renewal-with-reinstate]

key-files:
  created: [licenses/cli.py, tests/test_license_events.py]
  modified: [licenses/schema.sql, licenses/db.py, licenses/migrations.py, api/licenses.py, cli/main.py]

key-decisions:
  - "Events tracked in dedicated table, NOT via license status changes — more flexible, no schema rebuild"
  - "Renewal is single-action (update expiration + create event), not multi-step workflow — Phase 8 adds notifications"
  - "Auto-expire as CLI command with --dry-run — schedulable via Task Scheduler later"
  - "Expired licenses reinstated automatically during renewal — creates both reinstated + renewed events"

patterns-established:
  - "Event recording pattern: create_event() with audit trail, used by renew_license() and auto_expire_licenses()"
  - "CLI group registration: licenses/cli.py registered via _register_modules() in cli/main.py"
  - "Fee tracking per event: optional fee_amount + fee_type on any event"

# Metrics
duration: ~30min
started: 2026-03-06
completed: 2026-03-06
---

# Phase 7 Plan 01: License Events Backend Summary

**Added license_events table with 7 event types, fee tracking, auto-expire CLI, renewal API endpoint, and 22 tests — the backend foundation for renewal workflow and event history.**

## Performance

| Metric | Value |
|--------|-------|
| Duration | ~30 min |
| Started | 2026-03-06 |
| Completed | 2026-03-06 |
| Tasks | 3 completed (all auto) |
| Files modified | 7 (2 created, 5 modified) |

## Acceptance Criteria Results

| Criterion | Status | Notes |
|-----------|--------|-------|
| AC-1: License Events Table Exists | Pass | Table with CHECK constraints on event_type (7 types) and fee_type (5 types + NULL), FK to state_licenses ON DELETE CASCADE |
| AC-2: Event CRUD Functions Work | Pass | create_event, get_event, get_license_events all working with audit trail |
| AC-3: Auto-Expire Marks Overdue | Pass | Active licenses past expiration → expired status + event created, skips already-expired and future |
| AC-4: Renewal Endpoint Updates License | Pass | POST /renew updates expiration_date, creates renewed event, reinstates expired licenses automatically |
| AC-5: Event API Endpoints Work | Pass | GET/POST events with validation, 400 on invalid type/missing date, 404 on missing license |
| AC-6: CLI Auto-Expire Command | Pass | `qms licenses auto-expire` with --dry-run, registered in CLI module registry |
| AC-7: Tests Pass | Pass | 22 new tests, 582 total suite (0 failures, 0 regressions) |

## Accomplishments

- `license_events` table — 7 event types (issued/renewed/amended/suspended/revoked/expired/reinstated) with optional fee tracking (amount + type)
- 5 new DB functions — create_event, get_event, get_license_events, auto_expire_licenses, renew_license (with auto-reinstate for expired licenses)
- 3 new API endpoints — GET/POST `/licenses/api/licenses/<id>/events`, POST `/licenses/api/licenses/<id>/renew` with full input validation
- `qms licenses auto-expire` CLI — marks overdue licenses expired with --dry-run support
- Migration with backfill — existing licenses with issued_date get 'issued' events (idempotent)
- 22 tests — DB functions (13), API endpoints (7), CLI commands (2)

## Task Commits

| Task | Commit | Type | Description |
|------|--------|------|-------------|
| All 3 tasks | `14a6415` | feat | Schema, DB functions, API endpoints, CLI, migration, tests |

## Files Created/Modified

| File | Change | Purpose |
|------|--------|---------|
| `licenses/schema.sql` | Modified | Added license_events table definition with indexes |
| `licenses/db.py` | Modified | 5 new functions + VALID_EVENT_TYPES/VALID_FEE_TYPES constants |
| `licenses/migrations.py` | Modified | Phase 7 migration: create table + backfill issued events |
| `api/licenses.py` | Modified | 3 new endpoints + _validate_event_fields() + new imports |
| `licenses/cli.py` | Created | Typer CLI with auto_expire command + --dry-run |
| `cli/main.py` | Modified | Registered licenses CLI group in module registry |
| `tests/test_license_events.py` | Created | 22 tests: DB (13), API (7), CLI (2) |

## Decisions Made

| Decision | Rationale | Impact |
|----------|-----------|--------|
| Events in dedicated table, not status field | Avoids SQLite table rebuild for CHECK constraint change; more flexible event history | Phase 7 Plan 02 reads events for timeline UI |
| Single-action renewal (not multi-step workflow) | Keeps it simple; approval workflow is Phase 8 scope | Renewal = update expiration + create event |
| Auto-reinstate expired licenses during renewal | Natural workflow — if renewing an expired license, it should become active | Creates both 'reinstated' and 'renewed' events |
| CLI single-command Typer app | Only one command now; more can be added later (e.g., check-renewals) | Registered as `qms licenses` group |

## Deviations from Plan

### Summary

| Type | Count | Impact |
|------|-------|--------|
| Auto-fixed | 1 | Minor — CLI test invocation pattern |
| Scope additions | 1 | Minor — added get_event() helper function |
| Deferred | 0 | - |

**Total impact:** Minimal deviations, plan executed as designed.

### Auto-fixed Issues

**1. Typer single-command CLI test invocation**
- **Found during:** Task 3 (tests)
- **Issue:** `runner.invoke(app, ["auto-expire"])` returns exit code 2 because Typer single-command apps treat the command name as an unknown argument
- **Fix:** Changed test to `runner.invoke(app, [])` for default and `runner.invoke(app, ["--dry-run"])` for dry-run
- **Verification:** Both CLI tests pass

### Scope Additions

**1. get_event() helper function**
- Added `get_event(conn, event_id)` as a helper used internally by `create_event()` to return the newly created event
- Zero impact on plan scope, improves code reuse

## Issues Encountered

| Issue | Resolution |
|-------|------------|
| Typer CLI test pattern | Single-command Typer apps are invoked differently than multi-command apps in tests |

## Next Phase Readiness

**Ready:**
- license_events table populated (backfilled issued events for existing licenses)
- Event CRUD fully functional with validation and audit trail
- Renewal endpoint handles both active and expired license renewal
- Auto-expire CLI ready for scheduling
- 22 tests provide regression coverage for Plan 07-02 UI work

**Concerns:**
- None

**Blockers:**
- None — Plan 07-02 (Event Timeline UI + Renewal Workflow UI) can proceed

---
*Phase: 07-renewal-workflow-events, Plan: 01*
*Completed: 2026-03-06*
