---
phase: 18-m4-sop-intake-classification
plan: 01
subsystem: api
tags: [claude-api, pdf-upload, sop-classification, intake-pipeline]

requires:
  - phase: 14-schema-api-foundation
    provides: qm_sop_intake table, SOP CRUD functions, approve/publish endpoints
  - phase: 17-m4-sop-catalog-ui
    provides: M4 category browser and SOP detail view
provides:
  - PDF upload endpoint with SHA-256 dedup and file storage
  - Claude-powered SOP classification (category, scope, programs, codes)
  - Intake management endpoints (list, detail, approve→SOP, reject)
affects: [18-02 intake UI, future SOP search FTS]

tech-stack:
  added: [anthropic SDK (lazy import)]
  patterns: [PDF document classification via Claude API, intake-to-SOP conversion]

key-files:
  created: [qualitydocs/classifier.py]
  modified: [qualitydocs/db.py, qualitydocs/__init__.py, api/qualitydocs.py]

key-decisions:
  - "Synchronous classification inline with upload (no task queue)"
  - "PDF sent as base64 document type to Claude (not vision/image)"
  - "Document IDs auto-generated as SOP-{cat}-{seq} pattern"

patterns-established:
  - "Intake pipeline pattern: upload → classify → review → approve → SOP"
  - "File storage: data/quality-documents/intake/{id}/{filename}"

duration: 10min
completed: 2026-03-10T20:00:00Z
---

# Phase 18 Plan 01: SOP Intake Backend Pipeline Summary

**PDF upload with Claude-powered classification, intake management endpoints, and approve-to-SOP conversion pipeline.**

## Performance

| Metric | Value |
|--------|-------|
| Duration | ~10 min |
| Completed | 2026-03-10 |
| Tasks | 3 completed |
| Files modified | 4 |
| Commit | `31ec1bb` |

## Acceptance Criteria Results

| Criterion | Status | Notes |
|-----------|--------|-------|
| AC-1: PDF Upload & Storage | Pass | Upload validates PDF, stores to intake dir, creates record with SHA-256 hash, dedup works |
| AC-2: AI Classification | Pass | classifier.py sends PDF to Claude Sonnet, parses JSON, resolves category/program IDs, generates doc_id |
| AC-3: Intake Management Endpoints | Pass | List (paginated), detail (parsed JSON), approve (creates SOP + code refs + program links + history), reject |

## Accomplishments

- POST `/qualitydocs/api/sops/upload` — PDF upload with 50MB limit, SHA-256 dedup, file storage at `data/quality-documents/intake/{id}/`
- `qualitydocs/classifier.py` — Claude API classification with structured prompt including all 15 categories and 5 programs; returns category, scope tags, program links, code references, summary
- 5 new intake endpoints: upload, list, detail, approve (creates draft SOP with full linkage), reject
- 6 new db.py helper functions: `get_intake_by_hash`, `list_intakes_paginated`, `get_intake_detail`, `next_document_id`, `create_code_references`, `approve_intake`

## Files Created/Modified

| File | Change | Purpose |
|------|--------|---------|
| `qualitydocs/classifier.py` | Created | AI classification — Claude API call, prompt builder, JSON parser |
| `qualitydocs/db.py` | Modified | +6 functions: dedup, paginated list, detail, doc_id gen, code refs, approve |
| `qualitydocs/__init__.py` | Modified | Export new functions + classify_sop |
| `api/qualitydocs.py` | Modified | +5 endpoints: upload, intakes list/detail, approve, reject |

## Decisions Made

| Decision | Rationale | Impact |
|----------|-----------|--------|
| Synchronous classification (no async queue) | Simple for single-user LAN deployment; can add queue later | Upload blocks during classification (~10-30s) |
| PDF document type (not vision) | Better text extraction than page screenshots | Requires anthropic SDK with document support |
| Auto-generated document IDs (SOP-{cat}-{seq}) | Consistent numbering, avoids conflicts | User can override via approve endpoint |
| File storage under intake/{id}/ | Isolates uploads before SOP creation | Files persist even if intake rejected |

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## Next Phase Readiness

**Ready:**
- Full backend pipeline operational: upload → classify → review → approve → SOP
- All endpoints tested via Flask test client (auth bypass)
- Existing M4 catalog endpoints unaffected

**Concerns:**
- Classification quality depends on Claude model accuracy — may need prompt tuning after real SOP testing
- `programsCache` in UI still depends on M3 tab being visited first (pre-existing issue)

**Blockers:**
- None

---
*Phase: 18-m4-sop-intake-classification, Plan: 01*
*Completed: 2026-03-10*
