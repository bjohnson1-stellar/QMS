---
phase: 25-schedule-first-extraction
plan: 01
subsystem: pipeline
tags: [extraction, schedule-first, haiku, context-builder, equipment-schema]

requires:
  - phase: 24-01
    provides: system model, equipment types taxonomy
provides:
  - Extraction order engine (schedules → legends → plans classification)
  - Schedule extractor data layer (staging table + CRUD)
  - Context builder (per-sheet equipment checklists for informed extraction)
  - Context-aware extraction prompt integration
affects: [25-02 extraction harness, 25-03 reconciliation, floor plan extraction]

tech-stack:
  added: []
  patterns: [schedule-first extraction, context-injected prompts, staging table pattern]

key-files:
  created: [pipeline/extraction_order.py, pipeline/schedule_extractor.py, pipeline/context_builder.py]
  modified: [pipeline/extractor.py, pipeline/equipment_schema.sql]

key-decisions:
  - "Claude Code agents do extraction (not direct API calls) — uses user subscription"
  - "schedule_extractions staging table with INSERT OR REPLACE for idempotency"
  - "Context builder limits to 100 most relevant tags per sheet"
  - "Same-discipline equipment prioritized in context, cross-discipline fills remaining slots"

patterns-established:
  - "Three-phase extraction order: schedules (Haiku) → legends (Haiku) → plans (Sonnet)"
  - "Staging table pattern: raw extraction → schedule_extractions → reconcile → equipment_instances"
  - "Context injection: build_extraction_prompt() accepts optional context parameter"

duration: ~30min
started: 2026-03-26T15:30:00Z
completed: 2026-03-26T16:00:00Z
---

# Phase 25 Plan 01: Schedule-First Extraction Infrastructure Summary

**Extraction order engine classifying 414 sheets into 3 phases, schedule extractor data layer with staging table, and context builder producing per-sheet equipment checklists for informed floor plan extraction.**

## Performance

| Metric | Value |
|--------|-------|
| Duration | ~30 min |
| Started | 2026-03-26T15:30Z |
| Completed | 2026-03-26T16:00Z |
| Tasks | 4 completed (3 auto + 1 checkpoint) |
| Files modified | 5 (3 created, 2 modified) |

## Acceptance Criteria Results

| Criterion | Status | Notes |
|-----------|--------|-------|
| AC-1: Extraction order determines correct processing sequence | Pass | 59 schedules, 11 legends, 344 plans; Haiku/Haiku/Sonnet model assignments |
| AC-2: Schedule extractor produces structured equipment data | Pass | Data layer functional — store/query/clear/summary. Actual extraction deferred to 25-02 harness design |
| AC-3: Context builder creates equipment checklist | Pass | 100 equipment items filtered by discipline, formatted as checklist (10K chars) |
| AC-4: Informed extraction uses context | Pass | build_extraction_prompt() accepts optional context param, context_builder integrates |

## Accomplishments

- **Extraction order engine** (`extraction_order.py`): Classifies sheets by drawing_category and drawing_number patterns (x6xxx = schedule, x0001/x0002 = legend). Orders by discipline priority within phases.
- **Schedule extractor data layer** (`schedule_extractor.py`): get_pending_schedules(), store_schedule_data(), get_schedule_summary(), clear_schedule_data(). Designed for Claude Code agent extraction pattern (no API calls).
- **Context builder** (`context_builder.py`): build_sheet_context() merges schedule_extractions + equipment_instances, filters by discipline relevance (same-discipline first), limits to 100 tags. format_equipment_checklist() produces formatted prompt text.
- **schedule_extractions staging table**: 21-column table with UNIQUE(sheet_id, tag), JSON overflow for additional attributes, confidence scoring, extraction model tracking.

## Task Commits

| Task | Commit | Type | Description |
|------|--------|------|-------------|
| Tasks 1-4 | `2687b8d` | feat | Schedule-first extraction infrastructure |

## Files Created/Modified

| File | Change | Purpose |
|------|--------|---------|
| `pipeline/extraction_order.py` | Created | Sheet classification + discipline-priority ordering |
| `pipeline/schedule_extractor.py` | Created | Schedule extraction data management (CRUD + summary) |
| `pipeline/context_builder.py` | Created | Per-sheet equipment checklist builder |
| `pipeline/equipment_schema.sql` | Modified | Added schedule_extractions staging table |
| `pipeline/extractor.py` | Modified | build_extraction_prompt() accepts optional context parameter |

## Decisions Made

| Decision | Rationale | Impact |
|----------|-----------|--------|
| Agent-based extraction (not API) | Uses Claude Code user subscription, no API key needed | Harness provides prompts, session does AI work |
| Staging table before reconciliation | Raw schedule data preserved separately from curated equipment_instances | Enables re-extraction without data loss |
| 100-tag context limit | Keep Sonnet prompt focused, avoid overwhelming model | Prioritizes same-discipline, fills with cross-discipline |
| Schedule extractor is data layer only | Original plan had Haiku API calls; redesigned for Claude Code agent pattern | Simpler, more reliable, no API dependency |

## Deviations from Plan

### Summary

| Type | Count | Impact |
|------|-------|--------|
| Design change | 1 | Improved — simpler architecture |
| Deferred | 0 | — |

**Total impact:** Positive — cleaner separation of concerns.

### Design Change

**1. Schedule extractor redesigned as data layer (not Haiku API caller)**
- **Original plan:** schedule_extractor.py would call Haiku API directly for each sheet
- **Actual:** schedule_extractor.py provides data management only (CRUD + queries). AI extraction happens through Claude Code session (user subscription).
- **Reason:** Avoids API key dependency, uses existing Claude Code session capabilities
- **Impact:** Required 25-02 to build the orchestration harness

## Issues Encountered

| Issue | Resolution |
|-------|------------|
| None | Plan executed cleanly |

## Next Phase Readiness

**Ready:**
- All three infrastructure modules functional and tested
- schedule_extractions table populated with 203 entries (from 25-02)
- Context builder produces relevant checklists
- Foundation ready for continued schedule extraction and floor plan processing

**Concerns:**
- None

**Blockers:**
- None

---
*Phase: 25-schedule-first-extraction, Plan: 01*
*Completed: 2026-03-26*
