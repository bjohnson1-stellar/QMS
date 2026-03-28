---
phase: 27-floor-plan-extraction
plan: 02a
type: build
wave: 2
depends_on: ["27-02"]
files_modified:
  - pipeline/text_layer.py
autonomous: false
---

<objective>
## Goal
Build a text-layer preprocessor that extracts embedded text + bounding box coordinates from CAD-generated PDFs using PyMuPDF (fitz). This gives vision agents a complete tag list regardless of image resolution, replacing the need for expensive Opus multi-section reading on large floor plans.

## Purpose
Calibration on Plan 27-02 revealed Sonnet gets 14.6% accuracy on large floor plans because the PDF renders to a downscaled image where small tags are unreadable. Opus achieves 100% by reading the PDF 42+ times in different sections — but costs 10-15x more and exceeds session usage limits.

CAD-generated PDFs have embedded text (not scanned images). PyMuPDF can extract every text string with its page coordinates in milliseconds — zero API cost. Passing this text layer to Sonnet alongside the image should match Opus-level results at Sonnet cost.

## Output
- `pipeline/text_layer.py` — PyMuPDF text extraction with bounding box coordinates
- Updated `build_floor_plan_prompt()` to include text layer data
- Validation: Sonnet + text layer on R1101 matches Opus baseline (41 entries)
</objective>

<context>
## Project Context
@.paul/PROJECT.md
@.paul/STATE.md

## Prior Work
@.paul/phases/27-floor-plan-extraction/27-02-PLAN.md — Calibration results
@.paul/phases/27-floor-plan-extraction/27-01-SUMMARY.md — Infrastructure

## Workflow Reference
@memory/multi-pass-extraction.md — Extraction playbook (text-layer preprocessor listed as needed)

## Source Files
@pipeline/floor_plan_extractor.py — build_floor_plan_prompt() needs text layer injection
@pipeline/context_builder.py — format_equipment_checklist() for reference pattern
</context>

<skills>
## Required Skills
No specialized flows.
</skills>

<acceptance_criteria>

## AC-1: Text Layer Extraction Works on CAD PDFs
```gherkin
Given a CAD-generated PDF (e.g., R1101)
When extract_text_layer(file_path) is called
Then it returns a list of text blocks with: text, x, y, width, height, page_number
And it captures equipment tags (RAHU-1, RCU-4, etc.) with their coordinates
And it completes in under 1 second per page
```

## AC-2: Text Layer Injected into Extraction Prompt
```gherkin
Given a sheet with text layer data extracted
When build_floor_plan_prompt() is called
Then the prompt includes a TEXT LAYER section listing all extracted text with coordinates
And the prompt instructs: "Use both the image AND the text layer below to identify equipment"
```

## AC-3: Sonnet + Text Layer Matches Opus Baseline on R1101
```gherkin
Given R1101 text layer extracted and injected into prompt
When a Sonnet agent processes R1101 with the enhanced prompt
Then it finds >= 35 of the 41 entries that Opus found (>85% recall)
And the tags match actual equipment on the drawing (no hallucination increase)
```

</acceptance_criteria>

<tasks>

<task type="auto">
  <name>Task 1: Text Layer Extraction Module</name>
  <files>pipeline/text_layer.py</files>
  <action>
    **Create `pipeline/text_layer.py`:**

    ```python
    def extract_text_layer(file_path: str, page_num: int = 0) -> dict:
        """Extract all text with bounding boxes from a PDF page.

        Uses PyMuPDF (fitz) to get embedded text from CAD-generated PDFs.
        Returns structured data with text content and coordinates.

        Returns:
            {
                "page_count": int,
                "page_width": float,
                "page_height": float,
                "text_blocks": [
                    {"text": str, "x0": float, "y0": float, "x1": float, "y1": float},
                    ...
                ],
                "equipment_tags": ["RAHU-1", "RCU-4", ...],  # auto-detected tags
            }
        """
    ```

    Implementation:
    1. `fitz.open(file_path)` to open PDF
    2. `page.get_text("dict")` to get text with positions
    3. Iterate blocks/lines/spans to extract text + bounding boxes
    4. Auto-detect equipment tags using regex (pattern: 1-4 letters + dash + digits, e.g., RAHU-1, RCU-4, CV2, PT3)
    5. Return structured dict

    ```python
    def format_text_layer_for_prompt(text_data: dict, max_lines: int = 200) -> str:
        """Format extracted text layer as a prompt section.

        Returns a formatted string suitable for injection into extraction prompts.
        Prioritizes equipment-tag-containing text blocks.
        """
    ```

    Implementation:
    1. Sort text blocks: equipment-tag blocks first, then by position (top-to-bottom, left-to-right)
    2. Format as: "TEXT AT (x, y): {text content}"
    3. Cap at max_lines to keep prompt focused
    4. Include a header explaining what this data is

    PyMuPDF is already installed (used by pipeline). Import inside function for safety.

    Avoid:
    - Do NOT use OCR (Tesseract/EasyOCR) — CAD PDFs have embedded text
    - Do NOT process scanned PDFs (this is for CAD-generated only)
    - Keep it simple — extract text, format for prompt, done
  </action>
  <verify>
    ```python
    from qms.pipeline.text_layer import extract_text_layer, format_text_layer_for_prompt
    data = extract_text_layer("D:/qms/data/projects/07645-Vital/Refrigeration/R1101-OVERALL-FLOOR-REFRIGERATION-EQUIPMENT-PLAN-Rev.D.pdf")
    assert data["page_count"] >= 1
    assert len(data["text_blocks"]) > 0
    assert "RAHU-1" in data["equipment_tags"] or "RAHU-4" in data["equipment_tags"]
    prompt_section = format_text_layer_for_prompt(data)
    assert len(prompt_section) > 100
    print(f"Text blocks: {len(data['text_blocks'])}")
    print(f"Equipment tags found: {len(data['equipment_tags'])}")
    print(f"Tags: {data['equipment_tags'][:10]}")
    print(f"Prompt section length: {len(prompt_section)} chars")
    ```
  </verify>
  <done>AC-1 satisfied: text layer extraction works on CAD PDFs.</done>
</task>

<task type="auto">
  <name>Task 2: Integrate Text Layer into Floor Plan Prompt</name>
  <files>pipeline/floor_plan_extractor.py</files>
  <action>
    **Modify `build_floor_plan_prompt()` in floor_plan_extractor.py:**

    Add text layer extraction and injection:
    1. Call `extract_text_layer(file_path)` for the sheet's PDF
    2. Call `format_text_layer_for_prompt(text_data)` to get formatted section
    3. Append to the prompt after the equipment checklist section
    4. Add instruction: "Use BOTH the visual image AND the text layer below. The text layer contains every text string from the PDF with coordinates — use it to find tags that may be too small to read in the image."

    Get file_path from sheets table using sheet_id.

    If text layer extraction fails (e.g., scanned PDF, no fitz), log warning and proceed without it — graceful degradation.

    Avoid:
    - Do NOT change the existing checklist injection — add text layer alongside it
    - Do NOT make text layer required — it's an enhancement, not a replacement
  </action>
  <verify>
    ```python
    from qms.pipeline.floor_plan_extractor import build_floor_plan_prompt
    prompt = build_floor_plan_prompt(7, 1541, "Refrigeration", "R1101")
    assert "TEXT LAYER" in prompt or "text layer" in prompt
    assert len(prompt) > 12000  # should be longer now with text data
    print(f"Enhanced prompt length: {len(prompt)} chars")
    ```
  </verify>
  <done>AC-2 satisfied: text layer injected into prompt.</done>
</task>

<task type="auto">
  <name>Task 3: Validate Sonnet + Text Layer vs Opus Baseline</name>
  <files>pipeline/floor_plan_extractor.py</files>
  <action>
    **Execution task — no code changes.**

    Run a single Sonnet agent on R1101 with the enhanced text-layer prompt.
    Compare results against the Opus baseline (41 entries).

    1. Build enhanced prompt: `build_floor_plan_prompt(7, 1541, "Refrigeration", "R1101")`
    2. Dispatch Sonnet agent with the prompt
    3. Compare: how many of the 41 Opus entries did Sonnet find?
    4. Check for hallucination increase — did the text layer cause false positives?

    Target: >= 35 of 41 entries (>85% recall) without hallucination increase.

    Do NOT store results — this is a comparison test only.
    Record comparison in shadow_reviews table for tracking.
  </action>
  <verify>
    Sonnet + text layer found >= 35 of 41 Opus entries on R1101.
    No increase in hallucinated tags.
    Comparison recorded in shadow_reviews.
  </verify>
  <done>AC-3 satisfied: Sonnet + text layer matches Opus baseline.</done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <what-built>Text-layer preprocessor for CAD PDFs + Sonnet accuracy validation on R1101</what-built>
  <how-to-verify>
    1. Check text extraction: how many text blocks and equipment tags from R1101?
    2. Check enhanced prompt: is the text layer section clear and useful?
    3. Compare Sonnet+text vs Opus baseline: recall rate on 41 known entries
    4. Any hallucination increase from the text layer?
    5. DECISION: Ready to scale to 27-03 with Sonnet+text? Or need prompt refinement?
  </how-to-verify>
  <resume-signal>Type "approved" to scale, or describe issues</resume-signal>
</task>

</tasks>

<boundaries>

## DO NOT CHANGE
- pipeline/extraction_harness.py — harness stable
- pipeline/extraction_order.py — classification stable
- pipeline/context_builder.py — context builder stable
- pipeline/equipment_schema.sql — schema stable
- frontend/ — no UI changes

## SCOPE LIMITS
- Text extraction only — no OCR, no image processing
- PyMuPDF only — already installed, no new dependencies
- Graceful degradation — if text layer fails, extraction still works without it
- One validation run on R1101 — don't re-extract all 19 sheets

</boundaries>

<verification>
Before declaring plan complete:
- [ ] text_layer.py created with extract_text_layer() and format_text_layer_for_prompt()
- [ ] R1101 text extraction returns equipment tags with coordinates
- [ ] build_floor_plan_prompt() includes text layer section
- [ ] Sonnet + text layer finds >= 35/41 entries on R1101
- [ ] No hallucination increase
- [ ] Existing tests pass
</verification>

<success_criteria>
- Text-layer preprocessor works on CAD PDFs
- Sonnet + text layer approaches Opus accuracy on floor plans
- Ready to scale 27-03 with Sonnet + text (no Opus needed for floor plans)
</success_criteria>

<output>
After completion, create `.paul/phases/27-floor-plan-extraction/27-02a-SUMMARY.md`
</output>
