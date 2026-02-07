#!/usr/bin/env python3
"""
Refrigeration Schedule Extraction Script
Extract data from R60008, R60009, R60010 (Sheets 73-75)
Project 07308-BIRDCAGE
"""

import sqlite3
import json
import os
import sys
import base64
from datetime import datetime
from pathlib import Path

# Configuration
DB_PATH = "D:/quality.db"

# Drawing specifications for sheets 73-75
DRAWINGS = [
    {
        "sheet_id": 73,
        "file_path": "D:/Projects/07308-BIRDCAGE/Refrigeration/R60008-REFRIGERATION-SCHEDULES-Rev.10.pdf",
        "drawing_number": "R60008",
        "revision": "10"
    },
    {
        "sheet_id": 74,
        "file_path": "D:/Projects/07308-BIRDCAGE/Refrigeration/R60009-REFRIGERATION-SCHEDULES-Rev.8.pdf",
        "drawing_number": "R60009",
        "revision": "8"
    },
    {
        "sheet_id": 75,
        "file_path": "D:/Projects/07308-BIRDCAGE/Refrigeration/R60010-REFRIGERATION-SCHEDULES-Rev.10.pdf",
        "drawing_number": "R60010",
        "revision": "10"
    }
]

EXTRACTION_PROMPT = """You are analyzing a refrigeration schedule drawing. These schedules contain equipment data, specifications, and technical details.

Please extract ALL schedule data from this drawing. Look for:

1. **Equipment Schedules** (compressors, condensers, evaporators, pumps, fans, vessels, heat exchangers, etc.)
   - Equipment tag/ID (like "COMP-1", "COND-1A", "EVAP-101", etc.)
   - Equipment type (compressor, condenser, evaporator, pump, fan, vessel, etc.)
   - Description or location served
   - Manufacturer/model (if shown)
   - Capacity/size specifications
   - Refrigerant type (NH3, R404A, etc.)
   - Motor HP/power
   - Voltage/electrical specs
   - Flow rates, temperatures, pressures
   - Notes/remarks

2. **Piping/Line Information** (if shown)
   - Line number/tag
   - Size
   - Material
   - Service (suction, discharge, liquid, etc.)
   - Insulation requirements

3. **Instrument/Valve List** (if shown)
   - Instrument tag (PT-100, TT-200, FCV-300, etc.)
   - Type (pressure transmitter, temperature, flow control valve, etc.)
   - Location/service

4. **Notes and General Information**
   - Special requirements
   - Installation notes
   - References to other drawings

Return the extracted data as a JSON object with this structure:
{
    "drawing_info": {
        "drawing_number": "R60008",
        "title": "extracted title from drawing",
        "revision": "10",
        "has_schedules": true,
        "schedule_types": ["list of schedule types found"]
    },
    "equipment": [
        {
            "tag": "equipment tag/ID",
            "type": "compressor/condenser/evaporator/pump/fan/vessel/etc",
            "description": "full description or area served",
            "manufacturer": "if shown",
            "model": "if shown",
            "capacity": "size/capacity with units",
            "refrigerant": "if shown",
            "motor_hp": "if shown",
            "voltage": "if shown",
            "flow_rate": "if shown",
            "temperature": "if shown",
            "pressure": "if shown",
            "notes": "any additional specifications",
            "confidence": 0.95
        }
    ],
    "lines": [
        {
            "line_number": "line tag",
            "size": "pipe size",
            "material": "pipe material",
            "service": "suction/discharge/liquid/etc",
            "confidence": 0.90
        }
    ],
    "instruments": [
        {
            "tag": "instrument tag",
            "type": "PT/TT/FCV/etc",
            "description": "what it measures or controls",
            "confidence": 0.90
        }
    ],
    "notes": [
        "Important general note 1",
        "Important general note 2"
    ],
    "extraction_quality": {
        "overall_score": 0.85,
        "readability": "good/fair/poor",
        "completeness": "complete/partial",
        "issues": ["list any issues with extraction"]
    }
}

Be thorough and extract ALL visible data from all schedules on the drawing. For confidence scores:
- 0.95+ : Clear, unambiguous text
- 0.80-0.94 : Readable with minor uncertainty
- 0.60-0.79 : Partially unclear or ambiguous
- <0.60 : Poor quality or very uncertain

If you cannot read something clearly, still include it with lower confidence and note the issue in the "notes" field."""


def pdf_to_base64_image(pdf_path):
    """Convert PDF to base64-encoded PNG image using PyMuPDF."""
    try:
        import fitz  # PyMuPDF

        print(f"    Opening PDF with PyMuPDF...")
        doc = fitz.open(pdf_path)
        page = doc[0]  # First page

        # Render at high resolution (300 DPI)
        mat = fitz.Matrix(300/72, 300/72)  # 72 is default DPI
        pix = page.get_pixmap(matrix=mat)

        # Convert to PNG bytes
        img_bytes = pix.tobytes("png")
        print(f"    Image size: {len(img_bytes)} bytes")

        doc.close()

        return base64.standard_b64encode(img_bytes).decode('utf-8')

    except ImportError:
        raise Exception("PyMuPDF (fitz) not available. Please install: pip install PyMuPDF")
    except Exception as e:
        raise Exception(f"PDF conversion failed: {str(e)}")


def extract_with_claude(image_base64, drawing_info):
    """Use Claude API to extract data from drawing image."""
    try:
        import anthropic
    except ImportError:
        raise Exception("Anthropic SDK not available. Please install: pip install anthropic")

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise Exception("ANTHROPIC_API_KEY environment variable not set")

    client = anthropic.Anthropic(api_key=api_key)

    print(f"    Analyzing with Claude Sonnet 4.5...")

    message = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=16000,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": image_base64,
                        },
                    },
                    {
                        "type": "text",
                        "text": f"{EXTRACTION_PROMPT}\n\nDrawing: {drawing_info['drawing_number']} Rev {drawing_info['revision']}"
                    }
                ],
            }
        ],
    )

    # Extract JSON from response
    response_text = message.content[0].text
    print(f"    Received response ({len(response_text)} chars)")

    # Try to parse JSON from response
    try:
        # Look for JSON block
        if "```json" in response_text:
            json_start = response_text.index("```json") + 7
            json_end = response_text.index("```", json_start)
            json_str = response_text[json_start:json_end].strip()
        elif "```" in response_text:
            json_start = response_text.index("```") + 3
            json_end = response_text.index("```", json_start)
            json_str = response_text[json_start:json_end].strip()
        else:
            # Assume entire response is JSON
            json_str = response_text.strip()

        data = json.loads(json_str)
        return data

    except json.JSONDecodeError as e:
        print(f"    WARNING: Could not parse JSON response: {e}")
        print(f"    Response preview: {response_text[:500]}")
        return {
            "error": "JSON parse error",
            "raw_response": response_text[:2000],  # First 2000 chars
            "extraction_quality": {"overall_score": 0.0}
        }


def store_extraction(conn, sheet_id, data, model_used):
    """Store extracted data in database."""
    cursor = conn.cursor()

    equipment_count = 0
    lines_count = 0
    instruments_count = 0
    flags_count = 0

    # Store equipment
    if "equipment" in data and data["equipment"]:
        for eq in data["equipment"]:
            try:
                # Build description from available fields
                desc_parts = []
                if eq.get("description"):
                    desc_parts.append(eq["description"])
                for key in ["manufacturer", "model", "capacity"]:
                    if key in eq and eq[key]:
                        desc_parts.append(f"{key}: {eq[key]}")

                full_description = "; ".join(desc_parts) if desc_parts else ""

                cursor.execute("""
                    INSERT INTO equipment (sheet_id, tag, description, equipment_type, confidence)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    sheet_id,
                    eq.get("tag", ""),
                    full_description,
                    eq.get("type", ""),
                    eq.get("confidence", 0.85)
                ))
                equipment_count += 1

                # Flag low confidence items
                if eq.get("confidence", 1.0) < 0.70:
                    cursor.execute("""
                        INSERT INTO extraction_flags (sheet_id, field, issue, severity)
                        VALUES (?, ?, ?, ?)
                    """, (sheet_id, f"equipment:{eq.get('tag')}",
                          f"Low confidence ({eq.get('confidence'):.2f})", "medium"))
                    flags_count += 1

            except sqlite3.Error as e:
                print(f"    Warning: Could not insert equipment {eq.get('tag')}: {e}")

    # Store lines
    if "lines" in data and data["lines"]:
        for line in data["lines"]:
            try:
                cursor.execute("""
                    INSERT INTO lines (sheet_id, line_number, size, material, service, confidence)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    sheet_id,
                    line.get("line_number", ""),
                    line.get("size", ""),
                    line.get("material", ""),
                    line.get("service", ""),
                    line.get("confidence", 0.85)
                ))
                lines_count += 1
            except sqlite3.Error as e:
                print(f"    Warning: Could not insert line {line.get('line_number')}: {e}")

    # Store instruments
    if "instruments" in data and data["instruments"]:
        for inst in data["instruments"]:
            try:
                cursor.execute("""
                    INSERT INTO instruments (sheet_id, tag, instrument_type, confidence)
                    VALUES (?, ?, ?, ?)
                """, (
                    sheet_id,
                    inst.get("tag", ""),
                    inst.get("type", "") or inst.get("description", ""),
                    inst.get("confidence", 0.85)
                ))
                instruments_count += 1
            except sqlite3.Error as e:
                print(f"    Warning: Could not insert instrument {inst.get('tag')}: {e}")

    # Store extraction issues as flags
    if "extraction_quality" in data and "issues" in data["extraction_quality"]:
        for issue in data["extraction_quality"]["issues"]:
            cursor.execute("""
                INSERT INTO extraction_flags (sheet_id, field, issue, severity)
                VALUES (?, ?, ?, ?)
            """, (sheet_id, "general", issue, "low"))
            flags_count += 1

    # Update sheet metadata
    quality_score = 0.0
    if "extraction_quality" in data:
        quality_score = data["extraction_quality"].get("overall_score", 0.0)

    cursor.execute("""
        UPDATE sheets
        SET extracted_at = ?,
            extraction_model = ?,
            quality_score = ?,
            drawing_type = 'schedule',
            complexity = 'medium'
        WHERE id = ?
    """, (datetime.now().isoformat(), model_used, quality_score, sheet_id))

    conn.commit()

    return {
        "equipment": equipment_count,
        "lines": lines_count,
        "instruments": instruments_count,
        "flags": flags_count,
        "quality_score": quality_score
    }


def main():
    """Main extraction process."""

    print("=" * 80)
    print("REFRIGERATION SCHEDULE EXTRACTION")
    print("Project: 07308-BIRDCAGE")
    print("Sheets: 73-75 (R60008, R60009, R60010)")
    print("=" * 80)
    print()

    # Connect to database
    conn = sqlite3.connect(DB_PATH)

    results = []

    for drawing in DRAWINGS:
        print(f"Sheet {drawing['sheet_id']}: {drawing['drawing_number']} Rev {drawing['revision']}")
        print("-" * 80)

        try:
            # Check if file exists
            if not os.path.exists(drawing['file_path']):
                print(f"  ERROR: File not found: {drawing['file_path']}")
                results.append({
                    "sheet_id": drawing['sheet_id'],
                    "drawing_number": drawing['drawing_number'],
                    "status": "error",
                    "error": "File not found"
                })
                print()
                continue

            # Convert PDF to image
            print(f"  Step 1: Converting PDF to image...")
            image_base64 = pdf_to_base64_image(drawing['file_path'])
            print(f"    Base64 length: {len(image_base64)} chars")

            # Extract with Claude
            print(f"  Step 2: Extracting data with Claude Vision API...")
            data = extract_with_claude(image_base64, drawing)

            if "error" in data:
                print(f"  ERROR: {data['error']}")
                if "raw_response" in data:
                    print(f"  Response preview: {data['raw_response'][:300]}...")
                results.append({
                    "sheet_id": drawing['sheet_id'],
                    "drawing_number": drawing['drawing_number'],
                    "status": "error",
                    "error": data['error']
                })
                print()
                continue

            # Store in database
            print(f"  Step 3: Storing extracted data in database...")
            stats = store_extraction(conn, drawing['sheet_id'], data, "claude-sonnet-4-5")

            print(f"  COMPLETE:")
            print(f"    Equipment: {stats['equipment']}")
            print(f"    Lines: {stats['lines']}")
            print(f"    Instruments: {stats['instruments']}")
            print(f"    Flags: {stats['flags']}")
            print(f"    Quality Score: {stats['quality_score']:.2f}")

            results.append({
                "sheet_id": drawing['sheet_id'],
                "drawing_number": drawing['drawing_number'],
                "status": "success",
                "stats": stats
            })

        except Exception as e:
            print(f"  ERROR: {str(e)}")
            import traceback
            traceback.print_exc()
            results.append({
                "sheet_id": drawing['sheet_id'],
                "drawing_number": drawing['drawing_number'],
                "status": "error",
                "error": str(e)
            })

        print()

    conn.close()

    # Print summary
    print("=" * 80)
    print("EXTRACTION SUMMARY")
    print("=" * 80)
    print()

    success_count = sum(1 for r in results if r['status'] == 'success')
    error_count = sum(1 for r in results if r['status'] == 'error')

    print(f"Total Sheets Processed: {len(results)}")
    print(f"  Successful: {success_count}")
    print(f"  Errors: {error_count}")
    print()

    if success_count > 0:
        print("Successful Extractions:")
        total_equipment = 0
        total_lines = 0
        total_instruments = 0
        for r in results:
            if r['status'] == 'success':
                stats = r['stats']
                print(f"  {r['drawing_number']}: {stats['equipment']} equip, "
                      f"{stats['lines']} lines, {stats['instruments']} instr "
                      f"(quality={stats['quality_score']:.2f})")
                total_equipment += stats['equipment']
                total_lines += stats['lines']
                total_instruments += stats['instruments']

        print()
        print(f"TOTALS: {total_equipment} equipment, {total_lines} lines, {total_instruments} instruments")

    if error_count > 0:
        print()
        print("Errors:")
        for r in results:
            if r['status'] == 'error':
                print(f"  {r['drawing_number']}: {r['error']}")

    print()
    print("=" * 80)
    return 0 if error_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
