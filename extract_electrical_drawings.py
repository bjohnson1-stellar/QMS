"""
Extract electrical data from three Freshpet single-line diagrams.
Temporary script for extracting sheets 502, 503, 504.
"""

import sqlite3
from datetime import datetime

# Database path
DB_PATH = r"D:\qms\data\quality.db"

def insert_panel(cursor, data):
    """Insert panel with all fields, using None for missing values"""
    cursor.execute("""
        INSERT INTO electrical_panels (
            sheet_id, panel_name, location, voltage, phases, wires,
            bus_rating, fed_from, enclosure_type, aic_rating,
            total_connected_current, total_demand_current,
            total_connected_kva, total_demand_kva, demand_factor,
            panel_notes, confidence
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.get('sheet_id'),
        data.get('panel_name'),
        data.get('location'),
        data.get('voltage'),
        data.get('phases'),
        data.get('wires'),
        data.get('bus_rating'),
        data.get('fed_from'),
        data.get('enclosure_type'),
        data.get('aic_rating'),
        data.get('total_connected_current'),
        data.get('total_demand_current'),
        data.get('total_connected_kva'),
        data.get('total_demand_kva'),
        data.get('demand_factor'),
        data.get('panel_notes'),
        data.get('confidence', 0.9)
    ))
    return cursor.lastrowid


def insert_equipment(cursor, data):
    """Insert equipment with all fields"""
    cursor.execute("""
        INSERT INTO electrical_equipment (
            sheet_id, tag, equipment_type, location, area,
            voltage, amperage, notes, confidence
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.get('sheet_id'),
        data.get('tag'),
        data.get('equipment_type'),
        data.get('location'),
        data.get('area'),
        data.get('voltage'),
        data.get('amperage'),
        data.get('notes'),
        data.get('confidence', 0.9)
    ))
    return cursor.lastrowid


def insert_circuit(cursor, data):
    """Insert circuit with all fields"""
    cursor.execute("""
        INSERT INTO electrical_circuits (
            panel_id, sheet_id, circuit_number, circuit_description,
            equipment_tag, location, num_poles, breaker_frame, breaker_trip,
            wire_size, conduit_size, load_kva, load_amps, notes, confidence
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.get('panel_id'),
        data.get('sheet_id'),
        data.get('circuit_number'),
        data.get('circuit_description'),
        data.get('equipment_tag'),
        data.get('location'),
        data.get('num_poles'),
        data.get('breaker_frame'),
        data.get('breaker_trip'),
        data.get('wire_size'),
        data.get('conduit_size'),
        data.get('load_kva'),
        data.get('load_amps'),
        data.get('notes'),
        data.get('confidence', 0.9)
    ))
    return cursor.lastrowid


def extract_sheet_502(cursor):
    """E6011 - Main Service (12470V main switchgear)"""

    print(f"\n[Sheet 502] E6011 - MAIN SERVICE Rev.1")
    print("-" * 80)

    panels_count = 0
    equipment_count = 0

    # Main switchgear
    panels = [
        {"sheet_id": 502, "panel_name": "C2-5B-MSG1A", "voltage": "12470V", "phases": 3, "wires": 3,
         "panel_notes": "METER EQUAL TO PM5560, INTEGRAL TVSS, GFP, ST", "confidence": 0.95},
        {"sheet_id": 502, "panel_name": "C2-5B-MSG1B", "voltage": "12470V", "phases": 3, "wires": 3,
         "panel_notes": "METER EQUAL TO PM5560, INTEGRAL TVSS, GFP, ST", "confidence": 0.95},
        {"sheet_id": 502, "panel_name": "C1-4D-SS1A", "voltage": "4160V", "phases": 3, "wires": 3,
         "aic_rating": "100,000 AIC", "panel_notes": "600AF, 250AT", "confidence": 0.95},
        {"sheet_id": 502, "panel_name": "C1-4D-SS1B", "voltage": "4160V", "phases": 3, "wires": 3,
         "aic_rating": "100,000 AIC", "panel_notes": "600AF, 250AT", "confidence": 0.95},
        {"sheet_id": 502, "panel_name": "C1-5D-SS2A", "voltage": "480V", "phases": 3, "wires": 3,
         "panel_notes": "MCB, 600AF, 200AT", "confidence": 0.95},
        {"sheet_id": 502, "panel_name": "C1-5D-SS2B", "voltage": "480V", "phases": 3, "wires": 3,
         "panel_notes": "MCB, 600AF, 200AT", "confidence": 0.95},
        {"sheet_id": 502, "panel_name": "P2-J9-SS3A", "panel_notes": "600AF, 200AT", "confidence": 0.90},
        {"sheet_id": 502, "panel_name": "P2-J9-SS3B", "panel_notes": "600AF, 200AT", "confidence": 0.90},
        {"sheet_id": 502, "panel_name": "P2-J9-SS4A", "panel_notes": "600AF, 200AT", "confidence": 0.90},
        {"sheet_id": 502, "panel_name": "P2-J9-SS4B", "panel_notes": "600AF, 200AT", "confidence": 0.90},
        {"sheet_id": 502, "panel_name": "SS5A", "voltage": "12470V", "panel_notes": "600AF, 200AT", "confidence": 0.90},
        {"sheet_id": 502, "panel_name": "SS5B", "voltage": "12470V", "panel_notes": "600AF, 200AT", "confidence": 0.90},
        {"sheet_id": 502, "panel_name": "SS6A", "voltage": "12470V", "panel_notes": "600AF, 200AT, NEW CHP", "confidence": 0.90},
        {"sheet_id": 502, "panel_name": "SS6B", "voltage": "12470V", "panel_notes": "600AF, 200AT, NEW CHP", "confidence": 0.90},
    ]

    for panel in panels:
        insert_panel(cursor, panel)
        panels_count += 1

    # Equipment - Transformers and Motors
    equipment = [
        {"sheet_id": 502, "tag": "XFMR-SS1A", "equipment_type": "Transformer",
         "voltage": "12470V-4160V", "amperage": "3750KVA", "notes": "EXISTING, 3Ø, 4W, 60Hz", "confidence": 0.95},
        {"sheet_id": 502, "tag": "XFMR-SS1B", "equipment_type": "Transformer",
         "voltage": "12470V-4160V", "amperage": "3750KVA", "notes": "EXISTING, 3Ø, 4W, 60Hz", "confidence": 0.95},
        {"sheet_id": 502, "tag": "CU-HSC-001", "equipment_type": "Motor", "voltage": "5KV",
         "amperage": "800HP", "notes": "EXISTING, 1200A FRAME 175A TRIP", "confidence": 0.95},
        {"sheet_id": 502, "tag": "CU-HSC-002", "equipment_type": "Motor", "voltage": "5KV",
         "amperage": "800HP", "notes": "EXISTING, 1200A FRAME 175A TRIP", "confidence": 0.95},
        {"sheet_id": 502, "tag": "CU-HSC-003", "equipment_type": "Motor", "voltage": "5KV",
         "amperage": "800HP", "notes": "EXISTING, 1200A FRAME 200A TRIP", "confidence": 0.95},
        {"sheet_id": 502, "tag": "CU-HSC-004", "equipment_type": "Motor", "voltage": "5KV",
         "amperage": "800HP", "notes": "EXISTING, 1200A FRAME 175A TRIP", "confidence": 0.95},
        {"sheet_id": 502, "tag": "CU-HSC-005", "equipment_type": "Motor", "voltage": "5KV",
         "amperage": "800HP", "notes": "EXISTING, 1200A FRAME 175A TRIP", "confidence": 0.95},
        {"sheet_id": 502, "tag": "CU-HSC-007", "equipment_type": "Motor", "voltage": "5KV",
         "amperage": "800HP", "notes": "3-#1/0, 1-#6G, 2.5\"C, CL: 98A", "confidence": 0.95},
        {"sheet_id": 502, "tag": "CU-HSC-008", "equipment_type": "Motor", "voltage": "5KV",
         "amperage": "1000HP", "notes": "3-#2/0, 1-#6G, 3\"C, CL: 120A", "confidence": 0.95},
        {"sheet_id": 502, "tag": "CU-HSC-009", "equipment_type": "Motor", "voltage": "5KV",
         "amperage": "1000HP", "notes": "NEW, 3-#2/0, 1-#6G, 3\"C, CL: 120A, 1200A FRAME 225A TRIP", "confidence": 0.95},
        {"sheet_id": 502, "tag": "CU-HSC-010", "equipment_type": "Motor", "voltage": "5KV",
         "amperage": "1000HP", "notes": "NEW, 3-#2/0, 1-#6G, 3\"C, CL: 120A, 1200A FRAME 225A TRIP", "confidence": 0.95},
    ]

    for equip in equipment:
        insert_equipment(cursor, equip)
        equipment_count += 1

    print(f"  >> Extracted {panels_count} panels/switchgear")
    print(f"  >> Extracted {equipment_count} equipment items")

    return panels_count, equipment_count, 0


def extract_sheet_503(cursor):
    """E6101 - Service 1 (4160V substation loads)"""

    print(f"\n[Sheet 503] E6101 - SERVICE 1 Rev.2")
    print("-" * 80)

    panels_count = 0
    equipment_count = 0
    circuits_count = 0

    # Main panel C1-4D-SS1A
    panel_data = {
        "sheet_id": 503,
        "panel_name": "C1-4D-SS1A",
        "location": "CUB SUBSTATION C102",
        "voltage": "4160/2400V",
        "phases": 3,
        "wires": 4,
        "aic_rating": "100,000 AIC",
        "total_connected_current": 240.0,
        "total_demand_current": 168.0,
        "total_connected_kva": 1729.3,
        "total_demand_kva": 1210.0,
        "demand_factor": 0.70,
        "panel_notes": "EXISTING PANEL. NEW BREAKERS AS SHOWN.",
        "confidence": 0.95
    }

    panel_id = insert_panel(cursor, panel_data)
    panels_count += 1

    # Equipment
    equipment_list = [
        {"sheet_id": 503, "tag": "CU-EC-009", "equipment_type": "Equipment",
         "location": "AMMONIA ENGINE RM C100", "voltage": "4160V", "amperage": "250A",
         "notes": "3Ø, 250AF, 225AT, 3-#2/0, 1-#4G, 3\"C, 864.6 kVA", "confidence": 0.95},
        {"sheet_id": 503, "tag": "CU-EC-010", "equipment_type": "Equipment",
         "location": "AMMONIA ENGINE RM C100", "voltage": "4160V", "amperage": "250A",
         "notes": "3Ø, 250AF, 225AT, 3-#2/0, 1-#4G, 3\"C, 864.6 kVA", "confidence": 0.95},
    ]

    for equip in equipment_list:
        insert_equipment(cursor, equip)
        equipment_count += 1

    # Circuits
    circuit_list = [
        {"panel_id": panel_id, "sheet_id": 503, "circuit_number": "6",
         "circuit_description": "CU-EC-009 - AMMONIA ENGINE RM C100", "equipment_tag": "CU-EC-009",
         "num_poles": 3, "breaker_frame": 250, "breaker_trip": 225,
         "wire_size": "3-#2/0, 1-#4G, 3\"C", "load_kva": 864.6, "confidence": 0.95},
        {"panel_id": panel_id, "sheet_id": 503, "circuit_number": "7",
         "circuit_description": "CU-EC-010 - AMMONIA ENGINE RM C100", "equipment_tag": "CU-EC-010",
         "num_poles": 3, "breaker_frame": 250, "breaker_trip": 225,
         "wire_size": "3-#2/0, 1-#4G, 3\"C", "load_kva": 864.6, "confidence": 0.95},
    ]

    for circuit in circuit_list:
        insert_circuit(cursor, circuit)
        circuits_count += 1

    print(f"  >> Extracted {panels_count} panel")
    print(f"  >> Extracted {equipment_count} equipment items")
    print(f"  >> Extracted {circuits_count} circuits")

    return panels_count, equipment_count, circuits_count


def extract_sheet_504(cursor):
    """E6201 - Service 2 (480V substation loads)"""

    print(f"\n[Sheet 504] E6201 - SERVICE 2 Rev.1")
    print("-" * 80)

    panels_count = 0
    equipment_count = 0
    circuits_count = 0

    # Main panels with load calculations
    panels_list = [
        {"sheet_id": 504, "panel_name": "C1-5D-SS2A", "voltage": "480V", "phases": 3, "wires": 3,
         "enclosure_type": "MCB", "panel_notes": "METER PM5560, TVSS, GFP, ST", "confidence": 0.95},
        {"sheet_id": 504, "panel_name": "C1-5D-SS2B", "voltage": "480V", "phases": 3, "wires": 3,
         "enclosure_type": "MCB", "panel_notes": "METER PM5560, TVSS, GFP, ST", "confidence": 0.95},
        {"sheet_id": 504, "panel_name": "C2-D4-MCC5", "location": "CUB SUBSTATION C102",
         "voltage": "480V", "phases": 3, "wires": 3, "bus_rating": "800A MLO",
         "fed_from": "C1-5D-SS2A", "enclosure_type": "NEMA 12", "aic_rating": "65,000 AIC",
         "total_connected_current": 460.0, "total_demand_current": 322.0,
         "total_connected_kva": 382.4, "total_demand_kva": 268.0, "demand_factor": 0.70,
         "panel_notes": "800A HORIZ, 300A VERT", "confidence": 0.95},
        {"sheet_id": 504, "panel_name": "C1-E5-RP02", "location": "CUB SUBSTATION C102",
         "voltage": "208/120V", "phases": 3, "wires": 4, "bus_rating": "225A MCB",
         "enclosure_type": "TYPE 1", "aic_rating": "10,000 AIC",
         "total_connected_current": 26.0, "total_demand_current": 18.0,
         "total_connected_kva": 9.0, "total_demand_kva": 7.0, "demand_factor": 0.70,
         "panel_notes": "EXISTING, SURFACE MOUNT", "confidence": 0.95},
        {"sheet_id": 504, "panel_name": "C1-C4-2DP01", "voltage": "480V", "bus_rating": "1200A MLO",
         "aic_rating": "65,000 AIC", "panel_notes": "1200AF, 1200AT", "confidence": 0.90},
        {"sheet_id": 504, "panel_name": "C1-C5-2DP03", "voltage": "480V", "bus_rating": "1200A MLO",
         "aic_rating": "65,000 AIC", "panel_notes": "1200AF, 1200AT", "confidence": 0.90},
        {"sheet_id": 504, "panel_name": "C1-C5-2DP04", "voltage": "480V", "bus_rating": "1200A MLO",
         "aic_rating": "65,000 AIC", "panel_notes": "1200AF, 1200AT", "confidence": 0.90},
        {"sheet_id": 504, "panel_name": "C1-D5-2DP07", "voltage": "480V", "bus_rating": "1200A MLO",
         "aic_rating": "65,000 AIC", "panel_notes": "1200AF, 1200AT", "confidence": 0.90},
        {"sheet_id": 504, "panel_name": "C1-D5-2DP08", "voltage": "480V", "bus_rating": "1200A MLO",
         "aic_rating": "14,000 AIC", "panel_notes": "1200AF, 600AT", "confidence": 0.90},
        {"sheet_id": 504, "panel_name": "C2-D4-MCC1", "voltage": "480V", "bus_rating": "MLO",
         "aic_rating": "65,000 AIC", "panel_notes": "1200AF, 800AT", "confidence": 0.90},
        {"sheet_id": 504, "panel_name": "C2-D4-MCC2", "panel_notes": "1200AF, 800AT", "confidence": 0.90},
        {"sheet_id": 504, "panel_name": "C2-D3-MCC3", "panel_notes": "1200AF, 400AT", "confidence": 0.90},
        {"sheet_id": 504, "panel_name": "C2-D3-MCC4", "panel_notes": "1200AF, 400AT", "confidence": 0.90},
        {"sheet_id": 504, "panel_name": "CU-CPR-001", "panel_notes": "1200AF, 600AT", "confidence": 0.90},
        {"sheet_id": 504, "panel_name": "CU-CPR-002", "panel_notes": "1200AF, 600AT", "confidence": 0.90},
        {"sheet_id": 504, "panel_name": "CU-CPR-003", "panel_notes": "1200AF, 600AT", "confidence": 0.90},
    ]

    panel_map = {}
    for panel in panels_list:
        panel_id = insert_panel(cursor, panel)
        panel_map[panel['panel_name']] = panel_id
        panels_count += 1

    # Equipment - Transformers, UPS, Pumps
    equipment_list = [
        {"sheet_id": 504, "tag": "SS-5A", "equipment_type": "Transformer",
         "voltage": "12470V-480V", "amperage": "3000KVA", "notes": "3Ø, 3W, 60Hz", "confidence": 0.95},
        {"sheet_id": 504, "tag": "SS-5B", "equipment_type": "Transformer",
         "voltage": "12470V-480V", "amperage": "3000KVA", "notes": "3Ø, 3W, 60Hz", "confidence": 0.95},
        {"sheet_id": 504, "tag": "T-RP02", "equipment_type": "Transformer",
         "voltage": "480V-208/120V", "amperage": "75KVA", "notes": "3Ø", "confidence": 0.95},
        {"sheet_id": 504, "tag": "C2-C3-UPS", "equipment_type": "UPS",
         "voltage": "480/277V-208/120V", "amperage": "30KVA", "notes": "3Ø", "confidence": 0.95},
        {"sheet_id": 504, "tag": "CU-PUMP-011", "equipment_type": "Pump",
         "location": "AMMONIA ENGINE RM C100", "amperage": "40HP",
         "notes": "VFD, 100A, 3-#3, 1-#8G, 2\"C, 43.2 kVA", "confidence": 0.95},
        {"sheet_id": 504, "tag": "CU-PUMP-012", "equipment_type": "Pump",
         "location": "AMMONIA ENGINE RM C100", "amperage": "40HP",
         "notes": "VFD, 100A, 3-#3, 1-#8G, 2\"C, 43.2 kVA", "confidence": 0.95},
        {"sheet_id": 504, "tag": "CU-PUMP-013", "equipment_type": "Pump",
         "location": "AMMONIA ENGINE RM C100", "amperage": "40HP",
         "notes": "VFD, 100A, 3-#3, 1-#8G, 2\"C, 43.2 kVA", "confidence": 0.95},
        {"sheet_id": 504, "tag": "CU-PUMP-014", "equipment_type": "Pump",
         "location": "AMMONIA ENGINE RM C100", "amperage": "40HP",
         "notes": "VFD, 100A, 3-#3, 1-#8G, 2\"C, 43.2 kVA", "confidence": 0.95},
        {"sheet_id": 504, "tag": "CU-EC-006", "equipment_type": "Equipment",
         "notes": "6 VFD circuits, 15HP ea, 45A, 17.5 kVA ea", "confidence": 0.90},
        {"sheet_id": 504, "tag": "CU-EC-007", "equipment_type": "Equipment",
         "notes": "6 VFD circuits, 15HP ea, 45A, 17.5 kVA ea", "confidence": 0.90},
        {"sheet_id": 504, "tag": "CU-RFH-002", "equipment_type": "Heater",
         "notes": "20A, 0.6 kVA", "confidence": 0.90},
    ]

    for equip in equipment_list:
        insert_equipment(cursor, equip)
        equipment_count += 1

    # Circuits for MCC5
    mcc5_id = panel_map.get("C2-D4-MCC5")
    if mcc5_id:
        mcc5_circuits = [
            ("1", "CU-PUMP-011 - AMMONIA ENGINE RM C100", "CU-PUMP-011", 100, "3-#3, 1-#8G, 2\"C", 43.2),
            ("2", "CU-PUMP-012 - AMMONIA ENGINE RM C100", "CU-PUMP-012", 100, "3-#3, 1-#8G, 2\"C", 43.2),
            ("3", "CU-PUMP-013 - AMMONIA ENGINE RM C100", "CU-PUMP-013", 100, "3-#3, 1-#8G, 2\"C", 43.2),
            ("4", "CU-PUMP-014 - AMMONIA ENGINE RM C100", "CU-PUMP-014", 100, "3-#3, 1-#8G, 2\"C", 43.2),
            ("5", "CU-EC-006 CKT3", "CU-EC-006", 45, "3-#8, 1-#10G, 1.25\"C", 17.5),
            ("6", "CU-EC-006 CKT2", "CU-EC-006", 45, "3-#8, 1-#10G, 1.25\"C", 17.5),
            ("7", "CU-EC-006 CKT1", "CU-EC-006", 45, "3-#8, 1-#10G, 1.25\"C", 17.5),
            ("8", "CU-EC-006 CKT4", "CU-EC-006", 45, "3-#8, 1-#10G, 1.25\"C", 17.5),
            ("9", "CU-EC-006 CKT5", "CU-EC-006", 45, "3-#8, 1-#10G, 1.25\"C", 17.5),
            ("10", "CU-EC-006 CKT6", "CU-EC-006", 45, "3-#8, 1-#10G, 1.25\"C", 17.5),
            ("11", "CU-EC-007 CKT3", "CU-EC-007", 45, "3-#8, 1-#10G, 1.25\"C", 17.5),
            ("12", "CU-EC-007 CKT2", "CU-EC-007", 45, "3-#8, 1-#10G, 1.25\"C", 17.5),
            ("13", "CU-EC-007 CKT1", "CU-EC-007", 45, "3-#8, 1-#10G, 1.25\"C", 17.5),
            ("14", "CU-EC-007 CKT4", "CU-EC-007", 45, "3-#8, 1-#10G, 1.25\"C", 17.5),
            ("15", "CU-EC-007 CKT5", "CU-EC-007", 45, "3-#8, 1-#10G, 1.25\"C", 17.5),
            ("16", "CU-EC-007 CKT6", "CU-EC-007", 45, "3-#8, 1-#10G, 1.25\"C", 17.5),
        ]

        for ckt_num, desc, equip_tag, trip, wire, kva in mcc5_circuits:
            circuit_data = {
                "panel_id": mcc5_id,
                "sheet_id": 504,
                "circuit_number": ckt_num,
                "circuit_description": desc,
                "equipment_tag": equip_tag,
                "breaker_trip": trip,
                "wire_size": wire,
                "load_kva": kva,
                "confidence": 0.95
            }
            insert_circuit(cursor, circuit_data)
            circuits_count += 1

    # Circuits for panel RP02
    rp02_id = panel_map.get("C1-E5-RP02")
    if rp02_id:
        rp02_circuits = [
            ("1", "HEAT TRACE", 30, 1.4),
            ("3", "HEAT TRACE", 30, 1.4),
            ("5", "HEAT TRACE", 30, 1.0),
            ("59", "CU-RFH-002", 20, 0.6),
            ("61", "SUH-1, SUH-2 - AMMONIA ENGINE RM C100", 20, 1.1),
            ("63", "SUH-3, SUH-4 - AMMONIA ENGINE RM C100", 20, 1.1),
            ("65", "HEAT TRACE", 30, 1.4),
            ("67", "HEAT TRACE", 30, 1.4),
        ]

        for ckt_num, desc, trip, kva in rp02_circuits:
            circuit_data = {
                "panel_id": rp02_id,
                "sheet_id": 504,
                "circuit_number": ckt_num,
                "circuit_description": desc,
                "breaker_trip": trip,
                "load_kva": kva,
                "confidence": 0.90
            }
            insert_circuit(cursor, circuit_data)
            circuits_count += 1

    print(f"  >> Extracted {panels_count} panels")
    print(f"  >> Extracted {equipment_count} equipment items")
    print(f"  >> Extracted {circuits_count} circuits")

    return panels_count, equipment_count, circuits_count


def main():
    """Main extraction and database insertion"""

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        print("=" * 80)
        print("ELECTRICAL DRAWING EXTRACTION - PROJECT 07609 FRESHPET")
        print("=" * 80)

        # Track totals
        total_panels = 0
        total_equipment = 0
        total_circuits = 0

        # Extract all sheets
        p, e, c = extract_sheet_502(cursor)
        total_panels += p
        total_equipment += e
        total_circuits += c

        p, e, c = extract_sheet_503(cursor)
        total_panels += p
        total_equipment += e
        total_circuits += c

        p, e, c = extract_sheet_504(cursor)
        total_panels += p
        total_equipment += e
        total_circuits += c

        # Update sheets table with extraction metadata
        now = datetime.now().isoformat()
        for sheet_id in [502, 503, 504]:
            cursor.execute("""
                UPDATE sheets
                SET extracted_at = ?,
                    extraction_model = 'sonnet-4.5',
                    quality_score = 0.92,
                    complexity = 'medium'
                WHERE id = ?
            """, (now, sheet_id))

        conn.commit()

        # Summary
        print("\n" + "=" * 80)
        print("EXTRACTION SUMMARY")
        print("=" * 80)
        print(f"Total Panels/Switchgear: {total_panels}")
        print(f"Total Equipment:         {total_equipment}")
        print(f"Total Circuits:          {total_circuits}")
        print(f"\nQuality Score:           0.92")
        print(f"Extraction Model:        Sonnet 4.5")
        print(f"Extraction Time:         {now}")
        print("\n>> All data successfully loaded to database")

        # Verification queries
        print("\n" + "=" * 80)
        print("VERIFICATION QUERIES")
        print("=" * 80)

        # Count by sheet
        print("\nRecords by Sheet:")
        for sheet_id in [502, 503, 504]:
            cursor.execute("SELECT drawing_number, revision FROM sheets WHERE id = ?", (sheet_id,))
            sheet = cursor.fetchone()

            cursor.execute("SELECT COUNT(*) FROM electrical_panels WHERE sheet_id = ?", (sheet_id,))
            panel_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM electrical_equipment WHERE sheet_id = ?", (sheet_id,))
            equip_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM electrical_circuits WHERE sheet_id = ?", (sheet_id,))
            circuit_count = cursor.fetchone()[0]

            print(f"  {sheet[0]} Rev.{sheet[1]}: "
                  f"{panel_count} panels, {equip_count} equipment, {circuit_count} circuits")

        # Sample panel list
        print("\nExtracted Panels (sample):")
        cursor.execute("""
            SELECT s.drawing_number, p.panel_name, p.voltage, p.aic_rating
            FROM electrical_panels p
            JOIN sheets s ON p.sheet_id = s.id
            WHERE s.id IN (502, 503, 504)
            ORDER BY s.id, p.panel_name
            LIMIT 15
        """)
        for row in cursor.fetchall():
            print(f"  {row[0]}: {row[1]:20s} ({row[2] or 'N/A':15s}, {row[3] or 'N/A'})")

        print("\n" + "=" * 80)
        print("SUCCESS - Extraction complete!")
        print("=" * 80)

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    main()
