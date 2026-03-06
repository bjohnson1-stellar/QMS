# Roadmap: QMS — Quality Management System

## Overview

Modular quality management platform for construction. Milestone v0.1 focused on Procore quality intelligence (data aggregation, analytics, mobile capture). Milestone v0.2 expands the licenses module into a Harbor-like multi-state compliance management system with renewal workflows, notifications, document management, regulatory intelligence, and integrations.

---

## Current Milestone

**v0.2 License Compliance Platform** (v0.2.0)
Status: In progress
Phases: 3 of 8 complete

### Phases

| Phase | Name | Plans | Status | Completed |
|-------|------|-------|--------|-----------|
| 6 | Foundation Hardening | 3 | Complete | 2026-03-05 |
| 7 | Renewal Workflow & Events | 2 | Complete | 2026-03-06 |
| 8 | Notifications & Task Management | 2 | Complete | 2026-03-06 |
| 9 | Document Management & Activity Log | TBD | Not started | - |
| 10 | Entity Registration Tracking | TBD | Not started | - |
| 11 | Regulatory Intelligence Database | TBD | Not started | - |
| 12 | Advanced CE & Multi-Credential | TBD | Not started | - |
| 13 | Integrations & Automation | TBD | Not started | - |

### Phase Details

#### Phase 6: Foundation Hardening

**Goal:** Fix architectural limitations before building new features — security, performance, audit trail, pagination.
**Depends on:** Nothing (first phase, fixes existing issues)
**Research:** Unlikely (internal audit already done)

**Scope:**
- Fix N+1 query patterns in license list/detail pages (batch loading)
- Add `audit_log` entries for all license CRUD operations (use existing core audit_log table)
- Server-side pagination for licenses list (currently loads all)
- Input validation and sanitization on all license API endpoints
- Rate limiting on public-facing routes
- CSRF protection audit

#### Phase 7: Renewal Workflow & Events

**Goal:** Transform static expiration dates into an active renewal workflow with event tracking, fee history, and auto-expire logic.
**Depends on:** Phase 6 (audit trail must exist for event logging)

**Scope:**
- `license_events` table (event_type, event_date, notes, fee_amount, created_by)
- Event types: issued, renewed, amended, suspended, revoked, expired, reinstated
- Fee tracking per event (application fees, renewal fees)
- Auto-expire job: mark licenses expired when past expiration_date
- Renewal initiation workflow (status: renewal_pending → renewed)
- Event timeline on license detail page

#### Phase 8: Notifications & Task Management

**Goal:** Proactive alerts for expiring licenses, CE deadlines, and renewal tasks. Clone the welding notification pattern.
**Depends on:** Phase 7 (renewal workflow creates events to notify about)

**Scope:**
- `license_notification_rules` table (clone welding pattern)
- `license_notifications` table (generated alerts)
- CLI generator: `qms licenses check-notifications`
- Notification types: expiration_warning (30/60/90 day), ce_deadline, renewal_reminder
- Teams webhook integration for critical alerts
- Task queue UI: pending renewal actions, CE credits needed

#### Phase 9: Document Management & Activity Log

**Goal:** Attach documents to licenses (certificates, applications, correspondence) and maintain timestamped activity notes.
**Depends on:** Phase 6 (audit trail), Phase 7 (events)

**Scope:**
- `license_documents` table (type, filename, uploaded_by, uploaded_at)
- Document types: certificate, application, correspondence, receipt, bond, insurance
- Upload/download/delete with file storage in `data/license-documents/`
- `license_notes` table (timestamped text notes per license)
- Activity feed combining events + notes + document uploads on detail page
- Bulk document upload support

#### Phase 10: Entity Registration Tracking

**Goal:** Track business entity registrations (Secretary of State, DBE, MBE/WBE) alongside professional licenses.
**Depends on:** Phase 6 (foundation)

**Scope:**
- `business_entities` table (parent company, subsidiaries, DBAs)
- `entity_registrations` table (SoS filings, DBE certs, minority certs)
- Entity hierarchy (parent → subsidiary relationships)
- Registration renewal tracking (annual reports, filing deadlines)
- Link licenses to entities (many-to-one)
- Entity detail page with registration status

#### Phase 11: Regulatory Intelligence Database

**Goal:** Structured database of state licensing requirements, fee schedules, and compliance rules — the "Harbor Compliance Core" equivalent.
**Depends on:** Phase 6 (foundation)

**Scope:**
- `state_requirements` table (requirement_type, description, fee, frequency, authority)
- Requirement types: initial_application, renewal, ce_requirement, bond, insurance, exam
- Fee schedules per state/license type
- Compliance score calculation (% of requirements met per license)
- PDF compliance report generation (WeasyPrint, like quality manual export)
- Requirements gap analysis: what's needed vs what's on file

#### Phase 12: Advanced CE & Multi-Credential

**Goal:** Full CE lifecycle management with provider catalog, cross-state credit mapping, and employee credential portfolios.
**Depends on:** Phase 6 (foundation), Phase 11 (regulatory data)

**Scope:**
- `ce_providers` table (provider name, accreditation, contact)
- `ce_courses` table (provider_id, title, hours, states_accepted)
- Junction table: `ce_credit_courses` (credit → course mapping)
- Cross-state credit applicability matrix
- Employee credential portfolio view (all licenses + CE status per person)
- CE import from provider transcripts (CSV)
- CE calendar: upcoming deadlines by employee

#### Phase 13: Integrations & Automation

**Goal:** Connect licenses module to external systems and other QMS modules for automated compliance.
**Depends on:** Phases 6-12 (builds on all prior work)

**Scope:**
- Primary source verification: scrape state board websites for license status
- Calendar integration: iCal feed for renewal/CE deadlines
- Cross-module links: licenses ↔ welding certifications, licenses ↔ workforce employees
- Bulk operations: mass renewal processing, batch CE credit entry
- API endpoints for external system integration
- Dashboard widgets for home page (expiring licenses, CE alerts)

---

## Previous Milestone

**v0.1 Quality Intelligence Platform** (v0.1.0)
Status: In progress (4.5 of 5 phases — Phase 4 complete, Phase 5 not started)

### Phases

| Phase | Name | Plans | Status | Completed |
|-------|------|-------|--------|-----------|
| 1 | Quality Issues Foundation | 1 | Complete | 2026-02-25 |
| 2 | Procore Bulk Import | 3 | Complete | 2026-02-26 |
| 3 | Quality Intelligence Dashboard | 2 | Complete | 2026-02-27 |
| 4 | Mobile Capture Pipeline | 2 | Complete | 2026-03-05 |
| 5 | Procore Push | TBD | Not started | - |

### Phase Details

#### Phase 1: Quality Issues Foundation

**Goal:** Unified schema for all quality issue types with audit trail, issue relationships, tagging, corrective actions, and normalization config.
**Depends on:** Nothing (first phase)

**Plans:**
- [x] 01-01: Schema, module registration, config, verification — Complete (2026-02-25)

#### Phase 2: Procore Bulk Import

**Goal:** Import all quality data from multiple Procore projects into unified schema + normalize on ingest + vector index.
**Depends on:** Phase 1

**Plans:**
- [x] 02-01: Quality issue import engine (CSV parser, normalizer, dedup, CLI) — Complete (2026-02-25)
- [x] 02-02: Batch import, project resolver, pipeline config — Complete (2026-02-26)
- [x] 02-03: Attachment pipeline + vector indexing — Complete (2026-02-26)

#### Phase 3: Quality Intelligence Dashboard

**Goal:** Cross-project analytics, semantic search, pattern detection, benchmarking, recurring issue auto-detection.
**Depends on:** Phase 2

**Plans:**
- [x] 03-01: Quality blueprint, dashboard page, issue list API, module registration — Complete (2026-02-27)
- [x] 03-02: Analytics charts, browse page, semantic search — Complete (2026-02-27)

#### Phase 4: Mobile Capture Pipeline

**Goal:** OneDrive → AI photo analysis + voice transcription → structured quality issue creation.
**Depends on:** Phase 1

**Plans:**
- [x] 04-01: Photo processing engine — Claude vision + CLI capture command — Complete (2026-03-05)
- [x] 04-02: Voice transcription + capture review UI — Complete (2026-03-05)

#### Phase 5: Procore Push

**Goal:** Push new quality issues from QMS back into Procore observation pages.
**Depends on:** Phase 1, Phase 3

**Plans:**
- [ ] TBD during Phase 5 planning

---
*Roadmap created: 2026-02-25*
*Last updated: 2026-03-05 — v0.2 License Compliance Platform milestone created*
