#!/usr/bin/env python3
"""
Extract data from refrigeration detail drawings for project 07308-BIRDCAGE
Sheets 43-45: R50012, R50100, R50101 (Detail drawings)
"""

import os
import sys
import json
import sqlite3
import base64
from pathlib import Path
from anthropic import Anthropic

# Initialize Anthropic client
client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

DB_PATH = "D:/quality.db"

SHEETS = [
    {
        "id": 43,
        "path": "D:/Projects/07308-BIRDCAGE/Refrigeration/R50012-REFRIGERATION-DETAILS-GENERAL-Rev.3.pdf",
        "drawing_number": "R50012",
        "title": "REFRIGERATION-DETAILS-GENERAL",
        "revision": "3"
    },
    {
        "id": 44,
        "path": "D:/Projects/07308-BIRDCAGE/Refrigeration/R50100-REFRIGERATION-DETAILS-PIPE-AND-EQUIPMENT-Rev.3.pdf",
        "drawing_number": "R50100",
        "title": "REFRIGERATION-DETAILS-PIPE-AND-EQUIPMENT",
        "revision": "3"
    },
    {
        "id": 45,
        "path": "D:/Projects/07308-BIRDCAGE/Refrigeration/R50101-REFRIGERATION-DETAILS-PIPE-AND-EQUIPMENT-Rev.3.pdf",
        "drawing_number": "R50101",
        "title": "REFRIGERATION-DETAILS-PIPE-AND-EQUIPMENT",
        "revision": "3"
    }
]

EXTRACTION_PROMPT = """Extract all piping, equipment, and instrumentation data from this refrigeration detail drawing.

IMPORTANT: This is a DETAIL drawing showing construction details, pipe supports, equipment mounting, and assembly details.

For each PIPE/LINE detail shown:
- Line number or identifier
- Size (e.g., "2-1/2\"", "1-1/2\"")
- Material/specification (e.g., "SCH 40", "SCH 80", "CS", "SS")
- Service if noted (e.g., "RELIEF", "LIQUID", "SUCTION")
- From/to locations if shown
- Special notes (insulation, heat tracing, etc.)

For each EQUIPMENT item or detail:
- Tag number if shown
- Equipment type (valve, support, instrument, etc.)
- Description from drawing

For each WELD detail:
- Weld ID/designation
- Weld type (BW=Butt Weld, SW=Socket Weld, FW=Fillet Weld)
- Size information
- Joint type if shown
- NDE requirements if noted (RT, PT, MT, VT, etc.)

For each INSTRUMENT or VALVE:
- Tag number
- Type (PSV, PRV, control valve, isolation valve, etc.)
- Size if shown

SPECIAL ATTENTION for refrigeration details:
- Pressure relief valve details (PSV, PRV)
- Piping support details
- Valve mounting details
- Equipment pad/foundation details
- Insulation details
- Vibration isolation details

Return ONLY valid JSON in this exact format:
{
  "lines": [
    {
      "line_number": "string",
      "size": "string",
      "material": "string",
      "service": "string or null",
      "from_location": "string or null",
      "to_location": "string or null",
      "confidence": 0.0-1.0
    }
  ],
  "equipment": [
    {
      "tag": "string",
      "equipment_type": "string",
      "description": "string",
      "confidence": 0.0-1.0
    }
  ],
  "instruments": [
    {
      "tag": "string",
      "instrument_type": "string",
      "loop_number": "string or null",
      "confidence": 0.0-1.0
    }
  ],
  "welds": [
    {
      "weld_id": "string",
      "weld_type": "string (BW/SW/FW)",
      "size": "string or null",
      "joint_type": "string or null",
      "nde_required": "string or null",
      "confidence": 0.0-1.0
    }
  ],
  "notes": "Any observations about drawing quality, unclear items, or extraction challenges"
}

Focus on extracting clear, verifiable data. Set confidence lower (0.5-0.7) for unclear or ambiguous items."""


def encode_pdf_page(pdf_path: str, page: int = 1) -> str:
    """Convert first page of PDF to base64-encoded image."""
    try:
        # Try using PyMuPDF (fitz) if available
        import fitz
        doc = fitz.open(pdf_path)
        if page > len(doc):
            page = len(doc)

        pix = doc[page - 1].get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x zoom for better quality
        img_data = pix.pil_tobytes(format="PNG")
        doc.close()

        return base64.standard_b64encode(img_data).decode("utf-8")
    except ImportError:
        print("PyMuPDF not available, trying pdf2image...")
        try:
            from pdf2image import convert_from_path
            from io import BytesIO

            images = convert_from_path(pdf_path, first_page=page, last_page=page, dpi=150)
            if images:
                buffer = BytesIO()
                images[0].save(buffer, format="PNG")
                return base64.standard_b64encode(buffer.getvalue()).decode("utf-8")
        except Exception as e:
            print(f"Error converting PDF: {e}")
            raise


def extract_from_drawing(sheet_info: dict) -> dict:
    """Extract data from a single drawing using Claude API."""
    print(f"\nProcessing: {sheet_info['drawing_number']} Rev {sheet_info['revision']}")
    print(f"Path: {sheet_info['path']}")

    # Check if file exists
    if not os.path.exists(sheet_info['path']):
        print(f"ERROR: File not found: {sheet_info['path']}")
        return None

    # Convert PDF to image
    print("Converting PDF to image...")
    try:
        image_data = encode_pdf_page(sheet_info['path'])
    except Exception as e:
        print(f"ERROR: Could not convert PDF: {e}")
        return None

    # Call Claude API
    print("Calling Claude API for extraction...")
    try:
        response = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=4096,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": image_data,
                            },
                        },
                        {
                            "type": "text",
                            "text": EXTRACTION_PROMPT
                        }
                    ],
                }
            ],
        )

        # Parse response
        response_text = response.content[0].text

        # Try to extract JSON from response
        json_start = response_text.find('{')
        json_end = response_text.rfind('}') + 1

        if json_start >= 0 and json_end > json_start:
            json_text = response_text[json_start:json_end]
            extracted_data = json.loads(json_text)

            print(f"Extraction complete:")
            print(f"  - Lines: {len(extracted_data.get('lines', []))}")
            print(f"  - Equipment: {len(extracted_data.get('equipment', []))}")
            print(f"  - Instruments: {len(extracted_data.get('instruments', []))}")
            print(f"  - Welds: {len(extracted_data.get('welds', []))}")

            if extracted_data.get('notes'):
                print(f"  - Notes: {extracted_data['notes']}")

            return extracted_data
        else:
            print(f"ERROR: Could not find JSON in response")
            print(f"Response: {response_text[:500]}")
            return None

    except Exception as e:
        print(f"ERROR: API call failed: {e}")
        return None


def store_extracted_data(sheet_id: int, data: dict, conn: sqlite3.Connection):
    """Store extracted data in database."""
    cursor = conn.cursor()

    stats = {
        'lines': 0,
        'equipment': 0,
        'instruments': 0,
        'welds': 0,
        'flags': 0
    }

    # Insert lines
    for line in data.get('lines', []):
        cursor.execute("""
            INSERT INTO lines (sheet_id, line_number, size, material, spec_class,
                             from_location, to_location, service, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            sheet_id,
            line.get('line_number', ''),
            line.get('size'),
            line.get('material'),
            line.get('spec_class'),  # May be null
            line.get('from_location'),
            line.get('to_location'),
            line.get('service'),
            line.get('confidence', 0.8)
        ))
        stats['lines'] += 1

        # Flag low confidence items
        if line.get('confidence', 1.0) < 0.6:
            cursor.execute("""
                INSERT INTO extraction_flags (sheet_id, item_type, item_id, flag_reason, confidence)
                VALUES (?, 'line', ?, 'Low confidence extraction', ?)
            """, (sheet_id, line.get('line_number', ''), line.get('confidence', 0.5)))
            stats['flags'] += 1

    # Insert equipment
    for equip in data.get('equipment', []):
        cursor.execute("""
            INSERT INTO equipment (sheet_id, tag, equipment_type, description, confidence)
            VALUES (?, ?, ?, ?, ?)
        """, (
            sheet_id,
            equip.get('tag', ''),
            equip.get('equipment_type'),
            equip.get('description'),
            equip.get('confidence', 0.9)
        ))
        stats['equipment'] += 1

        # Flag low confidence items
        if equip.get('confidence', 1.0) < 0.6:
            cursor.execute("""
                INSERT INTO extraction_flags (sheet_id, item_type, item_id, flag_reason, confidence)
                VALUES (?, 'equipment', ?, 'Low confidence extraction', ?)
            """, (sheet_id, equip.get('tag', ''), equip.get('confidence', 0.5)))
            stats['flags'] += 1

    # Insert instruments
    for inst in data.get('instruments', []):
        cursor.execute("""
            INSERT INTO instruments (sheet_id, tag, instrument_type, loop_number, confidence)
            VALUES (?, ?, ?, ?, ?)
        """, (
            sheet_id,
            inst.get('tag', ''),
            inst.get('instrument_type'),
            inst.get('loop_number'),
            inst.get('confidence', 0.85)
        ))
        stats['instruments'] += 1

        # Flag low confidence items
        if inst.get('confidence', 1.0) < 0.6:
            cursor.execute("""
                INSERT INTO extraction_flags (sheet_id, item_type, item_id, flag_reason, confidence)
                VALUES (?, 'instrument', ?, 'Low confidence extraction', ?)
            """, (sheet_id, inst.get('tag', ''), inst.get('confidence', 0.5)))
            stats['flags'] += 1

    # Insert welds
    for weld in data.get('welds', []):
        cursor.execute("""
            INSERT INTO welds (sheet_id, weld_id, weld_type, size, joint_type, nde_required, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            sheet_id,
            weld.get('weld_id', ''),
            weld.get('weld_type'),
            weld.get('size'),
            weld.get('joint_type'),
            weld.get('nde_required'),
            weld.get('confidence', 0.8)
        ))
        stats['welds'] += 1

        # Flag low confidence items
        if weld.get('confidence', 1.0) < 0.6:
            cursor.execute("""
                INSERT INTO extraction_flags (sheet_id, item_type, item_id, flag_reason, confidence)
                VALUES (?, 'weld', ?, 'Low confidence extraction', ?)
            """, (sheet_id, weld.get('weld_id', ''), weld.get('confidence', 0.5)))
            stats['flags'] += 1

    # Calculate overall quality score
    all_confidences = []
    for line in data.get('lines', []):
        all_confidences.append(line.get('confidence', 0.8))
    for equip in data.get('equipment', []):
        all_confidences.append(equip.get('confidence', 0.9))
    for inst in data.get('instruments', []):
        all_confidences.append(inst.get('confidence', 0.85))
    for weld in data.get('welds', []):
        all_confidences.append(weld.get('confidence', 0.8))

    quality_score = sum(all_confidences) / len(all_confidences) if all_confidences else 0.0

    # Update sheet metadata
    cursor.execute("""
        UPDATE sheets
        SET extracted_at = CURRENT_TIMESTAMP,
            extraction_model = 'claude-sonnet-4-5-20250929',
            quality_score = ?,
            drawing_type = 'detail',
            complexity = 'medium'
        WHERE id = ?
    """, (quality_score, sheet_id))

    conn.commit()
    return stats, quality_score


def main():
    """Main extraction workflow."""
    print("=" * 80)
    print("REFRIGERATION DETAIL DRAWING EXTRACTION")
    print("=" * 80)
    print(f"Project: 07308-BIRDCAGE")
    print(f"Sheets: {len(SHEETS)}")
    print(f"Database: {DB_PATH}")
    print(f"Model: claude-sonnet-4-5-20250929")
    print("=" * 80)

    # Connect to database
    conn = sqlite3.connect(DB_PATH)

    overall_stats = {
        'sheets_processed': 0,
        'total_lines': 0,
        'total_equipment': 0,
        'total_instruments': 0,
        'total_welds': 0,
        'total_flags': 0
    }

    results = []

    # Process each sheet
    for sheet in SHEETS:
        sheet_id = sheet['id']

        # Extract data
        extracted_data = extract_from_drawing(sheet)

        if extracted_data:
            # Store in database
            stats, quality_score = store_extracted_data(sheet_id, extracted_data, conn)

            overall_stats['sheets_processed'] += 1
            overall_stats['total_lines'] += stats['lines']
            overall_stats['total_equipment'] += stats['equipment']
            overall_stats['total_instruments'] += stats['instruments']
            overall_stats['total_welds'] += stats['welds']
            overall_stats['total_flags'] += stats['flags']

            results.append({
                'sheet': sheet,
                'stats': stats,
                'quality_score': quality_score,
                'notes': extracted_data.get('notes', '')
            })
        else:
            print(f"FAILED to extract data from sheet {sheet_id}")

    conn.close()

    # Print summary report
    print("\n" + "=" * 80)
    print("EXTRACTION SUMMARY")
    print("=" * 80)

    for result in results:
        sheet = result['sheet']
        stats = result['stats']
        print(f"\nSheet {sheet['id']}: {sheet['drawing_number']} Rev {sheet['revision']}")
        print(f"  Lines: {stats['lines']}")
        print(f"  Equipment: {stats['equipment']}")
        print(f"  Instruments: {stats['instruments']}")
        print(f"  Welds: {stats['welds']}")
        print(f"  Quality Score: {result['quality_score']:.2f}")
        if stats['flags'] > 0:
            print(f"  Flagged for Review: {stats['flags']} items")
        if result['notes']:
            print(f"  Notes: {result['notes']}")

    print("\n" + "=" * 80)
    print("OVERALL TOTALS")
    print("=" * 80)
    print(f"Sheets Processed: {overall_stats['sheets_processed']}/{len(SHEETS)}")
    print(f"Total Lines: {overall_stats['total_lines']}")
    print(f"Total Equipment: {overall_stats['total_equipment']}")
    print(f"Total Instruments: {overall_stats['total_instruments']}")
    print(f"Total Welds: {overall_stats['total_welds']}")
    print(f"Total Flagged: {overall_stats['total_flags']}")
    print("=" * 80)

    return 0 if overall_stats['sheets_processed'] == len(SHEETS) else 1


if __name__ == "__main__":
    sys.exit(main())
