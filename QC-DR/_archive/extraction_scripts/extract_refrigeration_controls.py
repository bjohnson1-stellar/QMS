#!/usr/bin/env python3
"""
Extract instruments and equipment from Refrigeration-Controls drawings
using Claude vision API to read the PDFs.
"""

import anthropic
import base64
import sqlite3
import json
import sys
from pathlib import Path
from datetime import datetime

# Configuration
API_KEY = None  # Will use environment variable ANTHROPIC_API_KEY
MODEL = "claude-sonnet-4-5-20250929"
DB_PATH = "D:/quality.db"

SHEETS = [
    {
        "id": 141,
        "path": "D:/Projects/07308-BIRDCAGE/Refrigeration-Controls/RC11060-REFRIGERATION-CONTROLS-PLAN-PIPE-AND-DUCT-FLOOR-AREA-6-Rev.5.pdf",
        "drawing_number": "RC11060",
        "title": "REFRIGERATION CONTROLS PLAN PIPE AND DUCT FLOOR AREA 6",
        "revision": "5"
    },
    {
        "id": 142,
        "path": "D:/Projects/07308-BIRDCAGE/Refrigeration-Controls/RC11070-REFRIGERATION-CONTROLS-PLAN-PIPE-AND-DUCT-FLOOR-AREA-7-Rev.6.pdf",
        "drawing_number": "RC11070",
        "title": "REFRIGERATION CONTROLS PLAN PIPE AND DUCT FLOOR AREA 7",
        "revision": "6"
    },
    {
        "id": 143,
        "path": "D:/Projects/07308-BIRDCAGE/Refrigeration-Controls/RC11080-REFRIGERATION-CONTROLS-PLAN-PIPE-AND-DUCT-FLOOR---AREA-8-Rev.10.pdf",
        "drawing_number": "RC11080",
        "title": "REFRIGERATION CONTROLS PLAN PIPE AND DUCT FLOOR AREA 8",
        "revision": "10"
    }
]

EXTRACTION_PROMPT = """Extract all instruments and equipment from this Refrigeration-Controls drawing.

For each INSTRUMENT, provide:
- Tag number (e.g., TT-101, PT-201, TS-301, PS-401, etc.)
- Instrument type (Temperature Transmitter, Pressure Transmitter, Temperature Switch, Pressure Switch, etc.)
- Loop number if shown

For each EQUIPMENT item, provide:
- Tag number (e.g., P-101, V-201, TK-301, E-401, etc.)
- Equipment type (Pump, Vessel, Tank, Exchanger, Compressor, etc.)
- Description/name

Focus on:
1. All instrument tags visible on the drawing
2. All equipment tags and identifiers
3. Any control valves or automated equipment

Return as valid JSON with this structure:
{
    "instruments": [
        {"tag": "TT-101", "type": "Temperature Transmitter", "loop": "TIC-101", "confidence": 0.9}
    ],
    "equipment": [
        {"tag": "P-101", "type": "Pump", "description": "Ammonia Pump", "confidence": 0.95}
    ],
    "notes": "Any extraction notes or uncertainties"
}

Be thorough and capture ALL visible tags. Use confidence scores from 0.0 to 1.0.
"""


def convert_pdf_to_images(pdf_path):
    """Convert PDF to images using PyMuPDF (fitz)"""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        print("ERROR: PyMuPDF not installed. Install with: pip install PyMuPDF")
        sys.exit(1)

    doc = fitz.open(pdf_path)
    images = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        # Render at 150 DPI for good quality
        pix = page.get_pixmap(matrix=fitz.Matrix(150/72, 150/72))
        img_data = pix.tobytes("png")
        images.append(img_data)

    doc.close()
    return images


def extract_from_drawing(client, sheet_info):
    """Extract data from a single drawing using Claude vision API"""
    print(f"\nProcessing: {sheet_info['drawing_number']} Rev {sheet_info['revision']}")
    print(f"File: {sheet_info['path']}")

    # Convert PDF to images
    print("Converting PDF to images...")
    try:
        images = convert_pdf_to_images(sheet_info['path'])
        print(f"Converted {len(images)} page(s)")
    except Exception as e:
        print(f"ERROR converting PDF: {e}")
        return None

    # Process only first page for now (title sheet typically has the info)
    # For multi-page drawings, we'd process all pages
    image_data = images[0]
    image_b64 = base64.standard_b64encode(image_data).decode('utf-8')

    print("Sending to Claude for extraction...")
    try:
        response = client.messages.create(
            model=MODEL,
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
                                "data": image_b64
                            }
                        },
                        {
                            "type": "text",
                            "text": EXTRACTION_PROMPT
                        }
                    ]
                }
            ]
        )

        # Extract JSON from response
        response_text = response.content[0].text
        print(f"Response length: {len(response_text)} chars")

        # Try to find JSON in response
        json_start = response_text.find('{')
        json_end = response_text.rfind('}') + 1

        if json_start >= 0 and json_end > json_start:
            json_text = response_text[json_start:json_end]
            data = json.loads(json_text)
            return data
        else:
            print(f"WARNING: No JSON found in response")
            print(f"Response: {response_text[:500]}")
            return None

    except Exception as e:
        print(f"ERROR during extraction: {e}")
        import traceback
        traceback.print_exc()
        return None


def store_extractions(db_path, sheet_id, data):
    """Store extracted data in database"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    stats = {
        'instruments': 0,
        'equipment': 0,
        'avg_confidence': 0.0
    }

    try:
        # Store instruments
        if 'instruments' in data:
            for inst in data['instruments']:
                cursor.execute("""
                    INSERT INTO instruments (sheet_id, tag, instrument_type, loop_number, confidence)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    sheet_id,
                    inst.get('tag', 'UNKNOWN'),
                    inst.get('type', ''),
                    inst.get('loop', ''),
                    inst.get('confidence', 0.8)
                ))
                stats['instruments'] += 1

        # Store equipment
        if 'equipment' in data:
            for equip in data['equipment']:
                cursor.execute("""
                    INSERT INTO equipment (sheet_id, tag, description, equipment_type, confidence)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    sheet_id,
                    equip.get('tag', 'UNKNOWN'),
                    equip.get('description', ''),
                    equip.get('type', ''),
                    equip.get('confidence', 0.8)
                ))
                stats['equipment'] += 1

        # Calculate average confidence
        all_confidences = []
        if 'instruments' in data:
            all_confidences.extend([i.get('confidence', 0.8) for i in data['instruments']])
        if 'equipment' in data:
            all_confidences.extend([e.get('confidence', 0.8) for e in data['equipment']])

        if all_confidences:
            stats['avg_confidence'] = sum(all_confidences) / len(all_confidences)

        # Update sheet metadata
        cursor.execute("""
            UPDATE sheets
            SET extracted_at = ?,
                extraction_model = ?,
                quality_score = ?,
                drawing_type = 'plan',
                complexity = 'medium'
            WHERE id = ?
        """, (
            datetime.now().isoformat(),
            MODEL,
            stats['avg_confidence'],
            sheet_id
        ))

        # Update processing queue if it exists
        cursor.execute("""
            UPDATE processing_queue
            SET status = 'complete',
                completed_at = ?
            WHERE sheet_id = ? AND task = 'EXTRACT'
        """, (datetime.now().isoformat(), sheet_id))

        conn.commit()

    except Exception as e:
        conn.rollback()
        print(f"ERROR storing data: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        conn.close()

    return stats


def main():
    """Main extraction process"""
    print("=" * 70)
    print("REFRIGERATION-CONTROLS DRAWING EXTRACTION")
    print("=" * 70)
    print(f"Database: {DB_PATH}")
    print(f"Model: {MODEL}")
    print(f"Sheets: {len(SHEETS)}")

    # Initialize Anthropic client
    client = anthropic.Anthropic()  # Uses ANTHROPIC_API_KEY env var

    results = []

    for sheet in SHEETS:
        try:
            # Extract data
            data = extract_from_drawing(client, sheet)

            if data:
                # Store in database
                print("Storing extracted data in database...")
                stats = store_extractions(DB_PATH, sheet['id'], data)

                result = {
                    'sheet_id': sheet['id'],
                    'drawing_number': sheet['drawing_number'],
                    'revision': sheet['revision'],
                    'success': True,
                    'instruments': stats['instruments'],
                    'equipment': stats['equipment'],
                    'avg_confidence': stats['avg_confidence'],
                    'notes': data.get('notes', '')
                }
                results.append(result)

                print(f"SUCCESS: Extracted {stats['instruments']} instruments, "
                      f"{stats['equipment']} equipment (avg confidence: {stats['avg_confidence']:.2f})")
            else:
                result = {
                    'sheet_id': sheet['id'],
                    'drawing_number': sheet['drawing_number'],
                    'revision': sheet['revision'],
                    'success': False,
                    'error': 'No data extracted'
                }
                results.append(result)

        except Exception as e:
            print(f"ERROR processing sheet {sheet['id']}: {e}")
            result = {
                'sheet_id': sheet['id'],
                'drawing_number': sheet['drawing_number'],
                'revision': sheet['revision'],
                'success': False,
                'error': str(e)
            }
            results.append(result)

    # Print summary
    print("\n" + "=" * 70)
    print("EXTRACTION SUMMARY")
    print("=" * 70)

    total_instruments = 0
    total_equipment = 0
    successful = 0

    for result in results:
        status = "SUCCESS" if result['success'] else "FAILED"
        print(f"\n{result['drawing_number']} Rev {result['revision']}: {status}")

        if result['success']:
            successful += 1
            total_instruments += result['instruments']
            total_equipment += result['equipment']
            print(f"  Instruments: {result['instruments']}")
            print(f"  Equipment: {result['equipment']}")
            print(f"  Confidence: {result['avg_confidence']:.2f}")
            if result.get('notes'):
                print(f"  Notes: {result['notes']}")
        else:
            print(f"  Error: {result.get('error', 'Unknown error')}")

    print(f"\n" + "=" * 70)
    print(f"Total Successful: {successful}/{len(SHEETS)}")
    print(f"Total Instruments: {total_instruments}")
    print(f"Total Equipment: {total_equipment}")
    print("=" * 70)


if __name__ == '__main__':
    main()
