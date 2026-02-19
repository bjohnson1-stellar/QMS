"""
Refrigeration Drawing Extraction Agent.

Extracts structured data from refrigeration plan drawings including:
- Refrigerant lines (suction, discharge, liquid, hot gas)
- Equipment (compressors, evaporators, condensers, vessels)
- Instruments (pressure, temperature, level transmitters)
- Valves and fittings
- Pipe sizes, materials, and specifications
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
class RefrigExtractionResult:
    """Result of extracting a single refrigeration drawing."""
    sheet_id: int
    drawing_number: str
    status: str = "pending"  # success, partial, failed
    confidence: float = 0.0
    lines: List[Dict] = field(default_factory=list)
    equipment: List[Dict] = field(default_factory=list)
    instruments: List[Dict] = field(default_factory=list)
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
    """Build extraction prompt for refrigeration drawings."""
    return f"""Extract all structured data from this refrigeration plan drawing: {drawing_number}

This is a {drawing_type} drawing. Focus on extracting the following:

## 1. REFRIGERANT LINES
For each refrigerant pipe line shown, extract:
- line_number: Line tag/number (e.g., "LS-101", "LD-202", "LHG-301")
- size: Pipe size (e.g., "2\"", "3\"", "4\"", "6\"")
- service: Line service type (SUCTION, DISCHARGE, LIQUID, HOT GAS, DEFROST)
- material: Pipe material (SCH 40 SMLS STL, SCH 80, etc.)
- spec_class: Specification or class if shown
- refrigerant: Refrigerant type (NH3, R-507, R-404A, etc.) if indicated
- from_location: Start point or equipment connection
- to_location: End point or equipment connection
- insulation: Insulation type or thickness if shown
- slope: Pipe slope requirement if noted
- notes: Special requirements or observations

Common line service abbreviations:
- LS = Liquid Suction
- LD = Liquid Discharge
- LHG = Liquid Hot Gas
- SR = Suction Riser
- DR = Discharge Riser

## 2. EQUIPMENT
For each piece of refrigeration equipment on the plan, extract:
- tag: Equipment tag (e.g., "COMP-1", "EVAP-101", "COND-201", "REC-1")
- equipment_type: Type (COMPRESSOR, EVAPORATOR, CONDENSER, RECEIVER, VESSEL, PUMP, etc.)
- description: Equipment description or name
- location: Physical location, grid reference, or area
- capacity: Capacity rating if shown (tons, HP, CFM, etc.)
- notes: Special requirements or observations

Common equipment types:
- COMP = Compressor
- EVAP = Evaporator / Unit Cooler
- COND = Condenser
- REC = Receiver
- VES = Pressure Vessel
- PMP = Pump

## 3. INSTRUMENTS
For each instrument or control device, extract:
- tag: Instrument tag (e.g., "PT-101", "TT-202", "LT-301", "PSV-401")
- instrument_type: Type (PRESSURE TRANSMITTER, TEMPERATURE TRANSMITTER, LEVEL TRANSMITTER, PRESSURE SWITCH, RELIEF VALVE, CONTROL VALVE, etc.)
- service: Associated line or equipment service
- loop_number: Control loop number if shown
- location: Physical location or grid reference
- set_point: Set point value if shown
- notes: Special requirements

Common instrument prefixes:
- PT = Pressure Transmitter
- TT = Temperature Transmitter
- LT = Level Transmitter
- PSV = Pressure Safety Valve
- PRV = Pressure Relief Valve
- PCV = Pressure Control Valve
- TCV = Temperature Control Valve

## 4. GENERAL NOTES
Extract any important general notes, legends, or special requirements that appear on the drawing.

Return your answer as valid JSON with this structure:
{{
  "lines": [{{
    "line_number": "...",
    "size": "...",
    "service": "...",
    "material": "...",
    "spec_class": null,
    "refrigerant": "...",
    "from_location": "...",
    "to_location": "...",
    "insulation": null,
    "slope": null,
    "notes": null,
    "confidence": 0.0-1.0
  }}],
  "equipment": [{{
    "tag": "...",
    "equipment_type": "...",
    "description": "...",
    "location": null,
    "capacity": null,
    "notes": null,
    "confidence": 0.0-1.0
  }}],
  "instruments": [{{
    "tag": "...",
    "instrument_type": "...",
    "service": null,
    "loop_number": null,
    "location": null,
    "set_point": null,
    "notes": null,
    "confidence": 0.0-1.0
  }}],
  "notes": ["general notes or observations"],
  "confidence": 0.0-1.0 overall confidence score
}}

IMPORTANT:
- Only extract data you can clearly see in the drawing
- Use null for fields that are not visible or not applicable
- Include confidence: 0.0-1.0 for uncertain values in each item
- Note any ambiguities or unclear items in the notes array
- Focus on accuracy over completeness
- If you cannot read a line number or tag clearly, note it with "??" and mark confidence low
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
            "lines": [],
            "equipment": [],
            "instruments": [],
            "notes": [f"Parse error: {e}"],
            "confidence": 0.0,
        }


def extract_refrigeration_drawing(
    sheet_id: int,
    pdf_path: Path,
    drawing_number: str,
    model: str = "sonnet",
    dry_run: bool = False,
) -> RefrigExtractionResult:
    """
    Extract data from a refrigeration drawing PDF.

    Args:
        sheet_id: Sheet ID from sheets table
        pdf_path: Path to PDF file
        drawing_number: Drawing number for logging
        model: AI model to use (sonnet, opus)
        dry_run: If True, don't write to database

    Returns:
        RefrigExtractionResult with extracted data
    """
    start_time = time.time()

    result = RefrigExtractionResult(
        sheet_id=sheet_id,
        drawing_number=drawing_number,
        extraction_model=model,
    )

    try:
        # Determine drawing type from drawing number
        drawing_type = "Refrigeration Plan"
        drawing_upper = drawing_number.upper()

        if "ISO" in drawing_upper or "ISOMETRIC" in drawing_upper:
            drawing_type = "Isometric"
        elif "PLAN" in drawing_upper:
            drawing_type = "Refrigeration Plan"
        elif "SECTION" in drawing_upper or "DETAIL" in drawing_upper:
            drawing_type = "Section/Detail"
        elif "SCHEDULE" in drawing_upper:
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
        result.lines = data.get("lines", [])
        result.equipment = data.get("equipment", [])
        result.instruments = data.get("instruments", [])
        result.notes = data.get("notes", [])
        result.confidence = data.get("confidence", 0.7)

        # Calculate counts
        total_items = (
            len(result.lines) +
            len(result.equipment) +
            len(result.instruments)
        )

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
        "Extraction %s: %s - %d lines, %d equipment, %d instruments (%.1fs)",
        result.status,
        drawing_number,
        len(result.lines),
        len(result.equipment),
        len(result.instruments),
        result.processing_time_ms / 1000,
    )

    return result


def _store_extraction(result: RefrigExtractionResult) -> None:
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
                "low" if len(result.lines) < 10 else ("medium" if len(result.lines) < 30 else "high"),
                result.sheet_id,
            ),
        )

        # Store lines
        for line in result.lines:
            conn.execute(
                """INSERT INTO lines (
                    sheet_id, line_number, size, service, material,
                    spec_class, refrigerant, from_location, to_location,
                    confidence
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    result.sheet_id,
                    line.get("line_number"),
                    line.get("size"),
                    line.get("service"),
                    line.get("material"),
                    line.get("spec_class"),
                    line.get("refrigerant"),
                    line.get("from_location"),
                    line.get("to_location"),
                    line.get("confidence", result.confidence),
                ),
            )

        # Store equipment
        for equip in result.equipment:
            conn.execute(
                """INSERT INTO equipment (
                    sheet_id, tag, equipment_type, description, confidence
                ) VALUES (?, ?, ?, ?, ?)""",
                (
                    result.sheet_id,
                    equip.get("tag"),
                    equip.get("equipment_type"),
                    equip.get("description"),
                    equip.get("confidence", result.confidence),
                ),
            )

        # Store instruments
        for inst in result.instruments:
            conn.execute(
                """INSERT INTO instruments (
                    sheet_id, tag, instrument_type, service, loop_number,
                    location, extraction_notes, confidence
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    result.sheet_id,
                    inst.get("tag"),
                    inst.get("instrument_type"),
                    inst.get("service"),
                    inst.get("loop_number"),
                    inst.get("location"),
                    inst.get("notes"),
                    inst.get("confidence", result.confidence),
                ),
            )

        # Store extraction notes
        for note in result.notes:
            # Check if extraction_notes table exists
            table_check = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='extraction_notes'"
            ).fetchone()

            if table_check:
                conn.execute(
                    """INSERT INTO extraction_notes (
                        sheet_id, note_type, description, confidence
                    ) VALUES (?, ?, ?, ?)""",
                    (result.sheet_id, "extraction_note", note, result.confidence),
                )

        conn.commit()
        logger.info("Stored extraction for sheet_id=%d", result.sheet_id)


def extract_batch(
    sheet_ids: List[int],
    model: str = "sonnet",
    dry_run: bool = False
) -> List[RefrigExtractionResult]:
    """
    Extract data from multiple refrigeration sheets.

    Args:
        sheet_ids: List of sheet IDs to process
        model: AI model to use
        dry_run: If True, don't write to database

    Returns:
        List of RefrigExtractionResult
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
            result = extract_refrigeration_drawing(
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
