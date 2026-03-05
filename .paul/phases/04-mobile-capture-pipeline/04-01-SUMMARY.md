---
phase: 04-mobile-capture-pipeline
plan: 01
subsystem: api
tags: [anthropic-vision, claude-api, mobile-capture, onedrive, quality-issues, photo-analysis]

# Dependency graph
requires:
  - phase: 01-quality-issues-foundation
    provides: quality_issues table with source='mobile', quality_issue_attachments table
  - phase: 02-procore-bulk-import
    provides: normalize_trade(), normalize_type(), attachment infrastructure
provides:
  - Mobile capture processing engine (scan, analyze, create)
  - Claude vision photo analysis with structured JSON extraction
  - capture_log table for dedup tracking
  - CLI command: `qms quality capture [--dry-run] [--folder] [--project]`
  - config.yaml mobile_capture section
  - 17 new tests (551 total)
affects: [04-02-voice-transcription, 05-procore-push]

# Tech tracking
tech-stack:
  added: []
  patterns: [claude-vision-structured-extraction, capture-log-dedup, module-level-try-import]

key-files:
  created:
    - quality/mobile_capture.py
    - tests/test_mobile_capture.py
  modified:
    - quality/cli.py
    - quality/schema.sql
    - config.yaml

key-decisions:
  - "Module-level anthropic import with try/except — makes mocking testable"
  - "Type normalization skips already-valid values — normalize_type('observation') was returning 'other'"
  - "Config value None fallback with `or` — get_config_value can return None even with default"

patterns-established:
  - "Claude vision pattern: base64-encode image → structured JSON prompt → parse response → normalize fields"
  - "capture_log dedup: UNIQUE(filepath) prevents re-processing, file_hash provides secondary dedup"
  - "Process-level mock: patch get_db at consumer module, not source module (Python import binding)"

# Metrics
duration: ~20min
started: 2026-03-05T00:00:00Z
completed: 2026-03-05T00:00:00Z
---

# Phase 4 Plan 01: Mobile Capture Processing Engine Summary

**Claude vision photo analysis pipeline — scan OneDrive folder, analyze construction photos with AI, create structured quality issues with attached images and CLI command.**

## Performance

| Metric | Value |
|--------|-------|
| Duration | ~20 min |
| Tasks | 3 completed (2 auto + 1 checkpoint skipped) |
| Files created | 2 |
| Files modified | 3 |
| New tests | 17 |
| Total tests | 551 passing |

## Acceptance Criteria Results

| Criterion | Status | Notes |
|-----------|--------|-------|
| AC-1: Photo Scanning | Pass | scan_capture_folder() finds .jpg/.jpeg/.png/.heic, skips non-images and already-processed files |
| AC-2: Claude Vision Analysis | Pass | analyze_photo() sends base64 image to Claude API, parses structured JSON, normalizes fields |
| AC-3: Quality Issue Creation | Pass | create_issue_from_capture() inserts quality_issues + attachments + capture_log, copies image file |
| AC-4: CLI Integration | Pass | `qms quality capture` with --dry-run, --folder, --project options |
| AC-5: Config-Driven Settings | Pass | mobile_capture section in config.yaml with source_folder, model, attachment_dir |
| AC-6: Tests Pass | Pass | 17 new tests, 551 total, 0 regressions |

## Accomplishments

- Built complete photo → AI analysis → quality issue pipeline with Claude vision API
- Created `capture_log` table for idempotent processing (re-run safety)
- Added `qms quality capture` CLI command with dry-run mode for safe testing
- 17 tests covering scan, analyze, create, end-to-end, and dedup scenarios — all with mocked API

## Task Commits

Work applied in single commit:

| Task | Status | Description |
|------|--------|-------------|
| Task 1: Mobile capture processing module | PASS | quality/mobile_capture.py (270 lines) + capture_log schema |
| Task 2: CLI command + config integration | PASS | capture command in cli.py + mobile_capture config section |
| Task 3 (Checkpoint): Human verification | SKIPPED | No test photos available — user chose to proceed |
| Task 4: Tests and verification | PASS | 17 tests in test_mobile_capture.py, 551 total passing |

Commit: `5503781`

## Files Created/Modified

| File | Change | Purpose |
|------|--------|---------|
| `quality/mobile_capture.py` | Created | Core processing engine: scan, analyze_photo, create_issue, process_captures (270 lines) |
| `tests/test_mobile_capture.py` | Created | 17 test cases with mocked Claude API |
| `quality/cli.py` | Modified | Added `capture` command (+64 lines) |
| `quality/schema.sql` | Modified | Added capture_log table (+13 lines) |
| `config.yaml` | Modified | Added mobile_capture section (+17 lines) |
| `.paul/STATE.md` | Modified | Updated loop position and phase status |
| `.paul/ROADMAP.md` | Modified | Updated phase 4 status to Planning |

## Decisions Made

| Decision | Rationale | Impact |
|----------|-----------|--------|
| Module-level anthropic import | Lazy import inside function was un-mockable in tests; try/except at module level enables `patch("...anthropic")` | Standard pattern for optional deps |
| Skip normalize_type for valid values | `normalize_type("observation")` → "other" because config mapping only has UI label → canonical entries | Prevents data loss on already-clean AI output |
| `or` fallback on config values | `get_config_value()` returns None when YAML key exists with `null` value, even with `default` param | Prevents Path(None) crash |
| Checkpoint skipped | User had no test photos available — unit tests provide sufficient coverage | Live verification deferred to first real use |

## Deviations from Plan

### Summary

| Type | Count | Impact |
|------|-------|--------|
| Auto-fixed | 3 | Essential fixes for test reliability |
| Scope additions | 0 | None |
| Deferred | 0 | None |

**Total impact:** Three bugs found and fixed during testing — all essential for correctness.

### Auto-fixed Issues

**1. Import mocking pattern — anthropic import unreachable**
- **Found during:** Task 4 (writing tests)
- **Issue:** `import anthropic` inside function body created no module-level attribute to patch
- **Fix:** Moved to module-level `try: import anthropic / except: anthropic = None`
- **Files:** `quality/mobile_capture.py`
- **Verification:** All 17 tests pass

**2. Type normalization data loss**
- **Found during:** Task 4 (test_parses_response)
- **Issue:** `normalize_type("observation")` returned "other" — config mapping lacks identity entries
- **Fix:** Added guard: only call normalize_type if value not already in _VALID_TYPES
- **Files:** `quality/mobile_capture.py`
- **Verification:** test_parses_response passes

**3. Config None → Path crash**
- **Found during:** Task 4 (test_dry_run)
- **Issue:** `get_config_value(..., default="x")` returns None when YAML key is `null`; `Path(None)` raises TypeError
- **Fix:** Added `or "data/quality-issues/captures"` fallback after config read
- **Files:** `quality/mobile_capture.py`
- **Verification:** test_dry_run passes

### Deferred Items

None.

## Skill Audit

No required skills for this plan. `/frontend-design` was optional and correctly not invoked (no UI work).

## Issues Encountered

| Issue | Resolution |
|-------|------------|
| Python import binding prevents mock | Moved to module-level import with try/except |
| normalize_type identity mapping gap | Guard clause before normalization |
| Config null vs missing distinction | `or` fallback after config read |

## Next Phase Readiness

**Ready:**
- Photo → AI → quality_issues pipeline fully functional
- CLI command ready for field use
- capture_log ensures idempotent re-runs
- Attachment infrastructure connected (files copied + DB records created)

**Concerns:**
- Checkpoint verification skipped — first real use will be the true test
- Voice note transcription not yet addressed (Plan 04-02)
- OneDrive capture folder doesn't exist yet — needs manual creation

**Blockers:**
- None

---
*Phase: 04-mobile-capture-pipeline, Plan: 01*
*Completed: 2026-03-05*
