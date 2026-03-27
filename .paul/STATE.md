# Project State

## Project Reference

See: .paul/PROJECT.md

**Core value:** Unified quality management platform — quality intelligence (v0.1) + license compliance (v0.2) + quality manual platform (v0.3) + equipment-centric platform (v0.4).
**Current focus:** v0.4 Equipment-Centric Platform — Phase 26 (Schedule Reconciliation)

## Current Position

Milestone: v0.4 Equipment-Centric Platform — In Progress
Phase: 27 (Floor Plan Extraction) — In Progress
Plan: 27-01 complete, 27-02 next
Status: Loop closed, ready for next plan
Last activity: 2026-03-27 — Plan 27-01 unified

Progress:
- v0.4 Equipment-Centric Platform: [█████████░] 90%
- v0.3 Quality Manual Platform: [██████████] 100%
- v0.2 License Compliance Platform: [██████████] 100%
- v0.1 Quality Intelligence Platform: [████████░░] 80% (Phase 5 not started)

## Loop Position

Current loop state:
```
PLAN ──▶ APPLY ──▶ UNIFY
  ✓        ✓        ✓     [Loop complete — Plan 27-01 done, 27-02 next]
```

Note: Phases 22-01, 23-01, 24-01, 25-01 batch-closed on 2026-03-26.

## Execution Log

### v0.4 Equipment-Centric Platform

| Plan | Status | Description | Date |
|------|--------|-------------|------|
| 19-01 | Complete | Equipment registry schema (10 tables), reconciler, 585 instances for Vital | 2026-03-24 |
| 20-01 | Complete | Conflict detection engine, negative space scanner, CLI command (492 conflicts) | 2026-03-25 |
| 21-01 | Complete | Spec compliance engine (9 requirements, 4 violations) + impact chain analyzer (BFS traversal) | 2026-03-25 |
| 22-01 | Complete | Equipment web UI — dashboard + detail page with tabs (6 routes, 4 API endpoints) | 2026-03-26 |
| 23-01 | Complete | Tag parser, dedup 124 reversed duplicates, grouped dashboard view | 2026-03-26 |
| 24-01 | Complete | System type taxonomy, consolidation engine, system dashboard view | 2026-03-26 |
| 25-01 | Complete | Extraction order engine, schedule extractor data layer, context builder | 2026-03-26 |
| 25-02 | Complete | Extraction harness + Vital first batch (5 schedule sheets, 203 entries) | 2026-03-26 |
| 25-03 | Complete | Complete Vital MEP extraction: 452 entries, 19 sheets, Opus shadow QA | 2026-03-26 |
| 26-01 | Complete | Schedule reconciliation: 12th data source, 661 instances, 296 enriched, conflicts 496→473 | 2026-03-27 |
| 27-01 | Complete | Floor plan extraction infrastructure: table, prompts, harness, 344 pending sheets | 2026-03-27 |

### v0.3 Quality Manual Platform

| Plan | Status | Description | Date |
|------|--------|-------------|------|
| 14-01 | Complete | M3/M4 schema (7 tables) + qualitydocs/db.py CRUD module | 2026-03-10 |
| 14-02 | Complete | API endpoints for programs, categories, SOPs (12 endpoints) | 2026-03-10 |
| 15-01 | Complete | Tabbed UI shell + M1/M2 separated views + cross-module search | 2026-03-10 |
| 16-01 | Complete | M3 Programs UI — 5 programs seeded, cards grid, detail view | 2026-03-10 |
| 17-01 | Complete | M4 SOP Catalog UI — category grid, SOP list, SOP detail, search | 2026-03-10 |
| 18-01 | Complete | SOP intake backend pipeline — upload, AI classify, approve/reject | 2026-03-10 |
| 18-02 | Complete | Intake & Approval UI — upload modal, queue, review, lifecycle | 2026-03-11 |

### v0.2 License Compliance Platform

| Plan | Status | Description | Date |
|------|--------|-------------|------|
| 06-01 | Complete | N+1 query fixes + audit trail | 2026-03-05 |
| 06-02 | Complete | Pagination + input validation | 2026-03-05 |
| 06-03 | Complete | Rate limiting + CSRF hardening | 2026-03-05 |
| 07-01 | Complete | License events, auto-expire CLI, renewal API | 2026-03-06 |
| 07-02 | Complete | Event timeline UI, renewal modal, add-event modal | 2026-03-06 |
| 08-01 | Complete | Notification backend: schema, engine, CLI | 2026-03-06 |
| 08-02 | Complete | Teams webhook, notification API, task queue UI | 2026-03-06 |
| 09-01 | Complete | Documents + notes backend, activity feed API | 2026-03-06 |
| 09-02 | Complete | Documents/Notes/Activity UI on detail page | 2026-03-06 |
| 10-01 | Complete | Entity schema, DB functions, API endpoints | 2026-03-06 |
| 10-02 | Complete | Entity list page, detail page, registration UI | 2026-03-06 |
| 11-01 | Complete | Regulatory intelligence backend: schema, CRUD, scoring, gap analysis, seed CLI | 2026-03-06 |
| 11-02 | Complete | Regulatory intelligence UI: compliance gauge, requirements CRUD, compliance overview | 2026-03-06 |
| 12-01 | Complete | CE provider & course catalog backend | 2026-03-06 |
| 12-02 | Complete | CE catalog UI + employee credential portfolio | 2026-03-06 |
| 13-01 | Complete | Dashboard widgets + iCal calendar feed | 2026-03-06 |
| 13-02 | Complete | Cross-module credentials + bulk operations | 2026-03-09 |
| 13-03 | Complete | Verification tracking + external API | 2026-03-09 |

**Pre-milestone work (completed before PAUL tracking):**
- Licenses Phase 1: Base CRUD module, US state SVG map, CSV import, renewal timeline
- Licenses Phase 2: Drill-down navigation, scope mapping, CE tracking tables, board data
- Licenses Phase 3: CE seed data, compliance dashboard, certificate upload, CSV exports

### v0.1 Quality Intelligence Platform — Summary

| Phase | Status | Commit | Date |
|-------|--------|--------|------|
| 1: Quality Issues Foundation | Complete | `16933a0` | 2026-02-25 |
| 2: Procore Bulk Import | Complete | `3bf6242` | 2026-02-26 |
| 3: Quality Intelligence Dashboard | Complete | see summaries | 2026-02-27 |
| 4: Mobile Capture Pipeline | Complete (2/2 plans) | `5a2d9a6` | 2026-03-05 |
| 5: Procore Push | Not started | - | - |

## Accumulated Context

### Decisions
| Decision | Phase | Impact |
|----------|-------|--------|
| Harbor feature parity as target | v0.2 Init | Shapes all 8 phases |
| Foundation hardening first | v0.2 Phase 6 | Shipped — security + perf before new features |
| Clone welding notification pattern | v0.2 Phase 8 | Proven pattern, reduces implementation risk |
| WeasyPrint for compliance reports | v0.2 Phase 11 | Matches existing quality manual PDF pipeline |
| Phase numbering continues from v0.1 | v0.2 Init | Phases 6-13 follow phases 1-5 (unique directories) |
| API-layer validation pattern | v0.2 Phase 6 | Validation at API boundary, DB layer trusts |
| Pagination dict response pattern | v0.2 Phase 6 | {items, total, page, per_page, pages} for list endpoints |
| In-memory rate limiting | v0.2 Phase 6 | No Redis needed for LAN deployment |
| Unified tabbed QM UI replacing single viewer | v0.3 Init | M1/M2/M3/M4 as horizontal tabs |
| Master cross-module search | v0.3 Init | FTS5 across all modules |
| AI-powered SOP classification | v0.3 Init | Claude analyzes PDFs → category, scope, program |
| Draft → approved → published lifecycle | v0.3 Init | SOPs enter as draft, require approval |
| Schema-first for future CRUD | v0.3 Init | Don't build editor yet, but don't block it |
| Scope tag infrastructure without data | v0.3 Init | Schema ready, UI scaffolded, functional when populated |
| LIKE filter for scope_tags (not json_each) | v0.3 Phase 14 | Simpler, works on all SQLite versions |
| Separate transactions for SOP history | v0.3 Phase 14 | Avoids nested get_db() context manager issues |
| Stats show subsections + version per module | v0.3 Phase 15 | Module API lacks per-module block counts; subsections available |
| Search goes full-width (hides TOC) | v0.3 Phase 15 | Cross-module results don't pair with single-module TOC |
| Programs seeded as published, not draft | v0.3 Phase 16 | Foundational programs visible immediately |
| Search bar hidden on M3 tab | v0.3 Phase 16 | Only 5 programs — visual browsing sufficient |
| M4 search routes through existing search bar | v0.3 Phase 17 | Tab-aware branching: M4 searches SOPs, M1/M2 searches manual |
| Status badge CSS class convention | v0.3 Phase 17 | .status-{status} for color coding (6 states) |
| Synchronous classification (no async queue) | v0.3 Phase 18 | Simple for single-user LAN; upload blocks during classify |
| PDF document type (not vision) for classify | v0.3 Phase 18 | Better text extraction from PDFs |
| CSRF token in FormData for multipart uploads | v0.3 Phase 18 | JSON API bypasses CSRF via Origin header; multipart needs explicit token |
| Centralized hideAllM4Panels() navigation | v0.3 Phase 18 | Single function manages all M4 sub-view visibility |
| Alias mapping for cross-discipline attribute names | v0.4 Phase 20 | hp_rating ↔ hp ↔ power_hp — enables attribute comparison without uniform naming |
| Batch UPDATE for appearance attributes on re-run | v0.4 Phase 20 | INSERT OR IGNORE + UPDATE pattern for idempotent attribute enrichment |
| Voltage normalization (primary value extraction) | v0.4 Phase 20 | "480/277V" → 480.0 to reduce false positives |
| SQL seed for spec requirements (not Python migration) | v0.4 Phase 21 | INSERT OR IGNORE in schema file — consistent with conflict_rules pattern |
| Advisory-only violation propagation | v0.4 Phase 21 | Impact analysis returns results, doesn't create new conflict records |
| Extended _parse_numeric locally for AIC suffixes | v0.4 Phase 21 | Avoids modifying stable conflict_detector.py |
| Longest-parent-first tag matching | v0.4 Phase 23 | RAHU-20-CV2 → parent RAHU-20, not RAHU-2 — prevents false parent assignment |
| Client-side grouping (not SQL GROUP BY) | v0.4 Phase 23 | API returns flat list with parent_tag; JS groups — simpler, filter-compatible |
| Discipline priority: Refrig→Utility→Mech→Elec→Plumb | v0.4 Phase 25 | Refrigeration first (most complex), plumbing last (fixtures, not systems) |
| Harness is session-stepped state machine | v0.4 Phase 25 | No API calls or subprocess spawning — Claude Code session drives extraction |
| Expand grouped RAHU tags into individual entries | v0.4 Phase 25 | "RAHU-1 TO RAHU-3" stored as RAHU-1, RAHU-2, RAHU-3 individually |
| manufacturer/model in attributes JSON (not direct columns) | v0.4 Phase 26 | Future queries use JSON extraction; schema boundary respected |
| Non-NULL conflicts logged, not overwritten | v0.4 Phase 26 | Schedule doesn't trump drawing data; audit trail in attribute_log |
| Two-pass reconciliation (scan+create, then enrich) | v0.4 Phase 26 | Can re-run enrichment independently from full reconciliation |

### Git State
Last commit: `c3ccf33` (feat(pipeline): floor plan extraction infrastructure (Phase 27-01))
Branch: main

### Deferred Issues
| Issue | Impact | Resolution Path |
|-------|--------|-----------------|
| v0.1 Phase 5 not started | Procore push deferred | Can be done in parallel or after v0.3 |
| CE requirement type matching | Seeded types don't exactly match existing license_type values | Data cleanup when relevant |
| Production Waitress template caching | New templates require server restart | Configure auto_reload or restart after deploys |
| Parent program names on M4 cards depend on programsCache | Minor: empty if M3 not visited first | Will resolve naturally on use; could prefetch in init |
| R0001 legend not extracted | Instrument abbreviations not from authoritative source | Phase 23-02 planned for legend extraction |
| Drawing viewer in web UI | Side-by-side PDF + extracted data for human verification | Phase 26 — pdf.js viewer, page jump from extraction data |
| Phase 22-01 UNIFY pending | Applied but not formally closed | Close after 23-01 or in next session |

### Blockers/Concerns
| Blocker | Impact | Resolution Path |
|---------|--------|-----------------|
| Production server needs restart for new blueprint | Equipment module 404 on production | User must restart Waitress (zombie PID 79740 blocking port) |

## Session Continuity

Last session: 2026-03-27
Stopped at: Plan 27-01 complete
Next action: Plan 27-02 (Refrigeration P&ID batch extraction)
Resume file: .paul/phases/27-floor-plan-extraction/27-01-SUMMARY.md
Resume notes: |
  Phase 27-01 complete. Infrastructure ready: floor_plan_extractions table, context-aware prompts, harness.
  Next: Plan 27-02 — extract 10 Refrigeration P&IDs (highest-value first batch).
  344 total floor plan sheets pending (141 after skipping Arch/Civil/Structural/General).

---
*STATE.md — Updated after every significant action*
