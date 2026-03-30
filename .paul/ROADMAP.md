# Roadmap: QMS — Quality Management System

## Overview

Modular quality management platform for construction. Three completed milestones: v0.1 (Procore quality intelligence), v0.2 (Harbor-like license compliance), v0.3 (Quality Manual Platform). Current: v0.4 Equipment-Centric Platform.

---

## Current Milestone

**v0.4 Equipment-Centric Platform**
Status: In Progress
Phases: 9 (19-27)
Started: 2026-03-24

Equipment-centric project data platform — unified registry consolidating all discipline connections, cross-discipline conflict detection, negative space analysis, spec compliance checking, and lifecycle tracking. Piloted on Vital (07645).

| Phase | Name | Plans | Status | Completed |
|-------|------|-------|--------|-----------|
| 19 | Equipment Master Schedule — Schema & Reconciliation | 1 | Complete | 2026-03-24 |
| 20 | Conflict Detection & Negative Space | 1 | Complete | 2026-03-25 |
| 21 | Spec Compliance & Impact Chains | 1 | Complete | 2026-03-25 |
| 22 | Equipment Web UI | 1 | Complete | 2026-03-26 |
| 23 | Equipment Hierarchy | 1 | Complete | 2026-03-26 |
| 24 | System Model & Consolidation | 1 | Complete | 2026-03-26 |
| 25 | Schedule-First Extraction | 3 | Complete | 2026-03-26 |
| 26 | Schedule Reconciliation | 1 | Complete | 2026-03-27 |
| 27 | Floor Plan Extraction | 3 | In Progress | — |

### Phase 19: Equipment Master Schedule — Schema & Reconciliation

Focus: Create equipment registry schema (10 tables), reconciliation engine to auto-populate from extraction data, Type/Variant/Instance model, system groupings, relationship graph. Pilot on Vital (07645).

### Phase 20: Conflict Detection & Negative Space

Focus: Rule-based cross-discipline conflict detection, missing-discipline scanner (negative space), severity classification, auto-RFI generation from conflicts.

### Phase 21: Spec Compliance & Impact Chains

Focus: Cross-reference extracted attributes against spec requirements, drawing revision impact tracing through equipment relationship graph.

### Phase 22: Equipment Web UI

Focus: Equipment dashboard, filterable equipment list, equipment detail page (tabs: Overview, Connections, Documents, Conflicts, History), system view, conflict dashboard.

### Phase 23: Equipment Hierarchy

Focus: Tag parser for parent-child relationships, deduplication of 124 reversed instrument tags, sub-component type reclassification (CV→Control Valve, etc.), grouped dashboard view. Plan 23-02 (future): R0001 P&ID legend extraction for authoritative component classification.

### Phase 24: System Model & Consolidation

Focus: System type taxonomy (15 types), equipment_system_members junction table, consolidate refrigeration circuits into real systems, create plumbing/HVAC/compressed air systems, system dashboard view.

### Phase 25: Schedule-First Extraction

Focus: Extraction order engine (schedules→legends→plans), Docling structural + Sonnet vision, Opus shadow QA. 452 equipment entries across 19 MEP schedule sheets for Vital. Session-stepped harness pattern.

### Phase 26: Schedule Reconciliation

Focus: Integrate 452 schedule entries as 12th reconciler data source, enrich existing instances with manufacturer/model/HP/voltage/weight, re-run conflict detection. 661 instances, 296 enriched, conflicts 496→473.

### Phase 27: Floor Plan Extraction

Focus: Context-aware vision extraction of floor plans, P&IDs, and details. Anti-hallucination prompts inject schedule-built equipment checklist. Text-layer preprocessor (PyMuPDF) for tag visibility. Plan 27-01 (infrastructure), 27-02/02a (Refrigeration calibration + text layer), 27-03 (MEP scale), 27-04 (remaining disciplines).

---

## Future Phases (v0.4 continued)

| Phase | Name | Status | Notes |
|-------|------|--------|-------|
| 28 | Schedule Notes & Spec Text Extraction | Planned | Extract spec notes/requirements from schedule drawings into structured storage. PyMuPDF text layer captures notes like "FLUID: WATER WITH 30% PROPYLENE GLYCOL", "PROVIDE VFD STARTER WITH HARMONIC FILTER" — useful for spec compliance but currently filtered out of tag pipeline. New `schedule_notes` table keyed to sheet_id with equipment tag references. Feeds Phase 21 spec compliance engine. |
| 29 | Floor Plan Reconciliation | Planned | Reconcile 1,074+ floor plan extraction entries into equipment_instances. Deduplicate cross-sheet appearances, merge with schedule data, re-run conflict detection. |

---

## Prior Milestone

**v0.3 Quality Manual Platform**
Status: Complete
Phases: 5 of 5 complete
Completed: 2026-03-11

Unified tabbed UI for the complete quality manual (M1–M4), with search, AI-powered SOP intake for M4, draft/approval workflow, and infrastructure for future authoring and scope filtering.

| Phase | Name | Plans | Status | Completed |
|-------|------|-------|--------|-----------|
| 14 | Schema & API Foundation | 2 | Complete | 2026-03-10 |
| 15 | Tabbed UI Shell & M1/M2 | 1 | Complete | 2026-03-10 |
| 16 | M3 Programs UI | 1 | Complete | 2026-03-10 |
| 17 | M4 SOP Catalog UI | 1 | Complete | 2026-03-10 |
| 18 | M4 SOP Intake & Classification | 2 | Complete | 2026-03-11 |

### Phase 14: Schema & API Foundation

Focus: Extend DB schema for M3 programs + M4 SOPs (categories, scopes, program-SOP linkage). Build API endpoints for all 4 modules. Ensure schema supports future CRUD and draft/approval workflow.

### Phase 15: Tabbed UI Shell & M1/M2

Focus: Build the horizontal tab bar, master search across all modules, and M1/M2 tab views (refactor from existing viewer into separated tabs).

### Phase 16: M3 Programs UI

Focus: Program cards for 5 discipline programs, discipline detail view, code references, linked SOPs list. Empty-state handling for unpopulated programs.

### Phase 17: M4 SOP Catalog UI

Focus: Category-based SOP browser (15 categories), search/filter within M4, scope tag infrastructure (visible but data-pending). Empty-state handling.

### Phase 18: M4 SOP Intake & Classification

Focus: PDF upload, Claude-powered analysis (category, scope, program, codes), recommendation review UI, draft insertion. Approval workflow (draft → approved → published).

---

## Completed Milestones

<details>
<summary>v0.2 License Compliance Platform - 2026-03-09 (8 phases, 18 plans)</summary>

| Phase | Name | Plans | Completed |
|-------|------|-------|-----------|
| 6 | Foundation Hardening | 3 | 2026-03-05 |
| 7 | Renewal Workflow & Events | 2 | 2026-03-06 |
| 8 | Notifications & Task Management | 2 | 2026-03-06 |
| 9 | Document Management & Activity Log | 2 | 2026-03-06 |
| 10 | Entity Registration Tracking | 2 | 2026-03-06 |
| 11 | Regulatory Intelligence Database | 2 | 2026-03-06 |
| 12 | Advanced CE & Multi-Credential | 2 | 2026-03-06 |
| 13 | Integrations & Automation | 3 | 2026-03-09 |

**Archive:** `.paul/milestones/v0.2.0-ROADMAP.md`

</details>

<details>
<summary>v0.1 Quality Intelligence Platform - Partial (4 of 5 phases)</summary>

| Phase | Name | Plans | Completed |
|-------|------|-------|-----------|
| 1 | Quality Issues Foundation | 1 | 2026-02-25 |
| 2 | Procore Bulk Import | 3 | 2026-02-26 |
| 3 | Quality Intelligence Dashboard | 2 | 2026-02-27 |
| 4 | Mobile Capture Pipeline | 2 | 2026-03-05 |
| 5 | Procore Push | TBD | Not started |

</details>

---
*Roadmap created: 2026-02-25*
*Last updated: 2026-03-27 — Phase 27 (Floor Plan Extraction) in progress, Plan 27-01 complete*
