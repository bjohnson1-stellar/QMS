#!/usr/bin/env python3
"""
Extract data from Freshpet Utility P&IDs (sheets 725-727)
"""
import sqlite3
import json
from datetime import datetime

DB_PATH = r"D:\qms\data\quality.db"

# Extracted data from the three P&ID drawings
EXTRACTIONS = {
    725: {  # U8006 - HPWS AND HPWR DISTRIBUTION P&ID
        "drawing_type": "P&ID",
        "complexity": "medium",
        "lines": [
            # HPWS (High Pressure Water Supply) lines
            {"line_number": "4\" HPWS", "size": "4\"", "material": None, "service": "HPWS", "spec_class": None, "from_location": "FROM EXISTING 4\" HPWS RE: U4321", "to_location": "Distribution", "confidence": 0.90},
            {"line_number": "4\" HPWS", "size": "4\"", "material": None, "service": "HPWS", "spec_class": None, "from_location": "Distribution", "to_location": "FOR FUTURE 4\" HPWS RE: U4321", "confidence": 0.90},
            {"line_number": "4\" HPWS", "size": "4\"", "material": None, "service": "HPWS", "spec_class": None, "from_location": "M-2A-3", "to_location": "Distribution", "confidence": 0.92},
            {"line_number": "2\" HPWS", "size": "2\"", "material": None, "service": "HPWS", "spec_class": None, "from_location": "4\" HPWS", "to_location": "TP-069", "confidence": 0.92},
            {"line_number": "1 1/2\" HPWS", "size": "1 1/2\"", "material": None, "service": "HPWS", "spec_class": None, "from_location": "2\" HPWS", "to_location": "Process", "confidence": 0.90},
            {"line_number": "1 1/2\" HPWS", "size": "1 1/2\"", "material": None, "service": "HPWS", "spec_class": None, "from_location": "4\" HPWS", "to_location": "HS-4 BY PROCESS", "confidence": 0.90},
            {"line_number": "1\" HPWS", "size": "1\"", "material": None, "service": "HPWS", "spec_class": None, "from_location": "Various", "to_location": "Multiple HS-1 hose stations", "confidence": 0.88},
            {"line_number": "1\" HPWS FOR PROCESS", "size": "1\"", "material": None, "service": "HPWS", "spec_class": None, "from_location": "4\" HPWS", "to_location": "Process", "confidence": 0.92},
            {"line_number": "1\" HPWS", "size": "1\"", "material": None, "service": "HPWS", "spec_class": None, "from_location": "Circuit Setter", "to_location": "TP-XXX", "confidence": 0.85, "notes": "CIRCUIT SETTER SET @ 6 GPM"},

            # HPWR (High Pressure Water Return) lines
            {"line_number": "2\" HPWR", "size": "2\"", "material": None, "service": "HPWR", "spec_class": None, "from_location": "Return", "to_location": "TO EXISTING 2\" HPWR RE: U4321", "confidence": 0.90},
            {"line_number": "1 1/2\" HPWR", "size": "1 1/2\"", "material": None, "service": "HPWR", "spec_class": None, "from_location": "FROM FUTURE 1 1/2\" HPWR RE: U4321", "to_location": "2\" HPWR", "confidence": 0.90},
            {"line_number": "1\" HPWR", "size": "1\"", "material": None, "service": "HPWR", "spec_class": None, "from_location": "Multiple HS-2 returns", "to_location": "1 1/2\" HPWR", "confidence": 0.88},
        ],
        "equipment": [
            {"tag": "M-2A-3", "type": "Equipment", "description": "Equipment item on 4\" HPWS line", "confidence": 0.85},
        ],
        "instruments": [
            {"tag": "HS-1", "type": "Hose Station", "description": "Multiple hose stations on HPWS", "confidence": 0.92},
            {"tag": "HS-2", "type": "Hose Station", "description": "Multiple hose stations on HPWR return", "confidence": 0.92},
            {"tag": "HS-4", "type": "Hose Station", "description": "Hose station by process (dual)", "confidence": 0.90},
            {"tag": "TP-069", "type": "Test Point", "description": "Test point on 2\" HPWS", "confidence": 0.95},
            {"tag": "TP-XXX", "type": "Test Point", "description": "Test point on 1\" HPWS", "confidence": 0.85},
        ]
    },

    726: {  # U8007 - CA DISTRIBUTION P&ID
        "drawing_type": "P&ID",
        "complexity": "medium",
        "lines": [
            # CA (Compressed Air) lines
            {"line_number": "6\" CA", "size": "6\"", "material": None, "service": "CA", "spec_class": None, "from_location": "EXISTING 6\" CA RE: U4004", "to_location": "Distribution", "confidence": 0.92},
            {"line_number": "3\" CA", "size": "3\"", "material": None, "service": "CA", "spec_class": None, "from_location": "6\" CA / EXISTING 3\" CA RE: U4321", "to_location": "Distribution loops", "confidence": 0.90},
            {"line_number": "3\" CA FOR FUTURE", "size": "3\"", "material": None, "service": "CA", "spec_class": None, "from_location": "EXISTING 3\" CA", "to_location": "RE: U4321", "confidence": 0.88},
            {"line_number": "2\" CA", "size": "2\"", "material": None, "service": "CA", "spec_class": None, "from_location": "3\" CA", "to_location": "Multiple locations", "confidence": 0.90, "notes": "CONNECT NEW 2\" CA TO EXISTING 2\" CA LOOP AT THIS POINT. PROVIDE VALVED CONNECTION"},
            {"line_number": "EXISTING 2\" CA LOOP", "size": "2\"", "material": None, "service": "CA", "spec_class": None, "from_location": "RE: U4364", "to_location": "Loop", "confidence": 0.88},
            {"line_number": "1 1/2\" CA", "size": "1 1/2\"", "material": None, "service": "CA", "spec_class": None, "from_location": "Multiple", "to_location": "Distribution", "confidence": 0.88},
            {"line_number": "1 1/4\" CA", "size": "1 1/4\"", "material": None, "service": "CA", "spec_class": None, "from_location": "3\" CA", "to_location": "HS-8", "confidence": 0.90},
            {"line_number": "1\" CA", "size": "1\"", "material": None, "service": "CA", "spec_class": None, "from_location": "Multiple", "to_location": "Test points and equipment", "confidence": 0.88},
            {"line_number": "1\" CA FOR PROCESS", "size": "1\"", "material": None, "service": "CA", "spec_class": None, "from_location": "Distribution", "to_location": "Process", "confidence": 0.90},
            {"line_number": "1\" CA DOWN TO FOAM CONCENTRATE PUMP CU-PMP-2A-1", "size": "1\"", "material": None, "service": "CA", "spec_class": None, "from_location": "6\" CA", "to_location": "CU-PMP-2A-1", "confidence": 0.92},
            {"line_number": "1\" CA DOWN TO FOAM CONCENTRATE PUMP CU-PMP-2A-2", "size": "1\"", "material": None, "service": "CA", "spec_class": None, "from_location": "6\" CA", "to_location": "CU-PMP-2A-2", "confidence": 0.92},
            {"line_number": "3/4\" CA", "size": "3/4\"", "material": None, "service": "CA", "spec_class": None, "from_location": "Multiple", "to_location": "Hose stations and equipment", "confidence": 0.85},
            {"line_number": "3/4\" CA TO QUICK CONNECT", "size": "3/4\"", "material": None, "service": "CA", "spec_class": None, "from_location": "Distribution", "to_location": "Quick connect", "confidence": 0.90},
            {"line_number": "1/2\" CA", "size": "1/2\"", "material": None, "service": "CA", "spec_class": None, "from_location": "Multiple", "to_location": "FF-1, HS-1, HS-2, ECO LAB FOAMER", "confidence": 0.85},
        ],
        "equipment": [
            {"tag": "CU-PMP-2A-1", "type": "Pump", "description": "Foam concentrate pump", "confidence": 0.95},
            {"tag": "CU-PMP-2A-2", "type": "Pump", "description": "Foam concentrate pump", "confidence": 0.95},
        ],
        "instruments": [
            {"tag": "HS-1", "type": "Hose Station", "description": "Multiple hose stations (3/4\" and 1/2\" CA)", "confidence": 0.90},
            {"tag": "HS-2", "type": "Hose Station", "description": "Multiple hose stations (3/4\" and 1\" CA)", "confidence": 0.90},
            {"tag": "HS-6", "type": "Hose Station", "description": "Hose station on 3/4\" CA", "confidence": 0.90},
            {"tag": "HS-8", "type": "Hose Station", "description": "Hose station on 1 1/4\" CA", "confidence": 0.90},
            {"tag": "FF-1", "type": "Flow Device", "description": "Multiple flow devices on 1/2\" and 3/4\" CA", "confidence": 0.85},
            {"tag": "FF-3", "type": "Flow Device", "description": "Flow devices on 3/4\" CA", "confidence": 0.85},
            {"tag": "TP-001", "type": "Test Point", "description": "Test point", "confidence": 0.95},
            {"tag": "TP-002", "type": "Test Point", "description": "Test point", "confidence": 0.95},
            {"tag": "TP-004", "type": "Test Point", "description": "Test point", "confidence": 0.95},
            {"tag": "TP-005", "type": "Test Point", "description": "Test point", "confidence": 0.95},
            {"tag": "TP-006", "type": "Test Point", "description": "Test point", "confidence": 0.95},
            {"tag": "TP-007", "type": "Test Point", "description": "Test point", "confidence": 0.95},
            {"tag": "TP-008", "type": "Test Point", "description": "Test point", "confidence": 0.95},
            {"tag": "TP-015", "type": "Test Point", "description": "Test point", "confidence": 0.95},
            {"tag": "TP-016", "type": "Test Point", "description": "Test point", "confidence": 0.95},
            {"tag": "TP-022", "type": "Test Point", "description": "Test point", "confidence": 0.95},
            {"tag": "TP-024", "type": "Test Point", "description": "Test point", "confidence": 0.95},
            {"tag": "TP-026", "type": "Test Point", "description": "Test point", "confidence": 0.95},
            {"tag": "TP-1300", "type": "Test Point", "description": "Test point", "confidence": 0.90},
            {"tag": "TP-XXX", "type": "Test Point", "description": "Test point (UPDATED LOCATION)", "confidence": 0.85},
        ],
        "notes": [
            "TO SANI DAY TANK connection shown",
            "TO FOAM DAY TANK connection shown",
            "ADDED FOAMER 2 (ECO LAB FOAMER) revision 2",
        ]
    },

    727: {  # U8008 - PCW DISTRIBUTION P&ID
        "drawing_type": "P&ID",
        "complexity": "medium",
        "lines": [
            # PCW (Process Chilled Water) lines
            {"line_number": "6\" PCW", "size": "6\"", "material": None, "service": "PCW", "spec_class": None, "from_location": "EXISTING 6\" PCW RE: U4321", "to_location": "Distribution", "confidence": 0.92},
            {"line_number": "6\" PCW FOR FUTURE", "size": "6\"", "material": None, "service": "PCW", "spec_class": None, "from_location": "Distribution", "to_location": "RE: U4321", "confidence": 0.90},
            {"line_number": "6\" PCW", "size": "6\"", "material": None, "service": "PCW", "spec_class": None, "from_location": "M-2A-2", "to_location": "Distribution", "confidence": 0.92},
            {"line_number": "4\" PCW", "size": "4\"", "material": None, "service": "PCW", "spec_class": None, "from_location": "6\" PCW", "to_location": "Multiple locations", "confidence": 0.90},
            {"line_number": "4\" PCW FOR PROCESS", "size": "4\"", "material": None, "service": "PCW", "spec_class": None, "from_location": "Distribution", "to_location": "Process", "confidence": 0.92},
            {"line_number": "4\" PCW", "size": "4\"", "material": None, "service": "PCW", "spec_class": None, "from_location": "TP-005", "to_location": "Distribution", "confidence": 0.90},
            {"line_number": "2\" PCW", "size": "2\"", "material": None, "service": "PCW", "spec_class": None, "from_location": "4\" PCW", "to_location": "TP-004, TP-011", "confidence": 0.90},
            {"line_number": "1 1/2\" PCW", "size": "1 1/2\"", "material": None, "service": "PCW", "spec_class": None, "from_location": "Multiple", "to_location": "Distribution", "confidence": 0.88},
            {"line_number": "1\" PCW", "size": "1\"", "material": None, "service": "PCW", "spec_class": None, "from_location": "Multiple", "to_location": "Test points and equipment", "confidence": 0.88},
            {"line_number": "1\" PCW FOR PROCESS", "size": "1\"", "material": None, "service": "PCW", "spec_class": None, "from_location": "Distribution", "to_location": "Process", "confidence": 0.90},
            {"line_number": "3/4\" PCW", "size": "3/4\"", "material": None, "service": "PCW", "spec_class": None, "from_location": "Multiple", "to_location": "S-1, S-2, EWS-1, HB-3", "confidence": 0.85},
        ],
        "equipment": [
            {"tag": "M-2A-2", "type": "Equipment", "description": "Equipment item on 6\" PCW line", "confidence": 0.85},
        ],
        "instruments": [
            {"tag": "S-1", "type": "Sensor/Safety", "description": "Multiple safety/sensor devices on PCW", "confidence": 0.88},
            {"tag": "S-2", "type": "Sensor/Safety", "description": "Multiple safety/sensor devices on PCW", "confidence": 0.88},
            {"tag": "EWS-1", "type": "Equipment", "description": "Multiple equipment wash stations", "confidence": 0.88},
            {"tag": "HB-3", "type": "Hose Bib", "description": "Multiple hose bibs on PCW", "confidence": 0.88},
            {"tag": "TP-002", "type": "Test Point", "description": "Test point", "confidence": 0.95},
            {"tag": "TP-003", "type": "Test Point", "description": "Test point", "confidence": 0.95},
            {"tag": "TP-004", "type": "Test Point", "description": "Test point", "confidence": 0.95},
            {"tag": "TP-005", "type": "Test Point", "description": "Test point", "confidence": 0.95},
            {"tag": "TP-011", "type": "Test Point", "description": "Test point", "confidence": 0.95},
            {"tag": "TP-XXX", "type": "Test Point", "description": "Test point (future/placeholder)", "confidence": 0.80},
        ],
        "notes": [
            "PCW FROM existing connection shown",
            "DELETED 3/4\" PCW AND HB-3 revision 2 in CHEMICAL ROOM",
            "BOOT WASH area marked",
            "CAP FOR FUTURE HB-3 shown revision 2",
        ]
    }
}


def insert_extractions():
    """Insert extracted data into database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    stats = {
        "lines": 0,
        "equipment": 0,
        "instruments": 0,
        "errors": []
    }

    try:
        for sheet_id, data in EXTRACTIONS.items():
            print(f"\n{'='*60}")
            print(f"Sheet {sheet_id}: {data['drawing_type']} (Complexity: {data['complexity']})")
            print(f"{'='*60}")

            # Get sheet info
            cursor.execute("SELECT drawing_number, revision FROM sheets WHERE id = ?", (sheet_id,))
            sheet_info = cursor.fetchone()
            if sheet_info:
                print(f"Drawing: {sheet_info[0]} Rev {sheet_info[1]}")

            # Insert lines
            print(f"\nLines: {len(data.get('lines', []))}")
            for line in data.get('lines', []):
                try:
                    cursor.execute("""
                        INSERT INTO lines (sheet_id, line_number, size, material, service,
                                         spec_class, from_location, to_location, confidence)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        sheet_id,
                        line['line_number'],
                        line.get('size'),
                        line.get('material'),
                        line.get('service'),
                        line.get('spec_class'),
                        line.get('from_location'),
                        line.get('to_location'),
                        line.get('confidence', 0.9)
                    ))
                    stats['lines'] += 1
                    conf_icon = "✓" if line.get('confidence', 0) >= 0.85 else "!"
                    print(f"  {conf_icon} {line['line_number']:20s} (confidence: {line.get('confidence', 0.9):.2f})")
                except Exception as e:
                    error_msg = f"Line insertion error: {line['line_number']} - {str(e)}"
                    print(f"  ERROR: {error_msg}")
                    stats['errors'].append(error_msg)

            # Insert equipment
            print(f"\nEquipment: {len(data.get('equipment', []))}")
            for equip in data.get('equipment', []):
                try:
                    cursor.execute("""
                        INSERT INTO equipment (sheet_id, tag, description, equipment_type, confidence)
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        sheet_id,
                        equip['tag'],
                        equip.get('description'),
                        equip.get('type'),
                        equip.get('confidence', 0.9)
                    ))
                    stats['equipment'] += 1
                    conf_icon = "✓" if equip.get('confidence', 0) >= 0.85 else "!"
                    print(f"  {conf_icon} {equip['tag']:15s} - {equip.get('description', 'N/A')[:40]} (confidence: {equip.get('confidence', 0.9):.2f})")
                except Exception as e:
                    error_msg = f"Equipment insertion error: {equip['tag']} - {str(e)}"
                    print(f"  ERROR: {error_msg}")
                    stats['errors'].append(error_msg)

            # Insert instruments
            print(f"\nInstruments: {len(data.get('instruments', []))}")
            for inst in data.get('instruments', []):
                try:
                    cursor.execute("""
                        INSERT INTO instruments (sheet_id, tag, instrument_type, description, confidence)
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        sheet_id,
                        inst['tag'],
                        inst.get('type'),
                        inst.get('description'),
                        inst.get('confidence', 0.9)
                    ))
                    stats['instruments'] += 1
                    conf_icon = "✓" if inst.get('confidence', 0) >= 0.85 else "!"
                    print(f"  {conf_icon} {inst['tag']:15s} - {inst.get('type', 'N/A')[:25]} (confidence: {inst.get('confidence', 0.9):.2f})")
                except Exception as e:
                    error_msg = f"Instrument insertion error: {inst['tag']} - {str(e)}"
                    print(f"  ERROR: {error_msg}")
                    stats['errors'].append(error_msg)

            # Update sheet status
            cursor.execute("""
                UPDATE sheets
                SET extracted_at = ?,
                    quality_score = ?,
                    complexity = ?
                WHERE id = ?
            """, (
                datetime.now().isoformat(),
                sum(item.get('confidence', 0.9) for category in ['lines', 'equipment', 'instruments']
                    for item in data.get(category, [])) / max(1, sum(len(data.get(cat, [])) for cat in ['lines', 'equipment', 'instruments'])),
                data['complexity'],
                sheet_id
            ))

            if data.get('notes'):
                print(f"\nNotes:")
                for note in data['notes']:
                    print(f"  - {note}")

        conn.commit()

        # Print summary
        print(f"\n{'='*60}")
        print(f"EXTRACTION SUMMARY")
        print(f"{'='*60}")
        print(f"Lines extracted:       {stats['lines']}")
        print(f"Equipment extracted:   {stats['equipment']}")
        print(f"Instruments extracted: {stats['instruments']}")
        print(f"Total items:           {stats['lines'] + stats['equipment'] + stats['instruments']}")

        if stats['errors']:
            print(f"\nErrors encountered: {len(stats['errors'])}")
            for error in stats['errors']:
                print(f"  - {error}")
        else:
            print(f"\nNo errors encountered.")

        # Calculate overall quality
        total_items = stats['lines'] + stats['equipment'] + stats['instruments']
        if total_items > 0:
            avg_confidence = sum(
                item.get('confidence', 0.9)
                for sheet_data in EXTRACTIONS.values()
                for category in ['lines', 'equipment', 'instruments']
                for item in sheet_data.get(category, [])
            ) / total_items
            print(f"\nOverall quality score: {avg_confidence:.2f}")

    except Exception as e:
        conn.rollback()
        print(f"\nFATAL ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()


if __name__ == "__main__":
    insert_extractions()
