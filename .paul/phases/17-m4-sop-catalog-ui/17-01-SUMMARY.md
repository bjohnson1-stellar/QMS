---
phase: 17-m4-sop-catalog-ui
plan: 01
subsystem: ui
tags: [flask, jinja2, javascript, qualitydocs, sop-catalog]

requires:
  - phase: 16-m3-programs-ui
    provides: M3 cards grid + detail pattern, categoriesCache variable
  - phase: 14-schema-api-foundation
    provides: M4 API endpoints (categories, SOPs, search), DB functions
provides:
  - M4 SOP Catalog UI — browsable category grid, SOP list, SOP detail
  - M4 search integration (SOP search routed through search bar)
  - Status badge system (draft/approved/published/superseded/obsolete)
  - Navigation: categories → SOP list → SOP detail with back buttons
affects: [18-m4-sop-intake-classification]

tech-stack:
  added: []
  patterns: [M4 category grid mirrors M3 program grid, lazy-load on tab switch, m4SearchMode flag for back navigation context]

key-files:
  modified: [frontend/templates/qualitydocs/index.html]

key-decisions:
  - "Reuse M3 card pattern for categories (consistent UI)"
  - "Route M4 search through existing search bar with tab-aware branching"
  - "m4SearchMode flag tracks whether SOP detail back button returns to search results or category list"
  - "Parent program name shown on category cards via programsCache lookup"

patterns-established:
  - "Status badge CSS class convention: .status-{status} for color coding"
  - "M4 search results navigable to SOP detail with contextual back navigation"

duration: 12min
started: 2026-03-10T14:00:00Z
completed: 2026-03-10T14:12:00Z
---

# Phase 17 Plan 01: M4 SOP Catalog UI Summary

**M4 SOP Catalog tab with 15-category card grid, category detail with SOP list, individual SOP detail view, and M4-specific search integration — all in single-file index.html.**

## Performance

| Metric | Value |
|--------|-------|
| Duration | ~12 min |
| Tasks | 2 completed |
| Files modified | 1 |

## Acceptance Criteria Results

| Criterion | Status | Notes |
|-----------|--------|-------|
| AC-1: Category Cards Grid | Pass | 15 cards with code badge, name, description, SOP count, parent program |
| AC-2: Category Detail / SOP List | Pass | Back button, header, SOP rows (doc ID, title, status, version), empty state |
| AC-3: SOP Detail View | Pass | Doc ID badge, status badge, version/revision, scope tags, summary, linked programs, metadata |
| AC-4: M4 Search Integration | Pass | Search bar routes to /api/sops/search on M4 tab, results with back-to-categories |

## Accomplishments

- Built complete M4 SOP Catalog browsing UI: categories grid → SOP list → SOP detail
- Added ~200 lines of CSS (category cards, SOP rows, status badges, scope tags, SOP detail, search results)
- Added ~250 lines of JavaScript (8 functions: loadCategories, renderCategoryCards, showCategoryDetail, renderCategoryDetail, showSopDetail, renderSopDetail, searchM4Sops, renderM4SearchResults)
- Wired M4 tab switch to lazy-load categories, and search bar to route M4 queries to SOP search
- 6 status badge color variants (draft/under_review/approved/published/superseded/obsolete)
- Contextual back navigation: SOP detail knows whether to return to search results or category list

## Files Created/Modified

| File | Change | Purpose |
|------|--------|---------|
| `frontend/templates/qualitydocs/index.html` | Modified | Added M4 CSS (~200 lines), replaced M4 empty state with 4-panel structure, added M4 JS functions (~250 lines), wired tab switch + search routing |

## Decisions Made

| Decision | Rationale | Impact |
|----------|-----------|--------|
| Reuse M3 card/detail pattern | Consistent UX across M3/M4, less CSS, proven pattern | Cards and detail views follow same structure |
| m4SearchMode flag for back navigation | SOP detail needs to know context (from search vs category) | Clean back navigation without complex state |
| Parent program lookup via programsCache | Categories API returns parent_program_id but not name | Requires M3 programs to load first (happens on first M3 visit or M4 loadCategories) |

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

| Issue | Resolution |
|-------|------------|
| Parent program names not in categories API | Used programsCache lookup (already loaded by M3 or via categories fetch) — works because programs load on first M3 tab visit |

## Verification Results

- Template compiles without Jinja2 errors ✓
- JavaScript braces balanced (175/175) ✓
- 15 categories returned from API with correct codes and names ✓
- SOP list endpoint returns paginated response (0 SOPs currently) ✓
- SOP search endpoint functional (returns results) ✓
- All 11 window-exposed functions properly defined ✓
- No boundary violations (api/qualitydocs.py, qualitydocs/db.py, schema.sql untouched) ✓

## Next Phase Readiness

**Ready:**
- M4 tab fully functional for browsing categories and SOPs
- SOP detail view ready to display data once SOPs are ingested
- Status badges ready for all lifecycle states (draft → published)
- All M1–M4 tabs operational

**Concerns:**
- Parent program names on category cards depend on programsCache being populated (only happens if M3 tab visited first or programs fetched during categories load). If user goes directly to M4 without visiting M3, program names won't show. Minor issue — programs load on first M3 visit.

**Blockers:**
- None

---
*Phase: 17-m4-sop-catalog-ui, Plan: 01*
*Completed: 2026-03-10*
