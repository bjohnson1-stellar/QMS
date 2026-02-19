"""
Extract architectural data from Freshpet drawing sheets.

Extraction for:
- Sheet 476: A5061 - Bollard & Guard Details
- Sheet 477: A6001 - Room Finish Schedule
- Sheet 478: A7001 - Door & Window Types and Schedules
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path

DB_PATH = r"D:\qms\data\quality.db"

# Sheet 476: A5061 - Bollard & Guard Details
# This sheet contains detail drawings for bollards and guards
# Extract equipment tags and types

SHEET_476_EQUIPMENT = [
    {
        "sheet_id": 476,
        "tag": "GP.01",
        "description": "Type U1 Typical U-Guard Detail",
        "equipment_type": "U-Guard",
        "confidence": 0.95
    },
    {
        "sheet_id": 476,
        "tag": "GP.03",
        "description": "Type U1 Typical U-Guard with Wing Guard Detail",
        "equipment_type": "U-Guard",
        "confidence": 0.95
    },
    {
        "sheet_id": 476,
        "tag": "GP.10",
        "description": "Type B1 Typical Bollard Concrete Encased",
        "equipment_type": "Bollard",
        "confidence": 0.95
    },
    {
        "sheet_id": 476,
        "tag": "GP.11",
        "description": "Type B2 Typical Bollard Spool Mounted",
        "equipment_type": "Bollard",
        "confidence": 0.95
    },
    {
        "sheet_id": 476,
        "tag": "GP.14",
        "description": "Type D1 Fixed Dock Guardrail Detail",
        "equipment_type": "Guardrail",
        "confidence": 0.95
    },
]

# Sheet 477: A6001 - Room Finish Schedule
# Extract room data with finishes

SHEET_477_ROOMS = [
    {"room_number": "1201", "name": "SANITATION ROOM", "area_sf": 921, "floor": "URE-1", "base": "CONC - URETHANE", "walls": "IMP-2"},
    {"room_number": "1203", "name": "UTILITY ROOM", "area_sf": 511, "floor": "URE-1", "base": "CONC - URETHANE", "walls": "IMP-2"},
    {"room_number": "1401", "name": "ROLL PROCESSING LINE 7", "area_sf": 9215, "floor": "URE-1", "base": "CONC - URETHANE", "walls": "IMP-2"},
    {"room_number": "1405", "name": "CIP ROOM", "area_sf": 501, "floor": "URE-1", "base": "CONC - URETHANE", "walls": "IMP-2"},
    {"room_number": "1406", "name": "ROLL CHILLING LINE 7", "area_sf": 5160, "floor": "URE-1", "base": "CONC - URETHANE", "walls": "IMP-2"},
    {"room_number": "1601", "name": "PACKAGING & PALLETIZING", "area_sf": 10261, "floor": "C/SEAL", "base": "SEALED CONCRETE", "walls": "IMP-1"},
    {"room_number": "1602", "name": "FINISH GOODS COOLER", "area_sf": 11408, "floor": "C/SEAL", "base": "SEALED CONCRETE", "walls": "IMP-1"},
    {"room_number": "1603", "name": "INCLUSION FREEZER", "area_sf": 2453, "floor": "C/SEAL", "base": "SEALED CONCRETE", "walls": "IMP-1"},
    {"room_number": "1604", "name": "SHIPPING DOCK", "area_sf": 4192, "floor": "C/SEAL", "base": "SEALED CONCRETE", "walls": "IMP-1"},
    {"room_number": "1605", "name": "DOCK SUPPORT", "area_sf": 419, "floor": "EPX-1", "base": "EPXB-1", "walls": "PT-1"},
    {"room_number": "1606", "name": "DOCK SUPPORT TOILET", "area_sf": 60, "floor": "EPX-1", "base": "EPXB-1", "walls": "PT-1"},
    {"room_number": "1607", "name": "TRUCKER LOBBY", "area_sf": 261, "floor": "C/SEAL", "base": "EPXB-1", "walls": "PT-1"},
    {"room_number": "1610", "name": "TRUCKER TOILET", "area_sf": 65, "floor": "EPX-1", "base": "EPXB-1", "walls": "PT-1"},
    {"room_number": "2101", "name": "UTILITY CORRIDOR", "area_sf": None, "floor": "CONC", "base": "CONC", "walls": "IMP-1"},
    {"room_number": "2102", "name": "ELECTRICAL ROOM", "area_sf": None, "floor": "CONC", "base": "CONC", "walls": "IMP-1"},
    {"room_number": "2103", "name": "MDF", "area_sf": None, "floor": "ESD-1", "base": "VB-1", "walls": "IMP-1"},
    {"room_number": "2112", "name": "WALK-ON CEILING", "area_sf": None, "floor": "EPX-1", "base": "EPXB-1", "walls": "IMP-1"},
    {"room_number": "2120", "name": "CONFERENCE", "area_sf": None, "floor": "CPT-1", "base": "VB-2", "walls": "PT-7"},
    {"room_number": "2121", "name": "OPEN OFFICE", "area_sf": None, "floor": "CPT-1", "base": "VB-2", "walls": "PT-7"},
    {"room_number": "2122", "name": "OFFICE", "area_sf": None, "floor": "CPT-1", "base": "VB-2", "walls": "PT-7"},
    {"room_number": "2123", "name": "OFFICE", "area_sf": None, "floor": "CPT-1", "base": "VB-2", "walls": "PT-7"},
    {"room_number": "2124", "name": "OFFICE", "area_sf": None, "floor": "CPT-1", "base": "VB-2", "walls": "PT-7"},
    {"room_number": "2125", "name": "OFFICE", "area_sf": None, "floor": "CPT-1", "base": "VB-2", "walls": "PT-7"},
    {"room_number": "2126", "name": "OFFICE", "area_sf": None, "floor": "CPT-1", "base": "VB-2", "walls": "PT-7"},
    {"room_number": "2127", "name": "OFFICE", "area_sf": None, "floor": "CPT-1", "base": "VB-2", "walls": "PT-7"},
]

# Sheet 478: A7001 - Door & Window Types and Schedules
# Extract door and window data

SHEET_478_DOORS_PERSONNEL = [
    {"door_no": "1201A", "type": "G", "width": "3'-0\"", "height": "7'-0\"", "material": "FRP", "glazing": "PCARB", "frame": "F1 SS", "from_room": "EXISTING PROCESS SERVICE HALL", "to_room": "SANITATION ROOM"},
    {"door_no": "1203A", "type": "G", "width": "3'-0\"", "height": "7'-0\"", "material": "FRP", "glazing": "PCARB", "frame": "F1 SS", "from_room": "EXISTING PROCESS SERVICE HALL", "to_room": "UTILITY ROOM"},
    {"door_no": "1401A", "type": "G", "width": "3'-0\"", "height": "7'-0\"", "material": "FRP", "glazing": "PCARB", "frame": "F1 SS", "from_room": "EXISTING PROCESS SERVICE HALL", "to_room": "ROLL PROCESSING LINE 7"},
    {"door_no": "1401C", "type": "G", "width": "3'-0\"", "height": "7'-0\"", "material": "FRP", "glazing": "PCARB", "frame": "F1 SS", "from_room": "EXISTING PROCESS SERVICE HALL", "to_room": "ROLL PROCESSING LINE 7"},
    {"door_no": "1401E", "type": "G", "width": "3'-0\"", "height": "7'-0\"", "material": "FRP", "glazing": "PCARB", "frame": "F1 SS", "from_room": "EXISTING PROCESS SERVICE HALL", "to_room": "ROLL PROCESSING LINE 7"},
    {"door_no": "1405A", "type": "G", "width": "3'-0\"", "height": "7'-0\"", "material": "FRP", "glazing": "PCARB", "frame": "F1 SS", "from_room": "ROLL CHILLING LINE 7", "to_room": "CIP ROOM"},
    {"door_no": "1405B", "type": "G", "width": "3'-0\"", "height": "7'-0\"", "material": "FRP", "glazing": "PCARB", "frame": "F1 SS", "from_room": "ROLL PROCESSING LINE 7", "to_room": "CIP ROOM"},
    {"door_no": "1406A", "type": "G", "width": "3'-0\"", "height": "7'-0\"", "material": "FRP", "glazing": "PCARB", "frame": "F1 SS", "from_room": "EXISTING PROCESS SERVICE HALL", "to_room": "ROLL CHILLING LINE 7"},
    {"door_no": "1406C", "type": "G", "width": "3'-0\"", "height": "7'-0\"", "material": "FRP", "glazing": "PCARB", "frame": "F1 SS", "from_room": "EXISTING PROCESS SERVICE HALL", "to_room": "ROLL CHILLING LINE 7"},
    {"door_no": "1406E", "type": "G", "width": "3'-0\"", "height": "7'-0\"", "material": "FRP", "glazing": "PCARB", "frame": "F1 SS", "from_room": "ROLL CHILLING LINE 7", "to_room": "PACKAGING & PALLETIZING"},
    {"door_no": "1406F", "type": "G", "width": "3'-0\"", "height": "7'-0\"", "material": "FRP", "glazing": "PCARB", "frame": "F1 SS", "from_room": "ROLL CHILLING LINE 7", "to_room": "PACKAGING & PALLETIZING"},
    {"door_no": "1601E", "type": "G", "width": "3'-0\"", "height": "7'-0\"", "material": "FRP", "glazing": "PCARB", "frame": "F1 SS", "from_room": "EXISTING SUPPLY WAREHOUSE", "to_room": "PACKAGING & PALLETIZING"},
    {"door_no": "1601F", "type": "G", "width": "3'-0\"", "height": "7'-0\"", "material": "FRP", "glazing": "PCARB", "frame": "F1 SS", "from_room": "PACKAGING & PALLETIZING", "to_room": "FINISH GOODS COOLER"},
    {"door_no": "1602C", "type": "G", "width": "3'-0\"", "height": "7'-0\"", "material": "FRP", "glazing": "PCARB", "frame": "F1 SS", "from_room": "FINISH GOODS COOLER", "to_room": "SHIPPING DOCK"},
    {"door_no": "1605B", "type": "N", "width": "3'-0\"", "height": "7'-0\"", "material": "FRP", "glazing": "PCARB", "frame": "F1 INS SS", "from_room": "SHIPPING DOCK", "to_room": "DOCK SUPPORT"},
    {"door_no": "1606A", "type": "F", "width": "3'-0\"", "height": "7'-0\"", "material": "HM", "glazing": "N/A", "frame": "F1 HM", "from_room": "DOCK SUPPORT", "to_room": "DOCK SUPPORT TOILET"},
    {"door_no": "1607A", "type": "N", "width": "3'-0\"", "height": "7'-0\"", "material": "HM INS", "glazing": "SAF GLS", "frame": "F1 HM INS", "from_room": "TRUCKER LOBBY", "to_room": "EXTERIOR"},
    {"door_no": "1610A", "type": "F", "width": "3'-0\"", "height": "7'-0\"", "material": "HM", "glazing": "N/A", "frame": "F1 HM", "from_room": "TRUCKER LOBBY", "to_room": "TRUCKER TOILET"},
    {"door_no": "2102A", "type": "F", "width": "3'-0\"", "height": "8'-0\"", "material": "HM", "glazing": "N/A", "frame": "F11 HM", "from_room": None, "to_room": "ELECTRICAL ROOM"},
    {"door_no": "2102B", "type": "N", "width": "3'-0\"", "height": "7'-0\"", "material": "HM", "glazing": "SAF GLS", "frame": "F1 HM", "from_room": None, "to_room": "ELECTRICAL ROOM"},
    {"door_no": "2103A", "type": "N", "width": "3'-0\"", "height": "7'-0\"", "material": "HM", "glazing": "SAF GLS", "frame": "F1 HM", "from_room": "ELECTRICAL ROOM", "to_room": "MDF"},
]

SHEET_478_DOORS_SERVICE = [
    {"door_no": "1111B", "type": "OHC", "width": "12'-0\"", "height": "12'-0\"", "material": "STL", "operation": "ELECTRIC", "comments": "FIRE SHUTTER"},
    {"door_no": "1201B", "type": "RR-V", "width": "10'-0\"", "height": "12'-0\"", "material": "FAB", "operation": "ELECTRIC", "comments": "INTERIOR OPERATION ONLY"},
    {"door_no": "1203B", "type": "RR-V", "width": "16'-0\"", "height": "12'-0\"", "material": "FAB", "operation": "ELECTRIC", "comments": "INTERIOR OPERATION ONLY"},
    {"door_no": "1401B", "type": "RR-V", "width": "10'-0\"", "height": "12'-0\"", "material": "FAB", "operation": "ELECTRIC", "comments": ""},
    {"door_no": "1401D", "type": "RR-V", "width": "10'-0\"", "height": "12'-0\"", "material": "FAB", "operation": "ELECTRIC", "comments": ""},
    {"door_no": "1401F", "type": "RR-V", "width": "10'-0\"", "height": "12'-0\"", "material": "FAB", "operation": "ELECTRIC", "comments": ""},
    {"door_no": "1405C", "type": "RR-V", "width": "10'-0\"", "height": "12'-0\"", "material": "FAB", "operation": "ELECTRIC", "comments": ""},
    {"door_no": "1406B", "type": "RR-V", "width": "10'-0\"", "height": "12'-0\"", "material": "FAB", "operation": "ELECTRIC", "comments": ""},
    {"door_no": "1406D", "type": "RR-V", "width": "10'-0\"", "height": "12'-0\"", "material": "FAB", "operation": "ELECTRIC", "comments": ""},
    {"door_no": "1406G", "type": "RR-V", "width": "10'-0\"", "height": "12'-0\"", "material": "FAB", "operation": "ELECTRIC", "comments": ""},
    {"door_no": "1601D", "type": "RR-V", "width": "10'-0\"", "height": "12'-0\"", "material": "FAB", "operation": "ELECTRIC", "comments": ""},
    {"door_no": "1601G", "type": "RR-V", "width": "10'-0\"", "height": "12'-0\"", "material": "FAB", "operation": "ELECTRIC", "comments": ""},
    {"door_no": "1602A", "type": "IN", "width": "3'-0\"", "height": "7'-0\"", "material": "MFR", "operation": "MANUAL", "comments": "EXTERIOR COOLER"},
    {"door_no": "1602B", "type": "RR-V", "width": "10'-0\"", "height": "12'-0\"", "material": "FAB", "operation": "ELECTRIC", "comments": ""},
    {"door_no": "1602D", "type": "RR-V", "width": "10'-0\"", "height": "12'-0\"", "material": "FAB", "operation": "ELECTRIC", "comments": ""},
    {"door_no": "1603A", "type": "IN", "width": "3'-0\"", "height": "7'-0\"", "material": "MFR", "operation": "MANUAL", "comments": "INTERIOR FREEZER"},
    {"door_no": "1603B", "type": "RR", "width": "10'-0\"", "height": "12'-0\"", "material": "FAB INS", "operation": "ELECTRIC", "comments": "SPOOL PLATE, FORCED AIR CURTAIN"},
    {"door_no": "1603C", "type": "IN", "width": "3'-0\"", "height": "7'-0\"", "material": "MFR", "operation": "MANUAL", "comments": "INTERIOR FREEZER"},
    {"door_no": "1603D", "type": "RR", "width": "10'-0\"", "height": "12'-0\"", "material": "FAB INS", "operation": "ELECTRIC", "comments": "SPOOL PLATE, FORCED AIR CURTAIN"},
    {"door_no": "1604A", "type": "SEC-V", "width": "12'-0\"", "height": "14'-0\"", "material": "STL INS", "operation": "ELECTRIC", "comments": ""},
    {"door_no": "1604B", "type": "SEC-V", "width": "10'-0\"", "height": "11'-3.5\"", "material": "STL INS", "operation": "ELECTRIC", "comments": ""},
    {"door_no": "1604C", "type": "SEC-V", "width": "10'-0\"", "height": "11'-3.5\"", "material": "STL INS", "operation": "ELECTRIC", "comments": ""},
    {"door_no": "1604D", "type": "SEC-V", "width": "10'-0\"", "height": "11'-3.5\"", "material": "STL INS", "operation": "ELECTRIC", "comments": ""},
    {"door_no": "1604E", "type": "SEC-V", "width": "10'-0\"", "height": "11'-3.5\"", "material": "STL INS", "operation": "ELECTRIC", "comments": ""},
    {"door_no": "1604F", "type": "SEC-V", "width": "10'-0\"", "height": "11'-3.5\"", "material": "STL INS", "operation": "ELECTRIC", "comments": ""},
    {"door_no": "1604G", "type": "IN", "width": "3'-0\"", "height": "7'-0\"", "material": "MFR", "operation": "MANUAL", "comments": "EXTERIOR COOLER, DOOR BUZZER"},
]

SHEET_478_WINDOWS = [
    {"type": "W1", "width": "4'-0\"", "height": "2'-10.75\"", "frame": "HM", "glazing": "BULLET RESISTANT", "comments": "ALUMINUM FRAME BULLET RESISTANT INTERIOR WINDOW"},
    {"type": "W3", "width": "7'-0\"", "height": "4'-0\"", "frame": "SS", "glazing": "POLY CARB", "comments": "INTERIOR PROCESS VIEW WINDOWS"},
    {"type": "W4", "width": "4'-0\"", "height": "3'-0\"", "frame": "SS", "glazing": "INSULATED SAFETY GLASS", "comments": "INTERIOR PROCESS VIEW WINDOWS"},
    {"type": "W5", "width": "4'-0\"", "height": "5'-0\"", "frame": "SS", "glazing": "POLY CARB", "comments": "COORDINATE OPENINGS WITH PROCESS EQUIPMENT"},
    {"type": "W7", "width": "7'-6\"", "height": "7'-2\"", "frame": "ALUMINUM", "glazing": "INSULATED SAFETY GLASS", "comments": "SECOND FLOOR INTERIOR OFFICE WINDOWS"},
    {"type": "W8", "width": "7'-0\"", "height": "4'-0\"", "frame": "ALUMINUM", "glazing": "INSULATED SAFETY GLASS", "comments": "EXTERIOR VIEW WINDOW"},
]


def create_tables_if_needed(conn):
    """Create custom tables for architectural data if they don't exist."""

    # Rooms table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS arch_rooms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sheet_id INTEGER NOT NULL,
            room_number TEXT NOT NULL,
            room_name TEXT,
            area_sf REAL,
            floor_finish TEXT,
            base_finish TEXT,
            wall_finish TEXT,
            confidence REAL DEFAULT 0.95,
            FOREIGN KEY (sheet_id) REFERENCES sheets(id),
            UNIQUE(sheet_id, room_number)
        )
    """)

    # Doors table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS arch_doors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sheet_id INTEGER NOT NULL,
            door_number TEXT NOT NULL,
            door_type TEXT,
            width TEXT,
            height TEXT,
            material TEXT,
            glazing TEXT,
            frame_type TEXT,
            from_room TEXT,
            to_room TEXT,
            operation TEXT,
            comments TEXT,
            confidence REAL DEFAULT 0.95,
            FOREIGN KEY (sheet_id) REFERENCES sheets(id),
            UNIQUE(sheet_id, door_number)
        )
    """)

    # Windows table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS arch_windows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sheet_id INTEGER NOT NULL,
            window_type TEXT NOT NULL,
            width TEXT,
            height TEXT,
            frame_material TEXT,
            glazing_type TEXT,
            comments TEXT,
            confidence REAL DEFAULT 0.95,
            FOREIGN KEY (sheet_id) REFERENCES sheets(id),
            UNIQUE(sheet_id, window_type)
        )
    """)

    conn.commit()


def extract_and_load():
    """Extract data from sheets and load into database."""

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")

    try:
        # Create tables if needed
        create_tables_if_needed(conn)

        results = {
            "sheet_476": {"equipment": 0},
            "sheet_477": {"rooms": 0},
            "sheet_478": {"doors_personnel": 0, "doors_service": 0, "windows": 0, "equipment": 0},
            "errors": []
        }

        # Sheet 476: Equipment (bollards, guards)
        print("\n=== Sheet 476: A5061 - Bollard & Guard Details ===")
        for item in SHEET_476_EQUIPMENT:
            try:
                conn.execute("""
                    INSERT OR REPLACE INTO equipment
                    (sheet_id, tag, description, equipment_type, confidence)
                    VALUES (?, ?, ?, ?, ?)
                """, (item["sheet_id"], item["tag"], item["description"],
                      item["equipment_type"], item["confidence"]))
                results["sheet_476"]["equipment"] += 1
                print(f"  ✓ {item['tag']}: {item['description']}")
            except Exception as e:
                error_msg = f"Error inserting equipment {item['tag']}: {e}"
                print(f"  ✗ {error_msg}")
                results["errors"].append(error_msg)

        # Sheet 477: Rooms
        print("\n=== Sheet 477: A6001 - Room Finish Schedule ===")
        for room in SHEET_477_ROOMS:
            try:
                conn.execute("""
                    INSERT OR REPLACE INTO arch_rooms
                    (sheet_id, room_number, room_name, area_sf, floor_finish,
                     base_finish, wall_finish, confidence)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (477, room["room_number"], room["name"], room["area_sf"],
                      room["floor"], room["base"], room["walls"], 0.95))
                results["sheet_477"]["rooms"] += 1
                area_str = f"{room['area_sf']} SF" if room['area_sf'] else "N/A"
                print(f"  ✓ {room['room_number']}: {room['name']} ({area_str})")
            except Exception as e:
                error_msg = f"Error inserting room {room['room_number']}: {e}"
                print(f"  ✗ {error_msg}")
                results["errors"].append(error_msg)

        # Sheet 478: Doors (Personnel)
        print("\n=== Sheet 478: A7001 - Personnel Doors ===")
        for door in SHEET_478_DOORS_PERSONNEL:
            try:
                conn.execute("""
                    INSERT OR REPLACE INTO arch_doors
                    (sheet_id, door_number, door_type, width, height, material,
                     glazing, frame_type, from_room, to_room, confidence)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (478, door["door_no"], door["type"], door["width"],
                      door["height"], door["material"], door["glazing"],
                      door["frame"], door["from_room"], door["to_room"], 0.95))
                results["sheet_478"]["doors_personnel"] += 1
                print(f"  ✓ {door['door_no']}: {door['type']} {door['width']}x{door['height']}")
            except Exception as e:
                error_msg = f"Error inserting door {door['door_no']}: {e}"
                print(f"  ✗ {error_msg}")
                results["errors"].append(error_msg)

        # Sheet 478: Doors (Service)
        print("\n=== Sheet 478: A7001 - Service Doors ===")
        for door in SHEET_478_DOORS_SERVICE:
            try:
                conn.execute("""
                    INSERT OR REPLACE INTO arch_doors
                    (sheet_id, door_number, door_type, width, height, material,
                     operation, comments, confidence)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (478, door["door_no"], door["type"], door["width"],
                      door["height"], door["material"], door["operation"],
                      door["comments"], 0.95))
                results["sheet_478"]["doors_service"] += 1
                print(f"  ✓ {door['door_no']}: {door['type']} {door['width']}x{door['height']}")
            except Exception as e:
                error_msg = f"Error inserting door {door['door_no']}: {e}"
                print(f"  ✗ {error_msg}")
                results["errors"].append(error_msg)

        # Sheet 478: Windows
        print("\n=== Sheet 478: A7001 - Windows ===")
        for window in SHEET_478_WINDOWS:
            try:
                conn.execute("""
                    INSERT OR REPLACE INTO arch_windows
                    (sheet_id, window_type, width, height, frame_material,
                     glazing_type, comments, confidence)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (478, window["type"], window["width"], window["height"],
                      window["frame"], window["glazing"], window["comments"], 0.95))
                results["sheet_478"]["windows"] += 1
                print(f"  ✓ {window['type']}: {window['width']}x{window['height']} - {window['glazing']}")
            except Exception as e:
                error_msg = f"Error inserting window {window['type']}: {e}"
                print(f"  ✗ {error_msg}")
                results["errors"].append(error_msg)

        # Update sheet extraction status
        now = datetime.now().isoformat()
        for sheet_id in [476, 477, 478]:
            conn.execute("""
                UPDATE sheets
                SET extracted_at = ?,
                    extraction_model = 'manual',
                    quality_score = 0.95,
                    complexity = 'medium'
                WHERE id = ?
            """, (now, sheet_id))

        conn.commit()

        # Print summary
        print("\n" + "="*60)
        print("EXTRACTION SUMMARY")
        print("="*60)
        print(f"\nSheet 476 (A5061 - Bollard & Guard Details):")
        print(f"  - Equipment items: {results['sheet_476']['equipment']}")

        print(f"\nSheet 477 (A6001 - Room Finish Schedule):")
        print(f"  - Rooms: {results['sheet_477']['rooms']}")

        print(f"\nSheet 478 (A7001 - Door & Window Types):")
        print(f"  - Personnel doors: {results['sheet_478']['doors_personnel']}")
        print(f"  - Service doors: {results['sheet_478']['doors_service']}")
        print(f"  - Windows: {results['sheet_478']['windows']}")

        total_items = (results['sheet_476']['equipment'] +
                      results['sheet_477']['rooms'] +
                      results['sheet_478']['doors_personnel'] +
                      results['sheet_478']['doors_service'] +
                      results['sheet_478']['windows'])

        print(f"\nTotal items extracted: {total_items}")
        print(f"Average confidence: 0.95")
        print(f"Errors: {len(results['errors'])}")

        if results['errors']:
            print("\nErrors encountered:")
            for error in results['errors']:
                print(f"  - {error}")

        print("\n" + "="*60)

        return results

    except Exception as e:
        conn.rollback()
        print(f"\nFATAL ERROR: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    extract_and_load()
