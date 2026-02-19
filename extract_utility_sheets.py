"""
Extract utility equipment data from Freshpet utility drawings.

This script reads utility plan PDFs and extracts equipment schedules,
equipment marks, and specifications into the database.
"""

import json
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, List

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from qms.core import get_db, get_logger

logger = get_logger("extract_utility_sheets")


EXTRACTION_PROMPT = """You are analyzing a Utility Plan drawing for a food processing facility.

Extract ALL equipment from equipment schedules and the drawing itself.

For EACH piece of equipment, provide:
- equipment_mark: Tag/mark (e.g., "AHU-1", "HX-101", "P-1")
- equipment_type: Type (e.g., "Air Handling Unit", "Heat Exchanger", "Pump", "Water Heater", "Air Compressor")
- location: Location/area served
- manufacturer: Manufacturer name
- model: Model number
- capacity: Capacity (e.g., "1000 CFM", "100 GPM", "50 GAL")
- design_pressure: Design pressure (e.g., "150 PSI")
- dimensions: Dimensions (e.g., "48x24x36")
- weight_lbs: Empty weight in pounds (integer)
- operating_weight_lbs: Operating weight in pounds (integer)
- power_voltage: Electrical voltage (e.g., "480V-3PH-60HZ")
- power_hp: Horsepower (decimal)
- qty: Quantity (integer, default 1)

Additional schedule-specific fields if present:
- gpm: Flow rate in GPM
- temperature_in: Inlet temperature (F)
- temperature_out: Outlet temperature (F)
- pressure_drop_psi: Pressure drop
- steam_pressure_psi: Steam pressure
- flow_rate_lbs_hr: Flow rate in lbs/hr
- inlet_size: Inlet pipe size
- outlet_size: Outlet pipe size

Also capture:
- specifications: Spec references
- notes: Any special notes
- contact_info: Vendor/contact info if shown

Return as JSON with this structure:
{
  "sheet_info": {
    "drawing_number": "...",
    "title": "...",
    "revision": "..."
  },
  "equipment": [
    {
      "equipment_mark": "...",
      "equipment_type": "...",
      "location": "...",
      ... other fields ...
    }
  ]
}

Only include fields that have actual values. Be thorough - extract EVERY piece of equipment shown.
"""


def extract_with_anthropic(pdf_path: Path, sheet_id: int) -> Dict[str, Any]:
    """Extract equipment data using Claude vision API."""
    try:
        import anthropic
        import base64
    except ImportError:
        logger.error("anthropic SDK required: pip install anthropic")
        return {"equipment": []}

    # Read PDF as base64
    pdf_bytes = pdf_path.read_bytes()
    pdf_b64 = base64.standard_b64encode(pdf_bytes).decode("utf-8")

    client = anthropic.Anthropic()

    logger.info(f"Sending {pdf_path.name} to Claude Sonnet 4.5 for extraction...")

    response = client.messages.create(
        model="claude-sonnet-4-5-20250929",
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
                            "data": pdf_b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": EXTRACTION_PROMPT,
                    },
                ],
            }
        ],
    )

    # Parse response
    text = response.content[0].text

    # Extract JSON from response (may be wrapped in markdown code blocks)
    if "```json" in text:
        json_start = text.find("```json") + 7
        json_end = text.find("```", json_start)
        text = text[json_start:json_end].strip()
    elif "```" in text:
        json_start = text.find("```") + 3
        json_end = text.find("```", json_start)
        text = text[json_start:json_end].strip()

    try:
        data = json.loads(text)
        logger.info(f"Extracted {len(data.get('equipment', []))} equipment items")
        return data
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error: {e}")
        logger.error(f"Response text: {text[:500]}")
        return {"equipment": []}


def load_equipment_to_db(sheet_id: int, equipment_list: List[Dict[str, Any]]) -> int:
    """Load extracted equipment into utility_equipment table."""
    count = 0

    with get_db() as conn:
        # Clear existing equipment for this sheet
        conn.execute("DELETE FROM utility_equipment WHERE sheet_id = ?", (sheet_id,))

        for eq in equipment_list:
            # Map fields to table columns
            values = {
                "sheet_id": sheet_id,
                "equipment_mark": eq.get("equipment_mark", ""),
                "equipment_type": eq.get("equipment_type"),
                "location": eq.get("location"),
                "manufacturer": eq.get("manufacturer"),
                "model": eq.get("model"),
                "capacity": eq.get("capacity"),
                "design_pressure": eq.get("design_pressure"),
                "dimensions": eq.get("dimensions"),
                "weight_lbs": eq.get("weight_lbs"),
                "operating_weight_lbs": eq.get("operating_weight_lbs"),
                "power_voltage": eq.get("power_voltage"),
                "power_hp": eq.get("power_hp"),
                "qty": eq.get("qty", 1),
                "gpm": eq.get("gpm"),
                "temperature_in": eq.get("temperature_in"),
                "temperature_out": eq.get("temperature_out"),
                "pressure_drop_psi": eq.get("pressure_drop_psi"),
                "steam_pressure_psi": eq.get("steam_pressure_psi"),
                "flow_rate_lbs_hr": eq.get("flow_rate_lbs_hr"),
                "inlet_size": eq.get("inlet_size"),
                "outlet_size": eq.get("outlet_size"),
                "specifications": eq.get("specifications"),
                "notes": eq.get("notes"),
                "contact_info": eq.get("contact_info"),
                "confidence": 0.85,  # Sonnet extraction confidence
            }

            # Build INSERT statement
            cols = ", ".join(values.keys())
            placeholders = ", ".join(["?" for _ in values])
            sql = f"INSERT INTO utility_equipment ({cols}) VALUES ({placeholders})"

            conn.execute(sql, list(values.values()))
            count += 1

        # Update sheet extraction status
        conn.execute(
            """UPDATE sheets
               SET extracted_at = CURRENT_TIMESTAMP,
                   extraction_model = 'sonnet',
                   quality_score = 0.85
               WHERE id = ?""",
            (sheet_id,)
        )

        conn.commit()

    return count


def main():
    """Extract equipment from the three specified sheets."""

    sheets_to_process = [
        (689, "U1161-PARTIAL-FIRST-FLOOR-UTILITIES-PLAN---AREA-6-Rev.1.pdf"),
        (690, "U1301-UTILITY-OVERALL-INTERSTITIAL-FLOOR-PLAN-Rev.2.pdf"),
        (691, "U1401-UTILITY-OVERALL-ROOF-PLAN-Rev.2.pdf"),
    ]

    base_path = Path(r"D:\qms\data\projects\07609-Freshpet\Utility")

    total_equipment = 0
    results = []

    for sheet_id, filename in sheets_to_process:
        pdf_path = base_path / filename

        if not pdf_path.exists():
            logger.error(f"File not found: {pdf_path}")
            continue

        logger.info(f"\n{'='*80}")
        logger.info(f"Processing Sheet {sheet_id}: {filename}")
        logger.info(f"{'='*80}")

        # Extract data
        extracted_data = extract_with_anthropic(pdf_path, sheet_id)

        # Save raw extraction to JSON
        json_path = pdf_path.with_suffix(".extraction.json")
        json_path.write_text(json.dumps(extracted_data, indent=2))
        logger.info(f"Saved raw extraction to: {json_path}")

        # Load to database
        equipment_list = extracted_data.get("equipment", [])
        if equipment_list:
            count = load_equipment_to_db(sheet_id, equipment_list)
            total_equipment += count
            logger.info(f"Loaded {count} equipment items to database")

            results.append({
                "sheet_id": sheet_id,
                "filename": filename,
                "equipment_count": count,
                "status": "success"
            })
        else:
            logger.warning(f"No equipment extracted from {filename}")
            results.append({
                "sheet_id": sheet_id,
                "filename": filename,
                "equipment_count": 0,
                "status": "no_data"
            })

    # Summary
    logger.info(f"\n{'='*80}")
    logger.info("EXTRACTION SUMMARY")
    logger.info(f"{'='*80}")
    for r in results:
        logger.info(f"Sheet {r['sheet_id']}: {r['equipment_count']} items ({r['status']})")
    logger.info(f"\nTotal Equipment Extracted: {total_equipment}")
    logger.info(f"{'='*80}")


if __name__ == "__main__":
    main()
