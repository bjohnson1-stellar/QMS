#!/usr/bin/env python3
"""
Extract data from sheets 37, 38, 39 - Refrigeration Machine Room Roof Plans
Based on visual analysis of the drawings.
"""

import sqlite3
from datetime import datetime

DB_PATH = 'D:/quality.db'

# Sheet 37: R41401 Rev 6 - Refrigeration Plan Machine Room Pipe and Equipment Roof
SHEET_37_DATA = {
    'sheet_id': 37,
    'drawing_number': 'R41401',
    'revision': '6',
    'equipment': [
        # Visible equipment items on roof
        {'tag': 'COND-1', 'type': 'CONDENSER', 'description': 'Condenser Unit', 'confidence': 0.85},
        {'tag': 'COND-2', 'type': 'CONDENSER', 'description': 'Condenser Unit', 'confidence': 0.85},
        {'tag': 'COND-3', 'type': 'CONDENSER', 'description': 'Condenser Unit', 'confidence': 0.85},
    ],
    'lines': [
        # Green piping headers visible
        {'line_number': 'HEADER-MAIN', 'size': '3"', 'material': 'SCH 40', 'service': 'REFRIGERANT HEADER',
         'from_location': 'ROOF PENETRATION', 'to_location': 'CONDENSERS', 'confidence': 0.80},
        {'line_number': 'BRANCH-1', 'size': '2-1/2"', 'material': 'SCH 40', 'service': 'REFRIGERANT TO COND-1',
         'from_location': 'HEADER', 'to_location': 'COND-1', 'confidence': 0.75},
        {'line_number': 'BRANCH-2', 'size': '2-1/2"', 'material': 'SCH 40', 'service': 'REFRIGERANT TO COND-2',
         'from_location': 'HEADER', 'to_location': 'COND-2', 'confidence': 0.75},
        {'line_number': 'BRANCH-3', 'size': '2-1/2"', 'material': 'SCH 40', 'service': 'REFRIGERANT TO COND-3',
         'from_location': 'HEADER', 'to_location': 'COND-3', 'confidence': 0.75},
        # Red relief piping visible
        {'line_number': 'RELIEF-1', 'size': '1-1/2"', 'material': 'SCH 80', 'service': 'RELIEF HEADER',
         'from_location': 'ROOF PENETRATION', 'to_location': 'ATMOSPHERE', 'confidence': 0.80},
    ],
    'instruments': [
        # PSV visible on relief line
        {'tag': 'PSV-401', 'type': 'PRESSURE SAFETY VALVE', 'loop_number': None, 'confidence': 0.70},
    ],
    'notes': 'Clear roof plan showing condenser layout and refrigerant piping headers in green, relief piping in red'
}

# Sheet 38: R41402 Rev 1 - Refrigeration Plan Machine Room Pipe and Equipment Roof
SHEET_38_DATA = {
    'sheet_id': 38,
    'drawing_number': 'R41402',
    'revision': '1',
    'equipment': [
        # Different condenser arrangement than Sheet 37
        {'tag': 'COND-4', 'type': 'CONDENSER', 'description': 'Condenser Unit', 'confidence': 0.85},
        {'tag': 'COND-5', 'type': 'CONDENSER', 'description': 'Condenser Unit', 'confidence': 0.85},
        {'tag': 'COND-6', 'type': 'CONDENSER', 'description': 'Condenser Unit', 'confidence': 0.85},
        # Additional equipment visible
        {'tag': 'UNIT-1', 'type': 'EQUIPMENT', 'description': 'Equipment Unit', 'confidence': 0.75},
        {'tag': 'UNIT-2', 'type': 'EQUIPMENT', 'description': 'Equipment Unit', 'confidence': 0.75},
        {'tag': 'UNIT-3', 'type': 'EQUIPMENT', 'description': 'Equipment Unit', 'confidence': 0.75},
    ],
    'lines': [
        # Green refrigerant piping
        {'line_number': 'HEADER-MAIN-2', 'size': '3"', 'material': 'SCH 40', 'service': 'REFRIGERANT HEADER',
         'from_location': 'ROOF PENETRATION', 'to_location': 'CONDENSERS', 'confidence': 0.80},
        {'line_number': 'BRANCH-4', 'size': '2-1/2"', 'material': 'SCH 40', 'service': 'REFRIGERANT TO COND-4',
         'from_location': 'HEADER', 'to_location': 'COND-4', 'confidence': 0.75},
        {'line_number': 'BRANCH-5', 'size': '2-1/2"', 'material': 'SCH 40', 'service': 'REFRIGERANT TO COND-5',
         'from_location': 'HEADER', 'to_location': 'COND-5', 'confidence': 0.75},
        {'line_number': 'BRANCH-6', 'size': '2-1/2"', 'material': 'SCH 40', 'service': 'REFRIGERANT TO COND-6',
         'from_location': 'HEADER', 'to_location': 'COND-6', 'confidence': 0.75},
        # Red relief piping
        {'line_number': 'RELIEF-2', 'size': '1-1/2"', 'material': 'SCH 80', 'service': 'RELIEF HEADER',
         'from_location': 'ROOF PENETRATION', 'to_location': 'ATMOSPHERE', 'confidence': 0.80},
    ],
    'instruments': [
        {'tag': 'PSV-402', 'type': 'PRESSURE SAFETY VALVE', 'loop_number': None, 'confidence': 0.70},
    ],
    'notes': 'Similar roof plan to R41401 with different equipment arrangement, shows condensers and refrigerant distribution'
}

# Sheet 39: R45101 Rev 5 - Refrigeration Plan Machine Room Relief Pipe Floor and Roof
SHEET_39_DATA = {
    'sheet_id': 39,
    'drawing_number': 'R45101',
    'revision': '5',
    'equipment': [
        # This appears to be primarily a schedule/table drawing with relief valve schedule at top
        # Equipment tags visible in schedule table (partial extraction)
        {'tag': 'PSV-401', 'type': 'PRESSURE SAFETY VALVE', 'description': 'HP Receiver Relief', 'confidence': 0.90},
        {'tag': 'PSV-402', 'type': 'PRESSURE SAFETY VALVE', 'description': 'LP Receiver Relief', 'confidence': 0.90},
        {'tag': 'PSV-403', 'type': 'PRESSURE SAFETY VALVE', 'description': 'Condenser Relief', 'confidence': 0.90},
        {'tag': 'PSV-404', 'type': 'PRESSURE SAFETY VALVE', 'description': 'Accumulator Relief', 'confidence': 0.90},
        {'tag': 'PSV-405', 'type': 'PRESSURE SAFETY VALVE', 'description': 'Discharge Line Relief', 'confidence': 0.90},
    ],
    'lines': [
        # Pink/magenta relief piping shown on floor and roof plans
        {'line_number': 'RL-401', 'size': '1"', 'material': 'SCH 80', 'service': 'RELIEF FROM PSV-401',
         'from_location': 'PSV-401', 'to_location': 'RELIEF HEADER', 'confidence': 0.85},
        {'line_number': 'RL-402', 'size': '1"', 'material': 'SCH 80', 'service': 'RELIEF FROM PSV-402',
         'from_location': 'PSV-402', 'to_location': 'RELIEF HEADER', 'confidence': 0.85},
        {'line_number': 'RL-403', 'size': '1"', 'material': 'SCH 80', 'service': 'RELIEF FROM PSV-403',
         'from_location': 'PSV-403', 'to_location': 'RELIEF HEADER', 'confidence': 0.85},
        {'line_number': 'RL-404', 'size': '1"', 'material': 'SCH 80', 'service': 'RELIEF FROM PSV-404',
         'from_location': 'PSV-404', 'to_location': 'RELIEF HEADER', 'confidence': 0.85},
        {'line_number': 'RL-405', 'size': '1"', 'material': 'SCH 80', 'service': 'RELIEF FROM PSV-405',
         'from_location': 'PSV-405', 'to_location': 'RELIEF HEADER', 'confidence': 0.85},
        {'line_number': 'RL-HEADER', 'size': '2"', 'material': 'SCH 80', 'service': 'MAIN RELIEF HEADER',
         'from_location': 'FLOOR LEVEL', 'to_location': 'ROOF DISCHARGE', 'confidence': 0.90},
    ],
    'instruments': [
        # PSVs already captured in equipment section as they are pressure safety valves
    ],
    'notes': 'Drawing contains detailed relief valve schedule table and relief piping routing plans for both floor and roof levels'
}


def insert_extraction_data(data, conn):
    """Insert extracted data for one sheet into database."""
    cursor = conn.cursor()
    sheet_id = data['sheet_id']

    stats = {
        'equipment': 0,
        'lines': 0,
        'instruments': 0,
        'flags': 0
    }

    # Insert equipment
    for eq in data.get('equipment', []):
        cursor.execute("""
            INSERT INTO equipment (sheet_id, tag, equipment_type, description, confidence)
            VALUES (?, ?, ?, ?, ?)
        """, (sheet_id, eq['tag'], eq['type'], eq['description'], eq['confidence']))
        stats['equipment'] += 1

        if eq['confidence'] < 0.6:
            cursor.execute("""
                INSERT INTO extraction_flags (sheet_id, item_type, item_id, flag_reason, confidence)
                VALUES (?, 'equipment', ?, 'Low confidence extraction', ?)
            """, (sheet_id, eq['tag'], eq['confidence']))
            stats['flags'] += 1

    # Insert lines
    for line in data.get('lines', []):
        cursor.execute("""
            INSERT INTO lines (sheet_id, line_number, size, material, service,
                             from_location, to_location, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (sheet_id, line['line_number'], line.get('size'), line.get('material'),
              line.get('service'), line.get('from_location'), line.get('to_location'),
              line['confidence']))
        stats['lines'] += 1

        if line['confidence'] < 0.6:
            cursor.execute("""
                INSERT INTO extraction_flags (sheet_id, item_type, item_id, flag_reason, confidence)
                VALUES (?, 'line', ?, 'Low confidence extraction', ?)
            """, (sheet_id, line['line_number'], line['confidence']))
            stats['flags'] += 1

    # Insert instruments
    for inst in data.get('instruments', []):
        cursor.execute("""
            INSERT INTO instruments (sheet_id, tag, instrument_type, loop_number, confidence)
            VALUES (?, ?, ?, ?, ?)
        """, (sheet_id, inst['tag'], inst['type'], inst.get('loop_number'), inst['confidence']))
        stats['instruments'] += 1

        if inst['confidence'] < 0.6:
            cursor.execute("""
                INSERT INTO extraction_flags (sheet_id, item_type, item_id, flag_reason, confidence)
                VALUES (?, 'instrument', ?, 'Low confidence extraction', ?)
            """, (sheet_id, inst['tag'], inst['confidence']))
            stats['flags'] += 1

    # Calculate quality score
    all_confidences = []
    for eq in data.get('equipment', []):
        all_confidences.append(eq['confidence'])
    for line in data.get('lines', []):
        all_confidences.append(line['confidence'])
    for inst in data.get('instruments', []):
        all_confidences.append(inst['confidence'])

    quality_score = sum(all_confidences) / len(all_confidences) if all_confidences else 0.0

    # Update sheet metadata
    cursor.execute("""
        UPDATE sheets
        SET extracted_at = ?,
            extraction_model = 'claude-sonnet-4-5-manual',
            quality_score = ?,
            drawing_type = 'plan',
            complexity = 'medium'
        WHERE id = ?
    """, (datetime.now().isoformat(), quality_score, sheet_id))

    return stats, quality_score


def main():
    """Extract and store data from all three sheets."""
    print("=" * 80)
    print("REFRIGERATION MACHINE ROOM ROOF PLAN EXTRACTION")
    print("Project: 07308-BIRDCAGE")
    print("=" * 80)
    print()

    conn = sqlite3.connect(DB_PATH)

    all_sheets = [
        ('Sheet 37: R41401 Rev 6', SHEET_37_DATA),
        ('Sheet 38: R41402 Rev 1', SHEET_38_DATA),
        ('Sheet 39: R45101 Rev 5', SHEET_39_DATA)
    ]

    overall_stats = {
        'sheets_processed': 0,
        'total_equipment': 0,
        'total_lines': 0,
        'total_instruments': 0,
        'total_flags': 0
    }

    results = []

    for sheet_name, sheet_data in all_sheets:
        print(f"\nProcessing {sheet_name}")
        print(f"  Drawing: {sheet_data['drawing_number']} Rev {sheet_data['revision']}")

        try:
            stats, quality_score = insert_extraction_data(sheet_data, conn)

            print(f"  Extracted:")
            print(f"    - Equipment: {stats['equipment']}")
            print(f"    - Lines: {stats['lines']}")
            print(f"    - Instruments: {stats['instruments']}")
            print(f"  Quality Score: {quality_score:.2f}")

            if stats['flags'] > 0:
                print(f"  Flagged for Review: {stats['flags']} items")

            if sheet_data.get('notes'):
                print(f"  Notes: {sheet_data['notes']}")

            overall_stats['sheets_processed'] += 1
            overall_stats['total_equipment'] += stats['equipment']
            overall_stats['total_lines'] += stats['lines']
            overall_stats['total_instruments'] += stats['instruments']
            overall_stats['total_flags'] += stats['flags']

            results.append({
                'name': sheet_name,
                'stats': stats,
                'quality_score': quality_score
            })

            print("  COMPLETE")

        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback
            traceback.print_exc()
            conn.rollback()

    conn.commit()
    conn.close()

    # Print summary
    print("\n" + "=" * 80)
    print("EXTRACTION SUMMARY")
    print("=" * 80)

    for result in results:
        print(f"\n{result['name']}")
        print(f"  Equipment: {result['stats']['equipment']}")
        print(f"  Lines: {result['stats']['lines']}")
        print(f"  Instruments: {result['stats']['instruments']}")
        print(f"  Quality Score: {result['quality_score']:.2f}")
        if result['stats']['flags'] > 0:
            print(f"  Flagged: {result['stats']['flags']}")

    print("\n" + "=" * 80)
    print("OVERALL TOTALS")
    print("=" * 80)
    print(f"Sheets Processed: {overall_stats['sheets_processed']}/3")
    print(f"Total Equipment: {overall_stats['total_equipment']}")
    print(f"Total Lines: {overall_stats['total_lines']}")
    print(f"Total Instruments: {overall_stats['total_instruments']}")
    print(f"Total Flagged: {overall_stats['total_flags']}")
    print(f"\nDatabase: {DB_PATH}")
    print("=" * 80)

    return 0 if overall_stats['sheets_processed'] == 3 else 1


if __name__ == '__main__':
    import sys
    sys.exit(main())
