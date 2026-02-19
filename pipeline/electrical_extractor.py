"""
Electrical Drawing Extraction Agent.

Extracts structured data from electrical power plan drawings including:
- Panels and panel schedules
- Circuits and breakers
- Equipment tags and motor connections
- Transformers and switchgear
- Receptacles, lighting fixtures, switches
- Conduit routing and wire sizing
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
    """Result of extracting a single electrical drawing."""
    sheet_id: int
    drawing_number: str
    status: str = "pending"  # success, partial, failed
    confidence: float = 0.0
    panels: List[Dict] = field(default_factory=list)
    circuits: List[Dict] = field(default_factory=list)
    equipment: List[Dict] = field(default_factory=list)
    receptacles: List[Dict] = field(default_factory=list)
    lighting_fixtures: List[Dict] = field(default_factory=list)
    transformers: List[Dict] = field(default_factory=list)
    switchgear: List[Dict] = field(default_factory=list)
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
    """Build extraction prompt for electrical drawings."""
    return f"""Extract all structured data from this electrical power plan drawing: {drawing_number}

This is a {drawing_type} drawing. Focus on extracting the following:

## 1. PANELS
For each electrical panel or panelboard shown, extract:
- panel_name: Panel designation (e.g., "PP-1", "LP-2A")
- location: Physical location or room number
- voltage: Voltage rating (e.g., "120/208V", "277/480V")
- phases: Number of phases (1 or 3)
- wires: Number of wires (3 or 4)
- bus_rating: Bus amperage rating
- fed_from: Source panel or transformer
- enclosure_type: NEMA rating if shown
- aic_rating: Available fault current rating

## 2. CIRCUITS
For each circuit in panel schedules, extract:
- circuit_number: Circuit number (can be "1", "2,4,6" for multi-pole)
- circuit_description: Load description
- equipment_tag: Equipment tag if associated
- location: Load location or area
- num_poles: Number of poles (1, 2, or 3)
- breaker_frame: Breaker frame size
- breaker_trip: Breaker trip rating
- wire_size: Wire gauge (e.g., "#12", "#10")
- conduit_size: Conduit size (e.g., "3/4\"", "1\"")
- load_kva: Connected kVA if shown
- load_amps: Connected amperage

## 3. ELECTRICAL EQUIPMENT
For each piece of electrical equipment on the plan view, extract:
- tag: Equipment tag (e.g., "MCC-1", "VFD-101")
- equipment_type: Type (MCC, VFD, disconnect, junction box, etc.)
- location: Physical location or grid reference
- area: Area designation
- voltage: Operating voltage
- amperage: Current rating
- notes: Special notes or requirements

## 4. RECEPTACLES
For each receptacle shown, extract:
- receptacle_type: Type (duplex, quad, special-purpose)
- voltage: Voltage rating
- amperage: Current rating
- location: Room or area
- grid_location: Grid reference if shown
- mounting_height: Height above floor (AFF)
- circuit_number: Circuit number serving it
- gfci: true if GFCI protected
- notes: Special requirements

## 5. LIGHTING FIXTURES
For each lighting fixture, extract:
- fixture_type: Fixture designation from legend
- location: Room or area
- grid_location: Grid reference
- mounting_height: Mounting height if shown
- circuit_number: Circuit serving it
- switch_tag: Switch controlling it
- qty: Quantity at location

## 6. TRANSFORMERS
For any transformers shown, extract:
- tag: Transformer tag
- kva_rating: KVA rating
- primary_voltage: Primary voltage
- secondary_voltage: Secondary voltage
- phases: Number of phases
- wires: Number of wires
- frequency: Frequency (typically 60)

## 7. SWITCHGEAR
For any switchgear shown, extract:
- tag: Equipment tag
- equipment_type: Type (switchgear, switchboard, load center)
- voltage: Operating voltage
- current_rating: Continuous current rating
- frame_size: Frame size
- short_circuit_rating: SCCR rating if shown

Return your answer as valid JSON with this structure:
{{
  "panels": [{{panel fields}}],
  "circuits": [{{circuit fields}}],
  "equipment": [{{equipment fields}}],
  "receptacles": [{{receptacle fields}}],
  "lighting_fixtures": [{{fixture fields}}],
  "transformers": [{{transformer fields}}],
  "switchgear": [{{switchgear fields}}],
  "notes": ["general notes or observations"],
  "confidence": 0.0-1.0 overall confidence score
}}

IMPORTANT:
- Only extract data you can clearly see in the drawing
- Use null for fields that are not visible or not applicable
- Include confidence: 0.0-1.0 for uncertain values
- Note any ambiguities or unclear items in the notes array
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
            "panels": [],
            "circuits": [],
            "equipment": [],
            "receptacles": [],
            "lighting_fixtures": [],
            "transformers": [],
            "switchgear": [],
            "notes": [f"Parse error: {e}"],
            "confidence": 0.0,
        }


def extract_electrical_drawing(
    sheet_id: int,
    pdf_path: Path,
    drawing_number: str,
    model: str = "sonnet",
    dry_run: bool = False,
) -> ExtractionResult:
    """
    Extract data from an electrical drawing PDF.

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
        drawing_type = "Power Plan"
        if "LIGHTING" in drawing_number.upper():
            drawing_type = "Lighting Plan"
        elif "PANEL" in drawing_number.upper():
            drawing_type = "Panel Schedule"
        elif "ONE-LINE" in drawing_number.upper() or "SINGLE-LINE" in drawing_number.upper():
            drawing_type = "Single Line Diagram"

        logger.info("Extracting %s (%s) using %s...", drawing_number, drawing_type, model)

        # Encode PDF
        pdf_base64 = _encode_pdf_for_vision(pdf_path)

        # Build prompt and call Claude
        prompt = _build_extraction_prompt(drawing_number, drawing_type)
        response = _call_claude_vision(pdf_base64, prompt, model)

        # Parse response
        data = _parse_extraction_response(response)

        # Populate result
        result.panels = data.get("panels", [])
        result.circuits = data.get("circuits", [])
        result.equipment = data.get("equipment", [])
        result.receptacles = data.get("receptacles", [])
        result.lighting_fixtures = data.get("lighting_fixtures", [])
        result.transformers = data.get("transformers", [])
        result.switchgear = data.get("switchgear", [])
        result.notes = data.get("notes", [])
        result.confidence = data.get("confidence", 0.7)

        # Calculate counts
        total_items = (
            len(result.panels) +
            len(result.circuits) +
            len(result.equipment) +
            len(result.receptacles) +
            len(result.lighting_fixtures) +
            len(result.transformers) +
            len(result.switchgear)
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
        "Extraction %s: %s - %d panels, %d circuits, %d equipment, %d fixtures (%.1fs)",
        result.status,
        drawing_number,
        len(result.panels),
        len(result.circuits),
        len(result.equipment),
        len(result.lighting_fixtures),
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
                "medium" if len(result.circuits) < 50 else "high",
                result.sheet_id,
            ),
        )

        # Store panels
        for panel in result.panels:
            conn.execute(
                """INSERT INTO electrical_panels (
                    sheet_id, panel_name, location, voltage, phases, wires,
                    bus_rating, fed_from, enclosure_type, aic_rating,
                    panel_notes, confidence
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    result.sheet_id,
                    panel.get("panel_name"),
                    panel.get("location"),
                    panel.get("voltage"),
                    panel.get("phases"),
                    panel.get("wires"),
                    panel.get("bus_rating"),
                    panel.get("fed_from"),
                    panel.get("enclosure_type"),
                    panel.get("aic_rating"),
                    panel.get("notes"),
                    panel.get("confidence", result.confidence),
                ),
            )
            panel_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

            # Store circuits for this panel
            for circuit in result.circuits:
                # Match circuits to panel if they reference it
                conn.execute(
                    """INSERT INTO electrical_circuits (
                        panel_id, sheet_id, circuit_number, circuit_description,
                        equipment_tag, location, num_poles, breaker_frame,
                        breaker_trip, wire_size, conduit_size, load_kva,
                        load_amps, notes, confidence
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        panel_id,
                        result.sheet_id,
                        circuit.get("circuit_number"),
                        circuit.get("circuit_description"),
                        circuit.get("equipment_tag"),
                        circuit.get("location"),
                        circuit.get("num_poles"),
                        circuit.get("breaker_frame"),
                        circuit.get("breaker_trip"),
                        circuit.get("wire_size"),
                        circuit.get("conduit_size"),
                        circuit.get("load_kva"),
                        circuit.get("load_amps"),
                        circuit.get("notes"),
                        circuit.get("confidence", result.confidence),
                    ),
                )

        # Store equipment
        for equip in result.equipment:
            conn.execute(
                """INSERT INTO electrical_equipment (
                    sheet_id, tag, equipment_type, location, area,
                    voltage, amperage, notes, confidence
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    result.sheet_id,
                    equip.get("tag"),
                    equip.get("equipment_type"),
                    equip.get("location"),
                    equip.get("area"),
                    equip.get("voltage"),
                    equip.get("amperage"),
                    equip.get("notes"),
                    equip.get("confidence", result.confidence),
                ),
            )

        # Store receptacles
        for recept in result.receptacles:
            conn.execute(
                """INSERT INTO electrical_receptacles (
                    sheet_id, receptacle_type, voltage, amperage, location,
                    grid_location, mounting_height, circuit_number, gfci,
                    notes, confidence
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    result.sheet_id,
                    recept.get("receptacle_type"),
                    recept.get("voltage"),
                    recept.get("amperage"),
                    recept.get("location"),
                    recept.get("grid_location"),
                    recept.get("mounting_height"),
                    recept.get("circuit_number"),
                    1 if recept.get("gfci") else 0,
                    recept.get("notes"),
                    recept.get("confidence", result.confidence),
                ),
            )

        # Store lighting fixtures
        for fixture in result.lighting_fixtures:
            conn.execute(
                """INSERT INTO electrical_lighting_fixtures (
                    sheet_id, fixture_type, location, grid_location,
                    mounting_height, circuit_number, switch_tag, qty,
                    notes, confidence
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    result.sheet_id,
                    fixture.get("fixture_type"),
                    fixture.get("location"),
                    fixture.get("grid_location"),
                    fixture.get("mounting_height"),
                    fixture.get("circuit_number"),
                    fixture.get("switch_tag"),
                    fixture.get("qty", 1),
                    fixture.get("notes"),
                    fixture.get("confidence", result.confidence),
                ),
            )

        # Store transformers
        for xfmr in result.transformers:
            conn.execute(
                """INSERT INTO electrical_transformers (
                    sheet_id, tag, kva_rating, primary_voltage,
                    secondary_voltage, phases, wires, frequency, confidence
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    result.sheet_id,
                    xfmr.get("tag"),
                    xfmr.get("kva_rating"),
                    xfmr.get("primary_voltage"),
                    xfmr.get("secondary_voltage"),
                    xfmr.get("phases"),
                    xfmr.get("wires"),
                    xfmr.get("frequency", 60),
                    xfmr.get("confidence", result.confidence),
                ),
            )

        # Store switchgear
        for sg in result.switchgear:
            conn.execute(
                """INSERT INTO electrical_switchgear (
                    sheet_id, tag, equipment_type, voltage, current_rating,
                    frame_size, short_circuit_rating, confidence
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    result.sheet_id,
                    sg.get("tag"),
                    sg.get("equipment_type"),
                    sg.get("voltage"),
                    sg.get("current_rating"),
                    sg.get("frame_size"),
                    sg.get("short_circuit_rating"),
                    sg.get("confidence", result.confidence),
                ),
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
            result = extract_electrical_drawing(
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
