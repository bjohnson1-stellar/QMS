# QMS — Quality Management System

## What This Is

Modular Python platform for construction quality management. Two active milestones: (1) Procore quality intelligence — aggregating siloed quality data into unified analytics with mobile capture. (2) License compliance platform — Harbor-like multi-state license management with renewal workflows, CE tracking, regulatory intelligence, and document management.

## Core Value

Centralized quality and compliance management for MEP contractors — replacing manual spreadsheets, siloed Procore data, and expensive SaaS tools (Harbor ~$540/yr) with an integrated, self-hosted platform.

## Current State

| Attribute | Value |
|-----------|-------|
| Version | 0.2.0-alpha |
| Status | In Progress |
| Last Updated | 2026-03-05 (v0.2 milestone created) |

**Production URL:** http://L004470-CAD:5000

## Milestones

### v0.2 License Compliance Platform (Current)
Expand the licenses module from basic CRUD + CE tracking into a comprehensive Harbor-like compliance management system. 8 phases covering foundation hardening through integrations.

**Pre-PAUL work already completed:**
- Phase 1 (pre-tracked): Base CRUD, SVG map, CSV import, renewal timeline
- Phase 2 (pre-tracked): Drill-down navigation, scope mapping, CE tracking, board data for 51 states
- Phase 3 (pre-tracked): CE seed data, period-aware summary, certificate upload, CSV exports, compliance dashboard

### v0.1 Quality Intelligence Platform (80% complete)
Bidirectional Procore observation integration. Two tracks: personal mobile capture pipeline and team-wide Procore observation import.

## Requirements

### Validated (Shipped)
- [x] Quality issues foundation (8 tables, audit trail, normalization) — v0.1 Phase 1
- [x] Procore CSV bulk import with dedup, vector indexing — v0.1 Phase 2
- [x] Quality intelligence dashboard with Chart.js analytics, semantic search — v0.1 Phase 3
- [x] Mobile photo capture pipeline with Claude vision — v0.1 Phase 4 (partial)
- [x] License CRUD with US state SVG map, CSV import — Licenses Phase 1
- [x] Drill-down navigation, scope mapping, CE tracking — Licenses Phase 2
- [x] CE seed data, compliance dashboard, certificate upload, CSV exports — Licenses Phase 3
- [x] Foundation hardening (N+1 fixes, audit trail, pagination, validation, rate limiting, CSRF) — v0.2 Phase 6

### Active (v0.2 — In Progress)
- [ ] Renewal workflow with event tracking and fee history
- [ ] Notification system (expiration warnings, CE deadlines, Teams webhook)
- [ ] Document management (certificates, applications, correspondence)
- [ ] Entity registration tracking (SoS, DBE, minority certs)
- [ ] Regulatory intelligence database (state requirements, fee schedules)
- [ ] Advanced CE management (providers, courses, cross-state mapping)
- [ ] Integrations (primary source verification, calendar, cross-module)

### Paused (v0.1 remaining)
- [ ] Voice transcription + review UI (Phase 4 Plan 02)
- [ ] Procore push (Phase 5)

## Target Users

**Primary:** Brandon Johnson (admin, field quality oversight)
**Secondary:** SIS QMS users with license management responsibilities

## Context

**Business Context:**
SIS manages professional and business licenses across multiple states for MEP contracting. Currently tracked in spreadsheets. Harbor Compliance offers similar functionality at ~$540/yr but is a general-purpose SaaS — QMS can provide tighter integration with welding certs, workforce data, and project assignments.

**Technical Context:**
- Existing licenses module: `licenses/` package with schema, db, migrations
- 10 schema tables (state_licenses, ce_requirements, ce_credits, boards, scopes, etc.)
- Flask blueprint at `/licenses/` with full CRUD + compliance dashboard
- Certificate file storage at `data/certificates/`
- Welding notification pattern available for cloning (notification_rules + notifications tables)
- WeasyPrint PDF pipeline available from quality manual module

## Key Decisions

| Decision | Rationale | Date | Status |
|----------|-----------|------|--------|
| Harbor feature parity as target | Comprehensive compliance management, not just license tracking | 2026-03-05 | Active |
| Foundation hardening first | Security + perf fixes before new features (architecture audit findings) | 2026-03-05 | Shipped |
| API-layer validation, not DB-layer | Clean boundary: API validates input, DB trusts internal calls | 2026-03-05 | Active |
| In-memory rate limiting (no Redis) | LAN deployment, 1-5 users, restarts clear state acceptably | 2026-03-05 | Active |
| Pagination dict response pattern | {items, total, page, per_page, pages} for all future list endpoints | 2026-03-05 | Active |
| Clone welding notification pattern | Proven pattern reduces risk | 2026-03-05 | Active |
| Self-hosted over SaaS | Integration with existing QMS modules, no recurring cost | 2026-03-05 | Active |
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
*Last updated: 2026-03-05 — Phase 6 Foundation Hardening complete*
