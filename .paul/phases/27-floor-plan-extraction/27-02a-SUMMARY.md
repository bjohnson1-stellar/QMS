---
phase: 27-floor-plan-extraction
plan: 02a
subsystem: pipeline
tags: [pymupdf, text-extraction, floor-plans, cad-pdf, sonnet, vision]

requires:
  - phase: 27-01
    provides: floor_plan_extractions table, build_floor_plan_prompt(), extraction harness
  - phase: 27-02
    provides: calibration data showing Sonnet 14.6% vs Opus 100% on floor plans
provides:
  - PyMuPDF text-layer preprocessor (pipeline/text_layer.py)
  - Enhanced extraction prompt with embedded text + coordinates
  - Validated Sonnet+text approach matching Opus accuracy at ~10x cost reduction
affects: [27-02 remaining phases, 27-03 MEP scaling, all future floor plan extraction]

tech-stack:
  added: []
  patterns: [text-layer-augmented vision extraction]

key-files:
  created: [pipeline/text_layer.py]
  modified: [pipeline/floor_plan_extractor.py]

key-decisions:
  - "Bounding box format (x0,y0,x1,y1) over width/height — standard PyMuPDF format, more useful for spatial reasoning"
  - "Equipment tag regex: 2-5 letters + dash + digits (standard) plus 2-3 letters + digits (short) — filters grid refs and drawing numbers"
  - "Coordinates as percentage of page in prompt — model-agnostic spatial reference"
  - "Graceful degradation — text layer failure falls back to image-only extraction"

patterns-established:
  - "Text-layer augmentation: extract embedded text from CAD PDFs before vision pass to overcome image resolution limits"
  - "Cost optimization via preprocessing: zero-cost local extraction replaces expensive multi-pass Opus reads"

duration: ~30min
started: 2026-03-28T01:10:00Z
completed: 2026-03-28T01:40:00Z
---

# Phase 27 Plan 02a: Text-Layer Preprocessor Summary

**PyMuPDF text extraction from CAD PDFs, injected into vision prompts — Sonnet+text achieves 100% recall on R1101 (41/41), matching Opus at ~10x cost reduction.**

## Performance

| Metric | Value |
|--------|-------|
| Duration | ~30min |
| Started | 2026-03-28T01:10Z |
| Completed | 2026-03-28T01:40Z |
| Tasks | 4 completed (3 auto + 1 checkpoint) |
| Files modified | 2 (1 created, 1 modified) |

## Acceptance Criteria Results

| Criterion | Status | Notes |
|-----------|--------|-------|
| AC-1: Text Layer Extraction Works on CAD PDFs | Pass | 344 text blocks, 41 equipment tags, 150ms extraction on R1101 |
| AC-2: Text Layer Injected into Extraction Prompt | Pass | Prompt 12K → 18K chars with TEXT LAYER section + coordinates |
| AC-3: Sonnet + Text Layer Matches Opus Baseline | Pass | 41/41 = 100% recall (target was 85%), zero hallucinations |

## Accomplishments

- Built `pipeline/text_layer.py` — extracts embedded text + bounding boxes from CAD PDFs via PyMuPDF in ~150ms per page (zero API cost)
- Enhanced `build_floor_plan_prompt()` with text layer injection — coordinates formatted as % of page, equipment tags listed explicitly
- Validated on R1101: Sonnet+text found all 41 Opus baseline entries (31 RAHU + 10 RCU) with zero false positives
- Recorded routing change: floor plans shift from Opus to Sonnet+text-layer (~10x cost reduction)

## Task Commits

| Task | Commit | Type | Description |
|------|--------|------|-------------|
| Task 1-3: Text layer + integration + validation | `229b294` | feat | text_layer.py, prompt enhancement, Sonnet validation |
| State update | `69eb662` | docs | STATE.md updated for APPLY completion |

## Files Created/Modified

| File | Change | Purpose |
|------|--------|---------|
| `pipeline/text_layer.py` | Created | PyMuPDF text extraction with equipment tag detection |
| `pipeline/floor_plan_extractor.py` | Modified | `build_floor_plan_prompt()` now injects text layer data |

## Decisions Made

| Decision | Rationale | Impact |
|----------|-----------|--------|
| Bounding box (x0,y0,x1,y1) format | Standard PyMuPDF format, more useful than width/height | Consistent with PDF coordinate system |
| Coordinates as % of page in prompt | Model-agnostic spatial reference | Works regardless of page dimensions |
| Graceful degradation on failure | Scanned PDFs or missing fitz shouldn't break extraction | Image-only fallback preserved |
| Tag regex: letters-dash-digits pattern | Filters grid references (A1), drawing numbers (R1101), area labels | 41/41 true positives, 0 false positives on R1101 |

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## Next Phase Readiness

**Ready:**
- Sonnet+text-layer validated and ready for scaling
- `build_floor_plan_prompt()` automatically uses text layer for any sheet with a PDF
- Routing change documented in `routing_changes` table
- All existing pipeline tests pass (4/4)

**Concerns:**
- Plan 27-02 still partially open (Phase 2 discovery done on 19 sheets, but Phases 3-4 and remaining shadow reviews not yet run)
- Text layer validated on one drawing type (large floor plan) — P&IDs and BFDs may behave differently

**Blockers:**
- None

---
*Phase: 27-floor-plan-extraction, Plan: 02a*
*Completed: 2026-03-28*
