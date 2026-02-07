#!/usr/bin/env python3
"""
P&ID Data Extractor for Quality Database
Extracts lines, equipment, and instruments from P&ID drawings.
"""

import sqlite3
import json
import base64
import os
from pathlib import Path
import anthropic

# Configuration
DATABASE = "D:/quality.db"
SHEETS = [
    (97, "D:/Projects/07308-BIRDCAGE/Refrigeration/R70019-REFRIGERATION-P&ID-Rev.7.pdf"),
    (98, "D:/Projects/07308-BIRDCAGE/Refrigeration/R70020-REFRIGERATION-P&ID-Rev.7.pdf"),
    (99, "D:/Projects/07308-BIRDCAGE/Refrigeration/R70021-REFRIGERATION-P&ID-Rev.7.pdf"),
]

EXTRACTION_PROMPT = """Extract all piping and instrumentation data from this P&ID drawing.

For each PROCESS LINE, provide:
- line_number: Full line number (format: SIZE-MATERIAL-NUMBER-SPEC, e.g., "2-CS-101-A1A")
- size: Pipe size (e.g., "2\"", "4\"", "1-1/2\"")
- material: Material code (e.g., CS, SS, CU for Carbon Steel, Stainless Steel, Copper)
- spec_class: Specification class (e.g., A1A, 150#, 300#)
- service: Service description (e.g., "Refrigerant Liquid", "Hot Gas", "Oil")
- from_location: Starting point (equipment tag or location)
- to_location: Ending point (equipment tag or location)

For each EQUIPMENT item, provide:
- tag: Equipment tag number (e.g., P-101, V-201, TK-301)
- description: Equipment description/name
- equipment_type: Type of equipment (pump, vessel, tank, exchanger, compressor, valve, separator, filter, etc.)

For each INSTRUMENT, provide:
- tag: Instrument tag number (e.g., FT-101, PT-201, TT-301, PSV-401)
- instrument_type: Type of instrument (flow_transmitter, pressure_transmitter, temperature_transmitter, level_transmitter, control_valve, safety_valve, pressure_switch, temperature_switch, etc.)
- loop_number: Associated control loop number if shown

Important:
- Only extract clearly visible and readable items
- Use null for fields that aren't visible or readable
- For line_number, if you can see parts but not all, capture what you can see
- Focus on process lines, not instrument lines
- Include all equipment shown on the drawing
- Include all instruments, transmitters, valves, and control devices

Return ONLY a JSON object with this structure:
{
  "lines": [
    {
      "line_number": "2-CS-101-A1A",
      "size": "2\"",
      "material": "CS",
      "spec_class": "A1A",
      "service": "Refrigerant Liquid",
      "from_location": "V-101",
      "to_location": "P-201",
      "confidence": 0.95
    }
  ],
  "equipment": [
    {
      "tag": "P-101",
      "description": "Refrigerant Pump",
      "equipment_type": "pump",
      "confidence": 0.98
    }
  ],
  "instruments": [
    {
      "tag": "FT-101",
      "instrument_type": "flow_transmitter",
      "loop_number": "101",
      "confidence": 0.92
    }
  ]
}

Do NOT include any explanatory text, only the JSON object."""


def encode_pdf(pdf_path):
    """Encode PDF file to base64."""
    with open(pdf_path, 'rb') as f:
        return base64.standard_b64encode(f.read()).decode('utf-8')


def extract_from_pdf(pdf_path, model="claude-sonnet-4-5-20250929"):
    """Extract data from P&ID PDF using Claude."""
    client = anthropic.Anthropic()

    pdf_data = encode_pdf(pdf_path)

    message = client.messages.create(
        model=model,
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
                            "data": pdf_data,
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

    # Extract JSON from response
    response_text = message.content[0].text

    # Try to find JSON in the response
    try:
        # Try parsing directly
        data = json.loads(response_text)
        return data
    except json.JSONDecodeError:
        # Try to extract JSON from code blocks
        if "```json" in response_text:
            json_start = response_text.find("```json") + 7
            json_end = response_text.find("```", json_start)
            json_text = response_text[json_start:json_end].strip()
            data = json.loads(json_text)
            return data
        elif "```" in response_text:
            json_start = response_text.find("```") + 3
            json_end = response_text.find("```", json_start)
            json_text = response_text[json_start:json_end].strip()
            data = json.loads(json_text)
            return data
        else:
            raise ValueError(f"Could not parse JSON from response: {response_text[:500]}")


def store_extractions(conn, sheet_id, data):
    """Store extracted data in database."""
    cursor = conn.cursor()

    stats = {
        'lines': 0,
        'equipment': 0,
        'instruments': 0,
        'avg_confidence': {'lines': 0, 'equipment': 0, 'instruments': 0},
        'low_confidence_items': []
    }

    # Insert lines
    if data.get('lines'):
        for line in data['lines']:
            cursor.execute("""
                INSERT INTO lines (sheet_id, line_number, size, material, spec_class,
                                  service, from_location, to_location, confidence)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                sheet_id,
                line.get('line_number'),
                line.get('size'),
                line.get('material'),
                line.get('spec_class'),
                line.get('service'),
                line.get('from_location'),
                line.get('to_location'),
                line.get('confidence', 0.7)
            ))
            stats['lines'] += 1
            conf = line.get('confidence', 0.7)
            stats['avg_confidence']['lines'] += conf

            if conf < 0.6:
                stats['low_confidence_items'].append(f"Line {line.get('line_number')}: confidence {conf:.2f}")

    # Insert equipment
    if data.get('equipment'):
        for equip in data['equipment']:
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
            stats['avg_confidence']['equipment'] += conf

            if conf < 0.6:
                stats['low_confidence_items'].append(f"Equipment {equip.get('tag')}: confidence {conf:.2f}")

    # Insert instruments
    if data.get('instruments'):
        for inst in data['instruments']:
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
            stats['avg_confidence']['instruments'] += conf

            if conf < 0.6:
                stats['low_confidence_items'].append(f"Instrument {inst.get('tag')}: confidence {conf:.2f}")

    # Calculate averages
    if stats['lines'] > 0:
        stats['avg_confidence']['lines'] /= stats['lines']
    if stats['equipment'] > 0:
        stats['avg_confidence']['equipment'] /= stats['equipment']
    if stats['instruments'] > 0:
        stats['avg_confidence']['instruments'] /= stats['instruments']

    # Calculate overall quality score
    total_items = stats['lines'] + stats['equipment'] + stats['instruments']
    if total_items > 0:
        quality_score = (
            stats['avg_confidence']['lines'] * stats['lines'] +
            stats['avg_confidence']['equipment'] * stats['equipment'] +
            stats['avg_confidence']['instruments'] * stats['instruments']
        ) / total_items
    else:
        quality_score = 0.0

    conn.commit()

    return stats, quality_score


def update_sheet_metadata(conn, sheet_id, quality_score, model):
    """Update sheet metadata after extraction."""
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE sheets
        SET extracted_at = datetime('now'),
            extraction_model = ?,
            quality_score = ?,
            drawing_type = 'pid',
            complexity = CASE WHEN ? >= 0.85 THEN 'simple' ELSE 'medium' END
        WHERE id = ?
    """, (model, quality_score, quality_score, sheet_id))
    conn.commit()


def main():
    """Main extraction process."""
    conn = sqlite3.connect(DATABASE)

    print("P&ID Data Extraction - Project 07308-BIRDCAGE")
    print("=" * 80)
    print()

    for sheet_id, pdf_path in SHEETS:
        print(f"Processing Sheet {sheet_id}: {Path(pdf_path).name}")
        print("-" * 80)

        # Get sheet info
        cursor = conn.cursor()
        cursor.execute("""
            SELECT drawing_number, revision, title
            FROM sheets WHERE id = ?
        """, (sheet_id,))
        sheet_info = cursor.fetchone()

        if sheet_info:
            dwg_num, rev, title = sheet_info
            print(f"Drawing: {dwg_num} Rev {rev}")
            if title:
                print(f"Title: {title}")

        print(f"File: {pdf_path}")
        print()

        # Extract data
        print("Extracting data using Claude Sonnet 4.5...")
        try:
            data = extract_from_pdf(pdf_path)

            print(f"Found:")
            print(f"  - Lines: {len(data.get('lines', []))}")
            print(f"  - Equipment: {len(data.get('equipment', []))}")
            print(f"  - Instruments: {len(data.get('instruments', []))}")
            print()

            # Store in database
            print("Storing in database...")
            stats, quality_score = store_extractions(conn, sheet_id, data)

            print(f"Stored:")
            print(f"  - Lines: {stats['lines']} (avg confidence: {stats['avg_confidence']['lines']:.2f})")
            print(f"  - Equipment: {stats['equipment']} (avg confidence: {stats['avg_confidence']['equipment']:.2f})")
            print(f"  - Instruments: {stats['instruments']} (avg confidence: {stats['avg_confidence']['instruments']:.2f})")
            print()
            print(f"Quality Score: {quality_score:.2f}")

            if stats['low_confidence_items']:
                print()
                print("Flagged for Review:")
                for item in stats['low_confidence_items']:
                    print(f"  - {item}")

            # Update sheet metadata
            update_sheet_metadata(conn, sheet_id, quality_score, "claude-sonnet-4-5-20250929")

            print()
            print("SUCCESS")

        except Exception as e:
            print(f"ERROR: {e}")
            import traceback
            traceback.print_exc()

        print()
        print()

    conn.close()
    print("=" * 80)
    print("Extraction complete!")


if __name__ == "__main__":
    main()
