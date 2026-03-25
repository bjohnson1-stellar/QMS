# Phase 19 — Equipment-Centric Master Schedule

## Discussion Summary

This phase builds the **project data platform** — an equipment-centric registry that consolidates all discipline connections, tracks lifecycle from drawing to turnover, detects cross-discipline conflicts, and validates spec compliance. Piloted on Vital (07645) with all disciplines already extracted.

**This is not just a feature — it's the organizing principle for the entire project data model.** Every future module (procurement, change orders, scheduling, owner handover) will build on this foundation.

## Goals

1. **Unified Equipment Registry** — Every tagged piece of equipment in the project has one master record that consolidates data from all disciplines (Electrical, Mechanical, Plumbing, Refrigeration, Controls, Structural).

2. **Cross-Discipline Conflict Detection** — Auto-detect mismatches when the same equipment tag appears on multiple disciplines with different attributes (HP, voltage, pipe size, weight). Rule-based severity classification. Auto-generate RFI drafts.

3. **Negative Space Detection** — Flag equipment that's MISSING from disciplines where it should appear. An RCU on Refrigeration but absent from Structural = missing scope = change order risk. Expected-discipline matrix per equipment type.

4. **Drawing Revision Impact Chains** — When a revision changes an equipment attribute, trace the relationship graph to identify all downstream equipment that needs re-verification.

5. **Spec Compliance Checking** — Cross-reference extracted equipment attributes against specification requirements. Spec says "65kAIC minimum" but panel shows 35kAIC = spec violation.

6. **Equipment Lifecycle Tracking** — 12-stage lifecycle (Design → Submitted → Approved → Procured → Received → Installed → Connected → Startup → Tested → Punch → Commissioned → Turned Over) with document gates at each stage.

7. **Type/Variant/Instance Model** — One submittal covers a product type. Variants handle configurations (left/right hand, voltage options). Instances track individual tagged units with serial numbers.

8. **Web UI** — Equipment dashboard with completion metrics, filterable equipment list, equipment detail page with tabbed connections/documents/conflicts/history, system grouping view.

## Approach

### Data Model (SQLite — stay on current stack)

**New tables:**

```
equipment_types
  id, name, manufacturer, model_base, masterformat_section,
  expected_disciplines (JSON array),
  default_document_requirements (JSON template per stage)

equipment_variants
  id, type_id, variant_code, variant_description, model_number,
  distinguishing_attributes (JSON)

equipment_instances
  id, project_id, type_id, variant_id (nullable),
  tag (unique per project), serial_number,
  system_id, location_area, location_room,
  discipline_primary,
  hp, voltage, amperage, weight_lbs, pipe_size,  -- typed common attrs
  attributes (JSON overflow),
  lifecycle_stage, stage_updated_at

equipment_systems
  id, project_id, system_tag, system_name, system_category,
  discipline, description, cx_required, cx_priority,
  parent_system_id (nullable for hierarchy)

equipment_appearances
  id, instance_id, discipline, sheet_id, drawing_number,
  attributes_on_sheet (JSON — what this discipline says about this equipment),
  extracted_at

equipment_relationships
  id, project_id, source_tag, target_tag,
  relationship_type (feeds, serves, connects_to, mounted_on, controlled_by),
  discipline, drawing_number, attributes (JSON for connection details)

equipment_documents
  id, link_level ('type'|'variant'|'instance'), link_id,
  document_type, document_ref_type, document_ref_id,
  status (required|submitted|approved|rejected|waived),
  due_date, received_date, reviewed_by

equipment_stage_history
  id, instance_id, from_stage, to_stage,
  changed_at, changed_by, evidence_document_id, notes

equipment_attribute_log
  id, instance_id, attribute_name,
  old_value, new_value, source_discipline, source_drawing,
  changed_at, changed_by, reason
```

**Conflict detection tables:**

```
conflict_rules
  id, attribute_name, comparison_type (exact|numeric_tolerance|range|unit_convert|presence),
  tolerance_value, tolerance_type, severity (critical|warning|info),
  description, active

equipment_conflicts
  id, project_id, equipment_tag, conflict_type (attribute|missing_discipline|spec_violation),
  attribute_name,
  discipline_a, drawing_a, value_a,
  discipline_b, drawing_b, value_b,
  rule_id, severity, status (new|confirmed|assigned|resolved|false_positive),
  assigned_to, rfi_id, resolution_note,
  created_at, resolved_at
```

### Processing Pipeline

1. **Reconciliation engine** (`pipeline/reconciler.py`) — Runs after extraction. Matches equipment tags across disciplines, populates `equipment_appearances`, detects conflicts.

2. **Negative space scanner** — Checks equipment against expected-discipline matrix. Flags missing appearances.

3. **Spec compliance checker** — Cross-references extracted attributes against specification requirements from `references/` module.

4. **Impact tracer** — On revision changes, traverses `equipment_relationships` graph to flag downstream re-verification needs.

### UI Routes

- `/projects/<id>/equipment` — Dashboard + filterable equipment list
- `/projects/<id>/equipment/<tag>` — Equipment detail (tabs: Overview, Connections, Documents, Conflicts, History)
- `/projects/<id>/equipment/systems` — System grouping view
- `/projects/<id>/equipment/conflicts` — Conflict dashboard with severity filtering
- `/projects/<id>/equipment/completeness` — Document completeness by system/stage

### Pilot Scope (Vital 07645)

- Auto-populate from existing extraction data (463 items → ~150-200 equipment master records)
- Seed expected-discipline matrix for: Condensing Unit, AHU, Pump, Boiler, Panel, Transformer, Exhaust Fan
- Run conflict detection across all extracted disciplines
- Run negative space detection
- Build equipment detail UI with cross-discipline view

## Key Decisions Made

| Decision | Rationale |
|----------|-----------|
| Stay on SQLite | 1-5 users, single machine, ~200 equipment per project. PostgreSQL premature. |
| Type/Variant/Instance model | Handles "12 evaporators, 6 left-hand, 6 right-hand" with one submittal at type level |
| Hybrid attributes (typed + JSON) | Common fields (HP, voltage, weight) as columns for fast queries; overflow as JSON |
| Single-table document linking with discriminator | Cleaner than polymorphic FKs, same query performance |
| Rules in database, not code | Severity and tolerance configurable per project without deploys |
| Expected-discipline matrix per equipment type | Enables negative space detection — unique differentiator |
| Batch conflict detection (not real-time) | Run after extraction, cache results. Avoids complex joins on page load. |

## Standards Referenced

- **COBie v2.4** — Component/Type/System/Document structure
- **ASHRAE Standard 202** — Commissioning documentation requirements
- **ASHRAE Guideline 0** — Commissioning process phases
- **ISO 14224** — Equipment taxonomy hierarchy (System → Equipment → Component)
- **CSI MasterFormat 2018** — Equipment type classification by spec section
- **CSI 01 33 00** — Submittal procedures and requirements

## Deferred to Next Version

- Mobile pipeline integration (photo → equipment tag → lifecycle advance)
- Commissioning checklist templates with mobile completion
- System-level commissioning rollup dashboards
- Turnover package auto-assembly
- Cross-project equipment analytics and benchmarking
- Predictive scheduling based on historical stage durations

## Open Questions

1. Should the reconciliation engine run automatically on every extraction, or be manually triggered?
   → Recommendation: Auto-run, with a "re-scan" button for manual trigger
2. How to handle equipment tags that don't match exactly across disciplines (e.g., "RCU-1" on Refrigeration vs "RCU-1A/RCU-1B" on Electrical)?
   → Recommendation: Configurable tag aliasing rules per project
3. Should conflict notifications go to specific users or broadcast?
   → Recommendation: Configurable per project — start with broadcast to all project admins

---
*CONTEXT.md — Created 2026-03-24 from discussion session*
*Research: 3 parallel subagents (equipment standards, conflict detection, commissioning workflows)*
