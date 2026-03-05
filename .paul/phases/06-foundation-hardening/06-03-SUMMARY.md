---
phase: 06-foundation-hardening
plan: 03
subsystem: api
tags: [rate-limiting, csrf, security, flask, before-request]

# Dependency graph
requires:
  - phase: 06-foundation-hardening/06-01
    provides: Audit trail pattern
  - phase: 06-foundation-hardening/06-02
    provides: Validation pattern on mutation endpoints
provides:
  - APIRateLimiter class (60 req/min per IP on mutations)
  - CSRF coverage for POST/PUT/DELETE/PATCH
  - Origin header validation for JSON APIs
  - Proper 429 responses with Retry-After
affects: [phase-7-renewal-workflow, phase-8-notifications, phase-13-integrations]

# Tech tracking
tech-stack:
  added: []
  patterns: [api-rate-limiting, origin-validation, 429-response-pattern]

key-files:
  created: []
  modified: [auth/rate_limit.py, api/__init__.py, api/auth.py]

key-decisions:
  - "Combined check_and_record() for API limiter — counts all requests, not just failures"
  - "Origin validation as defense-in-depth, not primary CSRF defense (SameSite=Lax is primary)"
  - "60 req/min per IP — generous for LAN, catches runaway scripts"

patterns-established:
  - "APIRateLimiter: per-IP sliding window with atomic check+record"
  - "429 response pattern: JSON body + Retry-After header"
  - "Origin validation: allow same-origin (no Origin header) + matching Origin"

# Metrics
duration: ~10min
started: 2026-03-05
completed: 2026-03-05
---

# Phase 6 Plan 03: Rate Limiting + CSRF Hardening Summary

**Added general API rate limiting (60 req/min per IP on mutations), extended CSRF to all state-changing HTTP methods, and added Origin header validation for JSON APIs as defense-in-depth.**

## Performance

| Metric | Value |
|--------|-------|
| Duration | ~10 min |
| Started | 2026-03-05 |
| Completed | 2026-03-05 |
| Tasks | 2 completed |
| Files modified | 3 |

## Acceptance Criteria Results

| Criterion | Status | Notes |
|-----------|--------|-------|
| AC-1: API Mutation Rate Limiting | Pass | APIRateLimiter class, 60/min per IP, 429 + Retry-After |
| AC-2: Login Rate Limit Returns 429 | Pass | Both JSON (429 + body) and HTML (429 + rendered page) responses |
| AC-3: CSRF on All State-Changing Methods | Pass | check_csrf() now covers POST/PUT/DELETE/PATCH |
| AC-4: Origin Header Validation | Pass | JSON requests with mismatched Origin get 403 |
| AC-5: No Regressions | Pass | 551 tests pass |

## Accomplishments

- `APIRateLimiter` class with atomic `check_and_record()` — 60 req/min per IP on POST/PUT/DELETE/PATCH
- `check_api_rate_limit()` before_request hook wired before auth gate in app factory
- Login rate limit now returns HTTP 429 (was 200 with error in body) with Retry-After header
- CSRF `check_csrf()` extended from POST-only to POST/PUT/DELETE/PATCH
- Origin header validation on JSON API requests — blocks cross-origin, allows same-origin

## Task Commits

| Task | Commit | Type | Description |
|------|--------|------|-------------|
| Task 1+2: Rate limiting + CSRF | `622eba6` | feat | API rate limiter + CSRF hardening |

## Files Created/Modified

| File | Change | Purpose |
|------|--------|---------|
| `auth/rate_limit.py` | Modified | Added APIRateLimiter class + api_limiter singleton |
| `api/__init__.py` | Modified | check_api_rate_limit() hook, CSRF method extension, Origin validation |
| `api/auth.py` | Modified | Login returns 429 with Retry-After on rate limit |

## Decisions Made

| Decision | Rationale | Impact |
|----------|-----------|--------|
| Atomic check_and_record() | API limiter counts all requests (not just failures) | Simpler API, prevents race conditions |
| Origin validation as defense-in-depth | SameSite=Lax is primary defense; Origin is backup | No impact on same-origin fetch() calls |
| Auth endpoints exempt from API limiter | Login has its own dedicated limiter | Avoids double-counting |
| No external dependencies | In-memory limiter suits LAN deployment | Restarts clear state (acceptable) |

## Deviations from Plan

### Summary

| Type | Count | Impact |
|------|-------|--------|
| Auto-fixed | 0 | - |
| Scope additions | 0 | - |
| Deferred | 0 | - |

**Total impact:** Plan executed exactly as written.

## Issues Encountered

None

## Next Phase Readiness

**Ready:**
- Phase 6 complete: N+1 fixes, audit trail, pagination, validation, rate limiting, CSRF hardening
- All mutation endpoints protected by validation (06-02) + rate limiting (06-03) + CSRF (06-03)
- Foundation is solid for Phase 7 (Renewal Workflow & Events)

**Concerns:**
- None

**Blockers:**
- None

---
*Phase: 06-foundation-hardening, Plan: 03*
*Completed: 2026-03-05*
