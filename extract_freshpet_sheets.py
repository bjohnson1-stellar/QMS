"""
Extract data from Freshpet refrigeration drawings (sheets 577, 578, 579).
"""

import sqlite3
import json
import base64
from pathlib import Path
import anthropic
import os

# Sheet configurations
SHEETS = [
    {
        "id": 577,
        "path": r"D:\qms\data\projects\07609-Freshpet\Refrigeration\R1112.1-REFRIGERATION-PLAN-PIPE-AND-EQUIPMENT-FLOOR-AREA-2-Rev.1.pdf",
        "drawing_number": "R1112.1",
        "title": "REFRIGERATION PLAN PIPE AND EQUIPMENT FLOOR AREA 2"
    },
    {
        "id": 578,
        "path": r"D:\qms\data\projects\07609-Freshpet\Refrigeration\R1113.1-REFRIGERATION-PLAN-PIPE-AND-EQUIPMENT-FLOOR-AREA-3-Rev.1.pdf",
        "drawing_number": "R1113.1",
        "title": "REFRIGERATION PLAN PIPE AND EQUIPMENT FLOOR AREA 3"
    },
    {
        "id": 579,
        "path": r"D:\qms\data\projects\07609-Freshpet\Refrigeration\R1114.1-REFRIGERATION-PLAN-PIPE-AND-EQUIPMENT-FLOOR-AREA-4-Rev.1.pdf",
        "drawing_number": "R1114.1",
        "title": "REFRIGERATION PLAN PIPE AND EQUIPMENT FLOOR AREA 4"
    }
]

DB_PATH = r"D:\qms\data\quality.db"

EXTRACTION_PROMPT = """Extract all refrigeration piping and equipment data from this drawing.

This is a REFRIGERATION PLAN showing pipes, equipment, and instruments on a floor plan.

For each REFRIGERATION PIPE/LINE, provide:
- Line number (may be in formats like: RL-1, RL-2, SL-1, DL-1, or size-spec format)
- Pipe size (e.g., 1-1/8", 2-1/8", 3-1/8", 4-1/8", etc.)
- Service type (Suction, Liquid, Hot Gas, Defrost, etc.)
- From equipment/location
- To equipment/location
- Material/spec if shown
- Refrigerant type if shown (NH3, ammonia)

For each EQUIPMENT item, provide:
- Tag number (e.g., REC-1, EVAP-1, COMP-1, etc.)
- Equipment type (Receiver, Evaporator, Compressor, Vessel, Pump, etc.)
- Description/name if shown

For each INSTRUMENT, provide:
- Tag number
- Instrument type (transmitter, valve, gauge, switch, etc.)
- Service/measurement type if shown

Return ONLY valid JSON in this exact format:
{
  "lines": [
    {
      "line_number": "RL-1",
      "size": "2-1/8\"",
      "service": "Liquid",
      "from_location": "REC-1",
      "to_location": "EVAP-1",
      "material": "Schedule 40",
      "spec_class": null,
      "refrigerant": "NH3",
      "confidence": 0.95
    }
  ],
  "equipment": [
    {
      "tag": "REC-1",
      "equipment_type": "Receiver",
      "description": "Low Pressure Receiver",
      "confidence": 0.9
    }
  ],
  "instruments": [
    {
      "tag": "PT-101",
      "instrument_type": "Pressure Transmitter",
      "loop_number": null,
      "service": "Suction Pressure",
      "confidence": 0.85
    }
  ]
}

IMPORTANT:
- Return ONLY the JSON object, no other text
- Use null for missing values
- Confidence should be 0.0-1.0 based on clarity
- Be thorough - extract ALL visible items"""

def encode_pdf(pdf_path: str) -> str:
    """Encode PDF as base64."""
    with open(pdf_path, 'rb') as f:
        return base64.standard_b64encode(f.read()).decode('utf-8')

def extract_sheet_data(client: anthropic.Anthropic, sheet: dict) -> dict:
    """Extract data from one sheet using Claude."""
    print(f"\n{'='*80}")
    print(f"Extracting: {sheet['drawing_number']} - {sheet['title']}")
    print(f"Sheet ID: {sheet['id']}")
    print(f"{'='*80}")

    # Encode PDF
    pdf_base64 = encode_pdf(sheet['path'])

    # Call Claude Sonnet for extraction
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=16000,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": pdf_base64
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

    # Parse response
    response_text = message.content[0].text.strip()

    # Remove markdown code blocks if present
    if response_text.startswith("```"):
        lines = response_text.split('\n')
        response_text = '\n'.join(lines[1:-1]) if len(lines) > 2 else response_text
        if response_text.startswith("json"):
            response_text = response_text[4:].strip()

    try:
        data = json.loads(response_text)
    except json.JSONDecodeError as e:
        print(f"ERROR: Failed to parse JSON response")
        print(f"Response: {response_text[:500]}...")
        raise

    # Add sheet_id to all items
    for line in data.get('lines', []):
        line['sheet_id'] = sheet['id']
    for equip in data.get('equipment', []):
        equip['sheet_id'] = sheet['id']
    for inst in data.get('instruments', []):
        inst['sheet_id'] = sheet['id']

    return data

def save_to_database(data: dict, sheet_id: int):
    """Save extracted data to database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Insert lines
    for line in data.get('lines', []):
        cursor.execute("""
            INSERT INTO lines (
                sheet_id, line_number, size, material, spec_class,
                from_location, to_location, service, refrigerant, confidence
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            sheet_id,
            line.get('line_number'),
            line.get('size'),
            line.get('material'),
            line.get('spec_class'),
            line.get('from_location'),
            line.get('to_location'),
            line.get('service'),
            line.get('refrigerant'),
            line.get('confidence', 0.7)
        ))

    # Insert equipment
    for equip in data.get('equipment', []):
        cursor.execute("""
            INSERT INTO equipment (
                sheet_id, tag, equipment_type, description, confidence
            ) VALUES (?, ?, ?, ?, ?)
        """, (
            sheet_id,
            equip.get('tag'),
            equip.get('equipment_type'),
            equip.get('description'),
            equip.get('confidence', 0.7)
        ))

    # Insert instruments
    for inst in data.get('instruments', []):
        cursor.execute("""
            INSERT INTO instruments (
                sheet_id, tag, instrument_type, loop_number,
                service, confidence
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            sheet_id,
            inst.get('tag'),
            inst.get('instrument_type'),
            inst.get('loop_number'),
            inst.get('service'),
            inst.get('confidence', 0.7)
        ))

    # Update sheet metadata
    lines_count = len(data.get('lines', []))
    equip_count = len(data.get('equipment', []))
    inst_count = len(data.get('instruments', []))

    total_items = lines_count + equip_count + inst_count
    if total_items > 0:
        avg_confidence = sum(
            [l.get('confidence', 0.7) for l in data.get('lines', [])] +
            [e.get('confidence', 0.7) for e in data.get('equipment', [])] +
            [i.get('confidence', 0.7) for i in data.get('instruments', [])]
        ) / total_items
    else:
        avg_confidence = 0.0

    cursor.execute("""
        UPDATE sheets
        SET extracted_at = datetime('now'),
            extraction_model = 'claude-sonnet-4-20250514',
            quality_score = ?,
            complexity = 'medium',
            drawing_type = 'Refrigeration Plan'
        WHERE id = ?
    """, (avg_confidence, sheet_id))

    conn.commit()
    conn.close()

    print(f"\nExtracted and saved:")
    print(f"  - Lines: {lines_count} (avg confidence: {sum([l.get('confidence', 0.7) for l in data.get('lines', [])]) / max(lines_count, 1):.2f})")
    print(f"  - Equipment: {equip_count} (avg confidence: {sum([e.get('confidence', 0.7) for e in data.get('equipment', [])]) / max(equip_count, 1):.2f})")
    print(f"  - Instruments: {inst_count} (avg confidence: {sum([i.get('confidence', 0.7) for i in data.get('instruments', [])]) / max(inst_count, 1):.2f})")
    print(f"  - Overall quality score: {avg_confidence:.2f}")

def main():
    """Main extraction process."""
    # Initialize Anthropic client
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable not set")

    client = anthropic.Anthropic(api_key=api_key)

    # Process each sheet
    for sheet in SHEETS:
        try:
            # Check if file exists
            if not Path(sheet['path']).exists():
                print(f"ERROR: File not found: {sheet['path']}")
                continue

            # Extract data
            data = extract_sheet_data(client, sheet)

            # Save to database
            save_to_database(data, sheet['id'])

        except Exception as e:
            print(f"ERROR processing sheet {sheet['id']}: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "="*80)
    print("Extraction complete!")
    print("="*80)

if __name__ == '__main__':
    main()
