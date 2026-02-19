"""
Structural drawing extraction script for Freshpet project.

Extracts structural members, dimensions, and notes from framing plan drawings.
"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add QMS to path if running standalone
sys.path.insert(0, str(Path(__file__).parent))

from qms.core import get_db, get_logger

logger = get_logger("qms.structural_extraction")


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


def build_structural_extraction_prompt(text: str, drawing_number: str) -> str:
    """Build extraction prompt for structural framing plan drawings."""
    return f"""Extract all structural framing data from this drawing: {drawing_number}

This is a ROOF RAISED PLATFORM FRAMING PLAN. Extract the following information:

For each STRUCTURAL MEMBER (beams, joists, girders, columns), provide:
- Member mark/ID (e.g., B1, J12, G3, C4)
- Member type (beam, joist, girder, column, brace, etc.)
- Size/section (e.g., W12x26, HSS6x6x3/8, L4x4x1/2, C8x11.5)
- Material specification (e.g., A992, A36, A500 Grade B)
- Length or span if shown
- Location/grid reference (e.g., between Grid A-B at Line 3)
- Quantity if shown

For each CONNECTION detail shown:
- Connection ID or mark
- Type (moment connection, shear connection, base plate, etc.)
- Members being connected
- Fastener specification (bolts, welds)
- Reference to detail drawing if shown

For each DIMENSION or SPACING:
- Dimension value
- What it measures (span, spacing, offset, elevation)
- Grid line or reference point

For any GENERAL NOTES or SPECIFICATIONS:
- Note text
- Category (material spec, welding requirements, installation notes, etc.)

Return the data as a JSON object with this exact structure:
{{
  "members": [
    {{
      "mark": "string",
      "member_type": "string",
      "size": "string",
      "material": "string or null",
      "length": "string or null",
      "location": "string",
      "quantity": "number or null",
      "confidence": 0.0-1.0
    }}
  ],
  "connections": [
    {{
      "connection_id": "string",
      "connection_type": "string",
      "members": "string",
      "fasteners": "string or null",
      "detail_reference": "string or null",
      "confidence": 0.0-1.0
    }}
  ],
  "dimensions": [
    {{
      "value": "string",
      "description": "string",
      "reference": "string or null",
      "confidence": 0.0-1.0
    }}
  ],
  "notes": [
    {{
      "note_type": "string (GENERAL, MATERIAL, WELDING, INSTALLATION, OTHER)",
      "note_text": "string",
      "confidence": 0.0-1.0
    }}
  ],
  "drawing_info": {{
    "drawing_number": "{drawing_number}",
    "drawing_title": "string",
    "grid_references": ["list of grid line identifiers if shown"],
    "complexity": "simple|medium|complex"
  }}
}}

Confidence scoring:
- 1.0 = Clear, unambiguous text
- 0.8-0.9 = Standard format, minor interpretation needed
- 0.6-0.7 = Partially unclear or non-standard format
- Below 0.6 = Ambiguous or difficult to read

If a field cannot be determined from the text, use null (not empty string).
Focus on accuracy over quantity - only extract data you can read clearly.

Drawing text:
{text}
"""


def parse_extraction_response(response: str) -> Dict[str, Any]:
    """Parse JSON response from AI model."""
    # Try to find JSON in the response
    start = response.find("{")
    end = response.rfind("}") + 1

    if start == -1 or end == 0:
        raise ValueError("No JSON found in response")

    json_str = response[start:end]
    return json.loads(json_str)


def store_extraction(
    conn,
    sheet_id: int,
    data: Dict[str, Any],
    extraction_model: str,
    processing_time_ms: int
) -> Dict[str, int]:
    """Store extracted structural data in the database."""
    counts = {
        "members": 0,
        "connections": 0,
        "dimensions": 0,
        "notes": 0,
    }

    # Store structural members in drawing_details table
    members = data.get("members", [])
    for member in members:
        detail_id = member.get("mark", "UNKNOWN")
        description = f"{member.get('member_type', 'UNKNOWN')} - {member.get('size', 'UNKNOWN')}"
        materials = member.get("material")
        dimensions = f"Length: {member.get('length')}" if member.get("length") else None
        if member.get("quantity"):
            dimensions = f"{dimensions}, Qty: {member['quantity']}" if dimensions else f"Qty: {member['quantity']}"

        notes_text = f"Location: {member.get('location')}" if member.get("location") else None
        confidence = member.get("confidence", 0.7)

        conn.execute(
            """INSERT INTO drawing_details
               (sheet_id, detail_id, detail_title, detail_type, description,
                materials, dimensions, notes, confidence)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                sheet_id,
                detail_id,
                f"{member.get('member_type', '')} {detail_id}".strip(),
                "STRUCTURAL_MEMBER",
                description,
                materials,
                dimensions,
                notes_text,
                confidence,
            )
        )
        counts["members"] += 1

    # Store connections in drawing_details
    connections = data.get("connections", [])
    for conn_data in connections:
        detail_id = conn_data.get("connection_id", "CONN")
        description = conn_data.get("connection_type", "Connection")

        notes_parts = []
        if conn_data.get("members"):
            notes_parts.append(f"Members: {conn_data['members']}")
        if conn_data.get("fasteners"):
            notes_parts.append(f"Fasteners: {conn_data['fasteners']}")
        if conn_data.get("detail_reference"):
            notes_parts.append(f"Detail: {conn_data['detail_reference']}")

        confidence = conn_data.get("confidence", 0.7)

        conn.execute(
            """INSERT INTO drawing_details
               (sheet_id, detail_id, detail_title, detail_type, description,
                notes, confidence)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                sheet_id,
                detail_id,
                f"Connection {detail_id}",
                "CONNECTION",
                description,
                "; ".join(notes_parts) if notes_parts else None,
                confidence,
            )
        )
        counts["connections"] += 1

    # Store dimensions in drawing_details
    dimensions = data.get("dimensions", [])
    for dim in dimensions:
        dim_value = dim.get("value", "")
        description = dim.get("description", "")
        reference = dim.get("reference")
        confidence = dim.get("confidence", 0.7)

        detail_title = f"Dimension: {dim_value}"
        notes_text = f"Reference: {reference}" if reference else None

        conn.execute(
            """INSERT INTO drawing_details
               (sheet_id, detail_id, detail_title, detail_type, description,
                dimensions, notes, confidence)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                sheet_id,
                f"DIM-{counts['dimensions'] + 1}",
                detail_title,
                "DIMENSION",
                description,
                dim_value,
                notes_text,
                confidence,
            )
        )
        counts["dimensions"] += 1

    # Store notes in drawing_notes
    drawing_info = data.get("drawing_info", {})
    drawing_number = drawing_info.get("drawing_number", "UNKNOWN")

    notes = data.get("notes", [])
    for note in notes:
        note_type = note.get("note_type", "OTHER")
        note_text = note.get("note_text", "")

        conn.execute(
            """INSERT INTO drawing_notes
               (sheet_id, drawing_number, note_type, note_text, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (
                sheet_id,
                drawing_number,
                note_type,
                note_text,
                datetime.now().isoformat(),
            )
        )
        counts["notes"] += 1

    # Update sheet with extraction metadata
    complexity = drawing_info.get("complexity", "medium")
    avg_confidence = sum(
        m.get("confidence", 0.7) for m in members + connections + dimensions + notes
    ) / max(len(members) + len(connections) + len(dimensions) + len(notes), 1)

    conn.execute(
        """UPDATE sheets
           SET extracted_at = ?,
               extraction_model = ?,
               complexity = ?,
               quality_score = ?,
               drawing_type = 'STRUCTURAL_FRAMING'
           WHERE id = ?""",
        (
            datetime.now().isoformat(),
            extraction_model,
            complexity,
            avg_confidence,
            sheet_id,
        )
    )

    logger.info(
        f"Stored extraction: {counts['members']} members, {counts['connections']} connections, "
        f"{counts['dimensions']} dimensions, {counts['notes']} notes (avg confidence: {avg_confidence:.2f})"
    )

    return counts


def extract_sheet(sheet_id: int, file_path: str, drawing_number: str, model: str = "sonnet") -> Dict[str, Any]:
    """Extract data from a single structural drawing sheet."""
    start_time = time.time()

    logger.info(f"Starting extraction for sheet {sheet_id}: {drawing_number}")
    logger.info(f"File: {file_path}")

    # Step 1: Extract text from PDF
    logger.info("Extracting text from PDF...")
    pdf_text = extract_pdf_text(Path(file_path))

    if not pdf_text.strip():
        raise ValueError("No text extracted from PDF")

    logger.info(f"Extracted {len(pdf_text)} characters of text")

    # Step 2: Build prompt and call AI model
    logger.info(f"Building extraction prompt and calling {model} model...")
    prompt = build_structural_extraction_prompt(pdf_text, drawing_number)
    response = call_model(prompt, model)

    # Step 3: Parse response
    logger.info("Parsing extraction response...")
    data = parse_extraction_response(response)

    # Step 4: Store in database
    logger.info("Storing extraction data...")
    with get_db() as conn:
        counts = store_extraction(
            conn,
            sheet_id,
            data,
            model,
            int((time.time() - start_time) * 1000)
        )
        conn.commit()

    processing_time = time.time() - start_time

    result = {
        "sheet_id": sheet_id,
        "drawing_number": drawing_number,
        "status": "success",
        "counts": counts,
        "processing_time_sec": round(processing_time, 2),
        "complexity": data.get("drawing_info", {}).get("complexity", "unknown"),
    }

    logger.info(
        f"Extraction complete for {drawing_number}: "
        f"{counts['members']} members, {counts['connections']} connections, "
        f"{counts['dimensions']} dimensions, {counts['notes']} notes "
        f"({processing_time:.1f}s)"
    )

    return result


def main():
    """Extract data from specified Freshpet structural sheets."""

    sheets = [
        {
            "id": 666,
            "drawing": "S1522-ENLARGED-ROOF-RAISED-PLATFORM-FRAMING-PLAN Rev 1",
            "path": r"D:\qms\data\projects\07609-Freshpet\Structural\S1522-ENLARGED-ROOF-RAISED-PLATFORM-FRAMING-PLAN-Rev.1.pdf"
        },
        {
            "id": 667,
            "drawing": "S1523-ENLARGED-ROOF-RAISED-PLATFORM-FRAMING-PLAN Rev 1",
            "path": r"D:\qms\data\projects\07609-Freshpet\Structural\S1523-ENLARGED-ROOF-RAISED-PLATFORM-FRAMING-PLAN-Rev.1.pdf"
        },
        {
            "id": 668,
            "drawing": "S1525-ENLARGED-ROOF-RAISED-PLATFORM-FRAMING-PLAN Rev 1",
            "path": r"D:\qms\data\projects\07609-Freshpet\Structural\S1525-ENLARGED-ROOF-RAISED-PLATFORM-FRAMING-PLAN-Rev.1.pdf"
        },
    ]

    logger.info("="*80)
    logger.info("Freshpet Structural Drawing Extraction")
    logger.info(f"Processing {len(sheets)} sheets")
    logger.info("="*80)

    results = []

    for i, sheet in enumerate(sheets, 1):
        logger.info(f"\n[{i}/{len(sheets)}] Processing {sheet['drawing']}...")

        try:
            result = extract_sheet(
                sheet_id=sheet["id"],
                file_path=sheet["path"],
                drawing_number=sheet["drawing"],
                model="sonnet"  # Use Sonnet for structural drawings (moderate complexity)
            )
            results.append(result)

        except Exception as e:
            logger.error(f"Failed to extract {sheet['drawing']}: {e}", exc_info=True)
            results.append({
                "sheet_id": sheet["id"],
                "drawing_number": sheet["drawing"],
                "status": "failed",
                "error": str(e),
            })

    # Summary
    logger.info("\n" + "="*80)
    logger.info("EXTRACTION SUMMARY")
    logger.info("="*80)

    success_count = sum(1 for r in results if r["status"] == "success")
    failed_count = len(results) - success_count

    logger.info(f"Total sheets: {len(results)}")
    logger.info(f"Successful: {success_count}")
    logger.info(f"Failed: {failed_count}")

    total_members = sum(r.get("counts", {}).get("members", 0) for r in results)
    total_connections = sum(r.get("counts", {}).get("connections", 0) for r in results)
    total_dimensions = sum(r.get("counts", {}).get("dimensions", 0) for r in results)
    total_notes = sum(r.get("counts", {}).get("notes", 0) for r in results)

    logger.info(f"\nTotal extracted:")
    logger.info(f"  Members: {total_members}")
    logger.info(f"  Connections: {total_connections}")
    logger.info(f"  Dimensions: {total_dimensions}")
    logger.info(f"  Notes: {total_notes}")

    for result in results:
        if result["status"] == "success":
            logger.info(
                f"\n{result['drawing_number']}: "
                f"{result['counts']['members']} members, "
                f"{result['counts']['connections']} connections, "
                f"{result['counts']['dimensions']} dimensions, "
                f"{result['counts']['notes']} notes "
                f"({result['processing_time_sec']}s)"
            )
        else:
            logger.error(f"\n{result['drawing_number']}: FAILED - {result.get('error')}")

    logger.info("\n" + "="*80)


if __name__ == "__main__":
    main()
