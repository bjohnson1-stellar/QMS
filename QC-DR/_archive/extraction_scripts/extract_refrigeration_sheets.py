#!/usr/bin/env python3
"""
Extract data from Refrigeration-Controls drawing sheets for project 07308.
Uses Claude API with vision to read PDFs and extract structured data.
"""

import sqlite3
import json
import base64
import os
import sys
from pathlib import Path
from datetime import datetime
from anthropic import Anthropic

# Initialize Anthropic client - will use ANTHROPIC_API_KEY from environment or default config
try:
    client = Anthropic()
except Exception as e:
    print(f"ERROR: Could not initialize Anthropic client: {e}")
    print("Make sure ANTHROPIC_API_KEY environment variable is set")
    sys.exit(1)

# Sheet information for Refrigeration-Controls discipline
SHEETS = [
    {
        'id': 156,
        'path': 'D:/Projects/07308-BIRDCAGE/Refrigeration-Controls/RC14080-REFRIGERATION-CONTROLS-PLAN-PIPE-AND-DUCT-ROOF---AREA-8-Rev.8.pdf',
        'drawing_number': 'RC14080',
        'type': 'plan',
        'title': 'REFRIGERATION-CONTROLS-PLAN-PIPE-AND-DUCT-ROOF---AREA-8',
        'revision': '8'
    },
    {
        'id': 157,
        'path': 'D:/Projects/07308-BIRDCAGE/Refrigeration-Controls/RC41101-REFRIGERATION-CONTROLS-ENLARGED-PLAN-MACHINE-ROOM-PIPE-AND-EQUIPMENT-FLOOR-Rev.9.pdf',
        'drawing_number': 'RC41101',
        'type': 'plan',
        'title': 'REFRIGERATION-CONTROLS-ENLARGED-PLAN-MACHINE-ROOM-PIPE-AND-EQUIPMENT-FLOOR',
        'revision': '9'
    },
    {
        'id': 158,
        'path': 'D:/Projects/07308-BIRDCAGE/Refrigeration-Controls/RC50000-REFRIGERATION-CONTROLS-DETAIL-SHEET-Rev.5.pdf',
        'drawing_number': 'RC50000',
        'type': 'detail',
        'title': 'REFRIGERATION-CONTROLS-DETAIL-SHEET',
        'revision': '5'
    }
]

DB_PATH = 'D:/quality.db'

def encode_pdf_pages(pdf_path, max_pages=5):
    """Convert PDF pages to base64-encoded images using PyMuPDF."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        print("Installing PyMuPDF...")
        import subprocess
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'PyMuPDF'])
        import fitz

    doc = fitz.open(pdf_path)
    images = []

    num_pages = min(len(doc), max_pages)
    for page_num in range(num_pages):
        page = doc[page_num]
        # Render at 150 DPI for good quality without huge files
        mat = fitz.Matrix(150/72, 150/72)
        pix = page.get_pixmap(matrix=mat)
        img_bytes = pix.tobytes("png")
        images.append({
            'page': page_num + 1,
            'data': base64.b64encode(img_bytes).decode('utf-8')
        })

    doc.close()
    return images

def extract_controls_plan(images, drawing_number):
    """Extract refrigeration controls data from plan drawings."""

    prompt = f"""Extract all refrigeration control system data from this plan drawing {drawing_number}.

For each INSTRUMENT, provide:
- Tag number (e.g., TT-101, PT-201, TS-301, PS-401, LT-501)
- Instrument type (Temperature Transmitter, Pressure Transmitter, Temperature Switch, Pressure Switch, Level Transmitter, Flow Transmitter, etc.)
- Loop number if shown
- Service description if shown

For each EQUIPMENT item, provide:
- Tag number (e.g., P-101, C-201, E-301, V-401)
- Equipment type (Pump, Compressor, Evaporator, Condenser, Vessel, Receiver, Accumulator, Heat Exchanger, etc.)
- Description/service
- Any specifications shown (capacity, power, size, etc.)

For each CONTROL LINE (refrigerant lines, brine lines, glycol lines, control air), provide:
- Line number (complete format if shown, e.g., 2-REF-401-R1)
- Size
- Material or service type (refrigerant, brine, glycol, control air, etc.)
- Service description
- From/To locations if clear

For CONTROL VALVES, provide:
- Tag number (e.g., TCV-101, PCV-201)
- Valve type (Temperature Control Valve, Pressure Control Valve, Solenoid Valve, etc.)
- Size if shown
- Service/function

Return ONLY valid JSON in this exact format:
{{
  "drawing_number": "{drawing_number}",
  "drawing_type": "plan",
  "complexity": "simple|medium|complex",
  "equipment": [
    {{"tag": "C-401", "type": "Compressor", "description": "Refrigeration Compressor", "specifications": "100 HP", "confidence": 0.95}}
  ],
  "lines": [
    {{"line_number": "2-REF-401", "size": "2\\"", "material": "Refrigerant", "service": "Suction Line", "from_location": "Evaporator", "to_location": "Compressor", "confidence": 0.90}}
  ],
  "instruments": [
    {{"tag": "PT-401", "type": "Pressure Transmitter", "loop_number": "401", "service": "Suction Pressure", "confidence": 0.90}}
  ],
  "control_valves": [
    {{"tag": "TCV-401", "type": "Temperature Control Valve", "size": "1\\"", "service": "Refrigerant Flow Control", "confidence": 0.90}}
  ],
  "notes": "Any special observations or unclear items"
}}"""

    content = [{"type": "text", "text": prompt}]

    for img in images:
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": img['data']
            }
        })

    message = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=8000,
        messages=[{"role": "user", "content": content}]
    )

    response_text = message.content[0].text

    # Extract JSON from response (handle markdown code blocks)
    if '```json' in response_text:
        json_str = response_text.split('```json')[1].split('```')[0].strip()
    elif '```' in response_text:
        json_str = response_text.split('```')[1].split('```')[0].strip()
    else:
        json_str = response_text.strip()

    return json.loads(json_str)

def extract_controls_detail(images, drawing_number):
    """Extract refrigeration controls data from detail drawings."""

    prompt = f"""Extract all refrigeration control details from this detail sheet {drawing_number}.

Detail sheets typically show:
- Control sequences and logic
- Piping details and connections
- Instrument installation details
- Control valve arrangements
- Wiring and control diagrams

For each INSTRUMENT, provide:
- Tag number
- Instrument type
- Service description
- Setpoints or ranges if shown

For each EQUIPMENT item, provide:
- Tag number
- Equipment type
- Description
- Specifications if shown

For each CONTROL LINE or PIPING DETAIL, provide:
- Line number if shown
- Size
- Material/service type
- Connection details

For CONTROL SEQUENCES, provide:
- Description of the control logic
- Related instruments and equipment tags
- Setpoints and operating parameters

Return ONLY valid JSON in this exact format:
{{
  "drawing_number": "{drawing_number}",
  "drawing_type": "detail",
  "complexity": "simple|medium|complex",
  "equipment": [
    {{"tag": "...", "type": "...", "description": "...", "specifications": "...", "confidence": 0.95}}
  ],
  "lines": [
    {{"line_number": "...", "size": "...", "material": "...", "service": "...", "confidence": 0.90}}
  ],
  "instruments": [
    {{"tag": "...", "type": "...", "service": "...", "setpoint": "...", "confidence": 0.90}}
  ],
  "control_valves": [
    {{"tag": "...", "type": "...", "size": "...", "service": "...", "confidence": 0.90}}
  ],
  "control_sequences": [
    {{"description": "...", "tags": ["...", "..."], "setpoint": "...", "notes": "..."}}
  ],
  "notes": "Any special observations or unclear items"
}}"""

    content = [{"type": "text", "text": prompt}]

    for img in images:
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": img['data']
            }
        })

    message = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=8000,
        messages=[{"role": "user", "content": content}]
    )

    response_text = message.content[0].text

    # Extract JSON from response
    if '```json' in response_text:
        json_str = response_text.split('```json')[1].split('```')[0].strip()
    elif '```' in response_text:
        json_str = response_text.split('```')[1].split('```')[0].strip()
    else:
        json_str = response_text.strip()

    return json.loads(json_str)

def store_extractions(sheet_id, data, db_path):
    """Store extracted data in database."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    counts = {
        'equipment': 0,
        'lines': 0,
        'instruments': 0,
        'control_valves': 0,
        'control_sequences': 0
    }

    try:
        # Store equipment
        if 'equipment' in data:
            for eq in data['equipment']:
                cursor.execute("""
                    INSERT INTO equipment (sheet_id, tag, description, equipment_type, confidence)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    sheet_id,
                    eq.get('tag', ''),
                    eq.get('description', '') or eq.get('specifications', ''),
                    eq.get('type', ''),
                    eq.get('confidence', 0.85)
                ))
                counts['equipment'] += 1

        # Store lines
        if 'lines' in data:
            for line in data['lines']:
                cursor.execute("""
                    INSERT INTO lines (sheet_id, line_number, size, material, service,
                                     from_location, to_location, confidence)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    sheet_id,
                    line.get('line_number', ''),
                    line.get('size', ''),
                    line.get('material', ''),
                    line.get('service', ''),
                    line.get('from_location', ''),
                    line.get('to_location', ''),
                    line.get('confidence', 0.80)
                ))
                counts['lines'] += 1

        # Store instruments
        if 'instruments' in data:
            for inst in data['instruments']:
                loop_number = inst.get('loop_number', '') or inst.get('service', '')
                cursor.execute("""
                    INSERT INTO instruments (sheet_id, tag, instrument_type, loop_number, confidence)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    sheet_id,
                    inst.get('tag', ''),
                    inst.get('type', ''),
                    loop_number,
                    inst.get('confidence', 0.85)
                ))
                counts['instruments'] += 1

        # Store control valves as equipment
        if 'control_valves' in data:
            for valve in data['control_valves']:
                desc = f"{valve.get('service', '')} - {valve.get('size', '')}".strip(' -')
                cursor.execute("""
                    INSERT INTO equipment (sheet_id, tag, description, equipment_type, confidence)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    sheet_id,
                    valve.get('tag', ''),
                    desc,
                    valve.get('type', 'Control Valve'),
                    valve.get('confidence', 0.85)
                ))
                counts['control_valves'] += 1

        # Count control sequences (not stored in separate table, just for reporting)
        if 'control_sequences' in data:
            counts['control_sequences'] = len(data['control_sequences'])

        # Update sheet metadata
        all_items = []
        for category in ['equipment', 'lines', 'instruments', 'control_valves']:
            if category in data:
                all_items.extend(data[category])

        if all_items:
            avg_confidence = sum([item.get('confidence', 0.85) for item in all_items]) / len(all_items)
        else:
            avg_confidence = 0.0

        cursor.execute("""
            UPDATE sheets
            SET extracted_at = ?,
                extraction_model = 'claude-sonnet-4-5-20250929',
                quality_score = ?,
                drawing_type = ?,
                complexity = ?
            WHERE id = ?
        """, (
            datetime.now().isoformat(),
            avg_confidence,
            data.get('drawing_type', 'plan'),
            data.get('complexity', 'medium'),
            sheet_id
        ))

        conn.commit()

    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

    return counts

def main():
    """Main extraction process."""

    print("=" * 80)
    print("REFRIGERATION-CONTROLS DRAWING DATA EXTRACTION")
    print("Project: 07308-BIRDCAGE")
    print("Discipline: Refrigeration-Controls")
    print("=" * 80)
    print()

    results = []

    for sheet in SHEETS:
        print(f"\nProcessing Sheet {sheet['id']}: {sheet['drawing_number']} Rev {sheet['revision']}")
        print(f"  File: {sheet['path']}")
        print(f"  Type: {sheet['type']}")
        print(f"  Title: {sheet['title']}")

        # Check file exists
        if not os.path.exists(sheet['path']):
            print(f"  ERROR: File not found!")
            results.append({
                'sheet': sheet,
                'error': 'File not found',
                'counts': {}
            })
            continue

        try:
            # Convert PDF to images
            print("  Converting PDF to images...")
            max_pages = 10 if sheet['type'] == 'detail' else 5
            images = encode_pdf_pages(sheet['path'], max_pages=max_pages)
            print(f"  Converted {len(images)} pages")

            # Extract data based on drawing type
            print("  Extracting data with Claude Sonnet 4.5...")
            if sheet['type'] == 'detail':
                data = extract_controls_detail(images, sheet['drawing_number'])
            else:
                data = extract_controls_plan(images, sheet['drawing_number'])

            # Store in database
            print("  Storing in database...")
            counts = store_extractions(sheet['id'], data, DB_PATH)

            # Report
            print("  Extracted:")
            for category, count in counts.items():
                if count > 0:
                    print(f"    - {category}: {count}")

            if 'notes' in data and data['notes']:
                print(f"  Notes: {data['notes']}")

            results.append({
                'sheet': sheet,
                'counts': counts,
                'data': data
            })
            print("  COMPLETE")

        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback
            traceback.print_exc()
            results.append({
                'sheet': sheet,
                'error': str(e),
                'counts': {}
            })

    # Summary
    print("\n" + "=" * 80)
    print("EXTRACTION SUMMARY")
    print("=" * 80)

    total_counts = {
        'equipment': 0,
        'lines': 0,
        'instruments': 0,
        'control_valves': 0,
        'control_sequences': 0
    }

    successful = 0
    for result in results:
        if 'error' not in result:
            successful += 1
            for category, count in result['counts'].items():
                total_counts[category] += count

    print(f"\nTotal Extracted:")
    for category, count in total_counts.items():
        if count > 0:
            print(f"  - {category}: {count}")

    print(f"\nDatabase: {DB_PATH}")
    print(f"Sheets processed successfully: {successful}/{len(SHEETS)}")

    if successful < len(SHEETS):
        print("\nFailed sheets:")
        for result in results:
            if 'error' in result:
                print(f"  - {result['sheet']['drawing_number']}: {result['error']}")

    print("\nExtraction complete!")

    return 0 if successful == len(SHEETS) else 1

if __name__ == '__main__':
    sys.exit(main())
