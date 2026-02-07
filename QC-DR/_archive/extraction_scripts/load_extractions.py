"""
Load extracted refrigeration data into quality.db database.
"""
import json
import sqlite3
from datetime import datetime

DATABASE_PATH = "D:/quality.db"
EXTRACTION_FILES = [
    "D:/extracted_data_sheet7.json",
    "D:/extracted_data_sheet8.json",
    "D:/extracted_data_sheet9.json"
]

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
            None,  # spec_class not used for refrigeration
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

    # Store ducts as special lines
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
            duct.get('service'),
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
        'avg_confidence_instruments': calculate_avg_confidence(instruments),
        'avg_confidence_ducts': calculate_avg_confidence(ducts)
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

def main():
    print("Loading Refrigeration Plan Extractions")
    print("=" * 70)

    conn = sqlite3.connect(DATABASE_PATH)

    for extraction_file in EXTRACTION_FILES:
        try:
            # Load extraction JSON
            with open(extraction_file, 'r') as f:
                extraction = json.load(f)

            sheet_id = extraction['sheet_id']
            sheet_name = extraction['sheet_name']
            extracted_data = extraction['extraction_data']

            print(f"\nProcessing Sheet {sheet_id}: {sheet_name}")
            print("-" * 70)

            # Store data
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
            print(f"  - Ducts: {stats['ducts']} (avg confidence: {stats['avg_confidence_ducts']:.2f})")
            print(f"  - Overall Quality Score: {quality_score:.2f}")

            # Report flagged items (low confidence < 0.6)
            flagged = []
            for key in ['lines', 'equipment', 'instruments', 'ducts']:
                for item in extracted_data.get(key, []):
                    if item.get('confidence', 1.0) < 0.6:
                        item_id = item.get('line_number') or item.get('tag') or 'Unknown'
                        flagged.append(f"    - {item_id}: Low confidence ({item.get('confidence', 0):.2f})")

            if flagged:
                print(f"\n  Flagged for Review:")
                for flag in flagged:
                    print(flag)
            else:
                print(f"\n  No items flagged for review (all confidence >= 0.6)")

            # Show notes
            notes = metadata.get('notes', [])
            if notes:
                print(f"\n  Extraction Notes:")
                for note in notes:
                    print(f"    - {note}")

            print(f"\n  Status: COMPLETED")

        except Exception as e:
            print(f"\n  ERROR processing {extraction_file}: {str(e)}")
            import traceback
            traceback.print_exc()

    conn.close()
    print("\n" + "=" * 70)
    print("Extraction loading complete")
    print("\nSummary stored in database at: D:/quality.db")

if __name__ == "__main__":
    main()
