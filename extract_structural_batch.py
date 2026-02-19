"""
Extract data from structural drawing sheets for project 07609 Freshpet.

This script extracts:
- Structural support tags and descriptions
- Equipment tags if present
- Drawing notes
- Grid references and dimensions
"""

import json
import re
import sys
import time
from pathlib import Path

# Add qms to path
sys.path.insert(0, r"D:\qms")

from qms.core import get_db, get_logger
from qms.pipeline.extractor import extract_pdf_text, call_model, parse_extraction_response

logger = get_logger("structural_extraction")


def build_structural_prompt(text: str, drawing_number: str) -> str:
    """Build extraction prompt for structural drawings."""

    prompt_type = "general"
    if "SLAB" in drawing_number.upper():
        prompt_type = "slab"
    elif "HANGER" in drawing_number.upper():
        prompt_type = "hanger"
    elif "HOLES" in drawing_number.upper() or "FIRE-PROTECTION" in drawing_number.upper():
        prompt_type = "holes"

    base_prompt = f"""Extract structural information from this drawing.

DRAWING TEXT:
{text}

Please identify and extract:

1. STRUCTURAL SUPPORTS/ELEMENTS:
   - Support tags or identifiers (e.g., S-1, S-2, HSS6X6X1/4, W12X26)
   - Support types (e.g., beam, column, hanger, brace, angle)
   - Structural section sizes (e.g., W12X26, HSS6X6X1/4, L4X4X1/2)
   - Location descriptions or grid references

2. GRID LINES (if shown):
   - Grid identifiers (letters/numbers)
   - Grid dimensions between lines

3. DRAWING NOTES:
   - General notes
   - Structural notes
   - Material specifications
   - Installation requirements

4. DIMENSIONS:
   - Key dimensions
   - Spacings
   - Elevations
   - Clearances

"""

    if prompt_type == "slab":
        specific = """
SPECIFIC FOR SLAB PLAN:
- Slab thickness and reinforcement callouts
- Joint locations and types
- Forklift traffic zones or load ratings
- Slab elevation changes
- Special slab treatments or finishes
"""
    elif prompt_type == "hanger":
        specific = """
SPECIFIC FOR HANGER PLAN:
- Hanger locations and tags
- Hanger rod sizes
- Support beam sizes and locations
- Load capacities if noted
- Attachment details
"""
    elif prompt_type == "holes":
        specific = """
SPECIFIC FOR HOLES/PENETRATIONS:
- Hole sizes and locations
- Penetration types (fire protection, piping, etc.)
- Grid locations of holes
- Reinforcement requirements around holes
- Fire-stopping requirements
"""
    else:
        specific = ""

    return_format = """
Return as JSON in this format:
{
  "supports": [
    {
      "tag": "S-1",
      "type": "beam",
      "section": "W12X26",
      "description": "Roof beam at grid A between 1-2",
      "location": "Grid A, between 1-2",
      "confidence": 0.95
    }
  ],
  "grid_lines": [
    {
      "grid_id": "A",
      "orientation": "horizontal",
      "notes": "Reference grid line"
    }
  ],
  "dimensions": [
    {
      "type": "spacing",
      "value": "20'-0\\"",
      "from": "Grid 1",
      "to": "Grid 2",
      "description": "Bay spacing"
    }
  ],
  "notes": [
    {
      "type": "general",
      "text": "All structural steel to be ASTM A36 unless noted otherwise",
      "confidence": 0.98
    }
  ],
  "holes": [
    {
      "size": "4\\" DIA",
      "location": "Grid A-1, elevation +10'-0\\"",
      "purpose": "Fire protection piping",
      "reinforcement": "None required",
      "confidence": 0.90
    }
  ]
}

IMPORTANT:
- Focus on extracting actual structural elements, not title block information
- For support tags, look for patterns like S-1, H-1, C-1, beam callouts like W12X26
- Include grid references when mentioned
- If you cannot read a value clearly, reduce confidence
- Skip obviously non-structural items
- Confidence range: 0.0 (unable to read) to 1.0 (certain)
"""

    return base_prompt + specific + return_format


def store_structural_extraction(conn, sheet_id: int, drawing_number: str, data: dict) -> dict:
    """
    Store structural extraction results in database.

    Args:
        conn: Database connection
        sheet_id: Sheet ID
        drawing_number: Drawing number for logging
        data: Extracted data dictionary

    Returns:
        Dictionary with counts of items stored
    """
    counts = {
        "supports": 0,
        "notes": 0,
        "dimensions": 0,
        "grid_lines": 0,
        "holes": 0,
        "errors": []
    }

    # Store supports
    for support in data.get("supports", []):
        try:
            conn.execute("""
                INSERT INTO supports (
                    sheet_id, support_tag, support_type, structural_section,
                    description, confidence, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                sheet_id,
                support.get("tag"),
                support.get("type"),
                support.get("section"),
                support.get("description"),
                support.get("confidence", 0.7),
                support.get("location")
            ))
            counts["supports"] += 1
        except Exception as e:
            error_msg = f"Failed to insert support {support.get('tag')}: {e}"
            logger.error(error_msg)
            counts["errors"].append(error_msg)

    # Store general notes
    for note in data.get("notes", []):
        try:
            conn.execute("""
                INSERT INTO drawing_notes (
                    sheet_id, drawing_number, note_type, note_text
                ) VALUES (?, ?, ?, ?)
            """, (
                sheet_id,
                drawing_number,
                note.get("type", "general"),
                note.get("text")
            ))
            counts["notes"] += 1
        except Exception as e:
            error_msg = f"Failed to insert note: {e}"
            logger.error(error_msg)
            counts["errors"].append(error_msg)

    # Store dimensions as extraction notes
    for dim in data.get("dimensions", []):
        try:
            desc = f"{dim.get('type', 'dimension')}: {dim.get('value')} from {dim.get('from', '?')} to {dim.get('to', '?')}"
            if dim.get("description"):
                desc += f" - {dim['description']}"

            conn.execute("""
                INSERT INTO extraction_notes (
                    sheet_id, note_type, description, confidence
                ) VALUES (?, ?, ?, ?)
            """, (
                sheet_id,
                "dimension",
                desc,
                dim.get("confidence", 0.8)
            ))
            counts["dimensions"] += 1
        except Exception as e:
            error_msg = f"Failed to insert dimension: {e}"
            logger.error(error_msg)
            counts["errors"].append(error_msg)

    # Store grid lines as extraction notes
    for grid in data.get("grid_lines", []):
        try:
            desc = f"Grid {grid.get('grid_id')} ({grid.get('orientation', 'unknown')})"
            if grid.get("notes"):
                desc += f": {grid['notes']}"

            conn.execute("""
                INSERT INTO extraction_notes (
                    sheet_id, note_type, description, confidence
                ) VALUES (?, ?, ?, ?)
            """, (
                sheet_id,
                "grid_line",
                desc,
                0.9
            ))
            counts["grid_lines"] += 1
        except Exception as e:
            error_msg = f"Failed to insert grid line: {e}"
            logger.error(error_msg)
            counts["errors"].append(error_msg)

    # Store holes/penetrations as extraction notes
    for hole in data.get("holes", []):
        try:
            desc = f"Hole: {hole.get('size', '?')} at {hole.get('location', '?')}"
            if hole.get("purpose"):
                desc += f" for {hole['purpose']}"
            if hole.get("reinforcement"):
                desc += f" - Reinforcement: {hole['reinforcement']}"

            conn.execute("""
                INSERT INTO extraction_notes (
                    sheet_id, note_type, description, confidence
                ) VALUES (?, ?, ?, ?)
            """, (
                sheet_id,
                "hole",
                desc,
                hole.get("confidence", 0.8)
            ))
            counts["holes"] += 1
        except Exception as e:
            error_msg = f"Failed to insert hole: {e}"
            logger.error(error_msg)
            counts["errors"].append(error_msg)

    return counts


def extract_structural_sheet(sheet_id: int, file_path: str, drawing_number: str) -> dict:
    """
    Extract data from a single structural drawing.

    Args:
        sheet_id: Sheet ID from database
        file_path: Path to PDF file
        drawing_number: Drawing number

    Returns:
        Dictionary with extraction results
    """
    start_time = time.time()
    result = {
        "sheet_id": sheet_id,
        "drawing_number": drawing_number,
        "status": "pending",
        "model_used": "sonnet",
        "confidence": 0.0,
        "counts": {},
        "errors": [],
        "processing_time_ms": 0
    }

    try:
        # Extract text from PDF
        logger.info(f"Extracting text from {drawing_number}...")
        pdf_path = Path(file_path)

        if not pdf_path.exists():
            result["status"] = "failed"
            result["errors"].append(f"File not found: {file_path}")
            return result

        text = extract_pdf_text(pdf_path)

        if not text.strip():
            result["status"] = "failed"
            result["errors"].append("No text extracted from PDF")
            return result

        logger.info(f"Extracted {len(text)} characters from {drawing_number}")

        # Build prompt and call model
        logger.info(f"Calling AI model for {drawing_number}...")
        prompt = build_structural_prompt(text, drawing_number)
        response = call_model(prompt, model="sonnet")

        # Parse response
        logger.info(f"Parsing response for {drawing_number}...")
        data = parse_extraction_response(response)

        # Calculate overall confidence
        all_items = (
            data.get("supports", []) +
            data.get("notes", []) +
            data.get("dimensions", []) +
            data.get("holes", [])
        )

        if all_items:
            confidences = [item.get("confidence", 0.7) for item in all_items]
            avg_confidence = sum(confidences) / len(confidences)
            result["confidence"] = avg_confidence

        # Store in database
        logger.info(f"Storing extraction results for {drawing_number}...")
        with get_db() as conn:
            counts = store_structural_extraction(conn, sheet_id, drawing_number, data)
            result["counts"] = counts

            # Update sheet metadata
            conn.execute("""
                UPDATE sheets
                SET extracted_at = CURRENT_TIMESTAMP,
                    quality_score = ?,
                    complexity = 'medium',
                    extraction_model = 'sonnet',
                    drawing_type = 'Structural'
                WHERE id = ?
            """, (result["confidence"], sheet_id))

            conn.commit()

        result["status"] = "success"
        logger.info(f"Successfully extracted {drawing_number}: {counts}")

    except Exception as e:
        result["status"] = "failed"
        result["errors"].append(str(e))
        logger.error(f"Extraction failed for {drawing_number}: {e}", exc_info=True)

    result["processing_time_ms"] = int((time.time() - start_time) * 1000)
    return result


def main():
    """Extract data from three structural sheets."""

    sheets = [
        (681, "D:/Projects/07609-Freshpet/Structural/SF1214-PARTIAL-ELEVATED-FLOOR-FIRE-PROTECTION-HOLES-PLAN---AREA-2-&-4-Rev.1.pdf",
         "SF1214-PARTIAL-ELEVATED-FLOOR-FIRE-PROTECTION-HOLES-PLAN---AREA-2-&-4"),
        (682, "D:/Projects/07609-Freshpet/Structural/SF1461-PARTIAL-IMP-HANGER-PLAN---AREA-6-Rev.1.pdf",
         "SF1461-PARTIAL-IMP-HANGER-PLAN---AREA-6"),
        (683, "D:/Projects/07609-Freshpet/Structural/SK1101-OVERALL-SLAB-PLAN-W-FORKLIFT-TRAFFIC-Rev.1.pdf",
         "SK1101-OVERALL-SLAB-PLAN-W-FORKLIFT-TRAFFIC")
    ]

    results = []

    print("=" * 80)
    print("STRUCTURAL DRAWING EXTRACTION - Project 07609 Freshpet")
    print("=" * 80)
    print()

    for i, (sheet_id, file_path, drawing_number) in enumerate(sheets, 1):
        print(f"\n[{i}/3] Processing {drawing_number}...")
        print("-" * 80)

        result = extract_structural_sheet(sheet_id, file_path, drawing_number)
        results.append(result)

        # Display result
        print(f"Status: {result['status']}")
        print(f"Model: {result['model_used']}")
        print(f"Confidence: {result['confidence']:.2f}")
        print(f"Processing time: {result['processing_time_ms']} ms")

        if result['counts']:
            print("\nExtracted:")
            for key, count in result['counts'].items():
                if key != 'errors' and count > 0:
                    print(f"  - {key}: {count}")

        if result['errors']:
            print("\nErrors:")
            for error in result['errors']:
                print(f"  - {error}")

    # Summary
    print("\n" + "=" * 80)
    print("EXTRACTION SUMMARY")
    print("=" * 80)

    success_count = sum(1 for r in results if r['status'] == 'success')
    failed_count = sum(1 for r in results if r['status'] == 'failed')

    print(f"\nSheets processed: {len(results)}")
    print(f"Successful: {success_count}")
    print(f"Failed: {failed_count}")

    # Aggregate counts
    total_counts = {}
    for result in results:
        if result['status'] == 'success':
            for key, count in result['counts'].items():
                if key != 'errors':
                    total_counts[key] = total_counts.get(key, 0) + count

    if total_counts:
        print("\nTotal items extracted:")
        for key, count in sorted(total_counts.items()):
            if count > 0:
                print(f"  - {key}: {count}")

    # Overall stats
    avg_confidence = sum(r['confidence'] for r in results if r['status'] == 'success') / max(success_count, 1)
    total_time = sum(r['processing_time_ms'] for r in results)

    print(f"\nAverage confidence: {avg_confidence:.2f}")
    print(f"Total processing time: {total_time / 1000:.1f} seconds")

    print("\n" + "=" * 80)

    return 0 if failed_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
