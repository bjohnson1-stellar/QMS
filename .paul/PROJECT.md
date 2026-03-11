# QMS — Quality Management System

## What This Is

Modular Python platform for construction quality management. Two milestones shipped: (1) Procore quality intelligence — aggregating siloed quality data into unified analytics with mobile capture. (2) License compliance platform — Harbor-like multi-state license management with renewal workflows, CE tracking, regulatory intelligence, and document management.

## Core Value

Centralized quality and compliance management for MEP contractors — replacing manual spreadsheets, siloed Procore data, and expensive SaaS tools (Harbor ~$540/yr) with an integrated, self-hosted platform.

## Current State

| Attribute | Value |
|-----------|-------|
| Version | 0.3.0 |
| Status | Complete |
| Last Updated | 2026-03-11 (v0.3 milestone complete) |

**Production URL:** http://L004470-CAD:5000

## Milestones

### v0.3 Quality Manual Platform (Complete - 2026-03-11)
Unified tabbed UI for M1-M4 quality manual modules with cross-module search, AI-powered SOP intake and classification, draft/approval workflow, and SOP lifecycle management. 5 phases (7 plans) over 2 days.

### v0.2 License Compliance Platform (Complete - 2026-03-09)
Expanded licenses module from basic CRUD into comprehensive Harbor-like compliance management. 8 phases (18 plans) over 5 days: foundation hardening, renewal workflows, notifications, document management, entity registration, regulatory intelligence, CE catalog, and integrations/automation.

### v0.1 Quality Intelligence Platform (80% complete)
Procore quality intelligence with mobile capture. 4 of 5 phases complete. Phase 5 (Procore push) not started.

## Requirements

### Validated (Shipped)
- [x] Quality issues foundation (8 tables, audit trail, normalization) — v0.1 Phase 1
- [x] Procore CSV bulk import with dedup, vector indexing — v0.1 Phase 2
- [x] Quality intelligence dashboard with Chart.js analytics, semantic search — v0.1 Phase 3
- [x] Mobile capture pipeline — photo analysis (Claude vision) + voice transcription (Whisper) + review UI — v0.1 Phase 4
- [x] License CRUD with US state SVG map, CSV import — Licenses Phase 1
- [x] Drill-down navigation, scope mapping, CE tracking — Licenses Phase 2
- [x] CE seed data, compliance dashboard, certificate upload, CSV exports — Licenses Phase 3
- [x] Foundation hardening (N+1 fixes, audit trail, pagination, validation, rate limiting, CSRF) — v0.2 Phase 6
- [x] Renewal workflow with event tracking, fee history, auto-expire CLI, timeline UI — v0.2 Phase 7
- [x] Notification system (rule-driven alerts, CLI, API, dashboard UI, Teams webhook) — v0.2 Phase 8
- [x] Document management with notes, file storage, and unified activity feed — v0.2 Phase 9
- [x] Entity registration tracking (business entities, SoS filings, DBE/MBE/WBE certs, hierarchy, license linking) — v0.2 Phase 10
- [x] Regulatory intelligence database (state requirements, fee schedules, compliance scoring, gap analysis UI) — v0.2 Phase 11
- [x] Advanced CE management (provider catalog, course browser, cross-state mapping, employee credential portfolios) — v0.2 Phase 12
- [x] Integrations & automation (dashboard widgets, iCal feed, cross-module credentials, bulk ops, verification tracking, external API) — v0.2 Phase 13
- [x] M3/M4 schema foundation (7 tables, CRUD module, 15 seeded categories, SOP lifecycle) — v0.3 Phase 14
- [x] Quality manual API endpoints (12 endpoints: programs, categories, SOPs, lifecycle, search) — v0.3 Phase 14

- [x] Tabbed UI shell with M1/M2 separated views, cross-module search, URL hash routing — v0.3 Phase 15
- [x] M3 Programs UI — 5 discipline programs seeded, cards grid, detail view with code refs and linked categories — v0.3 Phase 16
- [x] M4 SOP Catalog UI — 15-category card grid, SOP list/detail, status badges, M4 search — v0.3 Phase 17
- [x] M4 SOP Intake backend — PDF upload, Claude classification, intake management, approve-to-SOP — v0.3 Phase 18
- [x] M4 SOP Intake UI — upload modal, intake queue, classification review, approve/reject, lifecycle buttons — v0.3 Phase 18

### Active
(No active requirements)

### Paused (v0.1 remaining)
- [ ] Procore push (Phase 5)

## Target Users

**Primary:** Brandon Johnson (admin, field quality oversight)
**Secondary:** SIS QMS users with license management responsibilities

## Context

**Business Context:**
SIS manages professional and business licenses across multiple states for MEP contracting. Currently tracked in spreadsheets. Harbor Compliance offers similar functionality at ~$540/yr but is a general-purpose SaaS — QMS can provide tighter integration with welding certs, workforce data, and project assignments.

**Technical Context:**
- Existing licenses module: `licenses/` package with schema, db, migrations
- ~24 schema tables (state_licenses, license_events, ce_requirements, ce_credits, ce_providers, ce_courses, boards, scopes, business_entities, entity_registrations, state_requirements, license_documents, license_notes, license_notifications, license_verifications, api_tokens, etc.)
- Flask blueprint at `/licenses/` with full CRUD + compliance dashboard
- Certificate file storage at `data/certificates/`
- Welding notification pattern available for cloning (notification_rules + notifications tables)
- WeasyPrint PDF pipeline available from quality manual module

## Key Decisions

| Decision | Rationale | Date | Status |
|----------|-----------|------|--------|
| Harbor feature parity as target | Comprehensive compliance management, not just license tracking | 2026-03-05 | Shipped |
| Foundation hardening first | Security + perf fixes before new features (architecture audit findings) | 2026-03-05 | Shipped |
| API-layer validation, not DB-layer | Clean boundary: API validates input, DB trusts internal calls | 2026-03-05 | Active |
| In-memory rate limiting (no Redis) | LAN deployment, 1-5 users, restarts clear state acceptably | 2026-03-05 | Active |
| Pagination dict response pattern | {items, total, page, per_page, pages} for all future list endpoints | 2026-03-05 | Active |
| Events in dedicated table, not status field | Flexible event history, avoids SQLite schema rebuild | 2026-03-06 | Active |
| Single-action renewal (not multi-step) | Simple now; approval workflow deferred to Phase 8 | 2026-03-06 | Active |
| Clone welding notification pattern | Proven pattern reduces risk | 2026-03-05 | Active |
| Self-hosted over SaaS | Integration with existing QMS modules, no recurring cost | 2026-03-05 | Active |
| Separate verification table (not events) | Avoids SQLite table rebuild for CHECK constraint | 2026-03-09 | Active |
| SHA-256 hashed API tokens | Plaintext shown once, never stored | 2026-03-09 | Active |
| Read-only external API v1 | Safety first for LAN deployment | 2026-03-09 | Active |
| Two-track approach (v0.1) | Personal mobile pipeline vs team-wide import | 2026-02-25 | Active |
| OneDrive as mobile bridge (v0.1) | No API integration needed | 2026-02-25 | Active |

## Tech Stack

| Layer | Technology | Notes |
|-------|------------|-------|
| Framework | Flask (existing QMS) | |
| Database | SQLite (quality.db) | |
| Charts | Chart.js via CDN | |
| PDF Export | WeasyPrint | |
| AI Processing | Claude API | Photo analysis, future voice transcription |
| File Storage | Local filesystem (`data/`) | Certificates, documents |

## Links

| Resource | URL |
|----------|-----|
| Repository | https://github.com/bjohnson1-stellar/QMS.git |
| Production | http://L004470-CAD:5000 |
| Harbor Reference | https://www.harborcompliance.com |
| Architecture | .planning/architecture.md |

---
*PROJECT.md — Updated when requirements or context change*
*Last updated: 2026-03-11 after v0.3 Phase 18 (M4 SOP Intake & Classification) complete — v0.3 milestone complete*
