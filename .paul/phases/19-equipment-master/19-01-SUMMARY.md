---
phase: 19-equipment-master
plan: 01
subsystem: pipeline
tags: [sqlite, equipment-registry, reconciliation, cross-discipline]

requires:
  - phase: pipeline-extraction
    provides: extracted equipment/lines/instruments data across disciplines
provides:
  - Equipment registry schema (10 tables + conflict rules)
  - Reconciliation engine (extraction → registry pipeline)
  - Equipment CRUD module
  - CLI reconcile command
  - Vital (07645) populated with 585 equipment records
affects: [19-02-conflict-detection, 19-03-spec-compliance, 19-04-equipment-ui]

tech-stack:
  added: []
  patterns: [type-variant-instance, expected-discipline-matrix, tag-based-reconciliation]

key-files:
  created:
    - pipeline/equipment_schema.sql
    - pipeline/equipment.py
    - pipeline/reconciler.py
  modified:
    - pipeline/cli.py
    - core/db.py

key-decisions:
  - "Legacy tables renamed (_legacy_equipment_master/appearances) to preserve extraction data"
  - "585 equipment items (not 200) — included instruments and fixtures, not just major equipment"
  - "Hybrid attribute model: typed columns (hp, voltage, amperage, weight, pipe_size) + JSON overflow"

patterns-established:
  - "Tag-based entity resolution across discipline extraction tables"
  - "UPSERT pattern for idempotent reconciliation"
  - "Expected-discipline matrix per equipment type (EXPECTED_DISCIPLINES dict)"

duration: ~30min
started: 2026-03-24T10:50:00Z
completed: 2026-03-24T11:02:00Z
---

# Phase 19 Plan 01: Equipment Schema & Reconciliation Summary

**Equipment registry schema (10 tables), reconciliation engine, and CLI command — Vital populated with 585 equipment instances, 23 systems, 524 relationships across 49 types.**

## Performance

| Metric | Value |
|--------|-------|
| Duration | ~30 min |
| Tasks | 3 completed |
| Files modified | 5 |
| Reconciliation time | 23s (first run), 15s (subsequent) |

## Acceptance Criteria Results

| Criterion | Status | Notes |
|-----------|--------|-------|
| AC-1: Equipment Registry Schema | Pass | 12 tables (10 new + 2 legacy renamed), 6 conflict rules seeded |
| AC-2: Reconciliation Populates Registry | Pass | 585 instances, 642 appearances, 23 systems, 524 relationships |
| AC-3: Type/Variant/Instance Model | Pass | 49 equipment types with expected_disciplines JSON |
| AC-4: CLI Command Works | Pass | `qms pipeline reconcile 07645` — idempotent on second run (0 new types) |

## Accomplishments

- Created 10-table equipment registry schema with Type/Variant/Instance model, lifecycle tracking, and conflict rule engine
- Built reconciliation engine that scans 11 extraction source tables and unifies by tag across disciplines
- Auto-populated Vital with 585 equipment records spanning Refrigeration (310), Mechanical (102), Electrical (60), Utility (60), Plumbing (53)
- Created 23 system groupings (13 Refrigeration Systems, 3 Electrical Services, 7 HVAC Systems)
- Built 524 equipment relationships (panel→equipment feeds, RCU→RAHU serves)
- 560 tests passing — zero regressions

## Files Created/Modified

| File | Change | Purpose |
|------|--------|---------|
| `pipeline/equipment_schema.sql` | Created | 10 tables: types, variants, instances, systems, appearances, relationships, documents, stage_history, attribute_log, conflict_rules |
| `pipeline/equipment.py` | Created | CRUD module: create/update/list instances, appearances, relationships, systems, lifecycle, stats |
| `pipeline/reconciler.py` | Created | Reconciliation engine: tag extraction, type inference, system building, relationship mapping |
| `pipeline/cli.py` | Modified | Added `reconcile` command |
| `core/db.py` | Modified | Added equipment schema migration with legacy table rename |

## Decisions Made

| Decision | Rationale | Impact |
|----------|-----------|--------|
| Rename legacy tables instead of drop | `equipment_master` and `equipment_appearances` had 1273/2044 rows from prior SIS extraction | Data preserved as `_legacy_*`, new schema takes canonical names |
| 585 items instead of ~200 estimate | Included instruments (124 RAHU sensors) and all fixture types, not just major equipment | More comprehensive registry; can filter by type in UI |
| Idempotent migration with Python rename | `ALTER TABLE RENAME` isn't idempotent in SQL; Python checks existence first | Safe to run migrate_all() repeatedly |
| Tag prefix inference for type classification | 40+ tag patterns (RCU→Condensing Unit, AHU→Air Handling Unit, etc.) | Works well for Stellar's systematic numbering; may need tuning for other naming conventions |

## Deviations from Plan

### Summary

| Type | Count | Impact |
|------|-------|--------|
| Auto-fixed | 2 | Essential fixes, no scope creep |
| Deferred | 0 | — |

**Total impact:** Minor fixes during execution, plan delivered as specified.

### Auto-fixed Issues

**1. sqlite3.Row doesn't support .get()**
- **Found during:** Task 2 (reconciler)
- **Issue:** `sqlite3.Row` objects don't have `.get()` method; code used `r.get("tag")` patterns
- **Fix:** Wrapped all Row objects with `dict(row)` before accessing
- **Verification:** Reconciliation runs successfully

**2. SQL string concatenation for optional columns**
- **Found during:** Task 2 (_scan_table function)
- **Issue:** f-string conditional expressions produced malformed SQL
- **Fix:** Pre-computed column expressions before building SQL string
- **Verification:** All 11 extraction tables scanned successfully

## Issues Encountered

| Issue | Resolution |
|-------|------------|
| Legacy `equipment_master` table had 1273 rows | Renamed to `_legacy_equipment_master` — data preserved |
| Pre-existing test failure (`test_auto_expire_cli`) | Unrelated to our changes — date-sensitive license test |

## Next Phase Readiness

**Ready:**
- Equipment registry fully populated for Vital (585 instances)
- Type/Variant/Instance model in place
- Expected-discipline matrix seeded (37 equipment categories)
- Conflict rules seeded (6 rules: hp, voltage, amperage, weight, pipe_size, refrigerant)
- CRUD functions ready for UI consumption (Plan 19-04)

**Concerns:**
- Cross-discipline appearances limited for some equipment (e.g., RCU-1 shows only Refrigeration appearance, not Electrical) — because electrical extraction stored data in generic `equipment` table, not `electrical_*` discipline tables. Will improve as extraction depth increases.
- Instrument tags (RAHU-1-PT3, RAHU-1-TT4) inflate instance count — may want to filter these in UI or classify differently.

**Blockers:**
- None

---
*Phase: 19-equipment-master, Plan: 01*
*Completed: 2026-03-24*
