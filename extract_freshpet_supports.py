"""
Extract data from Freshpet refrigeration support detail sheets.

Processes sheets 619-621: R5210.1, R5211.1, R5220.1 (REFRIGERATION-DETAILS-SUPPORTS)
"""

import json
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add QMS to path if running standalone
sys.path.insert(0, str(Path(__file__).parent))

from qms.core import get_db, get_logger

logger = get_logger("qms.drawing_extraction.supports")


def extract_pdf_text(pdf_path: Path) -> str:
    """Extract text from PDF using PyMuPDF."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        raise ImportError("PyMuPDF required: pip install PyMuPDF")

    doc = fitz.open(pdf_path)
    text_parts = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        text_parts.append(f"--- PAGE {page_num + 1} ---\n")
        text_parts.append(page.get_text())

    doc.close()
    return "\n".join(text_parts)


def call_model(prompt: str, model: str = "sonnet") -> str:
    """Call Anthropic API with the given prompt."""
    try:
        import anthropic
    except ImportError:
        raise ImportError("anthropic SDK required: pip install anthropic")

    model_map = {
        "haiku": "claude-haiku-4-5-20251001",
        "sonnet": "claude-sonnet-4-5-20250929",
        "opus": "claude-opus-4-6",
    }
    model_id = model_map.get(model, model)

    client = anthropic.Anthropic()
    response = client.messages.create(
        model=model_id,
        max_tokens=16000,
        messages=[{"role": "user", "content": prompt}],
    )

    return response.content[0].text


def build_detail_extraction_prompt(text: str) -> str:
    """Build extraction prompt for refrigeration detail/support drawings."""
    return f"""Extract all piping and equipment data from this refrigeration support detail drawing.

These are detail drawings showing pipe supports, hangers, structural details, and installation specifications.

For each PIPE LINE or PIPE RUN shown in details, provide:
- Line number/designation (if visible)
- Size (pipe diameter)
- Material (e.g., CS = Carbon Steel, SS = Stainless Steel, SCH = Schedule)
- Service (what the line carries: ammonia liquid, ammonia vapor, etc.)
- Support/mounting details if noted

For each EQUIPMENT or COMPONENT shown, provide:
- Tag number or identifier (if labeled)
- Equipment type (support, hanger, clamp, bracket, valve, etc.)
- Description

For any INSTRUMENTS or CONTROLS shown, provide:
- Tag number (e.g., FT-101, PT-201, etc.)
- Instrument type
- Service/function

For STRUCTURAL or SUPPORT components, provide:
- Type (beam, column, hanger rod, spring hanger, etc.)
- Size/specification
- Material if noted

Return the data as a JSON object with this exact structure:
{{
  "lines": [
    {{
      "line_number": "string or null",
      "size": "string or null",
      "material": "string or null",
      "service": "string or null",
      "from_location": "string or null",
      "to_location": "string or null",
      "confidence": 0.0-1.0
    }}
  ],
  "equipment": [
    {{
      "tag": "string",
      "equipment_type": "string",
      "description": "string",
      "confidence": 0.0-1.0
    }}
  ],
  "instruments": [
    {{
      "tag": "string",
      "instrument_type": "string",
      "service": "string or null",
      "location": "string or null",
      "confidence": 0.0-1.0
    }}
  ],
  "notes": [
    "Any important installation notes, specifications, or references"
  ]
}}

Drawing text:
{text}

Respond ONLY with valid JSON. No markdown, no explanation, just the JSON object.
"""


def parse_extraction_response(response: str) -> Dict[str, Any]:
    """Parse JSON response from model."""
    # Strip markdown code blocks if present
    response = response.strip()
    if response.startswith("```"):
        lines = response.split("\n")
        response = "\n".join(lines[1:-1])
    if response.startswith("json"):
        response = response[4:].strip()

    try:
        return json.loads(response)
    except json.JSONDecodeError as e:
        logger.error("Failed to parse JSON response: %s", e)
        logger.error("Response text: %s", response[:500])
        return {"lines": [], "equipment": [], "instruments": [], "notes": []}


def calculate_confidence(data: Dict[str, Any]) -> float:
    """Calculate overall extraction confidence score."""
    all_items = []
    all_items.extend(data.get("lines", []))
    all_items.extend(data.get("equipment", []))
    all_items.extend(data.get("instruments", []))

    if not all_items:
        return 0.0

    total_conf = sum(item.get("confidence", 0.7) for item in all_items)
    return total_conf / len(all_items)


def store_extraction(conn, sheet_id: int, data: Dict[str, Any],
                     quality_score: float, model: str) -> Dict[str, int]:
    """Store extracted data in database."""
    counts = {"lines": 0, "equipment": 0, "instruments": 0}

    # Store lines
    for line in data.get("lines", []):
        conn.execute(
            """INSERT INTO lines
               (sheet_id, line_number, size, material, service, from_location,
                to_location, confidence)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                sheet_id,
                line.get("line_number") or "DETAIL",
                line.get("size"),
                line.get("material"),
                line.get("service"),
                line.get("from_location"),
                line.get("to_location"),
                line.get("confidence", 0.7),
            ),
        )
        counts["lines"] += 1

    # Store equipment
    for equip in data.get("equipment", []):
        conn.execute(
            """INSERT INTO equipment
               (sheet_id, tag, equipment_type, description, confidence)
               VALUES (?, ?, ?, ?, ?)""",
            (
                sheet_id,
                equip.get("tag") or f"SUPPORT-{counts['equipment'] + 1}",
                equip.get("equipment_type"),
                equip.get("description"),
                equip.get("confidence", 0.7),
            ),
        )
        counts["equipment"] += 1

    # Store instruments
    for inst in data.get("instruments", []):
        conn.execute(
            """INSERT INTO instruments
               (sheet_id, tag, instrument_type, service, location, confidence, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                sheet_id,
                inst.get("tag"),
                inst.get("instrument_type"),
                inst.get("service"),
                inst.get("location"),
                inst.get("confidence", 0.7),
                datetime.now().isoformat(),
            ),
        )
        counts["instruments"] += 1

    # Store notes in extraction_notes field of sheets table
    notes = data.get("notes", [])
    notes_text = "\n".join(notes) if notes else None

    # Update sheet record
    conn.execute(
        """UPDATE sheets
           SET extracted_at = ?,
               extraction_model = ?,
               quality_score = ?,
               drawing_type = 'Detail',
               complexity = 'simple',
               extraction_notes = ?
           WHERE id = ?""",
        (
            datetime.now().isoformat(),
            model,
            quality_score,
            notes_text,
            sheet_id,
        ),
    )

    return counts


def extract_sheet(sheet_id: int, pdf_path: Path, model: str = "sonnet") -> Dict[str, Any]:
    """
    Extract data from a single drawing sheet.

    Returns:
        Dict with keys: status, quality_score, counts, errors
    """
    result = {
        "sheet_id": sheet_id,
        "status": "pending",
        "quality_score": 0.0,
        "counts": {"lines": 0, "equipment": 0, "instruments": 0},
        "errors": [],
        "model": model,
    }

    start_time = time.time()

    try:
        # Check if file exists
        if not pdf_path.exists():
            result["status"] = "failed"
            result["errors"].append(f"File not found: {pdf_path}")
            logger.error(f"[Sheet {sheet_id}] File not found: {pdf_path}")
            return result

        # Step 1: Extract text from PDF
        logger.info(f"[Sheet {sheet_id}] Extracting text from {pdf_path.name}")
        raw_text = extract_pdf_text(pdf_path)

        if not raw_text.strip():
            result["status"] = "failed"
            result["errors"].append("No text extracted from PDF")
            return result

        # Step 2: Classify drawing type
        drawing_type = "Detail (Supports)"
        logger.info(f"[Sheet {sheet_id}] Drawing type: {drawing_type}")

        # Step 3: Build extraction prompt
        prompt = build_detail_extraction_prompt(raw_text)

        # Step 4: Run extraction with selected model
        logger.info(f"[Sheet {sheet_id}] Running extraction with {model}...")
        response = call_model(prompt, model)

        # Step 5: Parse response
        data = parse_extraction_response(response)

        # Step 6: Calculate confidence
        quality_score = calculate_confidence(data)
        result["quality_score"] = quality_score

        # Step 7: Store in database
        logger.info(f"[Sheet {sheet_id}] Storing extracted data...")
        with get_db() as conn:
            counts = store_extraction(conn, sheet_id, data, quality_score, model)
            result["counts"] = counts
            conn.commit()

        result["status"] = "success"

        elapsed = time.time() - start_time
        logger.info(
            f"[Sheet {sheet_id}] Extraction complete: "
            f"{counts['lines']} lines, {counts['equipment']} equipment, "
            f"{counts['instruments']} instruments "
            f"(quality: {quality_score:.2f}, time: {elapsed:.1f}s)"
        )

    except Exception as e:
        result["status"] = "failed"
        result["errors"].append(str(e))
        logger.error(f"[Sheet {sheet_id}] Extraction failed: {e}", exc_info=True)

    return result


def main():
    """Extract data from the three Freshpet refrigeration support detail sheets."""

    # Use correct QMS data directory paths
    sheets = [
        {
            "id": 619,
            "path": "D:/qms/data/projects/07609-Freshpet/Refrigeration/R5210.1-REFRIGERATION-DETAILS-SUPPORTS-Rev.1.pdf",
            "drawing_number": "R5210.1"
        },
        {
            "id": 620,
            "path": "D:/qms/data/projects/07609-Freshpet/Refrigeration/R5211.1-REFRIGERATION-DETAILS-SUPPORTS-Rev.1.pdf",
            "drawing_number": "R5211.1"
        },
        {
            "id": 621,
            "path": "D:/qms/data/projects/07609-Freshpet/Refrigeration/R5220.1-REFRIGERATION-DETAILS-SUPPORTS-Rev.1.pdf",
            "drawing_number": "R5220.1"
        },
    ]

    logger.info("="*80)
    logger.info("Drawing Extraction: Project 07609-Freshpet Refrigeration Supports")
    logger.info("="*80)

    results = []
    for sheet in sheets:
        sheet_id = sheet["id"]
        pdf_path = Path(sheet["path"])

        result = extract_sheet(sheet_id, pdf_path, model="sonnet")
        results.append(result)

    # Summary
    logger.info("="*80)
    logger.info("EXTRACTION SUMMARY")
    logger.info("="*80)

    total_lines = 0
    total_equipment = 0
    total_instruments = 0
    success_count = 0
    failed_count = 0

    for result in results:
        sheet_id = result["sheet_id"]
        status = result["status"]

        if status == "success":
            success_count += 1
            counts = result["counts"]
            quality = result["quality_score"]
            total_lines += counts["lines"]
            total_equipment += counts["equipment"]
            total_instruments += counts["instruments"]

            logger.info(
                f"Sheet {sheet_id}: SUCCESS - "
                f"{counts['lines']} lines, {counts['equipment']} equipment, "
                f"{counts['instruments']} instruments (quality: {quality:.2f})"
            )
        else:
            failed_count += 1
            errors = ", ".join(result.get("errors", ["Unknown error"]))
            logger.error(f"Sheet {sheet_id}: FAILED - {errors}")

    logger.info("-"*80)
    logger.info(f"Overall: {success_count} succeeded, {failed_count} failed")
    logger.info(f"Total extracted: {total_lines} lines, {total_equipment} equipment, {total_instruments} instruments")
    logger.info("="*80)

    return 0 if failed_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
