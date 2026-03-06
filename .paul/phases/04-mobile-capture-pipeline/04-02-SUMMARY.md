---
phase: 04-mobile-capture-pipeline
plan: 02
subsystem: api
tags: [whisper, openai, voice-transcription, quality, mobile, captures, review-ui]

# Dependency graph
requires:
  - phase: 04-mobile-capture-pipeline/04-01
    provides: Photo capture pipeline, capture_log dedup, process_captures() engine
provides:
  - Voice note transcription via OpenAI Whisper API
  - Transcript analysis via Claude (structured extraction)
  - Capture review web page at /quality/captures with inline editing
  - Mixed image + audio capture processing
affects: [phase-5-procore-push]

# Tech tracking
tech-stack:
  added: [openai-sdk]
  patterns: [optional-import-try-except, mixed-media-processing, inline-edit-fetch]

key-files:
  created: [frontend/templates/quality/captures.html]
  modified: [quality/mobile_capture.py, api/quality.py, config.yaml, pyproject.toml, frontend/templates/base.html, tests/test_mobile_capture.py]

key-decisions:
  - "OpenAI Whisper API for transcription — no local model, handles m4a/mp3/wav/ogg natively"
  - "Optional import pattern for openai SDK (same as anthropic) — not a hard dependency"
  - "Transcript preserved in metadata JSON on quality_issues — no schema changes needed"

patterns-established:
  - "Mixed media processing: split files by extension, route to appropriate analyzer"
  - "Inline edit pattern: click row → expand edit form → PUT via fetch → update DOM"
  - "Optional SDK pattern: module-level try/except, return error dict if missing"

# Metrics
duration: ~45min (across two sessions)
started: 2026-03-05
completed: 2026-03-05
---

# Phase 4 Plan 02: Voice Transcription + Capture Review Summary

**Extended mobile capture pipeline with OpenAI Whisper voice transcription, Claude transcript analysis, and a web review page at `/quality/captures` with inline editing — completing the phone-to-database pipeline.**

## Performance

| Metric | Value |
|--------|-------|
| Duration | ~45 min (two sessions) |
| Started | 2026-03-05 |
| Completed | 2026-03-05 |
| Tasks | 4 completed (2 auto + 1 checkpoint + 1 auto) |
| Files modified | 7 |

## Acceptance Criteria Results

| Criterion | Status | Notes |
|-----------|--------|-------|
| AC-1: Audio File Discovery | Pass | _AUDIO_EXTENSIONS = {.m4a, .mp3, .wav, .ogg}, scan_capture_folder discovers mixed media |
| AC-2: Voice Note Transcription | Pass | transcribe_audio() calls Whisper API, returns {text} or {error} |
| AC-3: Transcript Analysis | Pass | analyze_transcript() sends text to Claude, returns structured dict, preserves original transcript |
| AC-4: Capture Review Page | Pass | /quality/captures renders with stats, table, inline edit, sub-nav link |
| AC-5: Capture Detail API | Pass | GET /quality/api/captures returns JSON with filters, PUT updates issue |
| AC-6: Tests Pass | Pass | 26 capture tests pass, 560 total tests pass |

## Accomplishments

- `transcribe_audio()` — OpenAI Whisper API integration with optional SDK import
- `analyze_transcript()` — Claude text analysis with structured JSON extraction, trade normalization
- Mixed media `process_captures()` — splits files by extension, routes images → analyze_photo, audio → transcribe → analyze_transcript
- `/quality/captures` review page with stats bar, filterable table, inline edit via fetch PUT
- Sub-nav updated: Dashboard | Browse | Captures
- 9 new tests (17 → 26) covering audio scanning, Whisper transcription, transcript analysis, audio attachments, metadata storage

## Task Commits

| Task | Commit | Type | Description |
|------|--------|------|-------------|
| Task 1+2+3 (code) | `2cd1fba` | feat | Voice transcription, capture review page, API endpoints |
| Task 4 (tests) | `5a2d9a6` | test | 9 new tests for voice + audio capture |

Note: Code commit was bundled with Licenses Phase 3 work in the same session.

## Files Created/Modified

| File | Change | Purpose |
|------|--------|---------|
| `quality/mobile_capture.py` | Modified | Added transcribe_audio(), analyze_transcript(), _AUDIO_EXTENSIONS, mixed media processing |
| `api/quality.py` | Modified | Added /quality/captures page route, GET/PUT /quality/api/captures endpoints |
| `frontend/templates/quality/captures.html` | Created | Capture review page with inline editing |
| `frontend/templates/base.html` | Modified | Added Captures sub-nav link in quality section |
| `config.yaml` | Modified | Added audio extensions and whisper_model config |
| `pyproject.toml` | Modified | Added openai>=1.0.0 to pipeline extras |
| `tests/test_mobile_capture.py` | Modified | 9 new tests (17 → 26 total) |

## Decisions Made

| Decision | Rationale | Impact |
|----------|-----------|--------|
| OpenAI Whisper API (not local) | Simpler than running local Whisper model, handles formats natively | Requires API key, adds cost per transcription |
| Optional openai import | Same pattern as anthropic SDK — not a hard dependency | Pipeline module works without openai installed |
| No schema changes | Transcript stored in existing metadata JSON column | No migration needed |
| Inline edit (not modal) | Simpler UX — click row to expand, edit in place | Matches the lightweight QMS UI pattern |

## Deviations from Plan

### Summary

| Type | Count | Impact |
|------|-------|--------|
| Auto-fixed | 0 | - |
| Scope additions | 0 | - |
| Deferred | 0 | - |

**Total impact:** Plan executed as written. Code committed across two sessions (code + tests separately).

## Issues Encountered

| Issue | Resolution |
|-------|------------|
| Code committed in mixed Licenses Phase 3 commit | No functional impact — code is correct, just commit message doesn't reflect 04-02 work |

## Next Phase Readiness

**Ready:**
- Full phone-to-database pipeline complete: photos (Claude vision) + voice notes (Whisper → Claude)
- Review page provides human-in-the-loop verification before Procore push (Phase 5)
- 26 tests with mocked APIs provide regression coverage

**Concerns:**
- None

**Blockers:**
- None — Phase 4 complete (2/2 plans), Phase 5 (Procore Push) can proceed when ready

---
*Phase: 04-mobile-capture-pipeline, Plan: 02*
*Completed: 2026-03-05*
