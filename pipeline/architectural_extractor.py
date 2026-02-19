"""
Architectural drawing data extraction.

Extracts data from architectural drawings including:
- Wall sections
- Building elevations
- Floor plans
- Detail drawings
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List
from qms.core import get_logger
from .extractor import extract_pdf_text, call_model

logger = get_logger("qms.pipeline.architectural_extractor")


def build_architectural_prompt(text: str, drawing_type: str) -> str:
    """
    Build extraction prompt for architectural drawings.

    Args:
        text: Extracted text from drawing.
        drawing_type: Type of architectural drawing.

    Returns:
        Extraction prompt for AI model.
    """
    return f"""Extract structured data from this architectural drawing (wall sections).

DRAWING TEXT:
{text}

Extract the following information:

DRAWING NOTES:
- General notes
- Material specifications
- Reference callouts
- Detail references

DETAILS (if shown):
- Detail number/ID
- Detail title
- Scale
- Material specifications
- Construction notes

ABBREVIATIONS (if shown):
- Abbreviation
- Full meaning

Return as JSON in this format:
{{
  "notes": [
    {{
      "note_type": "general|material|reference|construction",
      "note_text": "Full note text",
      "confidence": 0.95
    }}
  ],
  "details": [
    {{
      "detail_id": "1/A3111",
      "detail_title": "Typical Wall Section",
      "description": "Description of detail",
      "materials": "CMU, insulation, etc.",
      "notes": "Additional construction notes",
      "confidence": 0.90
    }}
  ],
  "abbreviations": [
    {{
      "abbreviation": "CMU",
      "full_text": "Concrete Masonry Unit",
      "confidence": 0.95
    }}
  ]
}}

IMPORTANT:
- Focus on construction-relevant information (materials, methods, specifications)
- Skip title block information (already captured)
- For unclear text, provide best interpretation and reduce confidence
- Confidence range: 0.0 (unreadable) to 1.0 (certain)
"""


def store_architectural_extraction(conn, sheet_id: int, data: Dict[str, Any]) -> Dict[str, int]:
    """
    Store extracted architectural data in database.

    Args:
        conn: Database connection.
        sheet_id: Sheet ID from sheets table.
        data: Extracted data dictionary.

    Returns:
        Counts of items stored by type.
    """
    counts = {"notes": 0, "details": 0, "abbreviations": 0}

    # Store general notes
    for note in data.get("notes", []):
        try:
            conn.execute("""
                INSERT INTO drawing_notes (
                    sheet_id, note_type, note_text
                ) VALUES (?, ?, ?)
            """, (
                sheet_id,
                note.get("note_type", "general"),
                note.get("note_text"),
            ))
            counts["notes"] += 1
        except Exception as e:
            logger.error("Failed to insert note: %s", e)

    # Store detail information
    for detail in data.get("details", []):
        try:
            conn.execute("""
                INSERT INTO drawing_details (
                    sheet_id, detail_id, detail_title, detail_type,
                    description, materials, notes, confidence
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                sheet_id,
                detail.get("detail_id"),
                detail.get("detail_title"),
                "wall_section",
                detail.get("description"),
                detail.get("materials"),
                detail.get("notes"),
                detail.get("confidence", 0.8),
            ))
            counts["details"] += 1
        except Exception as e:
            logger.error("Failed to insert detail %s: %s", detail.get("detail_id"), e)

    # Store abbreviations
    for abbr in data.get("abbreviations", []):
        try:
            conn.execute("""
                INSERT INTO drawing_abbreviations (
                    sheet_id, abbreviation, full_text, category, confidence
                ) VALUES (?, ?, ?, ?, ?)
            """, (
                sheet_id,
                abbr.get("abbreviation"),
                abbr.get("full_text"),
                "architectural",
                abbr.get("confidence", 0.9),
            ))
            counts["abbreviations"] += 1
        except Exception as e:
            logger.error("Failed to insert abbreviation %s: %s", abbr.get("abbreviation"), e)

    return counts


def extract_architectural_drawing(sheet_id: int, file_path: str, conn) -> Dict[str, Any]:
    """
    Extract data from an architectural drawing.

    Args:
        sheet_id: Sheet ID from database.
        file_path: Path to PDF file.
        conn: Database connection.

    Returns:
        Dictionary with extraction results.
    """
    import time
    start_time = time.time()

    result = {
        "sheet_id": sheet_id,
        "status": "pending",
        "notes": 0,
        "details": 0,
        "abbreviations": 0,
        "confidence": 0.0,
        "errors": [],
    }

    try:
        # Extract text from PDF
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

        logger.info("Extracting architectural data from sheet %d: %s", sheet_id, pdf_path.name)

        # Build prompt and call model (use Haiku for architectural details)
        prompt = build_architectural_prompt(text, "wall_section")
        response = call_model(prompt, model="haiku")

        # Parse JSON response
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group(0))
        else:
            data = {"notes": [], "details": [], "abbreviations": []}
            logger.warning("No JSON found in model response")

        # Store in database
        counts = store_architectural_extraction(conn, sheet_id, data)
        result["notes"] = counts["notes"]
        result["details"] = counts["details"]
        result["abbreviations"] = counts["abbreviations"]

        # Calculate confidence
        all_items = (
            data.get("notes", []) +
            data.get("details", []) +
            data.get("abbreviations", [])
        )
        if all_items:
            confidences = [item.get("confidence", 0.8) for item in all_items]
            result["confidence"] = sum(confidences) / len(confidences)
        else:
            result["confidence"] = 0.5  # Minimal extraction

        # Update sheet record
        conn.execute("""
            UPDATE sheets
            SET extracted_at = CURRENT_TIMESTAMP,
                quality_score = ?,
                extraction_model = 'haiku',
                drawing_type = 'Wall Section'
            WHERE id = ?
        """, (result["confidence"], sheet_id))

        result["status"] = "success"
        result["processing_time_ms"] = int((time.time() - start_time) * 1000)

        logger.info(
            "Sheet %d complete: %d notes, %d details, %d abbreviations (confidence: %.2f)",
            sheet_id, result["notes"], result["details"], result["abbreviations"], result["confidence"]
        )

    except Exception as e:
        result["status"] = "failed"
        result["errors"].append(str(e))
        logger.error("Architectural extraction error for sheet %d: %s", sheet_id, e, exc_info=True)

    return result
