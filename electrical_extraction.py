"""
Electrical drawing extraction script for Freshpet project sheets.
Extracts equipment, circuits, panels, and conduit data from electrical PDFs.
"""
import json
import sqlite3
from pathlib import Path
import fitz  # PyMuPDF

# Anthropic API for extraction
try:
    import anthropic
    client = anthropic.Anthropic()
except ImportError:
    print("ERROR: anthropic package required. Install with: pip install anthropic")
    exit(1)

DATABASE = r"D:\qms\data\quality.db"

SHEETS = [
    {
        "id": 523,
        "path": r"D:\qms\data\projects\07609-Freshpet\Electrical\EP1401-OVERALL-ROOF-POWER-PLAN-Rev.1.pdf",
        "drawing_number": "EP1401-OVERALL-ROOF-POWER-PLAN",
        "type": "Power Plan"
    },
    {
        "id": 524,
        "path": r"D:\qms\data\projects\07609-Freshpet\Electrical\EP1402-LIGHTNING-PROTECTION-SYSTEM-PLAN-Rev.1.pdf",
        "drawing_number": "EP1402-LIGHTNING-PROTECTION-SYSTEM-PLAN",
        "type": "Lightning Protection"
    },
    {
        "id": 525,
        "path": r"D:\qms\data\projects\07609-Freshpet\Electrical\EP4001-ELECTRICAL-ENLARGED-PLANS-Rev.1.pdf",
        "drawing_number": "EP4001-ELECTRICAL-ENLARGED-PLANS",
        "type": "Enlarged Plans"
    }
]

EXTRACTION_PROMPT_TEMPLATE = """Extract all electrical data from this {drawing_type} drawing.

Drawing Number: {drawing_number}
Sheet Type: {sheet_type}

TEXT FROM DRAWING:
{drawing_text}

Extract the following information and return as JSON:

1. **Equipment** - All electrical equipment tags with details
   Format: [{{"tag": "SA-AHU-029", "equipment_type": "AHU", "location": "grid_ref", "voltage": "480V", "amperage": "30A", "notes": ""}}]

2. **Circuits** - All circuit identifiers with panel references
   Format: [{{"panel_name": "P2-P13-5M3A", "circuit_number": "18", "equipment_tag": "SA-AHU-029", "wire_size": "#8", "conduit_size": "3/4\"", "notes": ""}}]

3. **Panels** - All electrical panels with ratings
   Format: [{{"panel_name": "P2-P13-5M3A", "location": "", "voltage": "480V", "phases": 3, "bus_rating": "100A", "fed_from": "", "notes": ""}}]

4. **Conduit** - Conduit runs with wire specifications
   Format: [{{"conduit_id": "P2-P13-5M3A/18", "conduit_size": "3/4\"", "wire_count": 3, "wire_size": "#8", "from_location": "", "to_location": "", "notes": "1-#8, 1-#8, 1-#8G"}}]

IMPORTANT PATTERNS:
- Equipment tags: SA-AHU-###, EF-FAN-###, CU-EC-###, CU-PUMP-###, etc.
- Panel/Circuit format: P2-G14-5M1A/6 means Panel P2-G14-5M1A, Circuit 6
- Wire specs: "1-#8, 1-#8, 1-#8G,3/4\"C" = three #8 wires (2 hot + 1 ground) in 3/4" conduit
- Breaker ratings: 30/2/3R = 30A, 2-pole, 3-wire circuit

Return ONLY valid JSON with these four arrays:
{{
  "equipment": [...],
  "circuits": [...],
  "panels": [...],
  "conduit": [...]
}}

If a field is unknown, use null or empty string. Be thorough but accurate."""

def extract_pdf_text(pdf_path: str) -> str:
    """Extract all text from PDF."""
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text()
    return text

def call_claude_sonnet(prompt: str) -> str:
    """Call Claude Sonnet for extraction."""
    response = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=8192,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text

def parse_json_response(response: str) -> dict:
    """Parse JSON from Claude response."""
    # Try to find JSON block
    if "```json" in response:
        start = response.find("```json") + 7
        end = response.find("```", start)
        json_str = response[start:end].strip()
    elif "```" in response:
        start = response.find("```") + 3
        end = response.find("```", start)
        json_str = response[start:end].strip()
    else:
        json_str = response.strip()

    return json.loads(json_str)

def insert_equipment(conn, sheet_id: int, items: list) -> int:
    """Insert equipment records."""
    count = 0
    for item in items:
        conn.execute("""
            INSERT INTO electrical_equipment
            (sheet_id, tag, equipment_type, location, area, voltage, amperage, notes, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            sheet_id,
            item.get("tag"),
            item.get("equipment_type"),
            item.get("location"),
            item.get("area"),
            item.get("voltage"),
            item.get("amperage"),
            item.get("notes"),
            0.85  # Sonnet extraction confidence
        ))
        count += 1
    return count

def insert_circuits(conn, sheet_id: int, items: list) -> int:
    """Insert circuit records."""
    count = 0
    for item in items:
        # Get or create panel
        panel_name = item.get("panel_name")
        if panel_name:
            panel_row = conn.execute(
                "SELECT id FROM electrical_panels WHERE sheet_id = ? AND panel_name = ?",
                (sheet_id, panel_name)
            ).fetchone()

            if panel_row:
                panel_id = panel_row[0]
            else:
                cursor = conn.execute("""
                    INSERT INTO electrical_panels (sheet_id, panel_name, confidence)
                    VALUES (?, ?, ?)
                """, (sheet_id, panel_name, 0.85))
                panel_id = cursor.lastrowid

            conn.execute("""
                INSERT INTO electrical_circuits
                (panel_id, sheet_id, circuit_number, circuit_description, equipment_tag,
                 location, wire_size, conduit_size, notes, confidence)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                panel_id,
                sheet_id,
                item.get("circuit_number"),
                item.get("description"),
                item.get("equipment_tag"),
                item.get("location"),
                item.get("wire_size"),
                item.get("conduit_size"),
                item.get("notes"),
                0.85
            ))
            count += 1
    return count

def insert_panels(conn, sheet_id: int, items: list) -> int:
    """Insert panel records."""
    count = 0
    for item in items:
        # Check if already exists
        existing = conn.execute(
            "SELECT id FROM electrical_panels WHERE sheet_id = ? AND panel_name = ?",
            (sheet_id, item.get("panel_name"))
        ).fetchone()

        if existing:
            # Update existing
            conn.execute("""
                UPDATE electrical_panels
                SET location = ?, voltage = ?, phases = ?, bus_rating = ?,
                    fed_from = ?, panel_notes = ?, confidence = ?
                WHERE id = ?
            """, (
                item.get("location"),
                item.get("voltage"),
                item.get("phases"),
                item.get("bus_rating"),
                item.get("fed_from"),
                item.get("notes"),
                0.85,
                existing[0]
            ))
        else:
            # Insert new
            conn.execute("""
                INSERT INTO electrical_panels
                (sheet_id, panel_name, location, voltage, phases, bus_rating,
                 fed_from, panel_notes, confidence)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                sheet_id,
                item.get("panel_name"),
                item.get("location"),
                item.get("voltage"),
                item.get("phases"),
                item.get("bus_rating"),
                item.get("fed_from"),
                item.get("notes"),
                0.85
            ))
            count += 1
    return count

def insert_conduit(conn, sheet_id: int, items: list) -> int:
    """Insert conduit records."""
    count = 0
    for item in items:
        conn.execute("""
            INSERT INTO electrical_conduit
            (sheet_id, conduit_id, conduit_size, wire_count, wire_size,
             from_location, to_location, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            sheet_id,
            item.get("conduit_id"),
            item.get("conduit_size"),
            item.get("wire_count"),
            item.get("wire_size"),
            item.get("from_location"),
            item.get("to_location"),
            item.get("notes")
        ))
        count += 1
    return count

def process_sheet(sheet_info: dict):
    """Process a single sheet."""
    print(f"\n{'=' * 80}")
    print(f"Processing: {sheet_info['drawing_number']}")
    print(f"Sheet ID: {sheet_info['id']}")
    print(f"Type: {sheet_info['type']}")
    print(f"{'=' * 80}\n")

    # Extract text
    print("Step 1: Extracting text from PDF...")
    text = extract_pdf_text(sheet_info['path'])
    print(f"  Extracted {len(text)} characters")

    # Build prompt
    print("\nStep 2: Building extraction prompt...")
    prompt = EXTRACTION_PROMPT_TEMPLATE.format(
        drawing_type=sheet_info['type'],
        drawing_number=sheet_info['drawing_number'],
        sheet_type=sheet_info['type'],
        drawing_text=text
    )

    # Call Claude
    print("Step 3: Calling Claude Sonnet for extraction...")
    response = call_claude_sonnet(prompt)

    # Parse response
    print("Step 4: Parsing JSON response...")
    try:
        data = parse_json_response(response)
    except json.JSONDecodeError as e:
        print(f"  ERROR: Failed to parse JSON: {e}")
        print(f"  Response preview: {response[:500]}")
        return

    # Validate structure
    equipment = data.get("equipment", [])
    circuits = data.get("circuits", [])
    panels = data.get("panels", [])
    conduit = data.get("conduit", [])

    print(f"\nExtracted:")
    print(f"  Equipment: {len(equipment)} items")
    print(f"  Circuits: {len(circuits)} items")
    print(f"  Panels: {len(panels)} items")
    print(f"  Conduit: {len(conduit)} items")

    # Insert into database
    print("\nStep 5: Inserting into database...")
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row

    try:
        eq_count = insert_equipment(conn, sheet_info['id'], equipment)
        print(f"  Inserted {eq_count} equipment records")

        panel_count = insert_panels(conn, sheet_info['id'], panels)
        print(f"  Inserted {panel_count} panel records")

        circuit_count = insert_circuits(conn, sheet_info['id'], circuits)
        print(f"  Inserted {circuit_count} circuit records")

        cond_count = insert_conduit(conn, sheet_info['id'], conduit)
        print(f"  Inserted {cond_count} conduit records")

        # Update sheet extraction status
        conn.execute("""
            UPDATE sheets
            SET extracted_at = CURRENT_TIMESTAMP,
                extraction_model = 'sonnet-4.5',
                quality_score = 0.85
            WHERE id = ?
        """, (sheet_info['id'],))

        conn.commit()
        print("\n  Database commit successful!")

    except Exception as e:
        conn.rollback()
        print(f"\n  ERROR during database insert: {e}")
        raise
    finally:
        conn.close()

    print(f"\n{'=' * 80}")
    print(f"Completed: {sheet_info['drawing_number']}")
    print(f"{'=' * 80}\n")

def main():
    print("Electrical Drawing Extraction")
    print("Project: 07609-Freshpet")
    print(f"Sheets to process: {len(SHEETS)}")
    print(f"Database: {DATABASE}")

    for i, sheet in enumerate(SHEETS, 1):
        print(f"\n\n[{i}/{len(SHEETS)}] Processing {sheet['drawing_number']}...")
        try:
            process_sheet(sheet)
        except Exception as e:
            print(f"\nFATAL ERROR processing {sheet['drawing_number']}: {e}")
            import traceback
            traceback.print_exc()
            continue

    print("\n\n" + "=" * 80)
    print("EXTRACTION COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    main()
