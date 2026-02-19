"""
Extract data from Freshpet refrigeration drawings.

This script processes three refrigeration drawings from project 07609:
- R4110.1: Machine Room Floor Plan
- R4140.1: Machine Room Roof Plan
- R4510.1: Machine Room Relief Pipe Floor Plan

Extracts:
- Lines (pipe numbers, sizes, materials, specs, from/to locations)
- Equipment (tags, descriptions, types)
- Instruments (tags, types, loop numbers)
- Drawing metadata
"""

import json
import sys
from datetime import datetime
from pathlib import Path

import anthropic

from qms.core import get_db, get_logger

logger = get_logger("extraction")

# Drawing metadata
DRAWINGS = [
    {
        "sheet_id": 607,
        "file_name": "R4110.1-REFRIGERATION-PLAN-MACHINE-ROOM-PIPE-AND-EQUIPMENT-FLOOR-Rev.1.pdf",
        "drawing_number": "R4110.1",
        "title": "REFRIGERATION PLAN - MACHINE ROOM PIPE AND EQUIPMENT - FLOOR",
        "revision": "1",
        "discipline": "Refrigeration",
        "drawing_type": "P&ID",
        "complexity": "medium"
    },
    {
        "sheet_id": 608,
        "file_name": "R4140.1-REFRIGERATION-PLAN-MACHINE-ROOM-PIPE-AND-EQUIPMENT-ROOF-Rev.1.pdf",
        "drawing_number": "R4140.1",
        "title": "REFRIGERATION PLAN - MACHINE ROOM PIPE AND EQUIPMENT - ROOF",
        "revision": "1",
        "discipline": "Refrigeration",
        "drawing_type": "P&ID",
        "complexity": "medium"
    },
    {
        "sheet_id": 609,
        "file_name": "R4510.1-REFRIGERATION-MACHINE-ROOM-RELIEF-PIPE-FLOOR-Rev.1.pdf",
        "drawing_number": "R4510.1",
        "title": "REFRIGERATION - MACHINE ROOM RELIEF PIPE - FLOOR",
        "revision": "1",
        "discipline": "Refrigeration",
        "drawing_type": "P&ID",
        "complexity": "simple"
    }
]

BASE_PATH = Path(r"D:\qms\data\projects\07609-Freshpet\Refrigeration")

EXTRACTION_PROMPT = """You are extracting structured data from a refrigeration P&ID drawing.

Drawing: {title}
Drawing Number: {drawing_number}
Revision: {revision}

Extract ALL of the following items from this drawing:

## 1. PROCESS LINES (refrigerant piping)

For each refrigerant line, extract:
- line_number: Full line number (format: SIZE-REFRIGERANT-NUMBER or similar)
- size: Pipe size (e.g., "2", "3", "4" - in inches)
- material: Pipe material (e.g., "CS" for Carbon Steel, "SS" for Stainless)
- refrigerant: Refrigerant type (e.g., "NH3", "R717", "Ammonia")
- service: Service description (e.g., "Liquid", "Suction", "Hot Gas", "Relief")
- from_location: Starting point/equipment
- to_location: Ending point/equipment
- spec_class: Specification class if shown (e.g., "A1A", "B31.5")

## 2. EQUIPMENT

For each equipment item, extract:
- tag: Equipment tag number (e.g., "C-101", "V-201", "P-301")
- description: Equipment name/description
- equipment_type: Type (e.g., "Compressor", "Vessel", "Pump", "Condenser", "Evaporator")

## 3. INSTRUMENTS

For each instrument, extract:
- tag: Instrument tag (e.g., "PT-101", "TT-201", "PSV-301")
- instrument_type: Type (e.g., "Pressure Transmitter", "Temperature Transmitter", "Pressure Safety Valve")
- loop_number: Associated loop number if shown
- service: What it's measuring/controlling
- location: Where it's located

## 4. NOTES

Extract any important general notes, design criteria, or special requirements.

Return your response as a JSON object with this structure:

```json
{{
  "lines": [
    {{
      "line_number": "2-NH3-101",
      "size": "2",
      "material": "CS",
      "refrigerant": "NH3",
      "service": "Liquid",
      "from_location": "V-201",
      "to_location": "P-301",
      "spec_class": "B31.5",
      "confidence": 0.95
    }}
  ],
  "equipment": [
    {{
      "tag": "C-101",
      "description": "Ammonia Compressor",
      "equipment_type": "Compressor",
      "confidence": 0.98
    }}
  ],
  "instruments": [
    {{
      "tag": "PT-101",
      "instrument_type": "Pressure Transmitter",
      "loop_number": "101",
      "service": "Suction Pressure",
      "location": "Compressor Suction",
      "confidence": 0.95
    }}
  ],
  "notes": [
    "All ammonia piping per IIAR 2",
    "Relief valves sized per ASHRAE 15"
  ]
}}
```

Be thorough - extract EVERY line, equipment item, and instrument you can identify. If you're uncertain about a value, note it in the confidence score (0.0 to 1.0).

Now extract from this drawing:

"""


def extract_pdf_with_claude(pdf_path: Path, sheet_data: dict) -> dict:
    """Extract data from PDF using Claude with vision."""
    logger.info(f"Processing {pdf_path.name}...")

    # Read PDF as base64
    pdf_bytes = pdf_path.read_bytes()

    # Build prompt
    prompt = EXTRACTION_PROMPT.format(
        title=sheet_data["title"],
        drawing_number=sheet_data["drawing_number"],
        revision=sheet_data["revision"]
    )

    # Call Claude with PDF
    client = anthropic.Anthropic()

    try:
        message = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=8192,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "document",
                            "source": {
                                "type": "base64",
                                "media_type": "application/pdf",
                                "data": pdf_bytes.hex()  # Convert bytes to hex for API
                            },
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }
            ]
        )

        # Parse response
        response_text = message.content[0].text

        # Extract JSON from response (handle markdown code blocks)
        if "```json" in response_text:
            json_start = response_text.find("```json") + 7
            json_end = response_text.find("```", json_start)
            json_text = response_text[json_start:json_end].strip()
        elif "```" in response_text:
            json_start = response_text.find("```") + 3
            json_end = response_text.find("```", json_start)
            json_text = response_text[json_start:json_end].strip()
        else:
            json_text = response_text.strip()

        extracted = json.loads(json_text)

        logger.info(f"Extracted: {len(extracted.get('lines', []))} lines, "
                   f"{len(extracted.get('equipment', []))} equipment, "
                   f"{len(extracted.get('instruments', []))} instruments")

        return extracted

    except Exception as e:
        logger.error(f"Extraction failed for {pdf_path.name}: {e}")
        raise


def save_to_database(sheet_id: int, extracted: dict, sheet_data: dict):
    """Save extracted data to the database."""
    with get_db() as conn:
        # Update sheet metadata
        conn.execute("""
            UPDATE sheets
            SET drawing_type = ?,
                complexity = ?,
                extracted_at = ?,
                extraction_model = 'sonnet',
                quality_score = ?
            WHERE id = ?
        """, (
            sheet_data["drawing_type"],
            sheet_data["complexity"],
            datetime.now().isoformat(),
            calculate_quality_score(extracted),
            sheet_id
        ))

        # Insert lines
        for line in extracted.get("lines", []):
            conn.execute("""
                INSERT INTO lines (
                    sheet_id, line_number, size, material, spec_class,
                    from_location, to_location, service, refrigerant, confidence
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
                line.get("confidence", 0.8)
            ))

        # Insert equipment
        for equip in extracted.get("equipment", []):
            conn.execute("""
                INSERT INTO equipment (
                    sheet_id, tag, description, equipment_type, confidence
                ) VALUES (?, ?, ?, ?, ?)
            """, (
                sheet_id,
                equip.get("tag"),
                equip.get("description"),
                equip.get("equipment_type"),
                equip.get("confidence", 0.8)
            ))

        # Insert instruments
        for inst in extracted.get("instruments", []):
            conn.execute("""
                INSERT INTO instruments (
                    sheet_id, tag, instrument_type, loop_number,
                    service, location, confidence, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                sheet_id,
                inst.get("tag"),
                inst.get("instrument_type"),
                inst.get("loop_number"),
                inst.get("service"),
                inst.get("location"),
                inst.get("confidence", 0.8),
                datetime.now().isoformat()
            ))

        # Insert notes as extraction notes
        for note in extracted.get("notes", []):
            conn.execute("""
                INSERT INTO extraction_notes (
                    sheet_id, note_type, description, created_at
                ) VALUES (?, ?, ?, ?)
            """, (
                sheet_id,
                "general",
                note,
                datetime.now().isoformat()
            ))

        conn.commit()
        logger.info(f"Saved sheet {sheet_id} to database")


def calculate_quality_score(extracted: dict) -> float:
    """Calculate overall quality score based on confidence and completeness."""
    total_items = 0
    total_confidence = 0.0

    for category in ["lines", "equipment", "instruments"]:
        items = extracted.get(category, [])
        for item in items:
            total_items += 1
            total_confidence += item.get("confidence", 0.7)

    if total_items == 0:
        return 0.0

    avg_confidence = total_confidence / total_items

    # Bonus for having all categories
    completeness = sum(1 for cat in ["lines", "equipment", "instruments"]
                      if extracted.get(cat, []))
    completeness_factor = completeness / 3.0

    return (avg_confidence * 0.7) + (completeness_factor * 0.3)


def main():
    """Process all three drawings."""
    results = []

    for drawing in DRAWINGS:
        sheet_id = drawing["sheet_id"]
        file_name = drawing["file_name"]
        pdf_path = BASE_PATH / file_name

        if not pdf_path.exists():
            logger.error(f"File not found: {pdf_path}")
            continue

        print(f"\n{'=' * 80}")
        print(f"Extracting: {drawing['title']}")
        print(f"Sheet ID: {sheet_id}")
        print(f"Drawing: {drawing['drawing_number']} Rev {drawing['revision']}")
        print(f"{'=' * 80}\n")

        try:
            # Extract data
            extracted = extract_pdf_with_claude(pdf_path, drawing)

            # Save to database
            save_to_database(sheet_id, extracted, drawing)

            # Record result
            results.append({
                "sheet_id": sheet_id,
                "drawing_number": drawing["drawing_number"],
                "status": "success",
                "lines": len(extracted.get("lines", [])),
                "equipment": len(extracted.get("equipment", [])),
                "instruments": len(extracted.get("instruments", [])),
                "quality_score": calculate_quality_score(extracted)
            })

            print(f"\nExtracted Data:")
            print(f"  Lines: {len(extracted.get('lines', []))}")
            print(f"  Equipment: {len(extracted.get('equipment', []))}")
            print(f"  Instruments: {len(extracted.get('instruments', []))}")
            print(f"  Quality Score: {calculate_quality_score(extracted):.2f}")

        except Exception as e:
            logger.error(f"Failed to process {file_name}: {e}")
            results.append({
                "sheet_id": sheet_id,
                "drawing_number": drawing["drawing_number"],
                "status": "failed",
                "error": str(e)
            })

    # Print summary
    print(f"\n{'=' * 80}")
    print("EXTRACTION SUMMARY")
    print(f"{'=' * 80}\n")

    for result in results:
        status_symbol = "✓" if result["status"] == "success" else "✗"
        print(f"{status_symbol} {result['drawing_number']}: {result['status']}")
        if result["status"] == "success":
            print(f"    Lines: {result['lines']}, Equipment: {result['equipment']}, "
                  f"Instruments: {result['instruments']}, Quality: {result['quality_score']:.2f}")
        else:
            print(f"    Error: {result.get('error', 'Unknown')}")

    successful = sum(1 for r in results if r["status"] == "success")
    print(f"\nCompleted: {successful}/{len(results)} drawings")


if __name__ == "__main__":
    main()
