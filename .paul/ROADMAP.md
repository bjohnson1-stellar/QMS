# Roadmap: QMS — Quality Management System

## Overview

Modular quality management platform for construction. Two completed milestones: v0.1 (Procore quality intelligence) and v0.2 (Harbor-like license compliance platform). Current: v0.3 Quality Manual Platform.

---

## Current Milestone

**v0.3 Quality Manual Platform**
Status: In Progress
Phases: 3 of 5 complete

Unified tabbed UI for the complete quality manual (M1–M4), with search, AI-powered SOP intake for M4, draft/approval workflow, and infrastructure for future authoring and scope filtering.

| Phase | Name | Plans | Status | Completed |
|-------|------|-------|--------|-----------|
| 14 | Schema & API Foundation | 2 | Complete | 2026-03-10 |
| 15 | Tabbed UI Shell & M1/M2 | 1 | Complete | 2026-03-10 |
| 16 | M3 Programs UI | 1 | Complete | 2026-03-10 |
| 17 | M4 SOP Catalog UI | TBD | Not started | - |
| 18 | M4 SOP Intake & Classification | TBD | Not started | - |

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
*Last updated: 2026-03-10 — Phase 16 (M3 Programs UI) complete*
