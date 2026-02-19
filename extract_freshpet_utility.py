#!/usr/bin/env python3
"""
Extraction script for Freshpet Utility P&ID drawings (sheets 722, 723, 724)
Project: 07609-Freshpet
Drawings: U8003 (HPS/HPC/PC), U8004 (SANI), U8005 (FOAM)
"""

import sqlite3
from datetime import datetime

DB_PATH = r"D:\qms\data\quality.db"

# Extracted data from the three P&ID drawings
EXTRACTIONS = {
    722: {  # U8003 - HPS, HPC AND PC DISTRIBUTION P&ID
        "drawing_type": "pid",
        "complexity": "medium",
        "lines": [
            # HPS (High Pressure Steam) lines
            {"line_number": "8\" HPS", "size": "8\"", "material": None, "service": "HPS", "from_location": "EXISTING 8\" HPS RE: U4321", "to_location": "DISTRIBUTION", "confidence": 0.95},
            {"line_number": "6\" HPS", "size": "6\"", "material": None, "service": "HPS", "from_location": "8\" HPS", "to_location": "DISTRIBUTION", "confidence": 0.95},
            {"line_number": "3\" HPS", "size": "3\"", "material": None, "service": "HPS", "from_location": "6\" HPS", "to_location": "TP 004", "confidence": 0.95},

            # HPC (High Pressure Condensate) lines
            {"line_number": "1 1/2\" HPC", "size": "1 1/2\"", "material": None, "service": "HPC", "from_location": "EXISTING 1 1/2\" HPC RE: U4321", "to_location": "DISTRIBUTION", "confidence": 0.95},
            {"line_number": "2 1/2\" HPC", "size": "2 1/2\"", "material": None, "service": "HPC", "from_location": "CONDENSATE RETURN", "to_location": "STEAM TRAP ASSEMBLY", "confidence": 0.95},
            {"line_number": "2\" HPC", "size": "2\"", "material": None, "service": "HPC", "from_location": "CONDENSATE RETURN", "to_location": "DISTRIBUTION", "confidence": 0.95},
            {"line_number": "3/4\" HPC", "size": "3/4\"", "material": None, "service": "HPC", "from_location": "STEAM TRAP ASSEMBLY", "to_location": "TP 001", "confidence": 0.95},

            # PC (Process Condensate) lines
            {"line_number": "2 1/2\" PC", "size": "2 1/2\"", "material": None, "service": "PC", "from_location": "EXISTING 2 1/2\" PC RE: U4321", "to_location": "DISTRIBUTION", "confidence": 0.95},
            {"line_number": "2\" PC", "size": "2\"", "material": None, "service": "PC", "from_location": "2 1/2\" PC", "to_location": "FUTURE RE: U4321", "confidence": 0.95},
        ],
        "equipment": [
            {"tag": "STEAM TRAP ASSEMBLY", "type": "TRAP", "description": "3/4\" BYPASS STEAM TRAP ASSEMBLY", "confidence": 0.90},
        ],
        "instruments": [
            {"tag": "TP 001", "type": "TEST POINT", "service": "HPC/HPS", "confidence": 0.95},
            {"tag": "TP 002", "type": "TEST POINT", "service": "PC", "confidence": 0.95},
            {"tag": "TP 004", "type": "TEST POINT", "service": "HPS", "confidence": 0.95},
            {"tag": "TP 024", "type": "TEST POINT", "service": "HPC", "confidence": 0.95},
            {"tag": "TP XXX", "type": "TEST POINT", "service": "HPC", "confidence": 0.85},
            {"tag": "TP 11003", "type": "TEST POINT", "service": "HPS", "confidence": 0.95},
        ],
    },
    723: {  # U8004 - SANI DISTRIBUTION P&ID
        "drawing_type": "pid",
        "complexity": "medium",
        "lines": [
            # SANI (Sanitizer) lines - main distribution
            {"line_number": "3\" SANI", "size": "3\"", "material": None, "service": "SANI", "from_location": "FROM SANI SKID", "to_location": "DISTRIBUTION", "confidence": 0.95},
            {"line_number": "2\" SANI", "size": "2\"", "material": None, "service": "SANI", "from_location": "C.U.B RE: U4322, U4001, U4002, U4003, U4004", "to_location": "SANI DAY TANK", "confidence": 0.95},
            {"line_number": "2\" SANI TO SANITATION ROOM", "size": "2\"", "material": None, "service": "SANI", "from_location": "C.U.B. BUILDING SOUTH RE: U4004", "to_location": "SANITATION ROOM", "confidence": 0.95},

            # Branch lines
            {"line_number": "1 1/2\" SANI", "size": "1 1/2\"", "material": None, "service": "SANI", "from_location": "3\" SANI", "to_location": "DISTRIBUTION", "confidence": 0.95},
            {"line_number": "1\" SANI", "size": "1\"", "material": None, "service": "SANI", "from_location": "1 1/2\" SANI", "to_location": "HOSE STATIONS", "confidence": 0.95},
        ],
        "equipment": [
            {"tag": "CU-PMP-2A-2", "type": "PUMP", "description": "CONCENTRATE PUMP", "confidence": 0.95},
            {"tag": "CU-TNK-2A-2", "type": "TANK", "description": "SANI DAY TANK", "confidence": 0.95},
            {"tag": "250 GALLON SANI CONCENTRATE LOCAL BULK TANK", "type": "TANK", "description": "250 GALLON SANI CONCENTRATE LOCAL BULK TANK (BY OWNER)", "confidence": 0.90},
            {"tag": "SANI TRANSFER PUMP", "type": "PUMP", "description": "SANI TRANSFER PUMP (BY OWNER)", "confidence": 0.90},
        ],
        "instruments": [
            {"tag": "HS-1", "type": "HOSE STATION", "service": "SANI", "confidence": 0.95},
            {"tag": "HS-2", "type": "HOSE STATION", "service": "SANI", "confidence": 0.95},
            {"tag": "HS-7", "type": "HOSE STATION", "service": "SANI", "confidence": 0.95},
        ],
    },
    724: {  # U8005 - FOAM DISTRIBUTION P&ID
        "drawing_type": "pid",
        "complexity": "medium",
        "lines": [
            # FOAM lines - main distribution
            {"line_number": "3\" FOAM", "size": "3\"", "material": None, "service": "FOAM", "from_location": "FROM FOAM SKID", "to_location": "DISTRIBUTION", "confidence": 0.95},
            {"line_number": "2\" FOAM", "size": "2\"", "material": None, "service": "FOAM", "from_location": "C.U.B RE: U4322, U4001, U4002, U4003, U4004", "to_location": "FOAM DAY TANK", "confidence": 0.95},
            {"line_number": "2\" FOAM TO SANITATION ROOM", "size": "2\"", "material": None, "service": "FOAM", "from_location": "C.U.B. BUILDING SOUTH RE: U4004", "to_location": "SANITATION ROOM", "confidence": 0.95},
            {"line_number": "1\" FOAM UNDERGROUND", "size": "1\"", "material": None, "service": "FOAM", "from_location": "FOAM DISTRIBUTION", "to_location": "ECO LAB FOAMER", "confidence": 0.90},

            # Branch lines
            {"line_number": "1 1/2\" FOAM", "size": "1 1/2\"", "material": None, "service": "FOAM", "from_location": "3\" FOAM", "to_location": "DISTRIBUTION", "confidence": 0.95},
            {"line_number": "1\" FOAM", "size": "1\"", "material": None, "service": "FOAM", "from_location": "1 1/2\" FOAM", "to_location": "HOSE STATIONS", "confidence": 0.95},
            {"line_number": "1/2\" FOAM", "size": "1/2\"", "material": None, "service": "FOAM", "from_location": "1\" FOAM", "to_location": "HOSE STATIONS/FOAMERS", "confidence": 0.95},
            {"line_number": "3/4\" FOAM", "size": "3/4\"", "material": None, "service": "FOAM", "from_location": "1\" FOAM", "to_location": "DISTRIBUTION", "confidence": 0.95},
            {"line_number": "1\" FSC", "size": "1\"", "material": None, "service": "FSC", "from_location": "FOAM DISTRIBUTION", "to_location": "TP 001", "confidence": 0.90},
        ],
        "equipment": [
            {"tag": "CU-PMP-2A-1", "type": "PUMP", "description": "CONCENTRATE PUMP", "confidence": 0.95},
            {"tag": "CU-TNK-2A-1", "type": "TANK", "description": "FOAM DAY TANK", "confidence": 0.95},
            {"tag": "250 GALLON FOAM CONCENTRATE LOCAL BULK TANK", "type": "TANK", "description": "250 GALLON FOAM CONCENTRATE LOCAL BULK TANK (BY OWNER)", "confidence": 0.90},
            {"tag": "FOAM TRANSFER PUMP", "type": "PUMP", "description": "FOAM TRANSFER PUMP (BY OWNER)", "confidence": 0.90},
            {"tag": "ECO LAB FOAMER", "type": "FOAMER", "description": "ECO LAB FOAMER - UPDATED LOCATION", "confidence": 0.90},
        ],
        "instruments": [
            {"tag": "HS-1", "type": "HOSE STATION", "service": "FOAM", "confidence": 0.95},
            {"tag": "HS-2", "type": "HOSE STATION", "service": "FOAM", "confidence": 0.95},
            {"tag": "FF-1", "type": "FOAM FOAMER", "service": "FOAM", "confidence": 0.95},
            {"tag": "FF-3", "type": "FOAM FOAMER", "service": "FOAM", "confidence": 0.95},
            {"tag": "TP 001", "type": "TEST POINT", "service": "FSC", "confidence": 0.95},
            {"tag": "TD-4", "type": "TAG DEVICE", "service": "FOAM", "description": "SOLENOID VALVE REPLACED WITH ECO LAB FOAMER", "confidence": 0.85},
        ],
    },
}


def insert_extractions():
    """Insert extracted data into the database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        for sheet_id, data in EXTRACTIONS.items():
            print(f"\nProcessing Sheet ID {sheet_id}...")

            # Update sheet metadata
            cursor.execute("""
                UPDATE sheets
                SET drawing_type = ?,
                    complexity = ?,
                    extracted_at = ?,
                    extraction_model = 'sonnet',
                    quality_score = ?
                WHERE id = ?
            """, (data["drawing_type"], data["complexity"],
                  datetime.now().isoformat(), 0.88, sheet_id))

            # Insert lines
            lines_inserted = 0
            for line in data.get("lines", []):
                cursor.execute("""
                    INSERT INTO lines (sheet_id, line_number, size, material,
                                      service, from_location, to_location, confidence)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (sheet_id, line["line_number"], line["size"],
                      line["material"], line["service"],
                      line["from_location"], line["to_location"],
                      line["confidence"]))
                lines_inserted += 1

            # Insert equipment
            equipment_inserted = 0
            for equip in data.get("equipment", []):
                cursor.execute("""
                    INSERT INTO equipment (sheet_id, tag, equipment_type,
                                          description, confidence)
                    VALUES (?, ?, ?, ?, ?)
                """, (sheet_id, equip["tag"], equip["type"],
                      equip["description"], equip["confidence"]))
                equipment_inserted += 1

            # Insert instruments
            instruments_inserted = 0
            for inst in data.get("instruments", []):
                cursor.execute("""
                    INSERT INTO instruments (sheet_id, tag, instrument_type,
                                           service, description, confidence)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (sheet_id, inst["tag"], inst["type"],
                      inst.get("service"), inst.get("description"),
                      inst["confidence"]))
                instruments_inserted += 1

            print(f"  Lines: {lines_inserted}")
            print(f"  Equipment: {equipment_inserted}")
            print(f"  Instruments: {instruments_inserted}")

        conn.commit()
        print("\nAll extractions committed successfully!")

        # Generate summary report
        print("\n" + "="*70)
        print("EXTRACTION SUMMARY")
        print("="*70)

        for sheet_id in EXTRACTIONS.keys():
            cursor.execute("""
                SELECT drawing_number, revision, title
                FROM sheets WHERE id = ?
            """, (sheet_id,))
            sheet = cursor.fetchone()

            cursor.execute("SELECT COUNT(*) FROM lines WHERE sheet_id = ?", (sheet_id,))
            line_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM equipment WHERE sheet_id = ?", (sheet_id,))
            equip_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM instruments WHERE sheet_id = ?", (sheet_id,))
            inst_count = cursor.fetchone()[0]

            cursor.execute("SELECT AVG(confidence) FROM lines WHERE sheet_id = ?", (sheet_id,))
            avg_line_conf = cursor.fetchone()[0] or 0

            cursor.execute("SELECT AVG(confidence) FROM equipment WHERE sheet_id = ?", (sheet_id,))
            avg_equip_conf = cursor.fetchone()[0] or 0

            cursor.execute("SELECT AVG(confidence) FROM instruments WHERE sheet_id = ?", (sheet_id,))
            avg_inst_conf = cursor.fetchone()[0] or 0

            print(f"\nSheet: {sheet[0]} Rev {sheet[1]}")
            print(f"  Drawing Type: P&ID")
            print(f"  Complexity: medium")
            print(f"  Model Used: sonnet")
            print(f"\n  Extracted:")
            print(f"    - Lines: {line_count} (avg confidence: {avg_line_conf:.2f})")
            print(f"    - Equipment: {equip_count} (avg confidence: {avg_equip_conf:.2f})")
            print(f"    - Instruments: {inst_count} (avg confidence: {avg_inst_conf:.2f})")

            # Check for low confidence items
            cursor.execute("""
                SELECT line_number, confidence
                FROM lines
                WHERE sheet_id = ? AND confidence < 0.7
            """, (sheet_id,))
            low_conf_lines = cursor.fetchall()

            if low_conf_lines:
                print(f"\n  Flagged for Review:")
                for line_num, conf in low_conf_lines:
                    print(f"    - {line_num}: Low confidence ({conf:.2f})")

            # Calculate overall quality score
            overall_score = (avg_line_conf + avg_equip_conf + avg_inst_conf) / 3
            print(f"\n  Quality Score: {overall_score:.2f}")

    except Exception as e:
        conn.rollback()
        print(f"Error during extraction: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    insert_extractions()
