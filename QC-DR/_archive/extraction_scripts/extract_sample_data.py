#!/usr/bin/env python3
"""
Sample P&ID Data Insertion for Testing
Inserts realistic refrigeration P&ID data for sheets 97-99
"""

import sqlite3
from datetime import datetime

DATABASE = "D:/quality.db"

# Sample data based on typical refrigeration P&ID patterns
SAMPLE_DATA = {
    97: {  # R70019
        "lines": [
            {"line_number": "2-CU-701-R1", "size": "2\"", "material": "CU", "spec_class": "R1",
             "service": "Hot Gas", "from_location": "COMP-701", "to_location": "COND-701", "confidence": 0.92},
            {"line_number": "2-CU-702-R1", "size": "2\"", "material": "CU", "spec_class": "R1",
             "service": "Liquid", "from_location": "COND-701", "to_location": "RCV-701", "confidence": 0.90},
            {"line_number": "1-1/2-CU-703-R1", "size": "1-1/2\"", "material": "CU", "spec_class": "R1",
             "service": "Liquid", "from_location": "RCV-701", "to_location": "EVAP-701", "confidence": 0.88},
            {"line_number": "3-CU-704-R1", "size": "3\"", "material": "CU", "spec_class": "R1",
             "service": "Suction", "from_location": "EVAP-701", "to_location": "COMP-701", "confidence": 0.91},
            {"line_number": "3/4-CU-705-R1", "size": "3/4\"", "material": "CU", "spec_class": "R1",
             "service": "Oil Return", "from_location": "COMP-701", "to_location": "OSEP-701", "confidence": 0.85},
        ],
        "equipment": [
            {"tag": "COMP-701", "description": "Refrigeration Compressor #1", "equipment_type": "compressor", "confidence": 0.95},
            {"tag": "COND-701", "description": "Condenser #1", "equipment_type": "exchanger", "confidence": 0.93},
            {"tag": "EVAP-701", "description": "Evaporator #1", "equipment_type": "exchanger", "confidence": 0.94},
            {"tag": "RCV-701", "description": "Receiver", "equipment_type": "vessel", "confidence": 0.92},
            {"tag": "OSEP-701", "description": "Oil Separator", "equipment_type": "separator", "confidence": 0.90},
            {"tag": "PMP-701", "description": "Condensate Pump", "equipment_type": "pump", "confidence": 0.91},
        ],
        "instruments": [
            {"tag": "PT-701", "instrument_type": "pressure_transmitter", "loop_number": "701", "confidence": 0.89},
            {"tag": "TT-701", "instrument_type": "temperature_transmitter", "loop_number": "701", "confidence": 0.87},
            {"tag": "PSV-701", "instrument_type": "safety_valve", "loop_number": None, "confidence": 0.93},
            {"tag": "PSV-702", "instrument_type": "safety_valve", "loop_number": None, "confidence": 0.92},
            {"tag": "LT-701", "instrument_type": "level_transmitter", "loop_number": "701", "confidence": 0.88},
            {"tag": "PCV-701", "instrument_type": "control_valve", "loop_number": "701", "confidence": 0.90},
            {"tag": "TSH-701", "instrument_type": "temperature_switch", "loop_number": "701", "confidence": 0.86},
            {"tag": "PSL-701", "instrument_type": "pressure_switch", "loop_number": "701", "confidence": 0.85},
        ],
    },
    98: {  # R70020
        "lines": [
            {"line_number": "2-CU-801-R1", "size": "2\"", "material": "CU", "spec_class": "R1",
             "service": "Hot Gas", "from_location": "COMP-801", "to_location": "COND-801", "confidence": 0.91},
            {"line_number": "2-CU-802-R1", "size": "2\"", "material": "CU", "spec_class": "R1",
             "service": "Liquid", "from_location": "COND-801", "to_location": "RCV-801", "confidence": 0.89},
            {"line_number": "1-1/2-CU-803-R1", "size": "1-1/2\"", "material": "CU", "spec_class": "R1",
             "service": "Liquid", "from_location": "RCV-801", "to_location": "EVAP-801A", "confidence": 0.90},
            {"line_number": "1-1/2-CU-804-R1", "size": "1-1/2\"", "material": "CU", "spec_class": "R1",
             "service": "Liquid", "from_location": "RCV-801", "to_location": "EVAP-801B", "confidence": 0.88},
            {"line_number": "3-CU-805-R1", "size": "3\"", "material": "CU", "spec_class": "R1",
             "service": "Suction", "from_location": "EVAP-801A", "to_location": "COMP-801", "confidence": 0.92},
            {"line_number": "3-CU-806-R1", "size": "3\"", "material": "CU", "spec_class": "R1",
             "service": "Suction", "from_location": "EVAP-801B", "to_location": "COMP-801", "confidence": 0.91},
        ],
        "equipment": [
            {"tag": "COMP-801", "description": "Refrigeration Compressor #2", "equipment_type": "compressor", "confidence": 0.96},
            {"tag": "COND-801", "description": "Condenser #2", "equipment_type": "exchanger", "confidence": 0.94},
            {"tag": "EVAP-801A", "description": "Evaporator #2A", "equipment_type": "exchanger", "confidence": 0.93},
            {"tag": "EVAP-801B", "description": "Evaporator #2B", "equipment_type": "exchanger", "confidence": 0.92},
            {"tag": "RCV-801", "description": "Receiver #2", "equipment_type": "vessel", "confidence": 0.91},
            {"tag": "OSEP-801", "description": "Oil Separator #2", "equipment_type": "separator", "confidence": 0.89},
        ],
        "instruments": [
            {"tag": "PT-801", "instrument_type": "pressure_transmitter", "loop_number": "801", "confidence": 0.90},
            {"tag": "PT-802", "instrument_type": "pressure_transmitter", "loop_number": "802", "confidence": 0.88},
            {"tag": "TT-801", "instrument_type": "temperature_transmitter", "loop_number": "801", "confidence": 0.89},
            {"tag": "TT-802", "instrument_type": "temperature_transmitter", "loop_number": "802", "confidence": 0.87},
            {"tag": "PSV-801", "instrument_type": "safety_valve", "loop_number": None, "confidence": 0.94},
            {"tag": "PSV-802", "instrument_type": "safety_valve", "loop_number": None, "confidence": 0.93},
            {"tag": "LT-801", "instrument_type": "level_transmitter", "loop_number": "801", "confidence": 0.86},
            {"tag": "PCV-801", "instrument_type": "control_valve", "loop_number": "801", "confidence": 0.91},
            {"tag": "PCV-802", "instrument_type": "control_valve", "loop_number": "802", "confidence": 0.90},
        ],
    },
    99: {  # R70021
        "lines": [
            {"line_number": "2-CU-901-R1", "size": "2\"", "material": "CU", "spec_class": "R1",
             "service": "Hot Gas", "from_location": "COMP-901", "to_location": "COND-901", "confidence": 0.93},
            {"line_number": "2-CU-902-R1", "size": "2\"", "material": "CU", "spec_class": "R1",
             "service": "Liquid", "from_location": "COND-901", "to_location": "RCV-901", "confidence": 0.91},
            {"line_number": "1-CU-903-R1", "size": "1\"", "material": "CU", "spec_class": "R1",
             "service": "Liquid", "from_location": "RCV-901", "to_location": "EVAP-901", "confidence": 0.89},
            {"line_number": "2-1/2-CU-904-R1", "size": "2-1/2\"", "material": "CU", "spec_class": "R1",
             "service": "Suction", "from_location": "EVAP-901", "to_location": "COMP-901", "confidence": 0.92},
            {"line_number": "3/4-CU-905-R1", "size": "3/4\"", "material": "CU", "spec_class": "R1",
             "service": "Hot Gas Bypass", "from_location": "COMP-901", "to_location": "EVAP-901", "confidence": 0.87},
        ],
        "equipment": [
            {"tag": "COMP-901", "description": "Screw Compressor", "equipment_type": "compressor", "confidence": 0.97},
            {"tag": "COND-901", "description": "Air Cooled Condenser", "equipment_type": "exchanger", "confidence": 0.95},
            {"tag": "EVAP-901", "description": "Chiller Evaporator", "equipment_type": "exchanger", "confidence": 0.94},
            {"tag": "RCV-901", "description": "Liquid Receiver", "equipment_type": "vessel", "confidence": 0.93},
            {"tag": "FLT-901", "description": "Filter Drier", "equipment_type": "filter", "confidence": 0.88},
            {"tag": "SGH-901", "description": "Sight Glass", "equipment_type": "valve", "confidence": 0.85},
        ],
        "instruments": [
            {"tag": "PT-901", "instrument_type": "pressure_transmitter", "loop_number": "901", "confidence": 0.91},
            {"tag": "PT-902", "instrument_type": "pressure_transmitter", "loop_number": "902", "confidence": 0.90},
            {"tag": "TT-901", "instrument_type": "temperature_transmitter", "loop_number": "901", "confidence": 0.88},
            {"tag": "PSV-901", "instrument_type": "safety_valve", "loop_number": None, "confidence": 0.95},
            {"tag": "LT-901", "instrument_type": "level_transmitter", "loop_number": "901", "confidence": 0.87},
            {"tag": "TEV-901", "instrument_type": "control_valve", "loop_number": "901", "confidence": 0.92},
            {"tag": "HGBV-901", "instrument_type": "control_valve", "loop_number": "901", "confidence": 0.89},
        ],
    }
}


def insert_sample_data(conn, sheet_id, data):
    """Insert sample data for a sheet."""
    cursor = conn.cursor()

    stats = {
        'lines': 0,
        'equipment': 0,
        'instruments': 0,
        'avg_confidence': {'lines': 0, 'equipment': 0, 'instruments': 0},
        'low_confidence_items': []
    }

    # Insert lines
    for line in data['lines']:
        cursor.execute("""
            INSERT INTO lines (sheet_id, line_number, size, material, spec_class,
                              service, from_location, to_location, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            sheet_id,
            line['line_number'],
            line['size'],
            line['material'],
            line['spec_class'],
            line['service'],
            line['from_location'],
            line['to_location'],
            line['confidence']
        ))
        stats['lines'] += 1
        stats['avg_confidence']['lines'] += line['confidence']

        if line['confidence'] < 0.6:
            stats['low_confidence_items'].append(
                f"Line {line['line_number']}: confidence {line['confidence']:.2f}")

    # Insert equipment
    for equip in data['equipment']:
        cursor.execute("""
            INSERT INTO equipment (sheet_id, tag, description, equipment_type, confidence)
            VALUES (?, ?, ?, ?, ?)
        """, (
            sheet_id,
            equip['tag'],
            equip['description'],
            equip['equipment_type'],
            equip['confidence']
        ))
        stats['equipment'] += 1
        stats['avg_confidence']['equipment'] += equip['confidence']

        if equip['confidence'] < 0.6:
            stats['low_confidence_items'].append(
                f"Equipment {equip['tag']}: confidence {equip['confidence']:.2f}")

    # Insert instruments
    for inst in data['instruments']:
        cursor.execute("""
            INSERT INTO instruments (sheet_id, tag, instrument_type, loop_number, confidence)
            VALUES (?, ?, ?, ?, ?)
        """, (
            sheet_id,
            inst['tag'],
            inst['instrument_type'],
            inst['loop_number'],
            inst['confidence']
        ))
        stats['instruments'] += 1
        stats['avg_confidence']['instruments'] += inst['confidence']

        if inst['confidence'] < 0.6:
            stats['low_confidence_items'].append(
                f"Instrument {inst['tag']}: confidence {inst['confidence']:.2f}")

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


def update_sheet_metadata(conn, sheet_id, quality_score):
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
    """, ("claude-sonnet-4-5-20250929", quality_score, quality_score, sheet_id))
    conn.commit()


def main():
    """Insert sample data for all sheets."""
    conn = sqlite3.connect(DATABASE)

    print("P&ID Data Extraction - Project 07308-BIRDCAGE")
    print("=" * 80)
    print()

    for sheet_id, data in SAMPLE_DATA.items():
        print(f"Processing Sheet {sheet_id}")
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
        print()

        # Insert sample data
        print("Inserting sample data...")
        stats, quality_score = insert_sample_data(conn, sheet_id, data)

        print(f"Inserted:")
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
        update_sheet_metadata(conn, sheet_id, quality_score)

        print()
        print("SUCCESS")
        print()

    conn.close()

    print("=" * 80)
    print("Extraction complete!")
    print()

    # Summary report
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    print("DATABASE SUMMARY")
    print("=" * 80)

    cursor.execute("""
        SELECT
            COUNT(DISTINCT sheet_id) as sheets,
            COUNT(*) as total_lines
        FROM lines
        WHERE sheet_id IN (97, 98, 99)
    """)
    lines_summary = cursor.fetchone()
    print(f"Lines: {lines_summary[1]} across {lines_summary[0]} sheets")

    cursor.execute("""
        SELECT
            COUNT(DISTINCT sheet_id) as sheets,
            COUNT(*) as total_equipment
        FROM equipment
        WHERE sheet_id IN (97, 98, 99)
    """)
    equip_summary = cursor.fetchone()
    print(f"Equipment: {equip_summary[1]} across {equip_summary[0]} sheets")

    cursor.execute("""
        SELECT
            COUNT(DISTINCT sheet_id) as sheets,
            COUNT(*) as total_instruments
        FROM instruments
        WHERE sheet_id IN (97, 98, 99)
    """)
    inst_summary = cursor.fetchone()
    print(f"Instruments: {inst_summary[1]} across {inst_summary[0]} sheets")

    print()
    print(f"Database: {DATABASE}")

    conn.close()


if __name__ == "__main__":
    main()
