---
phase: 20-conflict-detection
plan: 01
subsystem: pipeline
tags: [sqlite, conflict-detection, negative-space, cross-discipline, rfi]

requires:
  - phase: 19-equipment-master
    provides: equipment registry schema, reconciler, 585 equipment instances, conflict_rules table
provides:
  - Cross-discipline attribute conflict detection engine
  - Missing discipline (negative space) scanner
  - CLI conflicts command with summary and RFI output
  - Enhanced reconciler with per-discipline attribute capture
affects: [21-spec-compliance, 22-equipment-ui]

tech-stack:
  added: []
  patterns: [attribute-alias-mapping, rule-based-comparison, voltage-normalization]

key-files:
  created:
    - pipeline/conflict_detector.py
  modified:
    - pipeline/reconciler.py
    - pipeline/cli.py

key-decisions:
  - "Alias mapping for cross-discipline attribute comparison (hp_rating ↔ hp ↔ power_hp)"
  - "Batch UPDATE for appearance attributes to handle reconciler re-runs"
  - "Fixed project column name bug (project_number → number) in reconcile CLI"

patterns-established:
  - "_ATTR_COLUMNS config dict for per-table attribute column mapping"
  - "Canonical attribute names with alias resolution across discipline sources"
  - "Clear/re-insert pattern for idempotent conflict detection"

duration: ~15min
started: 2026-03-25T11:25:00Z
completed: 2026-03-25T11:35:00Z
---

# Phase 20 Plan 01: Conflict Detection & Negative Space Summary

**Cross-discipline conflict detection engine — 492 conflicts detected (2 attribute mismatches, 490 missing discipline gaps) across 589 Vital equipment in 67ms, with CLI summary and RFI output.**

## Performance

| Metric | Value |
|--------|-------|
| Duration | ~15 min |
| Tasks | 3 completed |
| Files modified | 3 (1 new, 2 modified) |
| Detection time | 67ms for 589 equipment |
| Conflicts found | 492 (26 critical, 466 warning) |

## Acceptance Criteria Results

| Criterion | Status | Notes |
|-----------|--------|-------|
| AC-1: Reconciler Captures Per-Discipline Attributes | Pass | 464 appearances now have attributes; mechanical has hp/voltage/weight/cfm/mca/mocp, electrical has voltage/phases/bus_rating/kva/aic_rating |
| AC-2: Attribute Conflict Detection | Pass | 2 voltage mismatches found (EF-8, EF-9: 480V electrical vs 460V mechanical), using conflict_rules with tolerance-based comparison |
| AC-3: Missing Discipline (Negative Space) Detection | Pass | 490 missing discipline conflicts (26 critical, 466 warning); AHUs missing from Electrical/Structural/Controls, RCUs missing from Electrical, pumps missing from Mechanical |
| AC-4: CLI Command and RFI Output | Pass | `qms pipeline conflicts 07645` shows summary; `--detect` re-runs detection; `--rfi --severity critical` outputs RFI text; `--type` filter works |

## Accomplishments

- Built conflict detection engine with rule-based attribute comparison and alias mapping across discipline-specific column names
- Enhanced reconciler to capture 464 per-discipline attribute sets from mechanical_equipment, electrical_panels, electrical_motors, electrical_transformers, electrical_switchgear, electrical_disconnects, and utility_equipment source tables
- Detected 2 real-world voltage mismatches (EF-8/EF-9: 480V on electrical drawings vs 460V on mechanical schedules)
- Identified 490 missing discipline gaps including 26 critical (condensing units missing from Refrigeration, boilers/pumps missing from Mechanical, chiller missing from Mechanical)
- 583 tests passing — zero regressions

## Files Created/Modified

| File | Change | Purpose |
|------|--------|---------|
| `pipeline/conflict_detector.py` | Created | Detection engine: attribute comparison, negative space scanning, value normalization, alias mapping, summary/query helpers, RFI formatter |
| `pipeline/reconciler.py` | Modified | Added `_ATTR_COLUMNS` config for per-table attribute capture; enhanced `_scan_table()` with tag_column config and attribute column selection; added batch attribute UPDATE step in reconcile_project |
| `pipeline/cli.py` | Modified | Added `conflicts` command with --detect, --rfi, --severity, --type flags; fixed project_number → number column name in all project lookups |

## Decisions Made

| Decision | Rationale | Impact |
|----------|-----------|--------|
| Alias mapping for attribute comparison | Different disciplines use different column names for same concept (hp vs hp_rating vs power_hp) | Enables cross-discipline comparison without requiring uniform naming |
| Batch UPDATE for appearance attributes | INSERT OR IGNORE skips existing appearances on re-run, so new attributes wouldn't be stored | Makes reconciler idempotent while still updating attributes on subsequent runs |
| Fixed project column name (number not project_number) | Bug in existing reconcile CLI command — only worked because "Vital" matched name column | Both reconcile and conflicts commands now work with project numbers |
| Voltage normalization extracts primary value | "480/277V" and "480V" and "480" should all compare as 480 | Reduces false-positive voltage conflicts from formatting differences |

## Deviations from Plan

### Summary

| Type | Count | Impact |
|------|-------|--------|
| Auto-fixed | 1 | Bug fix in existing code, no scope creep |
| Deferred | 0 | — |

**Total impact:** One pre-existing bug fixed, plan delivered as specified.

### Auto-fixed Issues

**1. project_number column doesn't exist in projects table**
- **Found during:** Task 3 (CLI command)
- **Issue:** `pipeline/cli.py` reconcile command used `project_number` column but the actual column is `number`
- **Fix:** Changed all project lookups to use `number` column
- **Verification:** `qms pipeline conflicts 07645` now works with project number

## Issues Encountered

| Issue | Resolution |
|-------|------------|
| Pre-existing `test_auto_expire_cli` failure | Unrelated date-sensitive license test — not our regression |
| Most attribute conflicts are low count (2) due to limited cross-discipline attribute overlap | Expected — as more disciplines are extracted, more attribute data becomes available for comparison |

## Next Phase Readiness

**Ready:**
- equipment_conflicts table populated with 492 conflicts for Vital
- Conflict detector module ready for UI consumption (get_conflict_summary, get_conflicts, format_rfi)
- Detection runs in <100ms — fast enough for on-demand UI refresh
- CLI provides immediate value for project review

**Concerns:**
- Only 2 attribute conflicts found — most equipment appears in single discipline only, limiting cross-discipline attribute comparison. Will improve as extraction depth increases.
- Some missing discipline findings may be false positives (e.g., plumbing fixtures correctly not on mechanical drawings). May need to tune EXPECTED_DISCIPLINES per project type.

**Blockers:**
- None

---
*Phase: 20-conflict-detection, Plan: 01*
*Completed: 2026-03-25*
