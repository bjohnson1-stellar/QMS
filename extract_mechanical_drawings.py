"""
Extract data from mechanical drawings for project 07609.

Reads PDF drawings using Anthropic vision API and extracts:
- Mechanical equipment (tags, types, specifications)
- HVAC equipment details (CFM, HP, voltage, etc.)
- Lines (if shown)
- Instruments (if shown)
"""

import json
import sqlite3
import base64
from pathlib import Path
from typing import Dict, List, Any, Optional

# Sheet IDs and paths
SHEETS = [
    {
        "id": 551,
        "path": r"D:\qms\data\projects\07609-Freshpet\Mechanical\M1401-MECHANICAL-OVERALL-ROOF-PLAN-Rev.1.pdf",
        "drawing_number": "M1401-MECHANICAL-OVERALL-ROOF-PLAN",
        "title": "MECHANICAL OVERALL ROOF PLAN",
    },
    {
        "id": 552,
        "path": r"D:\qms\data\projects\07609-Freshpet\Mechanical\M3001-MECHANICAL-SECTIONS-Rev.1.pdf",
        "drawing_number": "M3001-MECHANICAL-SECTIONS",
        "title": "MECHANICAL SECTIONS",
    },
    {
        "id": 553,
        "path": r"D:\qms\data\projects\07609-Freshpet\Mechanical\M4001-ENLARGED-FIRST-FLOOR-MECHANICAL-PLAN-Rev.1.pdf",
        "drawing_number": "M4001-ENLARGED-FIRST-FLOOR-MECHANICAL-PLAN",
        "title": "ENLARGED FIRST FLOOR MECHANICAL PLAN",
    },
]

DB_PATH = r"D:\qms\data\quality.db"


def convert_pdf_to_images(pdf_path: str) -> List[bytes]:
    """Convert PDF pages to PNG images for vision API."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        raise ImportError("PyMuPDF required: pip install PyMuPDF")

    images = []
    doc = fitz.open(pdf_path)

    for page_num in range(len(doc)):
        page = doc[page_num]
        # Render at 2x resolution for better OCR
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
        img_bytes = pix.tobytes("png")
        images.append(img_bytes)

    doc.close()
    return images


def extract_mechanical_data(pdf_path: str, drawing_number: str, drawing_title: str) -> Dict[str, Any]:
    """
    Extract mechanical equipment and instrument data from a drawing.

    Uses Anthropic vision API to read the PDF and extract structured data.
    """
    try:
        import anthropic
    except ImportError:
        raise ImportError("Anthropic SDK required: pip install anthropic")

    # Convert PDF to images
    print(f"Converting {Path(pdf_path).name} to images...")
    images = convert_pdf_to_images(pdf_path)

    # Build prompt for mechanical drawing extraction
    prompt = f"""Extract all mechanical equipment and instrumentation data from this {drawing_title} drawing.

This is drawing number: {drawing_number}

For each MECHANICAL EQUIPMENT item (fans, AHUs, exhaust units, heaters, etc.), extract:
- equipment_mark (tag number, e.g., EF-1, AHU-2, EU-3)
- equipment_type (e.g., "Exhaust Fan", "Air Handling Unit", "Makeup Air Unit")
- area_served (area or room designation)
- manufacturer (if shown)
- model (if shown)
- cfm or airflow_cfm (airflow in CFM)
- hp or bhp (horsepower)
- voltage (e.g., "480V", "208V")
- phase (e.g., "3", "1")
- mca (minimum circuit ampacity, if shown)
- mocp (maximum overcurrent protection, if shown)
- rpm (if shown)
- static_pressure (in inches water column, if shown)
- capacity_tons (cooling capacity, if applicable)
- capacity_mbh (heating capacity in MBH, if applicable)
- heating_kw (electric heating in kW, if applicable)
- qty (quantity if multiple units)
- notes (any special notes or requirements)

For each INSTRUMENT (sensors, controllers, dampers), extract:
- tag (instrument tag, e.g., T-1, TS-2, DACT-3)
- instrument_type (e.g., "Temperature Sensor", "Damper Actuator")
- service (what it controls/monitors)
- description (brief description)

Return as JSON with this structure:
{{
    "mechanical_equipment": [
        {{
            "equipment_mark": "EF-1",
            "equipment_type": "Exhaust Fan",
            "area_served": "Process Area",
            "cfm": 5000,
            "hp": 5.0,
            "voltage": "480V",
            "phase": "3",
            ...
        }}
    ],
    "instruments": [
        {{
            "tag": "TS-101",
            "instrument_type": "Temperature Sensor",
            "service": "Supply Air Temperature",
            "description": "Duct mounted temperature sensor"
        }}
    ],
    "extraction_notes": "Any notes about extraction quality, ambiguities, or issues"
}}

IMPORTANT:
- Extract ALL equipment shown on the drawing
- Use null for missing/unknown values
- Be precise with numeric values
- Include equipment schedules if present
- Note any equipment that is difficult to read or ambiguous"""

    # Prepare image content for API
    content = [{"type": "text", "text": prompt}]

    for i, img_bytes in enumerate(images):
        img_b64 = base64.standard_b64encode(img_bytes).decode("utf-8")
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": img_b64,
            },
        })

    # Call Anthropic API with vision
    print(f"Calling Anthropic API for extraction...")
    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=8192,
        messages=[{"role": "user", "content": content}],
    )

    # Parse response
    response_text = response.content[0].text

    # Extract JSON from response (handle markdown code blocks)
    if "```json" in response_text:
        json_start = response_text.index("```json") + 7
        json_end = response_text.index("```", json_start)
        json_text = response_text[json_start:json_end].strip()
    elif "```" in response_text:
        json_start = response_text.index("```") + 3
        json_end = response_text.index("```", json_start)
        json_text = response_text[json_start:json_end].strip()
    else:
        json_text = response_text.strip()

    return json.loads(json_text)


def store_extraction(conn: sqlite3.Connection, sheet_id: int, data: Dict[str, Any]) -> Dict[str, int]:
    """Store extracted data in the database."""
    counts = {"mechanical_equipment": 0, "instruments": 0}

    # Store mechanical equipment
    for eq in data.get("mechanical_equipment", []):
        conn.execute("""
            INSERT INTO mechanical_equipment (
                sheet_id, equipment_mark, equipment_type, area_served,
                manufacturer, model, cfm, airflow_cfm, hp, bhp,
                voltage, phase, frequency, mca, mocp, rpm,
                static_pressure, capacity_tons, capacity_mbh, heating_kw,
                qty, notes, confidence
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            sheet_id,
            eq.get("equipment_mark"),
            eq.get("equipment_type"),
            eq.get("area_served"),
            eq.get("manufacturer"),
            eq.get("model"),
            eq.get("cfm"),
            eq.get("airflow_cfm"),
            eq.get("hp"),
            eq.get("bhp"),
            eq.get("voltage"),
            eq.get("phase"),
            eq.get("frequency"),
            eq.get("mca"),
            eq.get("mocp"),
            eq.get("rpm"),
            eq.get("static_pressure"),
            eq.get("capacity_tons"),
            eq.get("capacity_mbh"),
            eq.get("heating_kw"),
            eq.get("qty", 1),
            eq.get("notes"),
            0.85,  # Sonnet extraction confidence
        ))
        counts["mechanical_equipment"] += 1

    # Store instruments
    for inst in data.get("instruments", []):
        conn.execute("""
            INSERT INTO instruments (
                sheet_id, tag, instrument_type, service, description,
                confidence, extraction_notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            sheet_id,
            inst.get("tag"),
            inst.get("instrument_type"),
            inst.get("service"),
            inst.get("description"),
            0.85,
            inst.get("notes"),
        ))
        counts["instruments"] += 1

    # Update sheet extraction status
    conn.execute("""
        UPDATE sheets
        SET extracted_at = CURRENT_TIMESTAMP,
            extraction_model = 'claude-sonnet-4-5-20250929',
            quality_score = 0.85,
            drawing_type = 'Mechanical Plan',
            complexity = 'medium'
        WHERE id = ?
    """, (sheet_id,))

    return counts


def main():
    """Extract data from all three mechanical drawings."""
    print("=" * 70)
    print("MECHANICAL DRAWING EXTRACTION - Project 07609 (Freshpet)")
    print("=" * 70)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    results = []

    for sheet in SHEETS:
        print(f"\n{'='*70}")
        print(f"Sheet {sheet['id']}: {sheet['drawing_number']}")
        print(f"Title: {sheet['title']}")
        print(f"Path: {sheet['path']}")
        print(f"{'='*70}")

        try:
            # Extract data
            data = extract_mechanical_data(
                sheet["path"],
                sheet["drawing_number"],
                sheet["title"]
            )

            # Store in database
            counts = store_extraction(conn, sheet["id"], data)

            # Print summary
            print(f"\nExtracted:")
            print(f"  - Mechanical Equipment: {counts['mechanical_equipment']}")
            print(f"  - Instruments: {counts['instruments']}")

            if data.get("extraction_notes"):
                print(f"\nNotes: {data['extraction_notes']}")

            # Show sample equipment
            if data.get("mechanical_equipment"):
                print(f"\nSample Equipment:")
                for eq in data["mechanical_equipment"][:3]:
                    print(f"  - {eq.get('equipment_mark')}: {eq.get('equipment_type')}")
                    if eq.get('cfm'):
                        print(f"    CFM: {eq['cfm']}")
                    if eq.get('hp'):
                        print(f"    HP: {eq['hp']}")

            results.append({
                "sheet_id": sheet["id"],
                "drawing_number": sheet["drawing_number"],
                "status": "success",
                "counts": counts,
                "notes": data.get("extraction_notes"),
            })

        except Exception as e:
            print(f"\nERROR: {e}")
            import traceback
            traceback.print_exc()

            results.append({
                "sheet_id": sheet["id"],
                "drawing_number": sheet["drawing_number"],
                "status": "failed",
                "error": str(e),
            })

    conn.commit()
    conn.close()

    # Final summary
    print(f"\n{'='*70}")
    print("EXTRACTION SUMMARY")
    print(f"{'='*70}")

    success_count = sum(1 for r in results if r["status"] == "success")
    total_equipment = sum(r.get("counts", {}).get("mechanical_equipment", 0) for r in results)
    total_instruments = sum(r.get("counts", {}).get("instruments", 0) for r in results)

    print(f"Sheets processed: {len(results)}")
    print(f"Successful: {success_count}")
    print(f"Failed: {len(results) - success_count}")
    print(f"\nTotal Extracted:")
    print(f"  - Mechanical Equipment: {total_equipment}")
    print(f"  - Instruments: {total_instruments}")

    return results


if __name__ == "__main__":
    main()
