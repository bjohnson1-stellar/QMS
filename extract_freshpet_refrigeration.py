"""
Extract data from Freshpet refrigeration drawing sheets.

Extracts lines, equipment, and instruments from P&ID and plan drawings.
"""

import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

# Try to import PDF processing library
try:
    import fitz  # PyMuPDF
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False

# Try to import Anthropic SDK
try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False


def extract_pdf_text(pdf_path: Path) -> str:
    """Extract text from PDF using PyMuPDF."""
    if not HAS_PYMUPDF:
        raise ImportError("PyMuPDF required. Install with: pip install PyMuPDF")

    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()
    return text


def call_claude(prompt: str, model: str = "sonnet") -> str:
    """Call Claude API for extraction."""
    if not HAS_ANTHROPIC:
        raise ImportError("anthropic SDK required. Install with: pip install anthropic")

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


def classify_drawing(pdf_text: str, file_name: str) -> Dict[str, str]:
    """Classify drawing type and determine extraction approach."""

    name_lower = file_name.lower()
    text_lower = pdf_text.lower()

    if "p&id" in name_lower or "piping and instrumentation" in text_lower:
        # Count instruments to estimate complexity
        instrument_count = len(re.findall(r'\b[A-Z]{2,3}-\d+', text_lower))
        complexity = "complex" if instrument_count > 20 else "moderate"
        return {
            "drawing_type": "pid",
            "complexity": complexity,
            "model": "sonnet",
            "description": f"P&ID with ~{instrument_count} instruments"
        }
    elif "plan" in name_lower or "layout" in name_lower:
        return {
            "drawing_type": "plan",
            "complexity": "moderate",
            "model": "sonnet",
            "description": "Refrigeration plan showing equipment and piping layout"
        }
    else:
        return {
            "drawing_type": "general",
            "complexity": "simple",
            "model": "haiku",
            "description": "General refrigeration drawing"
        }


def extract_pid(pdf_text: str, sheet_id: int, drawing_number: str) -> Dict[str, Any]:
    """Extract data from refrigeration P&ID."""

    prompt = f"""Extract all piping and instrumentation data from this refrigeration P&ID drawing.

For each PROCESS LINE, provide:
- Line number (format: SIZE-MATERIAL-NUMBER-SPEC or similar)
- Size (pipe diameter, e.g., "2\"", "4\"")
- Material (e.g., CS=Carbon Steel, SS=Stainless Steel)
- Spec Class (e.g., A1A, B2B)
- Refrigerant (e.g., NH3, CO2, R-404A)
- Service (e.g., "Liquid", "Suction", "Hot Gas", "Discharge")
- From equipment/location
- To equipment/location

For each EQUIPMENT item, provide:
- Tag number (e.g., V-101, E-201, P-301)
- Equipment type (e.g., Vessel, Evaporator, Pump, Compressor, Condenser)
- Description/name

For each INSTRUMENT, provide:
- Tag number (format: MEASUREMENT-NUMBER, e.g., FT-101, PT-201, TT-301)
- Instrument type (e.g., Flow Transmitter, Pressure Transmitter, Temperature Transmitter)
- Service description
- Associated loop number if shown

Return as JSON with this structure:
{{
    "lines": [
        {{
            "line_number": "...",
            "size": "...",
            "material": "...",
            "spec_class": "...",
            "refrigerant": "...",
            "service": "...",
            "from_location": "...",
            "to_location": "...",
            "confidence": 0.0-1.0
        }}
    ],
    "equipment": [
        {{
            "tag": "...",
            "equipment_type": "...",
            "description": "...",
            "confidence": 0.0-1.0
        }}
    ],
    "instruments": [
        {{
            "tag": "...",
            "instrument_type": "...",
            "service": "...",
            "loop_number": "...",
            "confidence": 0.0-1.0
        }}
    ]
}}

DRAWING TEXT:
{pdf_text[:10000]}
"""

    response_text = call_claude(prompt, model="sonnet")

    # Parse JSON response
    try:
        # Extract JSON from response (might be wrapped in markdown)
        json_match = re.search(r'```json\s*(\{.*\})\s*```', response_text, re.DOTALL)
        if json_match:
            response_text = json_match.group(1)

        data = json.loads(response_text)
        return data
    except json.JSONDecodeError as e:
        print(f"Failed to parse JSON response: {e}")
        print(f"Response: {response_text[:500]}")
        return {"lines": [], "equipment": [], "instruments": []}


def extract_plan(pdf_text: str, sheet_id: int, drawing_number: str) -> Dict[str, Any]:
    """Extract data from refrigeration plan drawing."""

    prompt = f"""Extract equipment and piping data from this refrigeration plan drawing.

For each EQUIPMENT item shown, provide:
- Tag number
- Equipment type
- Description
- Location/coordinates if shown

For any PIPE LINES visible with labels, provide:
- Line number
- Size
- Service type

Return as JSON:
{{
    "equipment": [
        {{
            "tag": "...",
            "equipment_type": "...",
            "description": "...",
            "confidence": 0.0-1.0
        }}
    ],
    "lines": [
        {{
            "line_number": "...",
            "size": "...",
            "service": "...",
            "confidence": 0.0-1.0
        }}
    ]
}}

DRAWING TEXT:
{pdf_text[:8000]}
"""

    response_text = call_claude(prompt, model="sonnet")

    try:
        json_match = re.search(r'```json\s*(\{.*\})\s*```', response_text, re.DOTALL)
        if json_match:
            response_text = json_match.group(1)
        data = json.loads(response_text)
        return data
    except json.JSONDecodeError:
        return {"equipment": [], "lines": []}


def save_to_database(sheet_id: int, extraction_data: Dict[str, Any], db_path: Path, model_used: str) -> tuple:
    """Save extracted data to database."""

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Save lines
    lines_inserted = 0
    for line in extraction_data.get("lines", []):
        cursor.execute("""
            INSERT INTO lines (sheet_id, line_number, size, material, spec_class,
                              refrigerant, service, from_location, to_location, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            sheet_id,
            line.get("line_number", "UNKNOWN"),
            line.get("size"),
            line.get("material"),
            line.get("spec_class"),
            line.get("refrigerant"),
            line.get("service"),
            line.get("from_location"),
            line.get("to_location"),
            line.get("confidence", 0.7)
        ))
        lines_inserted += 1

    # Save equipment
    equipment_inserted = 0
    for equip in extraction_data.get("equipment", []):
        cursor.execute("""
            INSERT INTO equipment (sheet_id, tag, description, equipment_type, confidence)
            VALUES (?, ?, ?, ?, ?)
        """, (
            sheet_id,
            equip.get("tag", "UNKNOWN"),
            equip.get("description"),
            equip.get("equipment_type"),
            equip.get("confidence", 0.7)
        ))
        equipment_inserted += 1

    # Save instruments
    instruments_inserted = 0
    for inst in extraction_data.get("instruments", []):
        cursor.execute("""
            INSERT INTO instruments (sheet_id, tag, instrument_type, service,
                                    loop_number, confidence)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            sheet_id,
            inst.get("tag", "UNKNOWN"),
            inst.get("instrument_type"),
            inst.get("service"),
            inst.get("loop_number"),
            inst.get("confidence", 0.7)
        ))
        instruments_inserted += 1

    # Calculate quality score based on average confidence
    all_items = (
        extraction_data.get("lines", []) +
        extraction_data.get("equipment", []) +
        extraction_data.get("instruments", [])
    )
    if all_items:
        quality_score = sum(item.get("confidence", 0.7) for item in all_items) / len(all_items)
    else:
        quality_score = 0.0

    # Update sheet status
    cursor.execute("""
        UPDATE sheets
        SET extracted_at = ?,
            extraction_model = ?,
            quality_score = ?
        WHERE id = ?
    """, (datetime.now().isoformat(), model_used, quality_score, sheet_id))

    conn.commit()
    conn.close()

    return lines_inserted, equipment_inserted, instruments_inserted, quality_score


def process_sheet(sheet_id: int, file_path: Path, db_path: Path, drawing_number: str) -> Dict[str, Any]:
    """Process a single drawing sheet."""

    print(f"\nProcessing sheet {sheet_id}: {file_path.name}")
    print("=" * 80)

    # Extract text from PDF
    print("Extracting PDF text...")
    pdf_text = extract_pdf_text(file_path)
    print(f"Extracted {len(pdf_text)} characters")

    # Classify drawing
    print("Classifying drawing...")
    classification = classify_drawing(pdf_text, file_path.name)
    print(f"Drawing Type: {classification['drawing_type']}")
    print(f"Complexity: {classification['complexity']}")
    print(f"Model: {classification['model']}")
    print(f"Description: {classification['description']}")

    # Extract based on type
    print("Extracting data...")
    if classification['drawing_type'] == 'pid':
        extraction_data = extract_pid(pdf_text, sheet_id, drawing_number)
    elif classification['drawing_type'] == 'plan':
        extraction_data = extract_plan(pdf_text, sheet_id, drawing_number)
    else:
        print("Unsupported drawing type for automated extraction")
        return {
            "status": "skipped",
            "reason": "Unsupported drawing type"
        }

    # Save to database
    print("Saving to database...")
    lines_count, equipment_count, instruments_count, quality = save_to_database(
        sheet_id, extraction_data, db_path, classification['model']
    )

    result = {
        "status": "success",
        "classification": classification,
        "lines_extracted": lines_count,
        "equipment_extracted": equipment_count,
        "instruments_extracted": instruments_count,
        "quality_score": quality,
        "total_items": lines_count + equipment_count + instruments_count
    }

    print(f"✓ Lines: {lines_count}")
    print(f"✓ Equipment: {equipment_count}")
    print(f"✓ Instruments: {instruments_count}")
    print(f"✓ Quality Score: {quality:.2f}")

    return result


def main():
    """Main extraction script."""

    # Sheet definitions for the three Freshpet refrigeration drawings
    sheets = [
        {
            "id": 634,
            "path": Path("data/projects/07609-Freshpet/Refrigeration/R7005.1-REFRIGERATION-P&ID-Rev.1.pdf"),
            "drawing_number": "R7005.1"
        },
        {
            "id": 635,
            "path": Path("data/projects/07609-Freshpet/Refrigeration/R7006.1-REFRIGERATION-P&ID-Rev.1.pdf"),
            "drawing_number": "R7006.1"
        },
        {
            "id": 636,
            "path": Path("data/projects/07609-Freshpet/Refrigeration/R7006A.1-REFRIGERATION-PLAN-Rev.1.pdf"),
            "drawing_number": "R7006A.1"
        }
    ]

    db_path = Path("data/quality.db")

    print("Freshpet Refrigeration Drawing Extraction")
    print("=" * 80)
    print(f"Project: 07609-Freshpet")
    print(f"Sheets to process: {len(sheets)}")
    print(f"Database: {db_path}")
    print()

    results = []
    for sheet in sheets:
        try:
            result = process_sheet(sheet["id"], sheet["path"], db_path, sheet["drawing_number"])
            results.append({
                "sheet_id": sheet["id"],
                "drawing_number": sheet["drawing_number"],
                **result
            })
        except Exception as e:
            print(f"ERROR processing sheet {sheet['id']}: {e}")
            import traceback
            traceback.print_exc()
            results.append({
                "sheet_id": sheet["id"],
                "drawing_number": sheet["drawing_number"],
                "status": "failed",
                "error": str(e)
            })

    # Summary
    print("\n" + "=" * 80)
    print("EXTRACTION SUMMARY")
    print("=" * 80)

    total_lines = sum(r.get("lines_extracted", 0) for r in results)
    total_equipment = sum(r.get("equipment_extracted", 0) for r in results)
    total_instruments = sum(r.get("instruments_extracted", 0) for r in results)

    for result in results:
        status_icon = "✓" if result["status"] == "success" else "✗"
        print(f"{status_icon} {result['drawing_number']}: {result['status']}")
        if result["status"] == "success":
            print(f"   Lines: {result['lines_extracted']}")
            print(f"   Equipment: {result['equipment_extracted']}")
            print(f"   Instruments: {result['instruments_extracted']}")
            print(f"   Quality: {result['quality_score']:.2f}")
        elif result["status"] == "failed":
            print(f"   Error: {result.get('error', 'Unknown')}")

    print(f"\nTotal Extracted:")
    print(f"  Lines: {total_lines}")
    print(f"  Equipment: {total_equipment}")
    print(f"  Instruments: {total_instruments}")
    print(f"  Total Items: {total_lines + total_equipment + total_instruments}")


if __name__ == "__main__":
    main()
