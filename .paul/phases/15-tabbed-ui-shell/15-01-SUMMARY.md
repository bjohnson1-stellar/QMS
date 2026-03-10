---
phase: 15-tabbed-ui-shell
plan: 01
subsystem: ui
tags: [flask, jinja2, javascript, tabs, qualitydocs, quality-manual]

requires:
  - phase: 14-schema-api-foundation
    provides: 14-02 API endpoints for M3 programs, M4 categories, M4 SOPs
provides:
  - 4-tab UI shell (M1, M2, M3, M4) for quality manual
  - Per-module TOC filtering and stats
  - Cross-module search with module badges
  - URL hash routing for tab persistence
  - M3/M4 empty-state placeholders for Phase 16/17
affects: [16 M3 Programs UI, 17 M4 SOP Catalog UI, 18 SOP Intake]

tech-stack:
  added: []
  patterns: [tab-based module navigation, URL hash routing, per-module stats rendering]

key-files:
  created: []
  modified: [frontend/templates/qualitydocs/index.html]

key-decisions:
  - "Stats show subsections + version per module (API lacks per-module content block counts)"
  - "M3/M4 tabs show empty-state cards referencing upcoming phases"
  - "Search runs full-width without TOC sidebar for better result display"

patterns-established:
  - "Tab switching via switchTab(tabId) — future phases plug into this"
  - "Module badge CSS classes: .mod-1, .mod-2 for color-coded search results"
  - "URL hash routing: #m1, #m2, #m3, #m4 with init-time restoration"

duration: ~15min
started: 2026-03-10T16:00:00Z
completed: 2026-03-10T16:15:00Z
---

# Phase 15 Plan 01: Tabbed UI Shell & M1/M2 Summary

**Refactored quality manual from single-page viewer into 4-tab UI shell with separated M1/M2 views, cross-module search with module badges, and M3/M4 empty-state placeholders.**

## Performance

| Metric | Value |
|--------|-------|
| Duration | ~15min |
| Started | 2026-03-10T16:00Z |
| Completed | 2026-03-10T16:15Z |
| Tasks | 2 completed |
| Files modified | 1 |

## Acceptance Criteria Results

| Criterion | Status | Notes |
|-----------|--------|-------|
| AC-1: Tab Navigation | Pass | 4 tabs render with icons, badges, active state styling |
| AC-2: M1/M2 Separated Views | Pass | TOC filters to active module only, section loading works |
| AC-3: M3/M4 Empty States | Pass | Centered cards with icons, descriptions, "Coming in Phase N" badges |
| AC-4: Cross-Module Search | Pass | Results show M1/M2 badges, clicking navigates to correct tab + section |
| AC-5: URL Hash Routing | Pass | Hash updates on tab switch, persists on page refresh |
| AC-6: Stats Cards Update | Pass | Shows module name, section count, subsection count, version per tab |

## Accomplishments

- 4-tab navigation bar with icons, section count badges, and active state highlighting
- M1/M2 each get their own filtered TOC and per-module stats cards
- Cross-module search with color-coded M1/M2 module badges on each result
- Clicking search results auto-switches to the correct tab and loads the section
- M3/M4 empty-state cards ready for Phase 16/17 to replace with real content

## Files Created/Modified

| File | Change | Purpose |
|------|--------|---------|
| `frontend/templates/qualitydocs/index.html` | Modified | Complete refactor: tab bar, per-module TOC, search badges, empty states, hash routing |

## Decisions Made

| Decision | Rationale | Impact |
|----------|-----------|--------|
| Stats show subsections + version instead of content blocks + xrefs | Module API doesn't return per-module content block or xref counts; subsection_count and version are available per module in summary API | Stats are meaningful and accurate; could revisit if per-module block counts added to API |
| Search goes full-width (hides TOC sidebar) | Search results span all modules — showing a single-module TOC alongside cross-module results is confusing | Clean UX; clearing search restores current tab's TOC |
| M3/M4 reference specific phase numbers | User knows the roadmap; concrete phase references set expectations | Update text when those phases ship |

## Deviations from Plan

### Summary

| Type | Count | Impact |
|------|-------|--------|
| Auto-fixed | 1 | Minor — stats card data source adjusted |
| Scope additions | 0 | None |
| Deferred | 0 | None |

**Total impact:** Minimal — one stats rendering adjustment, no scope creep.

### Auto-fixed Issues

**1. Stats card data source mismatch**
- **Found during:** Task 1 (tab bar + refactor)
- **Issue:** Plan specified content block and cross-reference counts per module, but the module API only returns section list without those counts. Initial implementation showed "0" for content blocks and xrefs.
- **Fix:** Changed stats to show subsection_count and version (both available in summary API per module) instead of unavailable block/xref counts.
- **Files:** `frontend/templates/qualitydocs/index.html`
- **Verification:** Stats display correct values: M1 (7 sections, 24 subsections, v1.4), M2 (6 sections, 45 subsections, v1.3)

## Issues Encountered

| Issue | Resolution |
|-------|------------|
| Production server (Waitress) caches templates | Started dev Flask server on port 5001 for testing; production will pick up changes on next restart |

## Next Phase Readiness

**Ready:**
- Tab shell is fully functional — Phase 16 (M3 Programs UI) and Phase 17 (M4 SOP Catalog UI) plug directly into the M3/M4 tab panels
- All M3/M4 API endpoints from Phase 14 are available for frontend consumption
- Search infrastructure ready to extend with M3/M4 results when content exists

**Concerns:**
- Production server needs restart to pick up template changes (template caching in Waitress)

**Blockers:**
- None

---
*Phase: 15-tabbed-ui-shell, Plan: 01*
*Completed: 2026-03-10*
