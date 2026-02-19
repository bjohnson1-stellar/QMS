"""
Drawing data extraction for P&IDs, isometrics, and refrigeration plans.

This module handles extraction of structured data from engineering drawings:
- Lines (pipe numbers, sizes, materials, specs)
- Equipment (tags, types, descriptions)
- Instruments (tags, types, loop numbers)
- Welds (for isometrics)

Uses AI models (Sonnet/Opus) to read drawings and extract data per the
.planning/subagents/extractor-agent.md specification.
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from qms.core import get_db, get_logger

logger = get_logger("qms.pipeline.extractor")


@dataclass
class ExtractionResult:
    """Result of drawing extraction."""
    sheet_id: int
    drawing_number: str
    drawing_type: str
    model_used: str
    status: str = "pending"  # pending, success, partial, failed
    confidence: float = 0.0
    lines_extracted: int = 0
    equipment_extracted: int = 0
    instruments_extracted: int = 0
    welds_extracted: int = 0
    flagged_items: List[Dict] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    processing_time_ms: int = 0


def extract_pdf_text(pdf_path: Path) -> str:
    """
    Extract text content from a PDF file using PyMuPDF.

    Args:
        pdf_path: Path to PDF file.

    Returns:
        Extracted text as a single string.
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        raise ImportError(
            "PyMuPDF is required for PDF extraction. "
            "Install with: pip install PyMuPDF>=1.23.0"
        )

    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    pages: List[str] = []
    with fitz.open(str(pdf_path)) as doc:
        for page_num, page in enumerate(doc):
            text = page.get_text("text")
            if text.strip():
                pages.append(f"--- PAGE {page_num + 1} ---\n{text}")

    full_text = "\n\n".join(pages)
    logger.info("Extracted %d pages, %d chars from %s", len(pages), len(full_text), pdf_path.name)
    return full_text


def classify_drawing(text: str, file_name: str) -> tuple[str, str]:
    """
    Classify drawing type and estimate complexity.

    Args:
        text: Extracted text from drawing.
        file_name: File name for hints.

    Returns:
        Tuple of (drawing_type, complexity).
    """
    text_upper = text.upper()
    fname_upper = file_name.upper()

    # Determine drawing type
    if "ISO" in fname_upper or "ISOMETRIC" in text_upper:
        drawing_type = "Isometric"
    elif "P&ID" in text_upper or "PIPING" in text_upper and "INSTRUMENT" in text_upper:
        drawing_type = "P&ID"
    elif "REFRIGERATION" in fname_upper or "REFRIG" in text_upper:
        if "PLAN" in fname_upper or "PLAN" in text_upper:
            drawing_type = "Refrigeration Plan"
        else:
            drawing_type = "Refrigeration"
    elif "GA" in fname_upper or "GENERAL ARRANGEMENT" in text_upper:
        drawing_type = "GA"
    elif "SLD" in fname_upper or "SINGLE LINE" in text_upper:
        drawing_type = "SLD"
    else:
        drawing_type = "Unknown"

    # Estimate complexity based on text length and keywords
    complexity = "simple"
    if len(text) > 10000:
        complexity = "complex"
    elif len(text) > 5000:
        complexity = "medium"

    # Bump up complexity for certain types
    if drawing_type in ("P&ID", "Isometric") and complexity == "simple":
        complexity = "medium"

    return drawing_type, complexity


def select_model(drawing_type: str, complexity: str) -> str:
    """
    Select appropriate AI model based on drawing characteristics.

    Per .planning/subagents/extractor-agent.md:
    - Simple P&ID: Sonnet
    - Complex P&ID: Sonnet
    - Isometric: Sonnet
    - GA/Layout: Haiku
    - Title block only: Haiku

    Args:
        drawing_type: Type of drawing.
        complexity: Estimated complexity.

    Returns:
        Model name ('haiku', 'sonnet', or 'opus').
    """
    if drawing_type in ("GA", "Unknown") and complexity == "simple":
        return "haiku"
    elif drawing_type in ("P&ID", "Isometric", "Refrigeration Plan", "Refrigeration"):
        return "sonnet"
    else:
        return "sonnet"


def build_extraction_prompt(text: str, drawing_type: str) -> str:
    """
    Build extraction prompt based on drawing type.

    Args:
        text: Extracted text from drawing.
        drawing_type: Type of drawing to extract.

    Returns:
        Extraction prompt for AI model.
    """
    if drawing_type == "P&ID":
        return _build_pid_prompt(text)
    elif drawing_type == "Isometric":
        return _build_iso_prompt(text)
    elif drawing_type in ("Refrigeration Plan", "Refrigeration"):
        return _build_refrig_prompt(text)
    elif drawing_type == "GA":
        return _build_ga_prompt(text)
    else:
        return _build_generic_prompt(text)


def _build_refrig_prompt(text: str) -> str:
    """Build extraction prompt for refrigeration plans."""
    return f"""Extract all refrigeration piping and equipment data from this drawing.

DRAWING TEXT:
{text}

For each REFRIGERATION LINE, provide:
- Line number (format: SIZE-MATERIAL-NUMBER-SPEC or similar)
- Size (e.g., 1-1/8", 2-1/8", 3-1/8")
- Material (e.g., CS=Carbon Steel, SS=Stainless Steel)
- Spec class (e.g., A1A, A2A, etc.)
- Refrigerant type (e.g., NH3, R-717, R-22, R-404A)
- Service (e.g., Hot Gas, Liquid, Suction)
- From equipment/location
- To equipment/location

For each EQUIPMENT item, provide:
- Tag number (e.g., C-101, V-201, TK-301)
- Equipment type (e.g., Compressor, Vessel, Tank, Heat Exchanger)
- Description/name

For each INSTRUMENT, provide:
- Tag number (e.g., PT-101, TT-201, LT-301)
- Instrument type (e.g., Pressure Transmitter, Temperature Transmitter)
- Loop number if shown
- Service/description

Return as JSON in this format:
{{
  "lines": [
    {{
      "line_number": "2-1/8\\"-NH3-101-A1A",
      "size": "2-1/8\\"",
      "material": "CS",
      "spec_class": "A1A",
      "refrigerant": "NH3",
      "service": "Hot Gas",
      "from_location": "C-101",
      "to_location": "V-201",
      "confidence": 0.95
    }}
  ],
  "equipment": [
    {{
      "tag": "C-101",
      "type": "Compressor",
      "description": "Ammonia Screw Compressor",
      "confidence": 0.92
    }}
  ],
  "instruments": [
    {{
      "tag": "PT-101",
      "type": "Pressure Transmitter",
      "loop_number": "PT-101",
      "service": "Compressor Suction Pressure",
      "confidence": 0.88
    }}
  ]
}}

IMPORTANT:
- If you cannot read a value clearly, reduce confidence and note in extraction_notes
- Skip items that are clearly not part of the main drawing (e.g., title block equipment lists)
- For ambiguous values, provide your best interpretation and flag with lower confidence
- Confidence range: 0.0 (unable to read) to 1.0 (certain)
"""


def _build_pid_prompt(text: str) -> str:
    """Build extraction prompt for P&ID drawings."""
    return f"""Extract all piping and instrumentation data from this P&ID drawing.

DRAWING TEXT:
{text}

For each PROCESS LINE, provide:
- Line number (format: SIZE-MATERIAL-NUMBER-SPEC)
- Size, Material, Spec Class
- From equipment/location
- To equipment/location
- Service description

For each EQUIPMENT item, provide:
- Tag number
- Equipment type
- Description/name

For each INSTRUMENT, provide:
- Tag number
- Instrument type
- Associated loop number

Return as structured JSON with same format as refrigeration prompt.
"""


def _build_iso_prompt(text: str) -> str:
    """Build extraction prompt for isometric drawings."""
    return f"""Extract all piping data from this isometric drawing.

DRAWING TEXT:
{text}

For each LINE SEGMENT:
- Line number
- Size, Material, Spec Class

For each WELD, provide:
- Weld ID/number
- Weld type (BW=Butt, SW=Socket, FW=Fillet)
- Size
- NDE requirements (RT, PT, MT, etc.)

For MATERIALS from the bill of materials:
- Item number
- Description
- Quantity
- Material spec

Return as structured JSON.
"""


def _build_ga_prompt(text: str) -> str:
    """Build extraction prompt for GA drawings."""
    return f"""Extract equipment tags and locations from this general arrangement drawing.

DRAWING TEXT:
{text}

For each EQUIPMENT item, provide:
- Tag number
- Location (grid reference if shown)
- Elevation

Return as structured JSON with equipment array.
"""


def _build_generic_prompt(text: str) -> str:
    """Build generic extraction prompt."""
    return f"""Extract any identifiable equipment tags, line numbers, and instrument tags from this drawing.

DRAWING TEXT:
{text}

Return as structured JSON with equipment, lines, and instruments arrays.
"""


def call_model(prompt: str, model: str = "sonnet") -> str:
    """
    Call an AI model with the given prompt.

    Args:
        prompt: Extraction prompt.
        model: Model name ('haiku', 'sonnet', 'opus').

    Returns:
        Model response as text.
    """
    try:
        import anthropic
    except ImportError:
        raise ImportError(
            "anthropic SDK is required for extraction. "
            "Install with: pip install anthropic>=0.25.0"
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
        max_tokens=8192,
        messages=[{"role": "user", "content": prompt}],
    )

    return response.content[0].text


def parse_extraction_response(response: str) -> Dict[str, Any]:
    """
    Parse JSON response from AI model.

    Args:
        response: Model response text.

    Returns:
        Parsed data dictionary.
    """
    # Try to extract JSON from response (model might include explanation)
    json_match = re.search(r'\{.*\}', response, re.DOTALL)
    if json_match:
        json_str = json_match.group(0)
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.warning("JSON parse error: %s", e)
            return {"lines": [], "equipment": [], "instruments": [], "welds": []}
    else:
        logger.warning("No JSON found in response")
        return {"lines": [], "equipment": [], "instruments": [], "welds": []}


def calculate_confidence(items: List[Dict], item_counts: Dict[str, int]) -> tuple[float, List[Dict]]:
    """
    Calculate overall confidence and identify flagged items.

    Args:
        items: List of extracted items.
        item_counts: Counts by type.

    Returns:
        Tuple of (confidence, flagged_items).
    """
    if not items:
        return 0.0, []

    confidences = [item.get("confidence", 0.7) for item in items]
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

    # Flag low-confidence items
    flagged = []
    for item in items:
        conf = item.get("confidence", 0.7)
        if conf < 0.6:
            flagged.append({
                "item": item.get("tag") or item.get("line_number") or item.get("weld_id"),
                "confidence": conf,
                "reason": "Low confidence extraction",
            })

    return avg_confidence, flagged


def store_extraction(conn, sheet_id: int, data: Dict[str, Any]) -> Dict[str, int]:
    """
    Store extracted data in database.

    Args:
        conn: Database connection.
        sheet_id: Sheet ID from sheets table.
        data: Extracted data dictionary.

    Returns:
        Counts of items stored by type.
    """
    counts = {"lines": 0, "equipment": 0, "instruments": 0, "welds": 0}

    # Store lines
    for line in data.get("lines", []):
        try:
            conn.execute("""
                INSERT INTO lines (
                    sheet_id, line_number, size, material, spec_class,
                    from_location, to_location, service, refrigerant,
                    confidence
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                sheet_id,
                line.get("line_number"),
                line.get("size"),
                line.get("material"),
                line.get("spec_class"),
                line.get("from_location"),
                line.get("to_location"),
                line.get("service"),
                line.get("refrigerant"),
                line.get("confidence", 1.0),
            ))
            counts["lines"] += 1
        except Exception as e:
            logger.error("Failed to insert line %s: %s", line.get("line_number"), e)

    # Store equipment
    for equip in data.get("equipment", []):
        try:
            conn.execute("""
                INSERT INTO equipment (
                    sheet_id, tag, description, equipment_type, confidence
                ) VALUES (?, ?, ?, ?, ?)
            """, (
                sheet_id,
                equip.get("tag"),
                equip.get("description"),
                equip.get("type"),
                equip.get("confidence", 1.0),
            ))
            counts["equipment"] += 1
        except Exception as e:
            logger.error("Failed to insert equipment %s: %s", equip.get("tag"), e)

    # Store instruments
    for inst in data.get("instruments", []):
        try:
            conn.execute("""
                INSERT INTO instruments (
                    sheet_id, tag, instrument_type, loop_number,
                    service, confidence
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                sheet_id,
                inst.get("tag"),
                inst.get("type"),
                inst.get("loop_number"),
                inst.get("service"),
                inst.get("confidence", 1.0),
            ))
            counts["instruments"] += 1
        except Exception as e:
            logger.error("Failed to insert instrument %s: %s", inst.get("tag"), e)

    # Store welds (if applicable)
    for weld in data.get("welds", []):
        try:
            conn.execute("""
                INSERT INTO welds (
                    sheet_id, weld_id, weld_type, size, nde_required
                ) VALUES (?, ?, ?, ?, ?)
            """, (
                sheet_id,
                weld.get("weld_id"),
                weld.get("type"),
                weld.get("size"),
                weld.get("nde"),
            ))
            counts["welds"] += 1
        except Exception as e:
            logger.error("Failed to insert weld %s: %s", weld.get("weld_id"), e)

    return counts


def extract_drawing(sheet_id: int, file_path: str, dry_run: bool = False) -> ExtractionResult:
    """
    Extract data from a single drawing.

    Args:
        sheet_id: Sheet ID from database.
        file_path: Path to PDF file.
        dry_run: If True, don't write to database.

    Returns:
        ExtractionResult with outcome.
    """
    import time
    start_time = time.time()

    # Get sheet info from database
    with get_db(readonly=True) as conn:
        row = conn.execute(
            "SELECT drawing_number, file_path FROM sheets WHERE id = ?",
            (sheet_id,)
        ).fetchone()
        if not row:
            raise ValueError(f"Sheet ID {sheet_id} not found")

        drawing_number = row["drawing_number"]
        db_file_path = row["file_path"]

    result = ExtractionResult(
        sheet_id=sheet_id,
        drawing_number=drawing_number,
        drawing_type="Unknown",
        model_used="sonnet",
    )

    try:
        # Extract text
        pdf_path = Path(file_path)
        if not pdf_path.exists():
            result.status = "failed"
            result.errors.append(f"File not found: {file_path}")
            return result

        text = extract_pdf_text(pdf_path)
        if not text.strip():
            result.status = "failed"
            result.errors.append("No text extracted from PDF")
            return result

        # Classify drawing
        drawing_type, complexity = classify_drawing(text, pdf_path.name)
        result.drawing_type = drawing_type

        # Select model
        model = select_model(drawing_type, complexity)
        result.model_used = model

        logger.info(
            "Sheet %d: %s (type=%s, complexity=%s, model=%s)",
            sheet_id, drawing_number, drawing_type, complexity, model
        )

        # Build prompt and extract
        prompt = build_extraction_prompt(text, drawing_type)
        response = call_model(prompt, model)
        data = parse_extraction_response(response)

        # Calculate confidence and flags
        all_items = (
            data.get("lines", []) +
            data.get("equipment", []) +
            data.get("instruments", []) +
            data.get("welds", [])
        )
        confidence, flagged = calculate_confidence(
            all_items,
            {
                "lines": len(data.get("lines", [])),
                "equipment": len(data.get("equipment", [])),
                "instruments": len(data.get("instruments", [])),
                "welds": len(data.get("welds", [])),
            }
        )
        result.confidence = confidence
        result.flagged_items = flagged

        # Store in database
        if not dry_run:
            with get_db() as conn:
                counts = store_extraction(conn, sheet_id, data)
                result.lines_extracted = counts["lines"]
                result.equipment_extracted = counts["equipment"]
                result.instruments_extracted = counts["instruments"]
                result.welds_extracted = counts["welds"]

                # Update sheet record
                conn.execute("""
                    UPDATE sheets
                    SET extracted_at = CURRENT_TIMESTAMP,
                        quality_score = ?,
                        complexity = ?,
                        extraction_model = ?
                    WHERE id = ?
                """, (confidence, complexity, model, sheet_id))

                conn.commit()
                logger.info(
                    "Stored: %d lines, %d equipment, %d instruments, %d welds",
                    counts["lines"], counts["equipment"], counts["instruments"], counts["welds"]
                )
        else:
            result.lines_extracted = len(data.get("lines", []))
            result.equipment_extracted = len(data.get("equipment", []))
            result.instruments_extracted = len(data.get("instruments", []))
            result.welds_extracted = len(data.get("welds", []))
            logger.info("[DRY RUN] Would store: %s", counts)

        result.status = "success" if not flagged else "partial"

    except Exception as e:
        result.status = "failed"
        result.errors.append(str(e))
        logger.error("Extraction error for sheet %d: %s", sheet_id, e, exc_info=True)

    result.processing_time_ms = int((time.time() - start_time) * 1000)
    return result


def extract_batch(sheet_ids: List[int], dry_run: bool = False) -> List[ExtractionResult]:
    """
    Extract data from multiple drawings.

    Args:
        sheet_ids: List of sheet IDs to process.
        dry_run: If True, don't write to database.

    Returns:
        List of ExtractionResult for each sheet.
    """
    results = []

    # Get file paths for all sheets
    with get_db(readonly=True) as conn:
        rows = conn.execute(
            f"SELECT id, file_path FROM sheets WHERE id IN ({','.join('?' * len(sheet_ids))})",
            sheet_ids
        ).fetchall()

    sheet_paths = {row["id"]: row["file_path"] for row in rows}

    for i, sheet_id in enumerate(sheet_ids, 1):
        file_path = sheet_paths.get(sheet_id)
        if not file_path:
            logger.warning("Sheet %d not found in database", sheet_id)
            continue

        logger.info("[%d/%d] Processing sheet %d...", i, len(sheet_ids), sheet_id)
        result = extract_drawing(sheet_id, file_path, dry_run=dry_run)
        results.append(result)

    # Summary
    success = sum(1 for r in results if r.status == "success")
    partial = sum(1 for r in results if r.status == "partial")
    failed = sum(1 for r in results if r.status == "failed")

    logger.info(
        "Batch complete: %d success, %d partial, %d failed (of %d total)",
        success, partial, failed, len(results)
    )

    return results
