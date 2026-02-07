#!/usr/bin/env python3
"""
Extract data from refrigeration plan drawings and insert into database.
"""

import sqlite3
import json
import base64
from pathlib import Path
from datetime import datetime
import anthropic
import os

# Drawing files to process - SHEETS 150, 151, 152
DRAWINGS = [
    {
        "id": 150,
        "path": "D:/Projects/07308-BIRDCAGE/Refrigeration-Controls/RC14020-REFRIGERATION-CONTROLS-PLAN-PIPE-AND-DUCT-ROOF-AREA-2-Rev.4.pdf",
        "sheet_number": "RC14020",
        "revision": "4"
    },
    {
        "id": 151,
        "path": "D:/Projects/07308-BIRDCAGE/Refrigeration-Controls/RC14030-REFRIGERATION-CONTROLS-PLAN-PIPE-AND-DUCT-ROOF-AREA-3-Rev.4.pdf",
        "sheet_number": "RC14030",
        "revision": "4"
    },
    {
        "id": 152,
        "path": "D:/Projects/07308-BIRDCAGE/Refrigeration-Controls/RC14040-REFRIGERATION-CONTROLS-PLAN-PIPE-AND-DUCT-ROOF---AREA-4-Rev.5.pdf",
        "sheet_number": "RC14040",
        "revision": "5"
    }
]

DB_PATH = "D:/quality.db"

# Extraction prompt for refrigeration controls plan drawings
EXTRACTION_PROMPT = """Extract all piping, equipment, and instrumentation data from this Refrigeration-Controls plan drawing.

This is a refrigeration controls plan showing piping and duct work on a roof area. Focus on:

For each REFRIGERATION LINE, provide:
- Line number/designation (e.g., RL-101, SR-201, DR-301, etc.)
- Size (nominal pipe diameter)
- Service type (suction, discharge, liquid, hot gas, condensate, etc.)
- From equipment/location
- To equipment/location

For each EQUIPMENT item, provide:
- Tag number (e.g., COND-1, EVAP-2, AHU-3, FAN-4, etc.)
- Equipment type (condenser, evaporator, compressor, air handler, fan, etc.)
- Description/name

For each INSTRUMENT, provide:
- Tag number (e.g., TT-101, PT-201, TS-301, PS-401, TE-501, PE-601, etc.)
- Instrument type (temperature transmitter, pressure transmitter, temperature element, pressure element, switch, etc.)
- Associated equipment or line (loop number if shown)

For CONTROL VALVES with tags, provide as equipment:
- Valve tag (e.g., TV-101, PV-201, etc.)
- Valve type (temperature control valve, pressure control valve, etc.)

Return ONLY valid JSON in this exact format (no markdown, no explanation):
{
  "lines": [
    {
      "line_number": "string",
      "size": "string",
      "service": "string",
      "from_location": "string",
      "to_location": "string",
      "material": "string or null",
      "spec_class": "string or null",
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
  "notes": "any special observations or issues"
}

If no items of a category exist, use an empty array []. Be thorough and extract ALL visible tagged items."""


def convert_pdf_to_images(pdf_path, max_pages=3):
    """Convert PDF pages to images using PyMuPDF."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        print("PyMuPDF not installed. Installing...")
        os.system("pip install PyMuPDF")
        import fitz

    doc = fitz.open(pdf_path)
    images = []

    # Limit to first few pages for efficiency
    num_pages = min(len(doc), max_pages)

    for page_num in range(num_pages):
        page = doc[page_num]
        # Render at 150 DPI for good quality
        pix = page.get_pixmap(matrix=fitz.Matrix(150/72, 150/72))
        img_data = pix.tobytes("png")
        images.append(base64.b64encode(img_data).decode('utf-8'))

    doc.close()
    return images


def extract_data_from_drawing(drawing_info):
    """Extract data from a single drawing using Claude."""
    print(f"\n{'='*80}")
    print(f"Processing: {drawing_info['sheet_number']} Rev {drawing_info['revision']}")
    print(f"Sheet ID: {drawing_info['id']}")
    print(f"File: {drawing_info['path']}")
    print(f"{'='*80}")

    # Check if file exists
    if not Path(drawing_info['path']).exists():
        print(f"ERROR: File not found: {drawing_info['path']}")
        return None

    # Convert PDF to images
    print("Converting PDF to images...")
    images = convert_pdf_to_images(drawing_info['path'])
    print(f"Converted {len(images)} page(s)")

    # Call Claude API
    print("Extracting data with Claude Sonnet 4.5...")
    client = anthropic.Anthropic()

    # Build content with images
    content = []
    for i, img_data in enumerate(images):
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": img_data
            }
        })

    content.append({
        "type": "text",
        "text": EXTRACTION_PROMPT
    })

    response = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=4096,
        messages=[{
            "role": "user",
            "content": content
        }]
    )

    # Parse response
    response_text = response.content[0].text.strip()

    # Remove markdown code blocks if present
    if response_text.startswith("```"):
        lines = response_text.split("\n")
        response_text = "\n".join(lines[1:-1])

    try:
        data = json.loads(response_text)
        print(f"\nExtracted:")
        print(f"  - Lines: {len(data.get('lines', []))}")
        print(f"  - Equipment: {len(data.get('equipment', []))}")
        print(f"  - Instruments: {len(data.get('instruments', []))}")
        if data.get('notes'):
            print(f"  - Notes: {data['notes']}")
        return data
    except json.JSONDecodeError as e:
        print(f"ERROR: Failed to parse JSON response: {e}")
        print(f"Response: {response_text[:500]}")
        return None


def insert_into_database(sheet_id, sheet_number, data):
    """Insert extracted data into the database."""
    print(f"\nInserting data into database for sheet {sheet_id}...")

    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    cursor = conn.cursor()

    stats = {
        "lines": 0,
        "equipment": 0,
        "instruments": 0,
        "avg_confidence": 0.0
    }

    confidences = []
    low_confidence_items = []

    # Insert lines
    for line in data.get('lines', []):
        cursor.execute("""
            INSERT INTO lines (sheet_id, line_number, size, material, spec_class,
                             from_location, to_location, service, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            sheet_id,
            line.get('line_number'),
            line.get('size'),
            line.get('material'),
            line.get('spec_class'),
            line.get('from_location'),
            line.get('to_location'),
            line.get('service'),
            line.get('confidence', 0.7)
        ))
        stats['lines'] += 1
        conf = line.get('confidence', 0.7)
        confidences.append(conf)
        if conf < 0.7:
            low_confidence_items.append(f"Line {line.get('line_number')}: {conf:.2f}")

    # Insert equipment
    for equip in data.get('equipment', []):
        cursor.execute("""
            INSERT INTO equipment (sheet_id, tag, description, equipment_type, confidence)
            VALUES (?, ?, ?, ?, ?)
        """, (
            sheet_id,
            equip.get('tag'),
            equip.get('description'),
            equip.get('equipment_type'),
            equip.get('confidence', 0.7)
        ))
        stats['equipment'] += 1
        conf = equip.get('confidence', 0.7)
        confidences.append(conf)
        if conf < 0.7:
            low_confidence_items.append(f"Equipment {equip.get('tag')}: {conf:.2f}")

    # Insert instruments
    for inst in data.get('instruments', []):
        cursor.execute("""
            INSERT INTO instruments (sheet_id, tag, instrument_type, loop_number, confidence)
            VALUES (?, ?, ?, ?, ?)
        """, (
            sheet_id,
            inst.get('tag'),
            inst.get('instrument_type'),
            inst.get('loop_number'),
            inst.get('confidence', 0.7)
        ))
        stats['instruments'] += 1
        conf = inst.get('confidence', 0.7)
        confidences.append(conf)
        if conf < 0.7:
            low_confidence_items.append(f"Instrument {inst.get('tag')}: {conf:.2f}")

    # Calculate average confidence
    if confidences:
        stats['avg_confidence'] = sum(confidences) / len(confidences)

    # Update sheet metadata
    cursor.execute("""
        UPDATE sheets
        SET extracted_at = ?,
            quality_score = ?,
            complexity = 'medium',
            drawing_type = 'plan',
            extraction_model = 'claude-sonnet-4-5-20250929'
        WHERE id = ?
    """, (datetime.now().isoformat(), stats['avg_confidence'], sheet_id))

    # Update processing queue if exists
    cursor.execute("""
        UPDATE processing_queue
        SET status = 'completed',
            completed_at = ?
        WHERE sheet_id = ? AND task = 'EXTRACT'
    """, (datetime.now().isoformat(), sheet_id))

    conn.commit()
    conn.close()

    print(f"Inserted:")
    print(f"  - Lines: {stats['lines']}")
    print(f"  - Equipment: {stats['equipment']}")
    print(f"  - Instruments: {stats['instruments']}")
    print(f"  - Average confidence: {stats['avg_confidence']:.2f}")

    if low_confidence_items:
        print(f"\nFlagged for Review ({len(low_confidence_items)} items):")
        for item in low_confidence_items:
            print(f"  - {item}")

    stats['low_confidence_count'] = len(low_confidence_items)
    return stats


def main():
    """Main extraction process."""
    print("Refrigeration-Controls Drawing Extraction")
    print("=" * 80)
    print(f"Database: {DB_PATH}")
    print(f"Drawings to process: {len(DRAWINGS)}")

    all_stats = []

    for drawing in DRAWINGS:
        try:
            # Extract data
            data = extract_data_from_drawing(drawing)

            if data:
                # Insert into database
                stats = insert_into_database(drawing['id'], drawing['sheet_number'], data)
                stats['sheet_id'] = drawing['id']
                stats['sheet_number'] = drawing['sheet_number']
                all_stats.append(stats)
            else:
                print(f"Skipping database insert for {drawing['sheet_number']} due to extraction error")

        except Exception as e:
            print(f"ERROR processing {drawing['sheet_number']}: {e}")
            import traceback
            traceback.print_exc()

    # Print summary
    print("\n" + "=" * 80)
    print("EXTRACTION SUMMARY")
    print("=" * 80)

    for stats in all_stats:
        print(f"\nSheet {stats['sheet_id']} ({stats['sheet_number']}):")
        print(f"  Lines: {stats['lines']}")
        print(f"  Equipment: {stats['equipment']}")
        print(f"  Instruments: {stats['instruments']}")
        print(f"  Quality Score: {stats['avg_confidence']:.2f}")
        if stats.get('low_confidence_count', 0) > 0:
            print(f"  Low confidence items: {stats['low_confidence_count']}")

    if all_stats:
        total_items = sum(s['lines'] + s['equipment'] + s['instruments'] for s in all_stats)
        avg_quality = sum(s['avg_confidence'] for s in all_stats) / len(all_stats)
        print(f"\nTotal items extracted: {total_items}")
        print(f"Average quality score: {avg_quality:.2f}")

    print("\nExtraction complete!")


if __name__ == "__main__":
    main()
