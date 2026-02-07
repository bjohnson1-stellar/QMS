#!/usr/bin/env python3
"""
Extract data from plumbing process waste riser diagram sheet 2107.
"""

import sqlite3
import json
import base64
from pathlib import Path
from datetime import datetime
import anthropic
import os

# Sheet to process
SHEET = {
    "id": 2107,
    "path": "D:/Projects/07650-BRV-PerroGrande/Plumbing/P70004-PLUMBING-PROCESS-WASTE-RISER-DIAGRAM-Rev.1.pdf",
    "sheet_number": "P70004",
    "revision": "1",
    "project": "07650"
}

DB_PATH = "D:/quality.db"

# Extraction prompt for plumbing riser diagram
EXTRACTION_PROMPT = """Extract all piping data from this plumbing process waste riser diagram.

This is a RISER DIAGRAM showing vertical and horizontal routing of process waste (PW) and process vent (PV) piping.

For each PIPE LINE SEGMENT, provide:
- Line designation/service (e.g., "PW" for process waste, "PV" for process vent)
- Size (e.g., "3\"", "4\"", "6\"", "8\"", "10\"")
- From location/equipment (e.g., "FD-1", "HD-1", "FCO-1", "CO", "V.T.R.")
- To location/equipment (if determinable from the diagram)
- Material specification if noted

For EQUIPMENT/FIXTURES, provide:
- Tag/designation (e.g., "FD-1" = Floor Drain, "HD-1" = Hub Drain, "FCO-1" = Floor Clean Out, "CO" = Clean Out, "V.T.R." = Vent Through Roof)
- Equipment type (floor drain, hub drain, cleanout, vent, etc.)
- Associated pipe size

IMPORTANT ABBREVIATIONS:
- PW = Process Waste
- PV = Process Vent
- FD-1 = Floor Drain Type 1
- HD-1 = Hub Drain Type 1
- FCO-1 = Floor Clean Out Type 1
- CO = Clean Out
- V.T.R. = Vent Through Roof
- FS-1 = Floor Sink Type 1

Be systematic and extract data for ALL visible pipe segments and connections. Look for:
- Multiple vertical risers with branches
- Horizontal runs at different elevations
- Size changes (reducers/increasers)
- Equipment connections

Return ONLY valid JSON in this exact format (no markdown, no explanation):
{
  "lines": [
    {
      "line_number": "string (e.g., 'PW-4in-segment-1', 'PV-3in-segment-1')",
      "size": "string (e.g., '4\"', '6\"')",
      "service": "string (PW or PV)",
      "from_location": "string",
      "to_location": "string or null",
      "material": "string or null",
      "spec_class": "string or null",
      "confidence": 0.0-1.0
    }
  ],
  "equipment": [
    {
      "tag": "string (e.g., 'FD-1', 'HD-1', 'CO')",
      "equipment_type": "string (e.g., 'floor drain', 'hub drain', 'cleanout', 'vent')",
      "description": "string",
      "confidence": 0.0-1.0
    }
  ],
  "notes": "any special observations, references to continuation sheets, or issues"
}

If no items of a category exist, use an empty array []. Extract ALL visible piping and equipment."""


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
        max_tokens=8192,
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
        # Find json start
        start_idx = 1
        for i, line in enumerate(lines[1:], 1):
            if line.strip() and not line.strip().lower().startswith('json'):
                start_idx = i
                break
        response_text = "\n".join(lines[start_idx:-1])

    try:
        data = json.loads(response_text)
        print(f"\nExtracted:")
        print(f"  - Lines: {len(data.get('lines', []))}")
        print(f"  - Equipment: {len(data.get('equipment', []))}")
        if data.get('notes'):
            print(f"  - Notes: {data['notes']}")
        return data
    except json.JSONDecodeError as e:
        print(f"ERROR: Failed to parse JSON response: {e}")
        print(f"Response: {response_text[:1000]}")
        return None


def insert_into_database(sheet_id, sheet_number, data):
    """Insert extracted data into the database."""
    print(f"\nInserting data into database for sheet {sheet_id}...")

    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    cursor = conn.cursor()

    stats = {
        "lines": 0,
        "equipment": 0,
        "avg_confidence": 0.0,
        "low_confidence_items": []
    }

    confidences = []

    # Insert lines
    for line in data.get('lines', []):
        confidence = line.get('confidence', 0.7)
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
            confidence
        ))
        stats['lines'] += 1
        confidences.append(confidence)

        if confidence < 0.6:
            stats['low_confidence_items'].append(
                f"Line {line.get('line_number')}: {confidence:.2f}"
            )

    # Insert equipment
    for equip in data.get('equipment', []):
        confidence = equip.get('confidence', 0.7)
        cursor.execute("""
            INSERT INTO equipment (sheet_id, tag, description, equipment_type, confidence)
            VALUES (?, ?, ?, ?, ?)
        """, (
            sheet_id,
            equip.get('tag'),
            equip.get('description'),
            equip.get('equipment_type'),
            confidence
        ))
        stats['equipment'] += 1
        confidences.append(confidence)

        if confidence < 0.6:
            stats['low_confidence_items'].append(
                f"Equipment {equip.get('tag')}: {confidence:.2f}"
            )

    # Calculate average confidence
    if confidences:
        stats['avg_confidence'] = sum(confidences) / len(confidences)

    # Determine complexity based on item count
    total_items = stats['lines'] + stats['equipment']
    if total_items > 100:
        complexity = 'high'
    elif total_items > 50:
        complexity = 'medium'
    else:
        complexity = 'low'

    # Update sheet metadata
    cursor.execute("""
        UPDATE sheets
        SET extracted_at = ?,
            quality_score = ?,
            complexity = ?,
            drawing_type = 'plumbing_riser',
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
    print(f"  - Lines: {stats['lines']}")
    print(f"  - Equipment: {stats['equipment']}")
    print(f"  - Average confidence: {stats['avg_confidence']:.2f}")
    print(f"  - Complexity: {complexity}")

    if stats['low_confidence_items']:
        print(f"\nLow confidence items flagged for review:")
        for item in stats['low_confidence_items']:
            print(f"  - {item}")

    return stats


def main():
    """Main extraction process."""
    print("Plumbing Process Waste Riser Diagram Extraction")
    print("=" * 80)
    print(f"Database: {DB_PATH}")
    print(f"Sheet ID: {SHEET['id']}")

    try:
        # Extract data
        data = extract_data_from_drawing(SHEET)

        if data:
            # Insert into database
            stats = insert_into_database(SHEET['id'], SHEET['sheet_number'], data)

            # Print summary
            print("\n" + "=" * 80)
            print("EXTRACTION COMPLETE")
            print("=" * 80)
            print(f"\nSheet {SHEET['id']} ({SHEET['sheet_number']} Rev {SHEET['revision']}):")
            print(f"  Lines: {stats['lines']}")
            print(f"  Equipment: {stats['equipment']}")
            print(f"  Quality Score: {stats['avg_confidence']:.2f}")
            print(f"  Total items: {stats['lines'] + stats['equipment']}")

            if data.get('notes'):
                print(f"\nExtraction Notes:")
                print(f"  {data['notes']}")
        else:
            print(f"ERROR: Failed to extract data from sheet {SHEET['sheet_number']}")

    except Exception as e:
        print(f"ERROR processing {SHEET['sheet_number']}: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
