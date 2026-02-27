# QMS — Procore Observation Integration

## What This Is

Bidirectional Procore observation integration for the QMS platform. Two tracks: (1) Brandon's personal mobile capture pipeline — photos and voice notes saved to OneDrive from phone, processed by AI into structured observations and pushed to Procore. (2) Team-wide Procore observation import — pull existing and historical observations from Procore into QMS for centralized tracking and reporting.

## Core Value

All quality data from siloed Procore projects unified in one database — enabling cross-project pattern analysis, trend detection, and data-driven quality decisions. Plus a mobile capture pipeline for field observations and bidirectional sync with Procore.

## Current State

| Attribute | Value |
|-----------|-------|
| Version | 0.1.0-alpha |
| Status | In Progress |
| Last Updated | 2026-02-27 (Phase 3 complete) |

**Production URL:** http://L004470-CAD:5000

## Requirements

### Validated (Shipped)

- [x] CSV project import from Procore Company Home export — `projects/procore_io.py`
- [x] Unified quality issues schema (8 tables, all issue types) — Phase 1
- [x] Root cause taxonomy and normalization config — Phase 1
- [x] Audit trail and issue linking infrastructure — Phase 1
- [x] CSV import engine with header auto-mapping, normalization, dedup — Phase 2
- [x] Batch import with project-from-filename resolution — Phase 2
- [x] Attachment URL capture during import — Phase 2
- [x] Quality issues vector indexing for semantic search — Phase 2
- [x] Pipeline classifier for observation CSV auto-detection — Phase 2
- [x] Quality intelligence dashboard with Chart.js analytics, browse page, semantic search — Phase 3

### Active (In Progress)

- [ ] Track 1: OneDrive → AI processing → structured observation → Procore push

### Planned (Next)

- [ ] Drawing zip import from Procore exports

### Out of Scope

- Procore real-time API sync (future milestone)
- Procore RFI or submittal integration

## Target Users

**Primary (Track 1):** Brandon Johnson
- Field visits with mobile phone
- Captures photos + voice notes to OneDrive
- Needs zero-effort observation creation in Procore

**Primary (Track 2):** All QMS users
- Need historical and ongoing Procore observations in QMS
- Centralized reporting across projects

## Context

**Business Context:**
SIS field teams use Procore for project management. Quality observations created during site visits currently require manual double-entry — once in the field notes and again in Procore. Historical observations in Procore are not visible in QMS reporting.

**Technical Context:**
- Existing CSV import: `projects/procore_io.py`
- Config: `config.yaml` → `procore:` section with per-project URL mappings
- Chrome MCP tools available for browser automation
- OneDrive folder accessible from this machine
- AI transcription available via Claude API

## Constraints

### Technical Constraints
- Must work with existing QMS Flask architecture and SQLite database
- OneDrive folder is local sync (not API-based)
- Procore API access status unknown — may require browser automation

### Business Constraints
- Track 1 is a personal workflow (Brandon only)
- Track 2 must be accessible to any QMS user with project access

## Key Decisions

| Decision | Rationale | Date | Status |
|----------|-----------|------|--------|
| Two-track approach | Personal mobile pipeline vs team-wide import serve different audiences | 2026-02-25 | Active |
| OneDrive as bridge | Already in use on mobile, local sync avoids API complexity | 2026-02-25 | Active |
| Wide schema (all issue types) | quality_issues supports observations, NCRs, CARs, deficiencies, punch — not just observations | 2026-02-25 | Active |
| Audit trail from day one | Cannot be retrofitted — captures all history from initial import | 2026-02-25 | Active |
| Normalization config in YAML | Trade/status/type aliases in config.yaml for import-time normalization | 2026-02-25 | Active |
| Manual CSV export from Procore | No API/browser automation needed for now; can add later | 2026-02-26 | Active |
| Data-source-agnostic import engine | CSV in → quality_issues out, regardless of extraction method | 2026-02-26 | Active |
| Attachment URL-only recording | Capture URLs now, download files later (Phase 4) | 2026-02-26 | Active |
| Chart.js via CDN for analytics | No build step, matches QMS inline-script convention | 2026-02-27 | Active |
| vectordb-first search with SQL fallback | Graceful degradation when vectordb unavailable | 2026-02-27 | Active |

## Success Metrics

| Metric | Target | Current | Status |
|--------|--------|---------|--------|
| Observation creation time (Track 1) | < 2 min from photo to Procore | Manual entry ~10 min | Not started |
| Historical observations imported | 100% of existing Procore observations | 0 | Not started |

## Tech Stack

| Layer | Technology | Notes |
|-------|------------|-------|
| Framework | Flask (existing QMS) | |
| Database | SQLite (quality.db) | |
| AI Processing | Claude API | Voice transcription + photo analysis |
| Browser Automation | Chrome MCP (Playwright) | Procore form filling |
| Mobile Bridge | OneDrive local sync | Photos + voice notes |

## Specialized Flows

See: .paul/SPECIAL-FLOWS.md

Quick Reference:
- /frontend-design → Web UI pages and components

## Links

| Resource | URL |
|----------|-----|
| Repository | https://github.com/bjohnson1-stellar/QMS.git |
| Production | http://L004470-CAD:5000 |
| Planning Doc | .planning/procore-integration.md |

---
*PROJECT.md — Updated when requirements or context change*
*Last updated: 2026-02-27 after Phase 3*
