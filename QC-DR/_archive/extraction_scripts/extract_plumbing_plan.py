#!/usr/bin/env python3
"""
Extract data from plumbing plan drawing and insert into database.
"""

import sqlite3
import json
import base64
from pathlib import Path
from datetime import datetime
import anthropic
import os

# Drawing to process
DRAWING = {
    "id": 2116,
    "path": "D:/Projects/07650-BRV-PerroGrande/Plumbing/PP11021-PARTIAL-FIRST-FLOOR-PLUMBING-PLAN---AREA-2-Rev.2.pdf",
    "sheet_number": "PP11021",
    "revision": "2",
    "project_id": 8
}

DB_PATH = "D:/quality.db"

# Extraction prompt for plumbing plan drawings
EXTRACTION_PROMPT = """Extract all piping, fixtures, equipment, and data from this plumbing plan drawing.

For each PLUMBING LINE/PIPE, provide:
- Line number/designation (if tagged)
- Size (nominal pipe diameter, e.g., 2", 3", 4")
- System type (sanitary, waste, vent, storm, water supply, gas, etc.)
- From fixture/equipment/location
- To fixture/equipment/location
- Material if shown (PVC, copper, cast iron, etc.)

For each PLUMBING FIXTURE, provide:
- Fixture type (water closet, lavatory, sink, floor drain, urinal, etc.)
- Location/room designation
- Quantity if multiple shown
- Any special notes

For each EQUIPMENT item, provide:
- Tag number or designation
- Equipment type (water heater, pump, tank, etc.)
- Description/name

For CLEANOUTS, provide:
- Location
- Size
- Type (wall, floor)

For any VALVES with tags or special designation:
- Valve tag/designation
- Valve type (shutoff, backflow preventer, PRV, etc.)
- Size

Return ONLY valid JSON in this exact format (no markdown, no explanation):
{
  "lines": [
    {
      "line_number": "string or null",
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
  "fixtures": [
    {
      "fixture_type": "string",
      "location": "string",
      "quantity": "number or null",
      "notes": "string or null",
      "confidence": 0.0-1.0
    }
  ],
  "cleanouts": [
    {
      "location": "string",
      "size": "string",
      "cleanout_type": "string",
      "confidence": 0.0-1.0
    }
  ],
  "valves": [
    {
      "tag": "string or null",
      "valve_type": "string",
      "size": "string or null",
      "confidence": 0.0-1.0
    }
  ],
  "notes": "any special observations or issues"
}

If no items of a category exist, use an empty array []. Be thorough and extract ALL visible items."""


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
    """Extract data from the plumbing drawing using Claude."""
    print(f"\n{'='*80}")
    print(f"Processing: {drawing_info['sheet_number']} Rev {drawing_info['revision']}")
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
        print(f"  - Fixtures: {len(data.get('fixtures', []))}")
        print(f"  - Cleanouts: {len(data.get('cleanouts', []))}")
        print(f"  - Valves: {len(data.get('valves', []))}")
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
        "fixtures": 0,
        "cleanouts": 0,
        "valves": 0,
        "avg_confidence": 0.0
    }

    confidences = []

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
        confidences.append(line.get('confidence', 0.7))

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
        confidences.append(equip.get('confidence', 0.7))

    # Insert fixtures (store in equipment table with type='fixture')
    for fixture in data.get('fixtures', []):
        # Create a descriptive tag for fixtures without explicit tags
        tag = f"{fixture.get('fixture_type', 'FX')}-{fixture.get('location', 'UNKNOWN')}"
        desc = f"{fixture.get('fixture_type', 'Unknown')} in {fixture.get('location', 'unknown location')}"
        if fixture.get('quantity'):
            desc += f" (qty: {fixture.get('quantity')})"
        if fixture.get('notes'):
            desc += f" - {fixture.get('notes')}"

        cursor.execute("""
            INSERT INTO equipment (sheet_id, tag, description, equipment_type, confidence)
            VALUES (?, ?, ?, ?, ?)
        """, (
            sheet_id,
            tag,
            desc,
            'plumbing_fixture',
            fixture.get('confidence', 0.7)
        ))
        stats['fixtures'] += 1
        confidences.append(fixture.get('confidence', 0.7))

    # Insert cleanouts (store in equipment table with type='cleanout')
    for co in data.get('cleanouts', []):
        tag = f"CO-{co.get('size', '')}-{co.get('location', 'UNKNOWN')}"
        desc = f"{co.get('size', '')} {co.get('cleanout_type', '')} cleanout at {co.get('location', 'unknown location')}"

        cursor.execute("""
            INSERT INTO equipment (sheet_id, tag, description, equipment_type, confidence)
            VALUES (?, ?, ?, ?, ?)
        """, (
            sheet_id,
            tag,
            desc,
            'cleanout',
            co.get('confidence', 0.7)
        ))
        stats['cleanouts'] += 1
        confidences.append(co.get('confidence', 0.7))

    # Insert valves (store in equipment table with type='valve')
    for valve in data.get('valves', []):
        tag = valve.get('tag') or f"V-{valve.get('valve_type', 'UNKNOWN')}"
        desc = f"{valve.get('size', '')} {valve.get('valve_type', 'valve')}"

        cursor.execute("""
            INSERT INTO equipment (sheet_id, tag, description, equipment_type, confidence)
            VALUES (?, ?, ?, ?, ?)
        """, (
            sheet_id,
            tag,
            desc,
            'valve',
            valve.get('confidence', 0.7)
        ))
        stats['valves'] += 1
        confidences.append(valve.get('confidence', 0.7))

    # Calculate average confidence
    if confidences:
        stats['avg_confidence'] = sum(confidences) / len(confidences)

    # Update sheet metadata
    cursor.execute("""
        UPDATE sheets
        SET extracted_at = ?,
            quality_score = ?,
            complexity = 'medium',
            drawing_type = 'plumbing_plan',
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
    print(f"  - Fixtures: {stats['fixtures']}")
    print(f"  - Cleanouts: {stats['cleanouts']}")
    print(f"  - Valves: {stats['valves']}")
    print(f"  - Average confidence: {stats['avg_confidence']:.2f}")

    return stats


def main():
    """Main extraction process."""
    print("Plumbing Plan Drawing Extraction")
    print("=" * 80)
    print(f"Database: {DB_PATH}")
    print(f"Sheet ID: {DRAWING['id']}")
    print(f"Project ID: {DRAWING['project_id']}")

    try:
        # Extract data
        data = extract_data_from_drawing(DRAWING)

        if data:
            # Insert into database
            stats = insert_into_database(DRAWING['id'], DRAWING['sheet_number'], data)

            # Print summary
            print("\n" + "=" * 80)
            print("EXTRACTION SUMMARY")
            print("=" * 80)
            print(f"\nSheet {DRAWING['id']} ({DRAWING['sheet_number']} Rev {DRAWING['revision']}):")
            print(f"  Lines: {stats['lines']}")
            print(f"  Equipment: {stats['equipment']}")
            print(f"  Fixtures: {stats['fixtures']}")
            print(f"  Cleanouts: {stats['cleanouts']}")
            print(f"  Valves: {stats['valves']}")
            print(f"  Quality Score: {stats['avg_confidence']:.2f}")

            total_items = stats['lines'] + stats['equipment'] + stats['fixtures'] + stats['cleanouts'] + stats['valves']
            print(f"\nTotal items extracted: {total_items}")
            print("\nExtraction complete!")
        else:
            print("Extraction failed - no data returned")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
