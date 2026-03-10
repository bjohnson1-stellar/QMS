---
phase: 16-m3-programs-ui
plan: 01
subsystem: ui
tags: [flask, jinja2, javascript, qualitydocs, programs, seed-data]

requires:
  - phase: 15-tabbed-ui-shell
    provides: 4-tab shell with M3 empty-state placeholder
  - phase: 14-schema-api-foundation
    provides: M3 programs API endpoints, qm_programs schema
provides:
  - 5 seeded M3 discipline programs (SIS-3.01–3.05)
  - M3 Programs tab UI with cards grid and detail view
  - Category-to-program linkage (11 of 15 categories linked)
affects: [17 M4 SOP Catalog UI, 18 SOP Intake]

tech-stack:
  added: []
  patterns: [program cards grid with click-to-detail, parallel API fetch with caching]

key-files:
  created: []
  modified: [qualitydocs/db.py, qualitydocs/__init__.py, frontend/templates/qualitydocs/index.html]

key-decisions:
  - "Programs seeded as 'published' status — no draft workflow needed for foundational programs"
  - "seed_programs() also fixes category linkage in same transaction"
  - "Search bar hidden on M3 tab — programs are few enough to browse visually"
  - "Categories fetched alongside programs for detail view linkage (parallel fetch)"

patterns-established:
  - "loadPrograms() with programsCache/categoriesCache for M3 tab data"
  - "Grid-to-detail navigation pattern: showProgramDetail() / backToPrograms()"
  - "Empty state fallback when API returns zero items"

duration: ~10min
started: 2026-03-10T17:00:00Z
completed: 2026-03-10T17:10:00Z
---

# Phase 16 Plan 01: M3 Programs UI Summary

**Seeded 5 discipline quality programs and built interactive M3 tab with program cards grid, click-to-expand detail view showing code references, qualification requirements, and linked M4 categories.**

## Performance

| Metric | Value |
|--------|-------|
| Duration | ~10min |
| Started | 2026-03-10T17:00Z |
| Completed | 2026-03-10T17:10Z |
| Tasks | 2 completed |
| Files modified | 3 |

## Acceptance Criteria Results

| Criterion | Status | Notes |
|-----------|--------|-------|
| AC-1: Programs Seeded | Pass | 5 programs (SIS-3.01–3.05) with titles, descriptions, codes, qualifications, status=published |
| AC-2: Category Linkage Fixed | Pass | 11 of 15 categories now have valid parent_program_id integers |
| AC-3: Program Cards Grid | Pass | Responsive grid with program_id badge, title, description, code tags, category count |
| AC-4: Program Detail View | Pass | Full detail with description, codes, qualifications, linked categories, SOPs (empty), back button |
| AC-5: Empty State Handling | Pass | "No Programs Configured" message with guidance when API returns empty array |

## Accomplishments

- Seeded 5 SIS discipline programs with comprehensive data (codes, qualifications, descriptions)
- Fixed M4 category → M3 program linkage (11 categories now properly linked)
- Built responsive program cards grid with hover effects and metadata badges
- Built program detail view with back navigation, code references, and linked categories list
- Exported seed_programs() function for reuse

## Files Created/Modified

| File | Change | Purpose |
|------|--------|---------|
| `qualitydocs/db.py` | Modified | Added _M3_PROGRAMS data, seed_programs() function with category linkage fix |
| `qualitydocs/__init__.py` | Modified | Exported seed_programs in imports and __all__ |
| `frontend/templates/qualitydocs/index.html` | Modified | Replaced M3 empty state with programs grid + detail view; added CSS + JS |

## Decisions Made

| Decision | Rationale | Impact |
|----------|-----------|--------|
| Programs seeded as 'published' | These are foundational discipline programs, not user-created content needing approval | Programs immediately visible in UI |
| Search bar hidden on M3 tab | Only 5 programs — visual browsing is faster than searching | Clean UI; search can be added if programs grow |
| Parallel fetch for programs + categories | Detail view needs category linkage; fetching both at once avoids sequential requests | Faster initial load, data cached for detail views |

## Deviations from Plan

### Summary

| Type | Count | Impact |
|------|-------|--------|
| Auto-fixed | 0 | None |
| Scope additions | 0 | None |
| Deferred | 0 | None |

**Total impact:** None — plan executed as written.

## Issues Encountered

| Issue | Resolution |
|-------|------------|
| seed_categories/seed_programs not wired into auto-migration | Both are exported for manual/CLI use; same pattern as existing seed_categories |

## Next Phase Readiness

**Ready:**
- M3 tab fully functional with program data
- Categories linked to programs — M4 UI (Phase 17) can show parent program info
- API endpoints proven working for programs and categories

**Concerns:**
- Production server (Waitress) caches templates — needs restart to see UI changes

**Blockers:**
- None

---
*Phase: 16-m3-programs-ui, Plan: 01*
*Completed: 2026-03-10*
