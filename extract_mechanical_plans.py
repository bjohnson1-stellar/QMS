"""
Extract mechanical equipment from mechanical plan sheets.

Processes sheets 548, 549, 550 for project 07609 (Freshpet).
Extracts mechanical equipment schedules and tags into mechanical_equipment table.
"""

import json
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add qms to path
sys.path.insert(0, str(Path(__file__).parent))

from qms.core import get_db, get_logger

logger = get_logger("mechanical_extraction")

try:
    import anthropic
except ImportError:
    print("ERROR: anthropic SDK required. Install with: pip install anthropic")
    sys.exit(1)

try:
    import pdfplumber
except ImportError:
    print("ERROR: pdfplumber required. Install with: pip install pdfplumber")
    sys.exit(1)


def extract_pdf_text(pdf_path: Path) -> str:
    """Extract text from PDF using pdfplumber."""
    text_parts = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
    except Exception as e:
        logger.error("PDF extraction error for %s: %s", pdf_path.name, e)
        return ""

    return "\n\n".join(text_parts)


def call_sonnet(prompt: str) -> str:
    """Call Claude Sonnet for extraction."""
    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=8192,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


def build_extraction_prompt(sheet_text: str, sheet_info: Dict) -> str:
    """Build extraction prompt for mechanical equipment."""
    return f"""Extract all mechanical equipment from this mechanical plan drawing.

Drawing Information:
- Number: {sheet_info['drawing_number']}
- Title: {sheet_info['title']}
- Revision: {sheet_info['revision']}
- Type: Mechanical Plan

Extract MECHANICAL EQUIPMENT from schedules, callouts, and tags on the drawing.

For each EQUIPMENT ITEM, provide:
- equipment_mark: Tag/mark number (e.g., AHU-1, EF-1, MAU-2)
- equipment_type: Type of equipment (e.g., Air Handling Unit, Exhaust Fan, Make-Up Air Unit, Unit Heater, Split System)
- area_served: Area or zone served by equipment
- manufacturer: Manufacturer name if shown
- model: Model number if shown
- cfm: Airflow in CFM (integer)
- airflow_cfm: Alternative airflow field (integer)
- hp: Horsepower (decimal)
- bhp: Brake horsepower (decimal)
- voltage: Voltage specification (e.g., "480V", "208V")
- phase: Phase (e.g., "3", "1")
- frequency: Frequency (e.g., "60Hz")
- electrical_spec: Combined electrical spec if individual fields not clear
- mca: Minimum circuit ampacity (decimal)
- mocp: Maximum overcurrent protection (integer)
- rpm: Rotations per minute (integer)
- static_pressure: Static pressure in inches WC (decimal)
- weight_lbs: Weight in pounds (decimal)
- capacity_tons: Cooling capacity in tons (decimal)
- capacity_mbh: Heating capacity in MBH (decimal)
- heating_kw: Electric heating capacity in kW (decimal)
- qty: Quantity (default 1)
- notes: Any special notes or specifications
- specifications: Specification section reference

Return as JSON:
{{
  "equipment": [
    {{
      "equipment_mark": "AHU-1",
      "equipment_type": "Air Handling Unit",
      "area_served": "Production Area",
      "cfm": 5000,
      "hp": 5.0,
      "voltage": "480V",
      "phase": "3",
      "qty": 1,
      "notes": "Variable speed drive"
    }},
    ...
  ]
}}

Only include fields that are clearly visible on the drawing. Leave fields null/empty if not shown.
Be precise with numbers - extract exact values from equipment schedules.

Drawing Text:
{sheet_text}
"""


def parse_extraction_response(response_text: str) -> Dict[str, Any]:
    """Parse JSON response from model."""
    # Try to find JSON in response
    response_text = response_text.strip()

    # Look for JSON block
    if "```json" in response_text:
        start = response_text.find("```json") + 7
        end = response_text.find("```", start)
        response_text = response_text[start:end].strip()
    elif "```" in response_text:
        start = response_text.find("```") + 3
        end = response_text.find("```", start)
        response_text = response_text[start:end].strip()

    try:
        data = json.loads(response_text)
        return data
    except json.JSONDecodeError as e:
        logger.error("JSON parse error: %s", e)
        logger.error("Response text: %s", response_text[:500])
        return {"equipment": []}


def insert_equipment(conn: sqlite3.Connection, sheet_id: int, equipment: Dict[str, Any]) -> None:
    """Insert mechanical equipment record."""

    # Convert None to NULL for numeric fields
    def to_num(val, default=None):
        if val is None or val == "":
            return default
        try:
            return float(val) if isinstance(val, (int, float)) else default
        except:
            return default

    def to_int(val, default=None):
        if val is None or val == "":
            return default
        try:
            return int(float(val)) if isinstance(val, (int, float)) else default
        except:
            return default

    conn.execute("""
        INSERT INTO mechanical_equipment (
            sheet_id, equipment_mark, equipment_type, area_served,
            manufacturer, model, cfm, airflow_cfm, hp, bhp,
            voltage, phase, frequency, electrical_spec,
            mca, mocp, rpm, static_pressure, weight_lbs,
            capacity_tons, capacity_mbh, heating_kw, qty, notes, specifications,
            confidence
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        sheet_id,
        equipment.get("equipment_mark"),
        equipment.get("equipment_type"),
        equipment.get("area_served"),
        equipment.get("manufacturer"),
        equipment.get("model"),
        to_int(equipment.get("cfm")),
        to_int(equipment.get("airflow_cfm")),
        to_num(equipment.get("hp")),
        to_num(equipment.get("bhp")),
        equipment.get("voltage"),
        equipment.get("phase"),
        equipment.get("frequency"),
        equipment.get("electrical_spec"),
        to_num(equipment.get("mca")),
        to_int(equipment.get("mocp")),
        to_int(equipment.get("rpm")),
        to_num(equipment.get("static_pressure")),
        to_num(equipment.get("weight_lbs")),
        to_num(equipment.get("capacity_tons")),
        to_num(equipment.get("capacity_mbh")),
        to_num(equipment.get("heating_kw")),
        equipment.get("qty", 1),
        equipment.get("notes"),
        equipment.get("specifications"),
        0.85  # Default confidence for Sonnet extraction
    ))


def extract_sheet(sheet_id: int, pdf_path: Path) -> Dict[str, Any]:
    """Extract equipment from a single sheet."""

    result = {
        "sheet_id": sheet_id,
        "file_name": pdf_path.name,
        "equipment_count": 0,
        "status": "pending",
        "errors": []
    }

    # Get sheet info
    with get_db(readonly=True) as conn:
        sheet_row = conn.execute(
            "SELECT drawing_number, title, revision FROM sheets WHERE id = ?",
            (sheet_id,)
        ).fetchone()

        if not sheet_row:
            result["status"] = "error"
            result["errors"].append(f"Sheet {sheet_id} not found in database")
            return result

        sheet_info = dict(sheet_row)

    # Extract text
    logger.info("Extracting text from %s...", pdf_path.name)
    sheet_text = extract_pdf_text(pdf_path)

    if not sheet_text.strip():
        result["status"] = "error"
        result["errors"].append("No text extracted from PDF")
        return result

    logger.info("Extracted %d characters of text", len(sheet_text))

    # Build prompt
    prompt = build_extraction_prompt(sheet_text, sheet_info)

    # Call Sonnet
    logger.info("Calling Claude Sonnet for extraction...")
    response = call_sonnet(prompt)

    # Parse response
    data = parse_extraction_response(response)
    equipment_list = data.get("equipment", [])

    logger.info("Extracted %d equipment items", len(equipment_list))

    if not equipment_list:
        result["status"] = "success"
        result["equipment_count"] = 0
        return result

    # Insert to database
    with get_db() as conn:
        for eq in equipment_list:
            try:
                insert_equipment(conn, sheet_id, eq)
                result["equipment_count"] += 1
            except Exception as e:
                logger.error("Error inserting equipment %s: %s", eq.get("equipment_mark"), e)
                result["errors"].append(f"Insert error: {str(e)}")

        # Update sheet status
        conn.execute("""
            UPDATE sheets
            SET extracted_at = CURRENT_TIMESTAMP,
                extraction_model = 'sonnet',
                quality_score = ?
            WHERE id = ?
        """, (0.85, sheet_id))

        conn.commit()

    result["status"] = "success"
    logger.info("Successfully extracted %d equipment items from sheet %d",
                result["equipment_count"], sheet_id)

    return result


def main():
    """Main extraction entry point."""

    sheets_to_process = [
        {
            "sheet_id": 548,
            "file_path": "D:/qms/data/projects/07609-Freshpet/Mechanical/M1101-OVERALL-FIRST-FLOOR-MECHANICAL-PLAN-Rev.1.pdf"
        },
        {
            "sheet_id": 549,
            "file_path": "D:/qms/data/projects/07609-Freshpet/Mechanical/M1201-OVERALL-SECOND-FLOOR-MEZZANINE-MECHANICAL-PLAN-Rev.1.pdf"
        },
        {
            "sheet_id": 550,
            "file_path": "D:/qms/data/projects/07609-Freshpet/Mechanical/M1301-OVERALL-INTERSTITIAL-SPACE-MECHANICAL-PLAN-Rev.1.pdf"
        }
    ]

    print("=" * 80)
    print("Mechanical Plan Extraction - Project 07609 (Freshpet)")
    print("=" * 80)
    print()

    results = []

    for sheet in sheets_to_process:
        sheet_id = sheet["sheet_id"]
        pdf_path = Path(sheet["file_path"])

        print(f"\nProcessing sheet {sheet_id}: {pdf_path.name}")
        print("-" * 80)

        if not pdf_path.exists():
            print(f"ERROR: File not found: {pdf_path}")
            results.append({
                "sheet_id": sheet_id,
                "status": "error",
                "errors": ["File not found"]
            })
            continue

        try:
            result = extract_sheet(sheet_id, pdf_path)
            results.append(result)

            if result["status"] == "success":
                print(f"SUCCESS: Extracted {result['equipment_count']} equipment items")
            else:
                print(f"ERROR: {', '.join(result['errors'])}")

        except Exception as e:
            logger.error("Extraction failed for sheet %d: %s", sheet_id, e, exc_info=True)
            print(f"EXCEPTION: {str(e)}")
            results.append({
                "sheet_id": sheet_id,
                "status": "error",
                "errors": [str(e)]
            })

    # Summary
    print("\n" + "=" * 80)
    print("EXTRACTION SUMMARY")
    print("=" * 80)

    total_equipment = sum(r.get("equipment_count", 0) for r in results)
    success_count = sum(1 for r in results if r["status"] == "success")
    error_count = sum(1 for r in results if r["status"] == "error")

    print(f"Sheets processed: {len(results)}")
    print(f"Successful: {success_count}")
    print(f"Errors: {error_count}")
    print(f"Total equipment extracted: {total_equipment}")
    print()

    for result in results:
        sheet_id = result["sheet_id"]
        status = result["status"]
        count = result.get("equipment_count", 0)
        print(f"  Sheet {sheet_id}: {status.upper()} ({count} items)")
        if result.get("errors"):
            for err in result["errors"]:
                print(f"    - {err}")

    print()

    # Query final counts
    with get_db(readonly=True) as conn:
        for sheet_id in [548, 549, 550]:
            count = conn.execute(
                "SELECT COUNT(*) as n FROM mechanical_equipment WHERE sheet_id = ?",
                (sheet_id,)
            ).fetchone()["n"]
            print(f"Sheet {sheet_id} now has {count} equipment records in database")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
