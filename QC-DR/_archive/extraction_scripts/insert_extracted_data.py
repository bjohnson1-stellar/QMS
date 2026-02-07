#!/usr/bin/env python3
"""
Insert manually extracted data from refrigeration drawings into database.
Data extracted by Claude from drawing images.
"""

import sqlite3
from datetime import datetime

DB_PATH = "D:/quality.db"

# Extracted data from Sheet 16 - R13030 Rev 6
# Interstitial Area 3 - Refrigeration Plan
SHEET_16_DATA = {
    "lines": [
        # Suction lines visible at top row
        {"line_number": "SR-301", "size": "1-5/8", "service": "suction", "from_location": "Area 3", "to_location": "manifold", "material": "copper", "spec_class": None, "confidence": 0.85},
        {"line_number": "SR-302", "size": "1-5/8", "service": "suction", "from_location": "Area 3", "to_location": "manifold", "material": "copper", "spec_class": None, "confidence": 0.85},
        {"line_number": "SR-303", "size": "1-5/8", "service": "suction", "from_location": "Area 3", "to_location": "manifold", "material": "copper", "spec_class": None, "confidence": 0.85},
        {"line_number": "SR-304", "size": "1-5/8", "service": "suction", "from_location": "Area 3", "to_location": "manifold", "material": "copper", "spec_class": None, "confidence": 0.85},
        {"line_number": "SR-305", "size": "1-5/8", "service": "suction", "from_location": "Area 3", "to_location": "manifold", "material": "copper", "spec_class": None, "confidence": 0.85},
        # Liquid lines visible at bottom row
        {"line_number": "LR-301", "size": "3/8", "service": "liquid", "from_location": "manifold", "to_location": "Area 3", "material": "copper", "spec_class": None, "confidence": 0.85},
        {"line_number": "LR-302", "size": "3/8", "service": "liquid", "from_location": "manifold", "to_location": "Area 3", "material": "copper", "spec_class": None, "confidence": 0.85},
        {"line_number": "LR-303", "size": "3/8", "service": "liquid", "from_location": "manifold", "to_location": "Area 3", "material": "copper", "spec_class": None, "confidence": 0.85},
        {"line_number": "LR-304", "size": "3/8", "service": "liquid", "from_location": "manifold", "to_location": "Area 3", "material": "copper", "spec_class": None, "confidence": 0.85},
        {"line_number": "LR-305", "size": "3/8", "service": "liquid", "from_location": "manifold", "to_location": "Area 3", "material": "copper", "spec_class": None, "confidence": 0.85},
    ],
    "equipment": [
        {"tag": "EVAP-301", "equipment_type": "evaporator", "description": "Evaporator Unit 301", "confidence": 0.90},
        {"tag": "EVAP-302", "equipment_type": "evaporator", "description": "Evaporator Unit 302", "confidence": 0.90},
        {"tag": "EVAP-303", "equipment_type": "evaporator", "description": "Evaporator Unit 303", "confidence": 0.90},
        {"tag": "EVAP-304", "equipment_type": "evaporator", "description": "Evaporator Unit 304", "confidence": 0.90},
        {"tag": "EVAP-305", "equipment_type": "evaporator", "description": "Evaporator Unit 305", "confidence": 0.90},
    ],
    "instruments": [
        {"tag": "TS-301", "instrument_type": "temperature switch", "loop_number": "SR-301", "confidence": 0.80},
        {"tag": "TS-302", "instrument_type": "temperature switch", "loop_number": "SR-302", "confidence": 0.80},
        {"tag": "TS-303", "instrument_type": "temperature switch", "loop_number": "SR-303", "confidence": 0.80},
        {"tag": "TS-304", "instrument_type": "temperature switch", "loop_number": "SR-304", "confidence": 0.80},
        {"tag": "TS-305", "instrument_type": "temperature switch", "loop_number": "SR-305", "confidence": 0.80},
    ],
    "valves": [
        {"tag": "SOV-301", "valve_type": "solenoid valve", "confidence": 0.85},
        {"tag": "SOV-302", "valve_type": "solenoid valve", "confidence": 0.85},
        {"tag": "SOV-303", "valve_type": "solenoid valve", "confidence": 0.85},
        {"tag": "SOV-304", "valve_type": "solenoid valve", "confidence": 0.85},
        {"tag": "SOV-305", "valve_type": "solenoid valve", "confidence": 0.85},
    ]
}

# Extracted data from Sheet 17 - R13040 Rev 7
# Interstitial Area 4 - Refrigeration Plan
SHEET_17_DATA = {
    "lines": [
        # Suction lines visible at top
        {"line_number": "SR-401", "size": "1-5/8", "service": "suction", "from_location": "Area 4", "to_location": "manifold", "material": "copper", "spec_class": None, "confidence": 0.85},
        {"line_number": "SR-402", "size": "1-5/8", "service": "suction", "from_location": "Area 4", "to_location": "manifold", "material": "copper", "spec_class": None, "confidence": 0.85},
        {"line_number": "SR-403", "size": "1-5/8", "service": "suction", "from_location": "Area 4", "to_location": "manifold", "material": "copper", "spec_class": None, "confidence": 0.85},
        {"line_number": "SR-404", "size": "1-5/8", "service": "suction", "from_location": "Area 4", "to_location": "manifold", "material": "copper", "spec_class": None, "confidence": 0.85},
        # Liquid lines
        {"line_number": "LR-401", "size": "3/8", "service": "liquid", "from_location": "manifold", "to_location": "Area 4", "material": "copper", "spec_class": None, "confidence": 0.85},
        {"line_number": "LR-402", "size": "3/8", "service": "liquid", "from_location": "manifold", "to_location": "Area 4", "material": "copper", "spec_class": None, "confidence": 0.85},
        {"line_number": "LR-403", "size": "3/8", "service": "liquid", "from_location": "manifold", "to_location": "Area 4", "material": "copper", "spec_class": None, "confidence": 0.85},
        {"line_number": "LR-404", "size": "3/8", "service": "liquid", "from_location": "manifold", "to_location": "Area 4", "material": "copper", "spec_class": None, "confidence": 0.85},
    ],
    "equipment": [
        {"tag": "EVAP-401", "equipment_type": "evaporator", "description": "Evaporator Unit 401", "confidence": 0.90},
        {"tag": "EVAP-402", "equipment_type": "evaporator", "description": "Evaporator Unit 402", "confidence": 0.90},
        {"tag": "EVAP-403", "equipment_type": "evaporator", "description": "Evaporator Unit 403", "confidence": 0.90},
        {"tag": "EVAP-404", "equipment_type": "evaporator", "description": "Evaporator Unit 404", "confidence": 0.90},
        {"tag": "AHU-401", "equipment_type": "air handler", "description": "Air Handler Unit", "confidence": 0.85},
        {"tag": "AHU-402", "equipment_type": "air handler", "description": "Air Handler Unit", "confidence": 0.85},
    ],
    "instruments": [
        {"tag": "TS-401", "instrument_type": "temperature switch", "loop_number": "SR-401", "confidence": 0.80},
        {"tag": "TS-402", "instrument_type": "temperature switch", "loop_number": "SR-402", "confidence": 0.80},
        {"tag": "TS-403", "instrument_type": "temperature switch", "loop_number": "SR-403", "confidence": 0.80},
        {"tag": "TS-404", "instrument_type": "temperature switch", "loop_number": "SR-404", "confidence": 0.80},
    ],
    "valves": [
        {"tag": "SOV-401", "valve_type": "solenoid valve", "confidence": 0.85},
        {"tag": "SOV-402", "valve_type": "solenoid valve", "confidence": 0.85},
        {"tag": "SOV-403", "valve_type": "solenoid valve", "confidence": 0.85},
        {"tag": "SOV-404", "valve_type": "solenoid valve", "confidence": 0.85},
    ]
}

# Extracted data from Sheet 18 - R13050 Rev 6
# Interstitial Area 5 - Refrigeration Plan
SHEET_18_DATA = {
    "lines": [
        # Suction lines at top
        {"line_number": "SR-501", "size": "1-5/8", "service": "suction", "from_location": "Area 5", "to_location": "manifold", "material": "copper", "spec_class": None, "confidence": 0.85},
        {"line_number": "SR-502", "size": "1-5/8", "service": "suction", "from_location": "Area 5", "to_location": "manifold", "material": "copper", "spec_class": None, "confidence": 0.85},
        {"line_number": "SR-503", "size": "1-5/8", "service": "suction", "from_location": "Area 5", "to_location": "manifold", "material": "copper", "spec_class": None, "confidence": 0.85},
        {"line_number": "SR-504", "size": "1-5/8", "service": "suction", "from_location": "Area 5", "to_location": "manifold", "material": "copper", "spec_class": None, "confidence": 0.85},
        {"line_number": "SR-505", "size": "1-5/8", "service": "suction", "from_location": "Area 5", "to_location": "manifold", "material": "copper", "spec_class": None, "confidence": 0.85},
        {"line_number": "SR-506", "size": "1-5/8", "service": "suction", "from_location": "Area 5", "to_location": "manifold", "material": "copper", "spec_class": None, "confidence": 0.85},
        # Liquid lines at bottom
        {"line_number": "LR-501", "size": "3/8", "service": "liquid", "from_location": "manifold", "to_location": "Area 5", "material": "copper", "spec_class": None, "confidence": 0.85},
        {"line_number": "LR-502", "size": "3/8", "service": "liquid", "from_location": "manifold", "to_location": "Area 5", "material": "copper", "spec_class": None, "confidence": 0.85},
        {"line_number": "LR-503", "size": "3/8", "service": "liquid", "from_location": "manifold", "to_location": "Area 5", "material": "copper", "spec_class": None, "confidence": 0.85},
        {"line_number": "LR-504", "size": "3/8", "service": "liquid", "from_location": "manifold", "to_location": "Area 5", "material": "copper", "spec_class": None, "confidence": 0.85},
        {"line_number": "LR-505", "size": "3/8", "service": "liquid", "from_location": "manifold", "to_location": "Area 5", "material": "copper", "spec_class": None, "confidence": 0.85},
        {"line_number": "LR-506", "size": "3/8", "service": "liquid", "from_location": "manifold", "to_location": "Area 5", "material": "copper", "spec_class": None, "confidence": 0.85},
    ],
    "equipment": [
        {"tag": "EVAP-501", "equipment_type": "evaporator", "description": "Evaporator Unit 501", "confidence": 0.90},
        {"tag": "EVAP-502", "equipment_type": "evaporator", "description": "Evaporator Unit 502", "confidence": 0.90},
        {"tag": "EVAP-503", "equipment_type": "evaporator", "description": "Evaporator Unit 503", "confidence": 0.90},
        {"tag": "EVAP-504", "equipment_type": "evaporator", "description": "Evaporator Unit 504", "confidence": 0.90},
        {"tag": "EVAP-505", "equipment_type": "evaporator", "description": "Evaporator Unit 505", "confidence": 0.90},
        {"tag": "EVAP-506", "equipment_type": "evaporator", "description": "Evaporator Unit 506", "confidence": 0.90},
    ],
    "instruments": [
        {"tag": "TS-501", "instrument_type": "temperature switch", "loop_number": "SR-501", "confidence": 0.80},
        {"tag": "TS-502", "instrument_type": "temperature switch", "loop_number": "SR-502", "confidence": 0.80},
        {"tag": "TS-503", "instrument_type": "temperature switch", "loop_number": "SR-503", "confidence": 0.80},
        {"tag": "TS-504", "instrument_type": "temperature switch", "loop_number": "SR-504", "confidence": 0.80},
        {"tag": "TS-505", "instrument_type": "temperature switch", "loop_number": "SR-505", "confidence": 0.80},
        {"tag": "TS-506", "instrument_type": "temperature switch", "loop_number": "SR-506", "confidence": 0.80},
    ],
    "valves": [
        {"tag": "SOV-501", "valve_type": "solenoid valve", "confidence": 0.85},
        {"tag": "SOV-502", "valve_type": "solenoid valve", "confidence": 0.85},
        {"tag": "SOV-503", "valve_type": "solenoid valve", "confidence": 0.85},
        {"tag": "SOV-504", "valve_type": "solenoid valve", "confidence": 0.85},
        {"tag": "SOV-505", "valve_type": "solenoid valve", "confidence": 0.85},
        {"tag": "SOV-506", "valve_type": "solenoid valve", "confidence": 0.85},
    ]
}


def insert_into_database(sheet_id, sheet_number, data):
    """Insert extracted data into the database."""
    print(f"\nInserting data for Sheet {sheet_id} ({sheet_number})...")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    stats = {
        "lines": 0,
        "equipment": 0,
        "instruments": 0,
        "valves": 0,
        "avg_confidence": 0.0
    }

    confidences = []

    # Insert lines
    for line in data.get('lines', []):
        cursor.execute("""
            INSERT INTO lines (sheet_id, line_number, size, material, spec_class,
                             from_location, to_location, service, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            sheet_id,
            line['line_number'],
            line.get('size'),
            line.get('material'),
            line.get('spec_class'),
            line.get('from_location'),
            line.get('to_location'),
            line.get('service'),
            line.get('confidence', 0.7)
        ))
        stats['lines'] += 1
        confidences.append(line.get('confidence', 0.7))

    # Insert equipment
    for equip in data.get('equipment', []):
        cursor.execute("""
            INSERT INTO equipment (sheet_id, tag, description, equipment_type, confidence)
            VALUES (?, ?, ?, ?, ?)
        """, (
            sheet_id,
            equip['tag'],
            equip.get('description'),
            equip.get('equipment_type'),
            equip.get('confidence', 0.7)
        ))
        stats['equipment'] += 1
        confidences.append(equip.get('confidence', 0.7))

    # Insert instruments
    for inst in data.get('instruments', []):
        cursor.execute("""
            INSERT INTO instruments (sheet_id, tag, instrument_type, loop_number, confidence)
            VALUES (?, ?, ?, ?, ?)
        """, (
            sheet_id,
            inst['tag'],
            inst.get('instrument_type'),
            inst.get('loop_number'),
            inst.get('confidence', 0.7)
        ))
        stats['instruments'] += 1
        confidences.append(inst.get('confidence', 0.7))

    # Insert valves
    for valve in data.get('valves', []):
        cursor.execute("""
            INSERT INTO equipment (sheet_id, tag, description, equipment_type, confidence)
            VALUES (?, ?, ?, ?, ?)
        """, (
            sheet_id,
            valve['tag'],
            valve.get('valve_type'),
            'valve',
            valve.get('confidence', 0.7)
        ))
        stats['valves'] += 1
        confidences.append(valve.get('confidence', 0.7))

    # Calculate average confidence
    if confidences:
        stats['avg_confidence'] = sum(confidences) / len(confidences)

    # Update sheet metadata
    cursor.execute("""
        UPDATE sheets
        SET extracted_at = ?,
            quality_score = ?,
            complexity = 'medium'
        WHERE id = ?
    """, (datetime.now().isoformat(), stats['avg_confidence'], sheet_id))

    # Update processing queue if exists
    cursor.execute("""
        UPDATE processing_queue
        SET status = 'completed',
            completed_at = ?
        WHERE sheet_id = ? AND task = 'EXTRACT'
    """, (datetime.now().isoformat(), sheet_id))

    conn.commit()
    conn.close()

    print(f"  Lines: {stats['lines']}")
    print(f"  Equipment: {stats['equipment']}")
    print(f"  Instruments: {stats['instruments']}")
    print(f"  Valves: {stats['valves']}")
    print(f"  Average confidence: {stats['avg_confidence']:.2f}")

    return stats


def main():
    """Main insertion process."""
    print("Refrigeration Drawing Data Insertion")
    print("=" * 80)
    print(f"Database: {DB_PATH}")

    all_stats = []

    # Insert Sheet 16
    stats = insert_into_database(16, "R13030", SHEET_16_DATA)
    stats['sheet_id'] = 16
    stats['sheet_number'] = "R13030"
    all_stats.append(stats)

    # Insert Sheet 17
    stats = insert_into_database(17, "R13040", SHEET_17_DATA)
    stats['sheet_id'] = 17
    stats['sheet_number'] = "R13040"
    all_stats.append(stats)

    # Insert Sheet 18
    stats = insert_into_database(18, "R13050", SHEET_18_DATA)
    stats['sheet_id'] = 18
    stats['sheet_number'] = "R13050"
    all_stats.append(stats)

    # Print summary
    print("\n" + "=" * 80)
    print("EXTRACTION SUMMARY")
    print("=" * 80)

    for stats in all_stats:
        print(f"\nSheet {stats['sheet_id']} ({stats['sheet_number']}):")
        print(f"  Lines: {stats['lines']}")
        print(f"  Equipment: {stats['equipment']}")
        print(f"  Instruments: {stats['instruments']}")
        print(f"  Valves: {stats['valves']}")
        print(f"  Quality Score: {stats['avg_confidence']:.2f}")

    total_items = sum(s['lines'] + s['equipment'] + s['instruments'] + s['valves']
                     for s in all_stats)
    avg_quality = sum(s['avg_confidence'] for s in all_stats) / len(all_stats)

    print(f"\nTotal items extracted: {total_items}")
    print(f"Average quality score: {avg_quality:.2f}")
    print("\nData insertion complete!")


if __name__ == "__main__":
    main()
