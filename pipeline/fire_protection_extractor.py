"""
Fire Protection Drawing Extraction Agent.

Extracts structured data from fire protection drawings including:
- Sprinkler heads and coverage
- Fire protection systems (risers, zones)
- Piping (mains, branch lines, sizes)
- Valves and control equipment
- Coverage areas and hazard classifications
"""

import base64
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from qms.core import get_db, get_logger

logger = get_logger(__name__)


@dataclass
class ExtractionResult:
    """Result of extracting a single fire protection drawing."""
    sheet_id: int
    drawing_number: str
    status: str = "pending"  # success, partial, failed
    confidence: float = 0.0
    equipment: List[Dict] = field(default_factory=list)
    systems: List[Dict] = field(default_factory=list)
    piping: List[Dict] = field(default_factory=list)
    valves: List[Dict] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    processing_time_ms: int = 0
    extraction_model: str = "sonnet"


def _encode_pdf_for_vision(pdf_path: Path) -> str:
    """Convert PDF to base64 for Claude vision API."""
    with open(pdf_path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8")


def _call_claude_vision(pdf_base64: str, prompt: str, model: str = "sonnet") -> str:
    """
    Call Claude vision API with PDF document.

    Args:
        pdf_base64: Base64-encoded PDF
        prompt: Extraction prompt
        model: Model name (sonnet, opus)

    Returns:
        Model response text
    """
    try:
        import anthropic
    except ImportError:
        raise ImportError(
            "anthropic SDK required. Install with: pip install anthropic>=0.25.0"
        )

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
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": pdf_base64,
                        },
                    },
                    {
                        "type": "text",
                        "text": prompt,
                    },
                ],
            }
        ],
    )

    return response.content[0].text


def _build_extraction_prompt(drawing_number: str, drawing_type: str) -> str:
    """Build extraction prompt for fire protection drawings."""
    return f"""Extract all structured data from this fire protection drawing: {drawing_number}

This is a {drawing_type} showing fire protection systems. Focus on extracting the following:

## 1. FIRE PROTECTION EQUIPMENT
For each piece of equipment (sprinkler heads, standpipes, hose stations, etc.), extract:

**Sprinkler Heads:**
- equipment_type: "Sprinkler Head" (specify type: upright, pendent, sidewall, concealed)
- location: Room name, area designation, or grid location
- zone_served: Fire protection zone designation
- size: Orifice size if specified (e.g., "1/2 inch K5.6")
- system_type: System type (wet, dry, preaction, deluge)
- quantity: Number of heads in this location/type
- area_designation: Coverage area or hazard class
- grid_location: Grid reference if shown
- notes: Temperature rating, response type, finish, special requirements

**Other Equipment:**
- equipment_type: Fire pump, standpipe, hose station, fire extinguisher, alarm panel, etc.
- location: Physical location
- zone_served: Zones or areas served
- size: Equipment size/capacity
- system_type: Associated system
- notes: Specifications, requirements

## 2. FIRE PROTECTION SYSTEMS
For each fire protection system (risers, zones), extract:
- system_name: System designation (e.g., "Riser 5A", "Zone 1", "Building Main")
- system_type: Type (wet pipe, dry pipe, preaction, deluge, standpipe, etc.)
- riser_area: Area or building section served
- pipe_size: Main pipe size feeding this system
- zone_count: Number of zones if a riser/main system
- zones_served: List or description of zones served
- notes: Coverage details, special requirements

## 3. FIRE PROTECTION PIPING
For visible piping (mains, branch lines, feed mains), extract:
- line_type: Type of line (main, branch, feed, cross-main, riser)
- size: Pipe size (e.g., "4 inch", "2-1/2 inch", "1 inch")
- from_location: Starting point (e.g., "Riser 5A", "Underground Main", "Grid B-3")
- to_location: Ending point or area served
- description: Additional details (e.g., "Branch line serving Zone 1 West")

## 4. FIRE PROTECTION VALVES
For valves shown on the drawing:
- valve_type: Type (OS&Y gate, butterfly, check, alarm, PIV, FDC, etc.)
- size: Valve size
- location_description: Where the valve is located
- notes: Valve function, accessibility, supervision requirements

## 5. DRAWING NOTES
Extract any general notes, legends, or coverage specifications that apply to the drawing.

Return your answer as valid JSON with this structure:
{{
  "equipment": [
    {{
      "equipment_type": "Sprinkler Head - Pendent",
      "location": "Processing Room West",
      "zone_served": "Zone 1",
      "size": "1/2\" K5.6",
      "system_type": "Wet Pipe",
      "quantity": 24,
      "area_designation": "Ordinary Hazard Group 2",
      "grid_location": "B3-D5",
      "notes": "165°F quick response, chrome finish",
      "confidence": 0.95
    }}
  ],
  "systems": [
    {{
      "system_name": "Riser 5A",
      "system_type": "Wet Pipe Sprinkler",
      "riser_area": "West Processing",
      "pipe_size": "4 inch",
      "zone_count": 2,
      "zones_served": "Zone 1 West, Zone 2 West",
      "confidence": 0.92
    }}
  ],
  "piping": [
    {{
      "line_type": "Main",
      "size": "4 inch",
      "from_location": "Riser 5A",
      "to_location": "Branch Lines Zone 1",
      "description": "Primary feed main to west processing area",
      "confidence": 0.88
    }}
  ],
  "valves": [
    {{
      "valve_type": "OS&Y Gate Valve",
      "size": "4 inch",
      "location_description": "Riser room, labeled FP-5A-01",
      "notes": "Electrically supervised, normally open",
      "confidence": 0.90
    }}
  ],
  "notes": ["Drawing shows wet pipe sprinkler system", "Coverage per NFPA 13"],
  "confidence": 0.0-1.0 overall confidence score
}}

IMPORTANT:
- Only extract data you can clearly see in the drawing
- Use null for fields that are not visible or not applicable
- Include per-field confidence: 0.0-1.0 for uncertain values
- For sprinkler head counts, count carefully or extract from schedules
- Pay attention to zone designations and coverage areas
- Note pipe sizes carefully - fire protection uses specific sizing
- Extract valve supervision/monitoring requirements
- Focus on accuracy over completeness
- If this is a sprinkler head layout plan, focus on head counts and spacing
- If this is a riser diagram, focus on systems, piping, and valves
"""


def _parse_extraction_response(response_text: str) -> Dict[str, Any]:
    """Parse JSON response from Claude."""
    # Try to extract JSON from response
    response_text = response_text.strip()

    # Remove markdown code fences if present
    if response_text.startswith("```json"):
        response_text = response_text[7:]
    if response_text.startswith("```"):
        response_text = response_text[3:]
    if response_text.endswith("```"):
        response_text = response_text[:-3]

    response_text = response_text.strip()

    try:
        data = json.loads(response_text)
        return data
    except json.JSONDecodeError as e:
        logger.error("Failed to parse extraction response: %s", e)
        logger.debug("Response text: %s", response_text[:500])
        return {
            "equipment": [],
            "systems": [],
            "piping": [],
            "valves": [],
            "notes": [f"Parse error: {e}"],
            "confidence": 0.0,
        }


def extract_fire_protection_drawing(
    sheet_id: int,
    pdf_path: Path,
    drawing_number: str,
    model: str = "sonnet",
    dry_run: bool = False,
) -> ExtractionResult:
    """
    Extract data from a fire protection drawing PDF.

    Args:
        sheet_id: Sheet ID from sheets table
        pdf_path: Path to PDF file
        drawing_number: Drawing number for logging
        model: AI model to use (sonnet, opus)
        dry_run: If True, don't write to database

    Returns:
        ExtractionResult with extracted data
    """
    start_time = time.time()

    result = ExtractionResult(
        sheet_id=sheet_id,
        drawing_number=drawing_number,
        extraction_model=model,
    )

    try:
        # Determine drawing type from drawing number
        drawing_type = "Fire Protection Plan"
        dn_upper = drawing_number.upper()

        if "SPRINKLER" in dn_upper or "HEADS" in dn_upper:
            drawing_type = "Sprinkler Head Layout"
        elif "RISER" in dn_upper:
            drawing_type = "Riser Diagram"
        elif "DETAIL" in dn_upper:
            drawing_type = "Detail Drawing"
        elif "SCHEDULE" in dn_upper:
            drawing_type = "Equipment Schedule"

        logger.info("Extracting %s (%s) using %s...", drawing_number, drawing_type, model)

        # Encode PDF
        pdf_base64 = _encode_pdf_for_vision(pdf_path)

        # Build prompt and call Claude
        prompt = _build_extraction_prompt(drawing_number, drawing_type)
        response = _call_claude_vision(pdf_base64, prompt, model)

        # Parse response
        data = _parse_extraction_response(response)

        # Populate result
        result.equipment = data.get("equipment", [])
        result.systems = data.get("systems", [])
        result.piping = data.get("piping", [])
        result.valves = data.get("valves", [])
        result.notes = data.get("notes", [])
        result.confidence = data.get("confidence", 0.7)

        # Calculate status
        total_items = len(result.equipment) + len(result.systems) + len(result.piping) + len(result.valves)

        if total_items > 0:
            result.status = "success"
        else:
            result.status = "partial"
            result.notes.append("No items extracted - may be title sheet or non-data drawing")

        # Store in database
        if not dry_run:
            _store_extraction(result)

    except Exception as e:
        result.status = "failed"
        result.errors.append(str(e))
        logger.error("Extraction failed for %s: %s", drawing_number, e)

    result.processing_time_ms = int((time.time() - start_time) * 1000)

    logger.info(
        "Extraction %s: %s - %d equipment, %d systems, %d piping, %d valves (%.1fs)",
        result.status,
        drawing_number,
        len(result.equipment),
        len(result.systems),
        len(result.piping),
        len(result.valves),
        result.processing_time_ms / 1000,
    )

    return result


def _store_extraction(result: ExtractionResult) -> None:
    """Store extraction results in database."""
    with get_db() as conn:
        # Update sheet record
        conn.execute(
            """UPDATE sheets
               SET extracted_at = CURRENT_TIMESTAMP,
                   extraction_model = ?,
                   quality_score = ?,
                   complexity = ?
               WHERE id = ?""",
            (
                result.extraction_model,
                result.confidence,
                "simple" if len(result.equipment) + len(result.systems) < 10 else "medium",
                result.sheet_id,
            ),
        )

        # Store equipment
        for equip in result.equipment:
            conn.execute(
                """INSERT INTO fire_protection_equipment (
                    sheet_id, equipment_type, location, zone_served, size,
                    system_type, quantity, area_designation, grid_location,
                    notes, confidence
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    result.sheet_id,
                    equip.get("equipment_type"),
                    equip.get("location"),
                    equip.get("zone_served"),
                    equip.get("size"),
                    equip.get("system_type"),
                    equip.get("quantity", 1),
                    equip.get("area_designation"),
                    equip.get("grid_location"),
                    equip.get("notes"),
                    equip.get("confidence", result.confidence),
                ),
            )

        # Store systems
        for system in result.systems:
            conn.execute(
                """INSERT INTO fire_protection_systems (
                    sheet_id, system_name, system_type, riser_area,
                    pipe_size, zone_count, zones_served, confidence
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    result.sheet_id,
                    system.get("system_name"),
                    system.get("system_type"),
                    system.get("riser_area"),
                    system.get("pipe_size"),
                    system.get("zone_count"),
                    system.get("zones_served"),
                    system.get("confidence", result.confidence),
                ),
            )

        # Store piping
        for pipe in result.piping:
            conn.execute(
                """INSERT INTO fire_protection_piping (
                    sheet_id, line_type, size, from_location,
                    to_location, description, confidence
                ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    result.sheet_id,
                    pipe.get("line_type"),
                    pipe.get("size"),
                    pipe.get("from_location"),
                    pipe.get("to_location"),
                    pipe.get("description"),
                    pipe.get("confidence", result.confidence),
                ),
            )

        # Store valves
        for valve in result.valves:
            conn.execute(
                """INSERT INTO fire_protection_valves (
                    sheet_id, valve_type, size, location_description,
                    notes, confidence
                ) VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    result.sheet_id,
                    valve.get("valve_type"),
                    valve.get("size"),
                    valve.get("location_description"),
                    valve.get("notes"),
                    valve.get("confidence", result.confidence),
                ),
            )

        # Store extraction notes
        for note in result.notes:
            conn.execute(
                """INSERT INTO fire_protection_notes (
                    sheet_id, note_text
                ) VALUES (?, ?)""",
                (result.sheet_id, note),
            )

        conn.commit()
        logger.info("Stored extraction for sheet_id=%d", result.sheet_id)


def extract_batch(sheet_ids: List[int], model: str = "sonnet", dry_run: bool = False) -> List[ExtractionResult]:
    """
    Extract data from multiple sheets.

    Args:
        sheet_ids: List of sheet IDs to process
        model: AI model to use
        dry_run: If True, don't write to database

    Returns:
        List of ExtractionResult
    """
    results = []

    with get_db(readonly=True) as conn:
        for i, sheet_id in enumerate(sheet_ids, 1):
            row = conn.execute(
                "SELECT drawing_number, file_path FROM sheets WHERE id = ?",
                (sheet_id,),
            ).fetchone()

            if not row:
                logger.warning("Sheet ID %d not found", sheet_id)
                continue

            drawing_number = row["drawing_number"]
            file_path = Path(row["file_path"])

            if not file_path.exists():
                logger.error("File not found: %s", file_path)
                continue

            logger.info("[%d/%d] Processing %s...", i, len(sheet_ids), drawing_number)
            result = extract_fire_protection_drawing(
                sheet_id, file_path, drawing_number, model, dry_run
            )
            results.append(result)

    # Summary
    success = sum(1 for r in results if r.status == "success")
    partial = sum(1 for r in results if r.status == "partial")
    failed = sum(1 for r in results if r.status == "failed")

    logger.info(
        "Batch complete: %d success, %d partial, %d failed (of %d total)",
        success, partial, failed, len(results),
    )

    return results
