---
phase: 14-schema-api-foundation
plan: 02
subsystem: api
tags: [flask, blueprint, rest-api, qualitydocs, m3-programs, m4-sops, m4-categories]

requires:
  - phase: 14-schema-api-foundation
    provides: 14-01 schema + db.py CRUD functions (22 functions)
provides:
  - 12 API endpoints for M3 programs, M4 categories, M4 SOPs
  - Full SOP lifecycle via API (create → approve → publish)
  - Paginated SOP listing with filters
  - SOP search endpoint
affects: [15 tabbed UI, 16 M3 UI, 17 M4 UI, 18 SOP intake]

tech-stack:
  added: []
  patterns: [API-layer validation, paginated list endpoints, lifecycle action endpoints]

key-files:
  created: []
  modified: [api/qualitydocs.py]

key-decisions:
  - "No auth decorators yet — added when auth wired in UI phases"
  - "SOP search route at /api/sops/search registered before /api/sops/<document_id> to avoid route collision"

patterns-established:
  - "Lifecycle action endpoints: POST /api/sops/<id>/approve, /publish"
  - "Link endpoints: POST /api/sops/<id>/link-program"
  - "Consistent 404 for missing resources, 400 for validation errors, 201 for creates"

duration: ~10min
started: 2026-03-10T15:00:00Z
completed: 2026-03-10T15:10:00Z
---

# Phase 14 Plan 02: API Endpoints Summary

**Added 12 REST endpoints to qualitydocs blueprint for M3 programs, M4 categories, and M4 SOPs — enabling frontend phases 15-17.**

## Performance

| Metric | Value |
|--------|-------|
| Duration | ~10min |
| Started | 2026-03-10T15:00Z |
| Completed | 2026-03-10T15:10Z |
| Tasks | 1 completed |
| Files modified | 1 |

## Acceptance Criteria Results

| Criterion | Status | Notes |
|-----------|--------|-------|
| AC-1: Programs API | Pass | GET list (200, 0 programs), GET detail with linked SOPs, 404 for missing |
| AC-2: Categories API | Pass | GET list (200, 15 seeded categories), GET detail, 404 for missing |
| AC-3: SOPs List and Detail API | Pass | Paginated response {items, total, page, per_page, pages}, detail with programs + scope_tags |
| AC-4: SOP Lifecycle API | Pass | POST approve (200), POST publish (200), history records 3 entries (created, approved, published) |
| AC-5: SOP Search API | Pass | GET search returns {results, query} |

## Accomplishments

- 12 new endpoints added to api/qualitydocs.py covering programs, categories, SOPs
- Full SOP lifecycle verified end-to-end: create (201) → approve (200) → publish (200) with history
- Input validation at API boundary: 400 for missing required fields, 404 for missing resources
- Existing M1/M2 endpoints (summary, module, section, search, export) verified unbroken

## Files Created/Modified

| File | Change | Purpose |
|------|--------|---------|
| `api/qualitydocs.py` | Modified | Added 12 M3/M4 API endpoints + db.py imports |

## Decisions Made

| Decision | Rationale | Impact |
|----------|-----------|--------|
| No auth decorators on new endpoints | Auth will be wired when UI phases add module access | Endpoints accessible without auth in dev bypass mode |
| Search route before detail route | Flask matches routes in registration order; /search must precede /<document_id> | Prevents search being captured by detail route |

## Deviations from Plan

### Summary

| Type | Count | Impact |
|------|-------|--------|
| Auto-fixed | 0 | None |
| Scope additions | 0 | None |
| Deferred | 0 | None |

**Total impact:** None — plan executed exactly as written.

## Issues Encountered

| Issue | Resolution |
|-------|------------|
| Test client 302 redirects from auth gate | Used session injection with admin user for test verification |

## Next Phase Readiness

**Ready:**
- All API endpoints functional for Phase 15 (Tabbed UI Shell)
- Programs, categories, SOPs all queryable from frontend JavaScript
- Phase 14 complete — schema + API foundation fully in place

**Concerns:**
- None

**Blockers:**
- None

---
*Phase: 14-schema-api-foundation, Plan: 02*
*Completed: 2026-03-10*
