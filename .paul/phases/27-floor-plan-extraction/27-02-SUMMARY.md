---
phase: 27-floor-plan-extraction
plan: 02
subsystem: pipeline
tags: [extraction, refrigeration, calibration, sonnet, opus, shadow-review, floor-plans]

requires:
  - phase: 27-01
    provides: floor_plan_extractions table, build_floor_plan_prompt(), extraction harness
provides:
  - Phase 2 discovery data for 19 Refrigeration sheets (213 entries, 11 sheets with equipment)
  - Calibration finding: Sonnet 14.6% on floor plans, Opus 100% — image resolution root cause
  - Shadow review data for 3 calibration sheets
  - Routing decision: floor plans → Opus (later superseded by 27-02a text-layer approach)
affects: [27-02a text-layer fix, 27-03 MEP scaling]

tech-stack:
  added: []
  patterns: [calibrate-first-then-scale, multi-model shadow review]

key-files:
  created: []
  modified: []

key-decisions:
  - "Expanded calibration from 3 sheets to all 19 Refrigeration sheets during Phase 2"
  - "Identified Sonnet floor plan failure: 14.6% accuracy due to image downscaling"
  - "Routed floor plans from Sonnet to Opus (later superseded by 27-02a Sonnet+text-layer)"
  - "Deferred Phases 3-4 to address root cause (text-layer preprocessor) first"

patterns-established:
  - "Calibrate-first approach validated: 3-sheet pilot caught critical Sonnet limitation before scale"
  - "Shadow review as quality gate: Opus blind review caught 75% miss rate on R1101"

duration: ~2hr
started: 2026-03-27T15:00:00Z
completed: 2026-03-28T01:40:00Z
---

# Phase 27 Plan 02: Refrigeration Floor Plan Extraction Summary

**Calibration-first extraction on 19 Refrigeration sheets — Phase 2 discovery complete (213 entries), calibration revealed Sonnet floor plan failure (14.6%), spawned 27-02a text-layer fix. Phases 3-4 deferred to 27-03.**

## Performance

| Metric | Value |
|--------|-------|
| Duration | ~2hr (across 2 sessions) |
| Started | 2026-03-27 |
| Completed | 2026-03-28 (partial — Phase 2 + calibration only) |
| Tasks | 2 of 5 completed, 3 carried forward |
| Files modified | 0 (execution-only plan) |

## Acceptance Criteria Results

| Criterion | Status | Notes |
|-----------|--------|-------|
| AC-1: Calibration Batch Validates Pipeline | Partial | Phase 2 done on all 19 sheets. Shadow on 3. Phase 3 (Haiku) and Phase 4 (conflict) not run. |
| AC-2: Prompts Refined Before Scaling | Pass | Calibration found Sonnet 14.6% on floor plans → spawned 27-02a text-layer fix → Sonnet+text 100% |
| AC-3: Scale Run Processes Remaining Sheets | Deferred | Phase 2 done on all sheets, but Phases 3-4 and remaining shadow reviews carry to 27-03 |
| AC-4: QA Tables Populated | Partial | shadow_reviews (3), extraction_misses (70), routing_changes (3). No accuracy_log, model_runs, gold_standard |
| AC-5: Gold Standard Created | Deferred | Carry to 27-03 |

## Accomplishments

- Ran Phase 2 (Sonnet discovery) on all 19 Refrigeration sheets — 213 entries across 11 sheets with equipment
- Identified critical Sonnet limitation: 14.6% accuracy on large floor plans due to image downscaling (Opus achieved 100%)
- Shadow review on 3 calibration sheets validated the finding (R1101: 75% miss rate, R7001: 100% match, R7002: image limit exceeded)
- 70 extraction misses documented for R1101 — systematic under-extraction of small tags
- Calibration-first approach proved its value: caught the Sonnet limitation on 3 sheets before it multiplied across 340+ pending sheets

## Extraction Results (Phase 2 Discovery)

| Drawing | Sheet ID | Entries | Type |
|---------|----------|---------|------|
| R1101 | 1541 | 41 | Floor Plan |
| R1102 | 1543 | 41 | Floor Plan |
| R1401 | 1544 | 13 | Floor Plan |
| R4101 | 1545 | 7 | Floor Plan |
| R4401 | 1546 | 3 | Floor Plan |
| R7001 | 1558 | 44 | BFD |
| R7002 | 1560 | 30 | P&ID |
| R7003 | 1562 | 11 | P&ID |
| R7004 | 1564 | 9 | P&ID |
| R7005 | 1566 | 11 | P&ID |
| R7006 | 1568 | 3 | P&ID |

8 detail/schedule/notes sheets had no extractable equipment (correct — empty OK).

## Shadow Review Results

| Drawing | Sonnet vs Opus | Accuracy | Key Finding |
|---------|---------------|----------|-------------|
| R1101 (floor plan) | 6 found / 41 actual | 14.6% | CRITICAL: Sonnet missed 25 RAHUs + 10 RCUs due to image downscaling |
| R7001 (BFD) | 44 / 44 | 100% | Perfect match — BFDs are simple enough for Sonnet |
| R7002 (P&ID) | Failed | N/A | Opus exceeded image dimension limit on P&ID |

## Decisions Made

| Decision | Rationale | Impact |
|----------|-----------|--------|
| Expanded to all 19 sheets in Phase 2 | Batching was efficient, no reason to stop at 3 | Got full Phase 2 coverage early |
| Deferred Phases 3-4 | Root cause (image resolution) needed infrastructure fix first | Spawned Plan 27-02a |
| Floor plans → Opus routing | Only model that could read small tags on large drawings | Later superseded by 27-02a Sonnet+text |

## Deviations from Plan

### Summary

| Type | Count | Impact |
|------|-------|--------|
| Scope change | 1 | Phase 2 expanded from 3 → 19 sheets (positive) |
| Deferred | 3 | Tasks 3-5 carried to 27-03 (Phases 3-4, gold standard, accuracy report) |
| Approach change | 1 | Spawned 27-02a to fix root cause before continuing |

**Total impact:** Calibration found a fundamental issue. Rather than proceeding with expensive Opus workaround, the plan correctly paused to build a proper fix (27-02a). This saved significant cost and time at scale.

### Carried Forward to 27-03

- Phase 3 (Haiku detail enrichment) on all sheets with Phase 2 tags
- Phase 4 (Sonnet conflict verification) on discrepancy sheets
- Shadow reviews on remaining 8 high-value sheets (only 3 of 11 shadowed)
- Gold standard creation (at least 1 user-verified sheet)
- accuracy_log and model_runs population
- Validator pass on all sheets

## Issues Encountered

| Issue | Resolution |
|-------|------------|
| Sonnet 14.6% on floor plans | Root cause: image downscaling. Fixed by 27-02a text-layer preprocessor |
| R7002 Opus shadow failed | Image dimension limit exceeded. P&IDs may need different shadow approach |
| Duplicate shadow_reviews records | Each recorded twice (minor data quality issue) |

## Next Phase Readiness

**Ready:**
- Phase 2 discovery complete for all 19 Refrigeration sheets
- Text-layer preprocessor built and validated (27-02a)
- Sonnet+text approach proven at 100% recall
- Prompt infrastructure enhanced with text layer injection
- Shadow review + extraction misses pipeline working

**Concerns:**
- R7002 P&ID shadow failed — need alternative shadow approach for large P&IDs
- Duplicate shadow_reviews entries need cleanup
- model_runs table never populated — tracking gap

**Blockers:**
- None

---
*Phase: 27-floor-plan-extraction, Plan: 02*
*Completed: 2026-03-28 (partial — carried forward to 27-03)*
