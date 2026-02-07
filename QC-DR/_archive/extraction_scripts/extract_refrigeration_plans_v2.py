"""
Extract data from refrigeration plan drawings and store in database.
This version creates extraction requests that can be processed by the Claude Code agent.
"""
import json
import sqlite3
from datetime import datetime
from pathlib import Path

# Configuration
DATABASE_PATH = "D:/quality.db"
SHEETS = [
    {"id": 7, "path": "D:/Projects/07308-BIRDCAGE/Refrigeration/R11040-REFRIGERATION-PLAN-PIPE-AND-DUCT-FLOOR-AREA-4-Rev.7.pdf"},
    {"id": 8, "path": "D:/Projects/07308-BIRDCAGE/Refrigeration/R11050-REFRIGERATION-PLAN-PIPE-AND-DUCT-FLOOR-AREA-5-Rev.7.pdf"},
    {"id": 9, "path": "D:/Projects/07308-BIRDCAGE/Refrigeration/R11060-REFRIGERATION-PLAN-PIPE-AND-DUCT-FLOOR-AREA-6-Rev.5.pdf"}
]

# Create extraction templates for manual processing
def create_extraction_templates():
    """Create JSON templates for each sheet to guide manual extraction."""

    templates_dir = Path("D:/extraction_templates")
    templates_dir.mkdir(exist_ok=True)

    for sheet in SHEETS:
        sheet_name = Path(sheet['path']).stem
        template = {
            "sheet_id": sheet['id'],
            "sheet_path": sheet['path'],
            "sheet_name": sheet_name,
            "drawing_type": "refrigeration_plan",
            "extraction_data": {
                "lines": [
                    {
                        "line_number": "Example: RL-101",
                        "size": "Example: 4 inch",
                        "service": "Example: suction, hot gas, liquid",
                        "material": "Example: copper, steel",
                        "from_location": "Example: EVAP-01",
                        "to_location": "Example: COMP-01",
                        "confidence": 0.85
                    }
                ],
                "equipment": [
                    {
                        "tag": "Example: COMP-01",
                        "equipment_type": "Example: compressor, evaporator, condenser",
                        "description": "Example: Screw compressor",
                        "location": "Example: Grid A-1",
                        "confidence": 0.90
                    }
                ],
                "instruments": [
                    {
                        "tag": "Example: PT-101",
                        "instrument_type": "Example: pressure_transmitter",
                        "loop_number": "101",
                        "confidence": 0.85
                    }
                ],
                "ducts": [
                    {
                        "tag": "Example: SA-01",
                        "size": "Example: 24x18",
                        "service": "Example: supply air, return air",
                        "confidence": 0.80
                    }
                ],
                "metadata": {
                    "floor_area": "Area 4/5/6",
                    "complexity": "medium",
                    "notes": []
                }
            }
        }

        template_path = templates_dir / f"{sheet_name}_template.json"
        with open(template_path, 'w') as f:
            json.dump(template, f, indent=2)

        print(f"Created template: {template_path}")

def store_extractions(conn, sheet_id, extracted_data):
    """Store extracted data in database."""
    cursor = conn.cursor()

    # Store lines
    lines = extracted_data.get('lines', [])
    for line in lines:
        # Skip example entries
        if isinstance(line.get('line_number'), str) and line.get('line_number').startswith('Example:'):
            continue

        cursor.execute("""
            INSERT INTO lines (sheet_id, line_number, size, material,
                             spec_class, from_location, to_location, service, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            sheet_id,
            line.get('line_number'),
            line.get('size'),
            line.get('material'),
            None,  # spec_class not used for refrigeration
            line.get('from_location'),
            line.get('to_location'),
            line.get('service'),
            line.get('confidence', 0.7)
        ))

    # Store equipment
    equipment_items = extracted_data.get('equipment', [])
    for equip in equipment_items:
        if isinstance(equip.get('tag'), str) and equip.get('tag').startswith('Example:'):
            continue

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
        if isinstance(inst.get('tag'), str) and inst.get('tag').startswith('Example:'):
            continue

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

    # Store ducts as special lines
    ducts = extracted_data.get('ducts', [])
    for duct in ducts:
        if isinstance(duct.get('tag'), str) and duct.get('tag').startswith('Example:'):
            continue

        cursor.execute("""
            INSERT INTO lines (sheet_id, line_number, size, spec_class, service, confidence)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            sheet_id,
            duct.get('tag'),
            duct.get('size'),
            'DUCT',
            duct.get('service'),
            duct.get('confidence', 0.7)
        ))

    conn.commit()

    # Calculate statistics
    return {
        'lines': len([l for l in lines if not (isinstance(l.get('line_number'), str) and l.get('line_number').startswith('Example:'))]),
        'equipment': len([e for e in equipment_items if not (isinstance(e.get('tag'), str) and e.get('tag').startswith('Example:'))]),
        'instruments': len([i for i in instruments if not (isinstance(i.get('tag'), str) and i.get('tag').startswith('Example:'))]),
        'ducts': len([d for d in ducts if not (isinstance(d.get('tag'), str) and d.get('tag').startswith('Example:'))])
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
    """, (
        datetime.now().isoformat(),
        'claude-sonnet-4-5-20250929',
        quality_score,
        complexity,
        'plan',
        sheet_id
    ))

    conn.commit()

def load_and_store_extraction(extraction_file):
    """Load extraction JSON and store in database."""
    with open(extraction_file, 'r') as f:
        extraction = json.load(f)

    conn = sqlite3.connect(DATABASE_PATH)

    sheet_id = extraction['sheet_id']
    sheet_name = extraction['sheet_name']
    extracted_data = extraction['extraction_data']

    print(f"\nStoring extraction for Sheet {sheet_id}: {sheet_name}")
    print("-" * 60)

    # Store data
    stats = store_extractions(conn, sheet_id, extracted_data)

    # Calculate quality score
    metadata = extracted_data.get('metadata', {})
    complexity = metadata.get('complexity', 'medium')

    all_confidences = []
    for key in ['lines', 'equipment', 'instruments', 'ducts']:
        for item in extracted_data.get(key, []):
            if isinstance(item.get('tag' if key != 'lines' else 'line_number'), str):
                if not item.get('tag' if key != 'lines' else 'line_number', '').startswith('Example:'):
                    all_confidences.append(item.get('confidence', 0.7))

    quality_score = sum(all_confidences) / len(all_confidences) if all_confidences else 0.7

    # Update sheet status
    update_sheet_status(conn, sheet_id, quality_score, complexity)

    print(f"  Lines: {stats['lines']}")
    print(f"  Equipment: {stats['equipment']}")
    print(f"  Instruments: {stats['instruments']}")
    print(f"  Ducts: {stats['ducts']}")
    print(f"  Quality Score: {quality_score:.2f}")
    print(f"  Status: COMPLETED")

    conn.close()

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "store":
        # Store mode: load extraction JSON and store in database
        if len(sys.argv) < 3:
            print("Usage: python extract_refrigeration_plans_v2.py store <extraction_file.json>")
            sys.exit(1)

        extraction_file = sys.argv[2]
        load_and_store_extraction(extraction_file)
    else:
        # Template mode: create extraction templates
        print("Creating extraction templates...")
        create_extraction_templates()
        print("\nTemplates created. These can be filled in manually or by the Claude Code agent.")
        print("To store completed extractions, run:")
        print("  python extract_refrigeration_plans_v2.py store <extraction_file.json>")
