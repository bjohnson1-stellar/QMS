#!/usr/bin/env python3
"""
Extract data from plumbing drawing sheet 2120 and insert into database.
Sheet: PP11061 - PARTIAL FIRST FLOOR PLUMBING PLAN - AREA 6 - Rev.2
Project: 07650-BRV-PerroGrande
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
    "id": 2120,
    "path": "D:/Projects/07650-BRV-PerroGrande/Plumbing/PP11061-PARTIAL-FIRST-FLOOR-PLUMBING-PLAN---AREA-6-Rev.2.pdf",
    "sheet_number": "PP11061",
    "revision": "2",
    "project": "07650"
}

DB_PATH = "D:/quality.db"

# Extraction prompt for plumbing plan drawings
EXTRACTION_PROMPT = """Extract all plumbing data from this plumbing plan drawing.

For each PLUMBING PIPE/LINE, provide:
- Pipe size (e.g., 2", 3", 4", etc.)
- Pipe type/material (e.g., PVC, CI, CW, copper, etc.)
- Service (e.g., sanitary waste, vent, cold water, hot water, storm drain, etc.)
- From location (where pipe originates)
- To location (where pipe terminates)
- Invert elevation if shown (elevation of bottom of pipe)

For each PLUMBING FIXTURE shown or listed, provide:
- Fixture type (water closet, lavatory, sink, urinal, floor drain, etc.)
- Manufacturer if shown
- Model number if shown
- Description
- Waste connection size if shown
- Vent connection size if shown
- Cold water supply size if shown (DCW)
- Hot water supply size if shown (DHW)
- Quantity if shown
- Any special notes

For each CLEANOUT, provide:
- Tag/identifier if shown
- Cleanout type (floor, wall, etc.)
- Location description
- Pipe size

For TAGGED ITEMS or LOCATIONS with identifiers, provide:
- Item tag (e.g., FD-1, WC-2, LAV-3, etc.)
- Item type (fixture type, drain, vent, etc.)
- Location description
- Room number if shown
- Room name if shown
- Grid location if shown (e.g., A-1, B-3, etc.)
- Associated pipe size
- Associated pipe material
- Invert elevation if shown
- Any special notes

Return ONLY valid JSON in this exact format (no markdown, no explanation):
{
  "pipes": [
    {
      "pipe_size": "string",
      "pipe_type": "string",
      "service": "string",
      "from_location": "string",
      "to_location": "string",
      "invert_elevation": "string or null",
      "confidence": 0.0-1.0
    }
  ],
  "fixtures": [
    {
      "fixture_type": "string",
      "manufacturer": "string or null",
      "model": "string or null",
      "description": "string",
      "waste_size": "string or null",
      "vent_size": "string or null",
      "dcw_size": "string or null",
      "dhw_size": "string or null",
      "qty": integer or 1,
      "notes": "string or null",
      "confidence": 0.0-1.0
    }
  ],
  "cleanouts": [
    {
      "cleanout_tag": "string",
      "cleanout_type": "string",
      "location": "string",
      "pipe_size": "string or null",
      "confidence": 0.0-1.0
    }
  ],
  "locations": [
    {
      "item_tag": "string",
      "item_type": "string",
      "location": "string",
      "room_number": "string or null",
      "room_name": "string or null",
      "grid_location": "string or null",
      "pipe_size": "string or null",
      "pipe_material": "string or null",
      "invert_elevation": "string or null",
      "notes": "string or null",
      "confidence": 0.0-1.0
    }
  ],
  "notes": "any special observations or issues",
  "complexity": "simple, medium, or complex"
}

If no items of a category exist, use an empty array []. Be thorough and extract ALL visible items.
Pay special attention to:
- Fixture schedule tables
- Pipe size callouts
- Room identifiers
- Grid references
- Elevation markers
- Legend/symbol information"""


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
    """Extract data from the drawing using Claude."""
    print(f"\n{'='*80}")
    print(f"Processing: {drawing_info['sheet_number']} Rev {drawing_info['revision']}")
    print(f"Project: {drawing_info['project']}")
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
        # Remove first and last line (``` markers)
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        response_text = "\n".join(lines)

    try:
        data = json.loads(response_text)
        print(f"\nExtracted:")
        print(f"  - Pipes: {len(data.get('pipes', []))}")
        print(f"  - Fixtures: {len(data.get('fixtures', []))}")
        print(f"  - Cleanouts: {len(data.get('cleanouts', []))}")
        print(f"  - Tagged Locations: {len(data.get('locations', []))}")
        print(f"  - Complexity: {data.get('complexity', 'unknown')}")
        if data.get('notes'):
            print(f"  - Notes: {data['notes']}")
        return data
    except json.JSONDecodeError as e:
        print(f"ERROR: Failed to parse JSON response: {e}")
        print(f"Response: {response_text[:500]}")
        return None


def insert_into_database(sheet_id, data):
    """Insert extracted data into the database."""
    print(f"\nInserting data into database for sheet {sheet_id}...")

    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    cursor = conn.cursor()

    stats = {
        "pipes": 0,
        "fixtures": 0,
        "cleanouts": 0,
        "locations": 0,
        "avg_confidence": 0.0
    }

    confidences = []

    # Insert pipes
    for pipe in data.get('pipes', []):
        cursor.execute("""
            INSERT INTO plumbing_pipes (sheet_id, pipe_size, pipe_type, service,
                                       from_location, to_location, invert_elevation, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            sheet_id,
            pipe.get('pipe_size'),
            pipe.get('pipe_type'),
            pipe.get('service'),
            pipe.get('from_location'),
            pipe.get('to_location'),
            pipe.get('invert_elevation'),
            pipe.get('confidence', 0.7)
        ))
        stats['pipes'] += 1
        confidences.append(pipe.get('confidence', 0.7))

    # Insert fixtures
    for fixture in data.get('fixtures', []):
        cursor.execute("""
            INSERT INTO plumbing_fixtures (sheet_id, fixture_type, manufacturer, model,
                                          description, waste_size, vent_size, dcw_size,
                                          dhw_size, qty, notes, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            sheet_id,
            fixture.get('fixture_type'),
            fixture.get('manufacturer'),
            fixture.get('model'),
            fixture.get('description'),
            fixture.get('waste_size'),
            fixture.get('vent_size'),
            fixture.get('dcw_size'),
            fixture.get('dhw_size'),
            fixture.get('qty', 1),
            fixture.get('notes'),
            fixture.get('confidence', 0.7)
        ))
        stats['fixtures'] += 1
        confidences.append(fixture.get('confidence', 0.7))

    # Insert cleanouts
    for cleanout in data.get('cleanouts', []):
        cursor.execute("""
            INSERT INTO plumbing_cleanouts (sheet_id, cleanout_tag, cleanout_type,
                                           location, pipe_size, confidence)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            sheet_id,
            cleanout.get('cleanout_tag'),
            cleanout.get('cleanout_type'),
            cleanout.get('location'),
            cleanout.get('pipe_size'),
            cleanout.get('confidence', 0.7)
        ))
        stats['cleanouts'] += 1
        confidences.append(cleanout.get('confidence', 0.7))

    # Insert tagged locations
    for location in data.get('locations', []):
        cursor.execute("""
            INSERT INTO plumbing_locations (sheet_id, item_tag, item_type, location,
                                           room_number, room_name, grid_location,
                                           pipe_size, pipe_material, invert_elevation,
                                           notes, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            sheet_id,
            location.get('item_tag'),
            location.get('item_type'),
            location.get('location'),
            location.get('room_number'),
            location.get('room_name'),
            location.get('grid_location'),
            location.get('pipe_size'),
            location.get('pipe_material'),
            location.get('invert_elevation'),
            location.get('notes'),
            location.get('confidence', 0.7)
        ))
        stats['locations'] += 1
        confidences.append(location.get('confidence', 0.7))

    # Calculate average confidence
    if confidences:
        stats['avg_confidence'] = sum(confidences) / len(confidences)
    else:
        stats['avg_confidence'] = 0.7

    # Determine complexity from extraction or default to medium
    complexity = data.get('complexity', 'medium')
    if complexity not in ['simple', 'medium', 'complex']:
        complexity = 'medium'

    # Update sheet metadata
    cursor.execute("""
        UPDATE sheets
        SET extracted_at = ?,
            quality_score = ?,
            complexity = ?,
            drawing_type = 'plumbing_plan',
            extraction_model = 'claude-sonnet-4-5-20250929'
        WHERE id = ?
    """, (datetime.now().isoformat(), stats['avg_confidence'], complexity, sheet_id))

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
    print(f"  - Pipes: {stats['pipes']}")
    print(f"  - Fixtures: {stats['fixtures']}")
    print(f"  - Cleanouts: {stats['cleanouts']}")
    print(f"  - Tagged Locations: {stats['locations']}")
    print(f"  - Average confidence: {stats['avg_confidence']:.2f}")
    print(f"  - Complexity: {complexity}")

    return stats


def main():
    """Main extraction process."""
    print("Plumbing Drawing Extraction")
    print("=" * 80)
    print(f"Database: {DB_PATH}")
    print(f"Sheet ID: {DRAWING['id']}")
    print(f"Sheet Number: {DRAWING['sheet_number']}")
    print(f"Project: {DRAWING['project']}")

    try:
        # Extract data
        data = extract_data_from_drawing(DRAWING)

        if data:
            # Insert into database
            stats = insert_into_database(DRAWING['id'], data)

            # Print final summary
            print("\n" + "=" * 80)
            print("EXTRACTION COMPLETE")
            print("=" * 80)
            print(f"\nSheet {DRAWING['id']} ({DRAWING['sheet_number']}):")
            print(f"  Pipes: {stats['pipes']}")
            print(f"  Fixtures: {stats['fixtures']}")
            print(f"  Cleanouts: {stats['cleanouts']}")
            print(f"  Tagged Locations: {stats['locations']}")
            print(f"  Quality Score: {stats['avg_confidence']:.2f}")

            total_items = stats['pipes'] + stats['fixtures'] + stats['cleanouts'] + stats['locations']
            print(f"\nTotal items extracted: {total_items}")
        else:
            print("\nExtraction failed - no data to insert into database")

    except Exception as e:
        print(f"\nERROR processing {DRAWING['sheet_number']}: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
