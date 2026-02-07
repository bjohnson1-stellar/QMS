"""
Extract data from refrigeration plan drawings and store in database.
"""
import json
import sqlite3
import base64
from datetime import datetime
from pathlib import Path
import anthropic
import os

# Configuration
DATABASE_PATH = "D:/quality.db"
SHEETS = [
    {"id": 4, "path": "D:/Projects/07308-BIRDCAGE/Refrigeration/R11010-REFRIGERATION-PLAN-PIPE-AND-DUCT-FLOOR-AREA1-Rev.6.pdf"},
    {"id": 5, "path": "D:/Projects/07308-BIRDCAGE/Refrigeration/R11020-REFRIGERATION-PLAN-PIPE-AND-DUCT-FLOOR-AREA-2-Rev.7.pdf"},
    {"id": 6, "path": "D:/Projects/07308-BIRDCAGE/Refrigeration/R11030-REFRIGERATION-PLAN-PIPE-AND-DUCT-FLOOR-AREA-3-Rev.6.pdf"}
]

EXTRACTION_PROMPT = """Extract all piping, equipment, and instrumentation data from this refrigeration plan drawing.

This is a PLAN VIEW showing pipe and duct routing for a refrigeration system.

For each REFRIGERATION LINE visible, provide:
- Line number/tag (e.g., RL-101, SR-201, LL-301)
- Size (pipe diameter)
- Service type (suction, hot gas, liquid, etc.)
- Material/insulation notes if visible
- From location/equipment
- To location/equipment

For each EQUIPMENT item shown, provide:
- Tag number (e.g., COMP-01, EVAP-02, REC-01)
- Equipment type (compressor, evaporator, receiver, condenser, etc.)
- Description/label if shown
- Location/grid reference

For each INSTRUMENT visible, provide:
- Tag number (e.g., PT-101, TT-201, PSV-301)
- Instrument type (pressure transmitter, temperature transmitter, safety valve, etc.)
- Associated equipment or line

For DUCTS shown:
- Duct tag/reference
- Size
- Service (supply, return, exhaust, etc.)

Also extract:
- Grid references (column lines)
- Area/floor designation
- Key dimensions if clearly labeled
- Special notes or legends

Return the data as a structured JSON object with the following format:
{
  "lines": [
    {
      "line_number": "RL-101",
      "size": "4 inch",
      "service": "suction",
      "material": "copper",
      "from_location": "EVAP-01",
      "to_location": "COMP-01",
      "confidence": 0.9
    }
  ],
  "equipment": [
    {
      "tag": "COMP-01",
      "equipment_type": "compressor",
      "description": "Screw compressor",
      "location": "Grid A-1",
      "confidence": 0.95
    }
  ],
  "instruments": [
    {
      "tag": "PT-101",
      "instrument_type": "pressure_transmitter",
      "loop_number": "101",
      "confidence": 0.85
    }
  ],
  "ducts": [
    {
      "tag": "SA-01",
      "size": "24x18",
      "service": "supply air",
      "confidence": 0.8
    }
  ],
  "metadata": {
    "floor_area": "Area 4",
    "grid_references": ["A", "B", "C", "1", "2", "3"],
    "complexity": "medium",
    "notes": []
  }
}

Assign confidence scores (0.0 to 1.0) based on:
- Text clarity: clear=+0.2, partially obscured=-0.2
- Standard format: standard=+0.1, non-standard=-0.1
- Information completeness: complete=+0.1, partial=-0.1
Base confidence: 0.7

If you cannot read something clearly, note it in a "notes" field with lower confidence."""

def pdf_to_images(pdf_path):
    """Convert PDF to images using PyMuPDF."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        print("Installing PyMuPDF...")
        os.system("pip install pymupdf -q")
        import fitz

    doc = fitz.open(pdf_path)
    images = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        # Render at high resolution for better text recognition
        mat = fitz.Matrix(2.0, 2.0)  # 2x zoom
        pix = page.get_pixmap(matrix=mat)
        img_data = pix.tobytes("png")
        images.append(base64.standard_b64encode(img_data).decode('utf-8'))

    doc.close()
    return images

def extract_with_claude(image_base64, sheet_info):
    """Extract data from drawing using Claude API."""
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    print(f"  Using model: claude-sonnet-4-5 (refrigeration plan - medium complexity)")

    message = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=4096,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": image_base64
                    }
                },
                {
                    "type": "text",
                    "text": EXTRACTION_PROMPT
                }
            ]
        }]
    )

    response_text = message.content[0].text

    # Extract JSON from response (might be wrapped in markdown code blocks)
    if "```json" in response_text:
        json_start = response_text.find("```json") + 7
        json_end = response_text.find("```", json_start)
        response_text = response_text[json_start:json_end].strip()
    elif "```" in response_text:
        json_start = response_text.find("```") + 3
        json_end = response_text.find("```", json_start)
        response_text = response_text[json_start:json_end].strip()

    return json.loads(response_text)

def calculate_avg_confidence(items):
    """Calculate average confidence from list of items."""
    if not items:
        return 0.0
    confidences = [item.get('confidence', 0.7) for item in items]
    return sum(confidences) / len(confidences)

def store_extractions(conn, sheet_id, extracted_data):
    """Store extracted data in database."""
    cursor = conn.cursor()

    # Store lines
    lines = extracted_data.get('lines', [])
    for line in lines:
        cursor.execute("""
            INSERT INTO lines (sheet_id, line_number, size, material,
                             spec_class, from_location, to_location, service, confidence)
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

    # Store equipment
    equipment_items = extracted_data.get('equipment', [])
    for equip in equipment_items:
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

    # Store instruments
    instruments = extracted_data.get('instruments', [])
    for inst in instruments:
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

    # Store ducts (as additional lines with special designation)
    ducts = extracted_data.get('ducts', [])
    for duct in ducts:
        cursor.execute("""
            INSERT INTO lines (sheet_id, line_number, size, spec_class, service, confidence)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            sheet_id,
            duct.get('tag'),
            duct.get('size'),
            'DUCT',
            duct.get('service', 'unknown'),
            duct.get('confidence', 0.7)
        ))

    conn.commit()

    return {
        'lines': len(lines),
        'equipment': len(equipment_items),
        'instruments': len(instruments),
        'ducts': len(ducts),
        'avg_confidence_lines': calculate_avg_confidence(lines),
        'avg_confidence_equipment': calculate_avg_confidence(equipment_items),
        'avg_confidence_instruments': calculate_avg_confidence(instruments)
    }

def update_sheet_status(conn, sheet_id, quality_score, complexity):
    """Update sheet metadata after extraction."""
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE sheets
        SET extracted_at = ?,
            extraction_model = ?,
            quality_score = ?,
            complexity = ?,
            drawing_type = ?
        WHERE id = ?
    """, (datetime.now().isoformat(), 'claude-sonnet-4-5-20250929', quality_score, complexity, 'plan', sheet_id))

    conn.commit()

def main():
    print("Refrigeration Plan Extraction Process")
    print("=" * 60)

    # Connect to database
    conn = sqlite3.connect(DATABASE_PATH)

    for sheet in SHEETS:
        sheet_id = sheet['id']
        sheet_path = sheet['path']
        sheet_name = Path(sheet_path).name

        print(f"\nProcessing Sheet {sheet_id}: {sheet_name}")
        print("-" * 60)

        try:
            # Convert PDF to images
            print("  Converting PDF to images...")
            images = pdf_to_images(sheet_path)
            print(f"  Converted {len(images)} page(s)")

            # Extract data from first page (assuming single-page drawings)
            print("  Extracting data with Claude API...")
            extracted_data = extract_with_claude(images[0], sheet)

            # Store in database
            print("  Storing extracted data in database...")
            stats = store_extractions(conn, sheet_id, extracted_data)

            # Calculate quality score
            metadata = extracted_data.get('metadata', {})
            complexity = metadata.get('complexity', 'medium')

            all_confidences = []
            for key in ['lines', 'equipment', 'instruments', 'ducts']:
                for item in extracted_data.get(key, []):
                    all_confidences.append(item.get('confidence', 0.7))

            quality_score = sum(all_confidences) / len(all_confidences) if all_confidences else 0.7

            # Update sheet status
            update_sheet_status(conn, sheet_id, quality_score, complexity)

            # Report results
            print(f"\n  Extraction Results:")
            print(f"  - Drawing Type: Refrigeration Plan View")
            print(f"  - Complexity: {complexity}")
            print(f"  - Lines: {stats['lines']} (avg confidence: {stats['avg_confidence_lines']:.2f})")
            print(f"  - Equipment: {stats['equipment']} (avg confidence: {stats['avg_confidence_equipment']:.2f})")
            print(f"  - Instruments: {stats['instruments']} (avg confidence: {stats['avg_confidence_instruments']:.2f})")
            print(f"  - Ducts: {stats['ducts']}")
            print(f"  - Quality Score: {quality_score:.2f}")

            # Report flagged items
            flagged = []
            for key in ['lines', 'equipment', 'instruments', 'ducts']:
                for item in extracted_data.get(key, []):
                    if item.get('confidence', 1.0) < 0.6:
                        item_id = item.get('line_number') or item.get('tag') or item.get('description', 'Unknown')
                        flagged.append(f"    - {item_id}: Low confidence ({item.get('confidence', 0):.2f})")

            if flagged:
                print(f"\n  Flagged for Review:")
                for flag in flagged:
                    print(flag)

            # Show metadata notes if any
            notes = metadata.get('notes', [])
            if notes:
                print(f"\n  Extraction Notes:")
                for note in notes:
                    print(f"    - {note}")

            print(f"\n  Status: COMPLETED")

        except Exception as e:
            print(f"  ERROR: {str(e)}")
            import traceback
            traceback.print_exc()

    conn.close()
    print("\n" + "=" * 60)
    print("Extraction process complete")

if __name__ == "__main__":
    main()
