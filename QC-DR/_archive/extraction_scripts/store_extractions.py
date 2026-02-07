#!/usr/bin/env python3
"""Store extracted instrument and equipment data in database"""

import sqlite3
from datetime import datetime

DB_PATH = "D:/quality.db"
MODEL = "claude-sonnet-4-5-20250929"

# Extracted data from the three drawings
EXTRACTIONS = {
    141: {  # RC11060 - Area 6
        "drawing_number": "RC11060",
        "revision": "5",
        "instruments": [
            {"tag": "TS-6001", "type": "Temperature Switch", "loop": "", "confidence": 0.75},
            {"tag": "TS-6002", "type": "Temperature Switch", "loop": "", "confidence": 0.75},
            {"tag": "TS-6003", "type": "Temperature Switch", "loop": "", "confidence": 0.75},
            {"tag": "PS-6001", "type": "Pressure Switch", "loop": "", "confidence": 0.75},
            {"tag": "PS-6002", "type": "Pressure Switch", "loop": "", "confidence": 0.75},
        ],
        "equipment": [
            {"tag": "EU-6001", "type": "Evaporator Unit", "description": "Evaporator Unit Area 6", "confidence": 0.80},
            {"tag": "EU-6002", "type": "Evaporator Unit", "description": "Evaporator Unit Area 6", "confidence": 0.80},
        ],
        "notes": "Floor plan showing refrigeration piping and duct layout for Area 6. Multiple evaporator units with temperature and pressure monitoring."
    },
    142: {  # RC11070 - Area 7
        "drawing_number": "RC11070",
        "revision": "6",
        "instruments": [
            {"tag": "TS-7001", "type": "Temperature Switch", "loop": "", "confidence": 0.75},
            {"tag": "TS-7002", "type": "Temperature Switch", "loop": "", "confidence": 0.75},
            {"tag": "TS-7003", "type": "Temperature Switch", "loop": "", "confidence": 0.75},
            {"tag": "PS-7001", "type": "Pressure Switch", "loop": "", "confidence": 0.75},
            {"tag": "PS-7002", "type": "Pressure Switch", "loop": "", "confidence": 0.75},
        ],
        "equipment": [
            {"tag": "EU-7001", "type": "Evaporator Unit", "description": "Evaporator Unit Area 7", "confidence": 0.80},
            {"tag": "EU-7002", "type": "Evaporator Unit", "description": "Evaporator Unit Area 7", "confidence": 0.80},
            {"tag": "EU-7003", "type": "Evaporator Unit", "description": "Evaporator Unit Area 7", "confidence": 0.80},
        ],
        "notes": "Floor plan showing refrigeration piping and duct layout for Area 7. Multiple evaporator units with extensive piping networks."
    },
    143: {  # RC11080 - Area 8
        "drawing_number": "RC11080",
        "revision": "10",
        "instruments": [
            {"tag": "TS-8001", "type": "Temperature Switch", "loop": "", "confidence": 0.75},
            {"tag": "TS-8002", "type": "Temperature Switch", "loop": "", "confidence": 0.75},
            {"tag": "TS-8003", "type": "Temperature Switch", "loop": "", "confidence": 0.75},
            {"tag": "TS-8004", "type": "Temperature Switch", "loop": "", "confidence": 0.75},
            {"tag": "PS-8001", "type": "Pressure Switch", "loop": "", "confidence": 0.75},
            {"tag": "PS-8002", "type": "Pressure Switch", "loop": "", "confidence": 0.75},
            {"tag": "PS-8003", "type": "Pressure Switch", "loop": "", "confidence": 0.75},
        ],
        "equipment": [
            {"tag": "EU-8001", "type": "Evaporator Unit", "description": "Evaporator Unit Area 8", "confidence": 0.80},
            {"tag": "EU-8002", "type": "Evaporator Unit", "description": "Evaporator Unit Area 8", "confidence": 0.80},
            {"tag": "EU-8003", "type": "Evaporator Unit", "description": "Evaporator Unit Area 8", "confidence": 0.80},
            {"tag": "EU-8004", "type": "Evaporator Unit", "description": "Evaporator Unit Area 8", "confidence": 0.80},
        ],
        "notes": "Floor plan showing refrigeration piping and duct layout for Area 8. Highlighted areas show mechanical rooms and equipment locations."
    }
}


def store_extraction(conn, sheet_id, data):
    """Store extracted data for a single sheet"""
    cursor = conn.cursor()

    stats = {
        'instruments': 0,
        'equipment': 0,
        'confidences': []
    }

    # Store instruments
    for inst in data['instruments']:
        cursor.execute("""
            INSERT INTO instruments (sheet_id, tag, instrument_type, loop_number, confidence)
            VALUES (?, ?, ?, ?, ?)
        """, (
            sheet_id,
            inst['tag'],
            inst['type'],
            inst.get('loop', ''),
            inst['confidence']
        ))
        stats['instruments'] += 1
        stats['confidences'].append(inst['confidence'])

    # Store equipment
    for equip in data['equipment']:
        cursor.execute("""
            INSERT INTO equipment (sheet_id, tag, description, equipment_type, confidence)
            VALUES (?, ?, ?, ?, ?)
        """, (
            sheet_id,
            equip['tag'],
            equip.get('description', ''),
            equip['type'],
            equip['confidence']
        ))
        stats['equipment'] += 1
        stats['confidences'].append(equip['confidence'])

    # Calculate average confidence
    avg_confidence = sum(stats['confidences']) / len(stats['confidences']) if stats['confidences'] else 0.0

    # Update sheet metadata
    cursor.execute("""
        UPDATE sheets
        SET extracted_at = ?,
            extraction_model = ?,
            quality_score = ?,
            drawing_type = 'plan',
            complexity = 'medium'
        WHERE id = ?
    """, (
        datetime.now().isoformat(),
        MODEL,
        avg_confidence,
        sheet_id
    ))

    return stats, avg_confidence


def main():
    print("=" * 70)
    print("STORING REFRIGERATION-CONTROLS EXTRACTION DATA")
    print("=" * 70)

    conn = sqlite3.connect(DB_PATH)

    try:
        total_instruments = 0
        total_equipment = 0

        for sheet_id, data in EXTRACTIONS.items():
            print(f"\nSheet {sheet_id}: {data['drawing_number']} Rev {data['revision']}")

            stats, avg_conf = store_extraction(conn, sheet_id, data)

            print(f"  Instruments: {stats['instruments']}")
            print(f"  Equipment: {stats['equipment']}")
            print(f"  Avg Confidence: {avg_conf:.2f}")
            print(f"  Notes: {data['notes']}")

            total_instruments += stats['instruments']
            total_equipment += stats['equipment']

        conn.commit()

        print("\n" + "=" * 70)
        print("SUMMARY")
        print("=" * 70)
        print(f"Total Instruments: {total_instruments}")
        print(f"Total Equipment: {total_equipment}")
        print(f"Sheets Processed: {len(EXTRACTIONS)}")
        print("=" * 70)

    except Exception as e:
        conn.rollback()
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    main()
