---
phase: 21-spec-compliance-impact
plan: 01
subsystem: pipeline
tags: [sqlite, spec-compliance, impact-analysis, graph-traversal, bfs]

requires:
  - phase: 20-conflict-detection
    provides: conflict detection engine, equipment_conflicts table with spec_violation type, value normalization helpers
  - phase: 19-equipment-master
    provides: equipment registry (585 instances, 524 relationships, 49 types), reconciler
provides:
  - Spec compliance checking engine (equipment_spec_requirements → spec_violation conflicts)
  - Impact chain analyzer (BFS graph traversal, drawing impact, violation propagation)
  - CLI commands: spec-check and impact
affects: [22-equipment-ui]

tech-stack:
  added: []
  patterns: [spec-requirements-table, bfs-graph-traversal, advisory-propagation]

key-files:
  created:
    - pipeline/spec_checker.py
    - pipeline/impact_analyzer.py
  modified:
    - pipeline/equipment_schema.sql
    - pipeline/cli.py
    - core/db.py

key-decisions:
  - "Seed spec requirements via SQL INSERT OR IGNORE in schema file (consistent with conflict_rules pattern)"
  - "Extended _parse_numeric locally for AIC/MLO/MCB suffixes (avoid modifying stable conflict_detector.py)"
  - "Advisory-only violation propagation — no new conflict records for inherited impacts"

patterns-established:
  - "equipment_spec_requirements table for configurable compliance rules per equipment type"
  - "BFS adjacency-list traversal for equipment relationship graph"
  - "Drawing-based blast radius analysis via appearance→impact chain"

duration: ~20min
started: 2026-03-25T11:49:00Z
completed: 2026-03-25T11:55:00Z
---

# Phase 21 Plan 01: Spec Compliance & Impact Chains Summary

**Spec compliance engine (9 requirements, 4 violations detected for Vital) and equipment impact chain analyzer (BFS graph traversal across 524 relationships) with CLI commands for compliance checking, downstream/upstream tracing, and drawing revision impact assessment.**

## Performance

| Metric | Value |
|--------|-------|
| Duration | ~20 min |
| Tasks | 2 completed |
| Files modified | 5 (2 new, 3 modified) |
| Spec check time | 50ms for 61 equipment types |
| Impact traversal | <10ms per tag |

## Acceptance Criteria Results

| Criterion | Status | Notes |
|-----------|--------|-------|
| AC-1: Spec Requirements Table and Seeding | Pass | equipment_spec_requirements table with 9 seeded rules (8 original + 1 AIC min); columns match spec exactly |
| AC-2: Spec Compliance Checker Detects Violations | Pass | 4 AIC rating violations detected; discipline_a='Spec', value_a=expected, discipline_b=source discipline, value_b=actual; idempotent (clears 4, re-detects 4) |
| AC-3: Impact Chain Forward/Reverse Traversal | Pass | 1HMCC041→8 pumps (feeds), RCU-1→35 RAHUs (serves); reverse P-C1→1HMCC041; visited set prevents cycles |
| AC-4: Drawing Revision Impact Analysis | Pass | E6203→14 direct equipment with blast radius summary; deduplicates indirect across chains |
| AC-5: CLI Commands Work | Pass | `spec-check 07645`, `impact 07645 1HMSB`, `impact 07645 --drawing E6203`, `impact 07645 --violations`, `impact 07645 P-C1 --reverse` all work |

## Accomplishments

- Built spec compliance engine with 6 check types (exact, one_of, min, max, range, regex), voltage normalization, and extended numeric parsing for AIC/MLO/MCB suffixes
- Created equipment impact analyzer with BFS graph traversal through 524 relationships (510 serves, 14 feeds), forward/reverse/drawing/violation modes
- Detected 4 real spec violations (panelboards 1LG041, 1LG051, 2LG024, 2LG041: AIC rating 10,000 below 14,000 minimum)
- RCU-1 impact chain demonstrates full blast radius: 1 condensing unit → 35 downstream RAHU units and instruments
- Fixed pre-existing migration bug: legacy table rename now handles already-renamed tables gracefully

## Files Created/Modified

| File | Change | Purpose |
|------|--------|---------|
| `pipeline/spec_checker.py` | Created | Compliance engine: check_compliance(), _check_value() with 6 check types, _find_attr_in_appearances(), get_compliance_summary(), get_violations() |
| `pipeline/impact_analyzer.py` | Created | Graph traversal: _build_adjacency(), get_forward_impact(), get_reverse_trace(), get_drawing_impact(), get_violation_impact(), format_impact_tree() |
| `pipeline/equipment_schema.sql` | Modified | Added equipment_spec_requirements table + indexes + 8 seeded requirements (voltage, phases, refrigerant, AIC, primary voltage) |
| `pipeline/cli.py` | Modified | Added spec-check command (compliance + summary) and impact command (tag/drawing/violations/reverse modes) |
| `core/db.py` | Modified | Made legacy table rename per-rename try/except to prevent already-renamed tables from blocking schema application |

## Decisions Made

| Decision | Rationale | Impact |
|----------|-----------|--------|
| SQL seed in schema file (not Python migration) | Consistent with conflict_rules seeding pattern; INSERT OR IGNORE is idempotent | Simple, runs with executescript() |
| Local _parse_numeric wrapper for AIC suffixes | Plan boundary: don't modify conflict_detector.py | Extends base parser without touching stable code |
| Advisory-only violation propagation | Plan boundary: no new conflict records for inherited impacts | get_violation_impact() returns analysis, doesn't write to DB |
| type_name matching (not just type_id) | Equipment types may not have stable IDs across re-reconciliation | More resilient requirement matching |

## Deviations from Plan

### Summary

| Type | Count | Impact |
|------|-------|--------|
| Auto-fixed | 1 | Essential fix, no scope creep |
| Minor adjustments | 2 | Implementation details, same outcome |
| Deferred | 0 | — |

**Total impact:** Minor adjustments during execution, plan delivered as specified.

### Auto-fixed Issues

**1. Legacy table rename blocks schema application**
- **Found during:** Task 1 (migration)
- **Issue:** `ALTER TABLE equipment_master RENAME TO _legacy_equipment_master` fails when `_legacy_equipment_master` already exists from prior migration
- **Fix:** Wrapped each rename in individual try/except in core/db.py
- **Verification:** `migrate_all()` runs successfully, equipment_spec_requirements table created

### Minor Adjustments

**1. Seeding via SQL instead of Python migration**
- Plan specified Python migration function; used SQL INSERT OR IGNORE in schema file instead
- Same outcome: idempotent seeding, consistent with existing conflict_rules pattern

**2. Extended numeric parser added locally**
- AIC rating values like "10,000 AIC" not parsed by base `_parse_numeric`
- Added local wrapper in spec_checker.py that strips AIC/MLO/MCB/AT/AF suffixes before delegating to base parser

## Issues Encountered

| Issue | Resolution |
|-------|------------|
| Pre-existing `test_auto_expire_cli` failure | Unrelated date-sensitive license test — not our regression |
| Plan referenced `--drawing E-401` but no such drawing in Vital | Verified with E6203 (14 equipment); same functionality |
| Condensing units have no refrigerant attribute in appearances | Correctly handled: absent attributes are not flagged as violations |

## Next Phase Readiness

**Ready:**
- Spec compliance checker generates spec_violation conflicts ready for UI display
- Impact analyzer functions ready for equipment detail page integration
- 9 configurable spec requirements in database (add more via SQL or future UI)
- CLI provides immediate operational value for project review

**Concerns:**
- Refrigerant attribute not captured in equipment_appearances for condensing units — compliance checking for refrigerant will require extraction improvements
- Impact chain instrument count inflates downstream counts (RAHU sensors counted as separate equipment) — may want UI filtering by equipment category

**Blockers:**
- None

---
*Phase: 21-spec-compliance-impact, Plan: 01*
*Completed: 2026-03-25*
