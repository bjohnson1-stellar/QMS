# Roadmap: QMS — Procore Quality Intelligence

## Overview

Build a unified quality intelligence platform that aggregates siloed quality data from all Procore projects into one database, enabling cross-project pattern analysis, trend detection, and data-driven quality decisions. Includes a mobile capture pipeline for field observations and bidirectional sync with Procore.

## Current Milestone

**v0.1 Quality Intelligence Platform** (v0.1.0)
Status: In progress
Phases: 2 of 5 complete

## Phases

| Phase | Name | Plans | Status | Completed |
|-------|------|-------|--------|-----------|
| 1 | Quality Issues Foundation | 1 | Complete | 2026-02-25 |
| 2 | Procore Bulk Import | 3 | Complete | 2026-02-26 |
| 3 | Quality Intelligence Dashboard | TBD | Not started | - |
| 4 | Mobile Capture Pipeline | TBD | Not started | - |
| 5 | Procore Push | TBD | Not started | - |

## Phase Details

### Phase 1: Quality Issues Foundation

**Goal:** Unified schema for all quality issue types with audit trail, issue relationships, tagging, corrective actions, and normalization config.
**Depends on:** Nothing (first phase)
**Research:** Unlikely (internal patterns, existing QMS conventions)

**Scope:**
- 8 new database tables (quality_issues, attachments, history, links, tags, corrective_actions, root_causes)
- FK relationships to projects, business_units, employees
- Normalization config for trades, statuses, types
- Root cause taxonomy seeded
- Quality module registered in SCHEMA_ORDER

**Plans:**
- [x] 01-01: Schema, module registration, config, verification — Complete (2026-02-25)

### Phase 2: Procore Bulk Import

**Goal:** Import all quality data (observations, NCRs, deficiencies, punch items) from multiple Procore projects into unified schema + normalize on ingest + vector index.
**Depends on:** Phase 1 (schema must exist)
**Research:** Likely (Procore export formats, API vs browser automation)
**Research topics:** Procore observation export format, available data fields, batch download approach

**Scope:**
- Procore data extraction (browser automation or API)
- Field mapping and normalization during import
- Photo/attachment download
- Vector indexing of issue descriptions
- Deduplication via source_id tracking

**Plans:**
- [x] 02-01: Quality issue import engine (CSV parser, normalizer, dedup, CLI) — Complete (2026-02-25)
- [x] 02-02: Batch import, project resolver, pipeline config — Complete (2026-02-26)
- [x] 02-03: Attachment pipeline + vector indexing — Complete (2026-02-26)

### Phase 3: Quality Intelligence Dashboard

**Goal:** Cross-project analytics, semantic search, pattern detection, benchmarking, recurring issue auto-detection.
**Depends on:** Phase 2 (needs imported data to visualize)
**Research:** Unlikely (existing QMS dashboard patterns)

**Scope:**
- Web UI for quality issue browsing and filtering
- Cross-project analytics (by trade, type, root cause, project)
- Semantic search via vector DB
- Benchmarking (project comparisons, averages)
- Recurring issue auto-flagging
- Trend charts and KPIs

**Plans:**
- [ ] TBD during Phase 3 planning

### Phase 4: Mobile Capture Pipeline

**Goal:** OneDrive → AI photo analysis + voice transcription → structured quality issue creation.
**Depends on:** Phase 1 (schema), optionally Phase 5 (push to Procore)
**Research:** Likely (OneDrive folder watching, voice transcription approach)

**Scope:**
- OneDrive folder monitoring for new photos/voice notes
- AI transcription of voice memos
- AI photo analysis for auto-categorization
- Structured quality issue creation from unstructured input
- Brandon's personal workflow integration

**Plans:**
- [ ] TBD during Phase 4 planning

### Phase 5: Procore Push

**Goal:** Push new quality issues from QMS back into Procore observation pages.
**Depends on:** Phase 1 (schema), Phase 3 (UI to trigger push from)
**Research:** Likely (Procore form structure, browser automation reliability)

**Scope:**
- Format quality issues for Procore observation format
- Browser automation to fill Procore observation forms
- Status sync (push updates when issues are resolved)
- Per-project Procore URL mapping from config

**Plans:**
- [ ] TBD during Phase 5 planning

---
*Roadmap created: 2026-02-25*
*Last updated: 2026-02-26 — Phase 2 complete*
