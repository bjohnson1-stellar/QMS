"""
Utility Drawing Extraction Agent.

Extracts structured data from utility roof plan drawings including:
- Utility equipment (RTUs, chillers, condensers, pumps, fans)
- Equipment schedules with specifications
- Piping connections and sizes
- Electrical connections
- Mounting details and locations
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
    """Result of extracting a single utility drawing."""
    sheet_id: int
    drawing_number: str
    status: str = "pending"  # success, partial, failed
    confidence: float = 0.0
    equipment: List[Dict] = field(default_factory=list)
    piping: List[Dict] = field(default_factory=list)
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
    """Build extraction prompt for utility drawings."""
    return f"""Extract all structured data from this utility roof plan drawing: {drawing_number}

This is a {drawing_type} drawing showing rooftop utility equipment. Focus on extracting the following:

## 1. UTILITY EQUIPMENT
For each piece of equipment shown on the plan or in schedules, extract:

**Basic Info:**
- equipment_mark: Equipment designation (e.g., "RTU-1", "CH-1", "CU-1", "P-1")
- equipment_type: Type of equipment (RTU, Chiller, Condenser, Pump, Fan, etc.)
- location: Physical location or area designation
- qty: Quantity (usually 1, or higher if noted "2 QTY", etc.)

**Manufacturer & Model:**
- manufacturer: Manufacturer name
- model: Model number or designation
- capacity: Capacity rating with units (e.g., "5 TON", "100 GPM", "10,000 CFM")

**Physical Properties:**
- dimensions: Overall dimensions (L x W x H) with units
- weight_lbs: Dry/shipping weight in pounds
- operating_weight_lbs: Operating weight in pounds
- design_pressure: Design pressure rating (e.g., "250 PSIG")

**Power & Electrical:**
- power_voltage: Voltage rating (e.g., "460/3/60", "208V")
- power_hp: Motor horsepower rating

**HVAC Specific (if applicable):**
- gpm: Flow rate in gallons per minute
- temperature_in: Inlet/entering temperature (°F)
- temperature_out: Outlet/leaving temperature (°F)
- pressure_drop_psi: Pressure drop across equipment
- steam_pressure_psi: Steam pressure if applicable
- flow_rate_lbs_hr: Mass flow rate in lbs/hr
- inlet_size: Inlet pipe/connection size
- outlet_size: Outlet pipe/connection size

**Additional Details:**
- specifications: Relevant spec section or notes
- notes: Special installation requirements, mounting details, clearances
- contact_info: Service contact or access requirements

## 2. PIPING CONNECTIONS
For visible piping connections to equipment, extract:
- equipment_mark: Equipment tag this pipe connects to
- pipe_type: Service type (CW, CHW, HW, Steam, Condensate, Refrigerant, etc.)
- pipe_size: Nominal pipe size (e.g., "2\"", "3/4\"")
- material: Pipe material (Cu, CS, SS, etc.)
- insulation: Insulation type/thickness if noted
- location: Connection point or routing notes

Return your answer as valid JSON with this structure:
{{
  "equipment": [
    {{
      "equipment_mark": "RTU-1",
      "equipment_type": "Rooftop Unit",
      "location": "Area 2",
      "manufacturer": "Carrier",
      "model": "48VL-012",
      "capacity": "10 TON",
      "dimensions": "120\" x 48\" x 48\"",
      "weight_lbs": 850,
      "operating_weight_lbs": null,
      "power_voltage": "460/3/60",
      "power_hp": 3.5,
      "qty": 1,
      "gpm": null,
      "temperature_in": null,
      "temperature_out": null,
      "pressure_drop_psi": null,
      "steam_pressure_psi": null,
      "flow_rate_lbs_hr": null,
      "inlet_size": null,
      "outlet_size": null,
      "specifications": "Spec 23 74 13",
      "notes": "Roof curb by manufacturer",
      "contact_info": null,
      "confidence": 0.95
    }}
  ],
  "piping": [
    {{
      "equipment_mark": "RTU-1",
      "pipe_type": "Condensate",
      "pipe_size": "3/4\"",
      "material": "Cu",
      "insulation": null,
      "location": "West side connection",
      "confidence": 0.85
    }}
  ],
  "notes": ["general observations about the drawing"],
  "confidence": 0.0-1.0 overall confidence score
}}

IMPORTANT:
- Only extract data you can clearly see in the drawing or equipment schedules
- Use null for fields that are not visible or not applicable
- Include per-field confidence: 0.0-1.0 for uncertain values
- Look for equipment schedules - they contain detailed specifications
- Parse dimensions carefully (may be in format like "120 x 48 x 48")
- Note any ambiguities or unclear items in the notes array
- For quantities, look for "QTY" notation or count if multiple identical units
- Focus on accuracy over completeness
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
            "piping": [],
            "notes": [f"Parse error: {e}"],
            "confidence": 0.0,
        }


def extract_utility_drawing(
    sheet_id: int,
    pdf_path: Path,
    drawing_number: str,
    model: str = "sonnet",
    dry_run: bool = False,
) -> ExtractionResult:
    """
    Extract data from a utility roof plan PDF.

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
        drawing_type = "Utility Roof Plan"
        if "SCHEDULE" in drawing_number.upper():
            drawing_type = "Equipment Schedule"
        elif "DETAIL" in drawing_number.upper():
            drawing_type = "Detail Drawing"

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
        result.piping = data.get("piping", [])
        result.notes = data.get("notes", [])
        result.confidence = data.get("confidence", 0.7)

        # Calculate status
        total_items = len(result.equipment) + len(result.piping)

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
        "Extraction %s: %s - %d equipment, %d piping (%.1fs)",
        result.status,
        drawing_number,
        len(result.equipment),
        len(result.piping),
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
                "simple" if len(result.equipment) < 10 else "medium",
                result.sheet_id,
            ),
        )

        # Store equipment
        for equip in result.equipment:
            conn.execute(
                """INSERT INTO utility_equipment (
                    sheet_id, equipment_mark, equipment_type, location,
                    manufacturer, model, capacity, design_pressure,
                    dimensions, weight_lbs, operating_weight_lbs,
                    power_voltage, power_hp, qty,
                    gpm, temperature_in, temperature_out, pressure_drop_psi,
                    steam_pressure_psi, flow_rate_lbs_hr,
                    inlet_size, outlet_size,
                    specifications, notes, contact_info, confidence
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    result.sheet_id,
                    equip.get("equipment_mark"),
                    equip.get("equipment_type"),
                    equip.get("location"),
                    equip.get("manufacturer"),
                    equip.get("model"),
                    equip.get("capacity"),
                    equip.get("design_pressure"),
                    equip.get("dimensions"),
                    equip.get("weight_lbs"),
                    equip.get("operating_weight_lbs"),
                    equip.get("power_voltage"),
                    equip.get("power_hp"),
                    equip.get("qty", 1),
                    equip.get("gpm"),
                    equip.get("temperature_in"),
                    equip.get("temperature_out"),
                    equip.get("pressure_drop_psi"),
                    equip.get("steam_pressure_psi"),
                    equip.get("flow_rate_lbs_hr"),
                    equip.get("inlet_size"),
                    equip.get("outlet_size"),
                    equip.get("specifications"),
                    equip.get("notes"),
                    equip.get("contact_info"),
                    equip.get("confidence", result.confidence),
                ),
            )

        # Store piping connections in notes table for now
        for pipe in result.piping:
            note_text = (
                f"Piping connection to {pipe.get('equipment_mark')}: "
                f"{pipe.get('pipe_type')} {pipe.get('pipe_size')} {pipe.get('material')} "
                f"at {pipe.get('location')}"
            )
            conn.execute(
                """INSERT INTO extraction_notes (
                    sheet_id, note_type, description, confidence
                ) VALUES (?, ?, ?, ?)""",
                (result.sheet_id, "piping_connection", note_text, pipe.get("confidence", result.confidence)),
            )

        # Store extraction notes
        for note in result.notes:
            conn.execute(
                """INSERT INTO extraction_notes (
                    sheet_id, note_type, description, confidence
                ) VALUES (?, ?, ?, ?)""",
                (result.sheet_id, "extraction_note", note, result.confidence),
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
            result = extract_utility_drawing(
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
