"""
Manual extraction results for Freshpet refrigeration drawings.
Based on visual analysis of the three PDFs.
"""

import json
from datetime import datetime
from qms.core import get_db, get_logger

logger = get_logger("extraction.freshpet")

# =============================================================================
# R4110.1 - MACHINE ROOM FLOOR PLAN
# =============================================================================

R4110_DATA = {
    "sheet_id": 607,
    "drawing_number": "R4110.1",
    "title": "REFRIGERATION PLAN - MACHINE ROOM PIPE AND EQUIPMENT - FLOOR",
    "drawing_type": "P&ID",
    "complexity": "high",

    "lines": [
        # Cooling Tower and Condenser Water Lines
        {"line_number": "CU-HSC-009", "size": "2", "material": "ES", "service": "Condenser Water", "confidence": 0.95},
        {"line_number": "CU-HSC-010", "size": None, "material": None, "service": "Condenser Water", "confidence": 0.90},
        {"line_number": "16\" TWR", "size": "16", "material": None, "service": "Tower Water Return", "confidence": 0.90},
        {"line_number": "4\" TSR", "size": "4", "material": None, "service": "Tower Supply Return", "confidence": 0.85},
        {"line_number": "3\" TSS", "size": "3", "material": None, "service": "Tower Supply", "confidence": 0.85},
    ],

    "equipment": [
        # Main Equipment visible on floor plan
        {"tag": "P10", "description": "Pump", "equipment_type": "Pump", "confidence": 0.95},
        {"tag": "P11", "description": "Pump", "equipment_type": "Pump", "confidence": 0.95},
        {"tag": "C6", "description": "Compressor", "equipment_type": "Compressor", "confidence": 0.95},
        {"tag": "C7", "description": "Compressor", "equipment_type": "Compressor", "confidence": 0.95},
        {"tag": "CD", "description": "Condenser", "equipment_type": "Condenser", "confidence": 0.90},
        {"tag": "CE", "description": "Condenser", "equipment_type": "Condenser", "confidence": 0.90},
    ],

    "instruments": [
        # Area designations visible
        {"tag": "14.3", "instrument_type": "Area Designation", "service": "Zone marking", "confidence": 0.85},
        {"tag": "14.5", "instrument_type": "Area Designation", "service": "Zone marking", "confidence": 0.85},
        {"tag": "15.1", "instrument_type": "Area Designation", "service": "Zone marking", "confidence": 0.85},
    ],

    "notes": [
        "ROUTING TO BE ADJUSTED",
        "Complex machine room layout with multiple compressors and vessels",
        "Magenta/pink highlighted piping indicates new or modified routing"
    ]
}

# =============================================================================
# R4140.1 - MACHINE ROOM ROOF PLAN
# =============================================================================

R4140_DATA = {
    "sheet_id": 608,
    "drawing_number": "R4140.1",
    "title": "REFRIGERATION PLAN - MACHINE ROOM PIPE AND EQUIPMENT - ROOF",
    "drawing_type": "P&ID",
    "complexity": "medium",

    "lines": [
        # Roof level piping (highlighted in green/yellow)
        {"line_number": "CU-EC-006", "size": "4", "material": "HSD", "service": "Condensate/Drainage", "confidence": 0.90},
        {"line_number": "16\" CRWR", "size": "16", "material": None, "service": "Cooling Water Return", "confidence": 0.85},
    ],

    "equipment": [
        # Equipment visible on roof plan
        {"tag": "P10", "description": "Pump (roof penetration)", "equipment_type": "Pump", "confidence": 0.90},
        {"tag": "P11", "description": "Pump (roof penetration)", "equipment_type": "Pump", "confidence": 0.90},
        {"tag": "P12", "description": "Pump (roof penetration)", "equipment_type": "Pump", "confidence": 0.90},
        {"tag": "C6", "description": "Compressor (roof penetration)", "equipment_type": "Compressor", "confidence": 0.90},
        {"tag": "C7", "description": "Compressor (roof penetration)", "equipment_type": "Compressor", "confidence": 0.90},
        {"tag": "CD", "description": "Condenser (roof level)", "equipment_type": "Condenser", "confidence": 0.90},
        {"tag": "CE", "description": "Condenser (roof level)", "equipment_type": "Condenser", "confidence": 0.90},
    ],

    "instruments": [
        {"tag": "14.3", "instrument_type": "Area Designation", "service": "Zone marking", "confidence": 0.85},
        {"tag": "14.5", "instrument_type": "Area Designation", "service": "Zone marking", "confidence": 0.85},
        {"tag": "15.1", "instrument_type": "Area Designation", "service": "Zone marking", "confidence": 0.85},
        {"tag": "15.2", "instrument_type": "Area Designation", "service": "Zone marking", "confidence": 0.85},
        {"tag": "15.4", "instrument_type": "Area Designation", "service": "Zone marking", "confidence": 0.85},
    ],

    "notes": [
        "Roof-level piping shown in green/yellow highlighting",
        "Shows routing over machine room",
        "Coordinates with floor plan R4110.1"
    ]
}

# =============================================================================
# R4510.1 - MACHINE ROOM RELIEF PIPE FLOOR
# =============================================================================

R4510_DATA = {
    "sheet_id": 609,
    "drawing_number": "R4510.1",
    "title": "REFRIGERATION - MACHINE ROOM RELIEF PIPE - FLOOR",
    "drawing_type": "Relief System",
    "complexity": "medium",

    "lines": [
        # Relief piping from schedules
        {"line_number": "CU-HSC-008", "size": None, "material": None, "service": "Relief/Safety", "confidence": 0.85},
        {"line_number": "CU-HSC-009", "size": None, "material": None, "service": "Relief/Safety", "confidence": 0.90},
        {"line_number": "CU-HSC-010", "size": None, "material": None, "service": "Relief/Safety", "confidence": 0.90},
    ],

    "equipment": [
        # Relief valves from schedule
        {"tag": "PR01", "description": "Relief Valve - CU-REC-002", "equipment_type": "Relief Valve", "confidence": 0.95},
        {"tag": "PR02", "description": "Relief Valve - CU-REC-002", "equipment_type": "Relief Valve", "confidence": 0.95},
        {"tag": "PR03", "description": "Relief Valve - CU-REC-001", "equipment_type": "Relief Valve", "confidence": 0.95},
        {"tag": "PR04", "description": "Relief Valve - CPNL", "equipment_type": "Relief Valve", "confidence": 0.95},
        {"tag": "PR05", "description": "Relief Valve - CPNL", "equipment_type": "Relief Valve", "confidence": 0.95},
        {"tag": "PR06", "description": "Relief Valve - CPNL", "equipment_type": "Relief Valve", "confidence": 0.95},
        {"tag": "PR07", "description": "Relief Valve - MPNL", "equipment_type": "Relief Valve", "confidence": 0.95},
    ],

    "instruments": [
        # From valve schedule - pressure relief valves
        {"tag": "PR01", "instrument_type": "Pressure Relief Valve", "service": "Vessel CU-REC-002", "location": "Vessel", "confidence": 0.95},
        {"tag": "PR02", "instrument_type": "Pressure Relief Valve", "service": "Vessel CU-REC-002", "location": "Vessel", "confidence": 0.95},
        {"tag": "PR03", "instrument_type": "Pressure Relief Valve", "service": "Vessel CU-REC-001", "location": "Vessel", "confidence": 0.95},
        {"tag": "PR04", "instrument_type": "Pressure Relief Valve", "service": "Panel CPNL", "location": "Panel", "confidence": 0.95},
        {"tag": "PR05", "instrument_type": "Pressure Relief Valve", "service": "Panel CPNL", "location": "Panel", "confidence": 0.95},
        {"tag": "PR06", "instrument_type": "Pressure Relief Valve", "service": "Panel CPNL", "location": "Panel", "confidence": 0.95},
        {"tag": "PR07", "instrument_type": "Pressure Relief Valve", "service": "Panel MPNL", "location": "Panel", "confidence": 0.95},
    ],

    "notes": [
        "Contains valve schedules for existing, piping calculations, and piping schedule Phase 2A",
        "Shows relief valve locations and routing to relief header",
        "Multiple relief valves protecting vessels and panels",
        "Relief system design per ASHRAE 15 and IIAR 2"
    ]
}


def save_extraction_to_db(data: dict):
    """Save extracted data to database."""
    sheet_id = data["sheet_id"]

    with get_db() as conn:
        # Update sheet metadata
        conn.execute("""
            UPDATE sheets
            SET drawing_type = ?,
                complexity = ?,
                extracted_at = ?,
                extraction_model = 'claude-sonnet-4.5',
                quality_score = ?
            WHERE id = ?
        """, (
            data["drawing_type"],
            data["complexity"],
            datetime.now().isoformat(),
            calculate_quality_score(data),
            sheet_id
        ))

        # Clear existing extractions for this sheet
        conn.execute("DELETE FROM lines WHERE sheet_id = ?", (sheet_id,))
        conn.execute("DELETE FROM equipment WHERE sheet_id = ?", (sheet_id,))
        conn.execute("DELETE FROM instruments WHERE sheet_id = ?", (sheet_id,))
        conn.execute("DELETE FROM extraction_notes WHERE sheet_id = ?", (sheet_id,))

        # Insert lines
        for line in data.get("lines", []):
            conn.execute("""
                INSERT INTO lines (
                    sheet_id, line_number, size, material,
                    service, from_location, to_location, confidence
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                sheet_id,
                line.get("line_number"),
                line.get("size"),
                line.get("material"),
                line.get("service"),
                line.get("from_location"),
                line.get("to_location"),
                line.get("confidence", 0.8)
            ))

        # Insert equipment
        for equip in data.get("equipment", []):
            conn.execute("""
                INSERT INTO equipment (
                    sheet_id, tag, description, equipment_type, confidence
                ) VALUES (?, ?, ?, ?, ?)
            """, (
                sheet_id,
                equip.get("tag"),
                equip.get("description"),
                equip.get("equipment_type"),
                equip.get("confidence", 0.8)
            ))

        # Insert instruments
        for inst in data.get("instruments", []):
            conn.execute("""
                INSERT INTO instruments (
                    sheet_id, tag, instrument_type, service,
                    location, confidence, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                sheet_id,
                inst.get("tag"),
                inst.get("instrument_type"),
                inst.get("service"),
                inst.get("location"),
                inst.get("confidence", 0.8),
                datetime.now().isoformat()
            ))

        # Insert notes
        for note in data.get("notes", []):
            conn.execute("""
                INSERT INTO extraction_notes (
                    sheet_id, note_type, description, created_at
                ) VALUES (?, ?, ?, ?)
            """, (
                sheet_id,
                "general",
                note,
                datetime.now().isoformat()
            ))

        conn.commit()
        logger.info(f"Saved sheet {sheet_id} ({data['drawing_number']}) to database")


def calculate_quality_score(data: dict) -> float:
    """Calculate quality score based on confidence and item counts."""
    total_items = 0
    total_confidence = 0.0

    for category in ["lines", "equipment", "instruments"]:
        items = data.get(category, [])
        for item in items:
            total_items += 1
            total_confidence += item.get("confidence", 0.7)

    if total_items == 0:
        return 0.5

    avg_confidence = total_confidence / total_items

    # Bonus for having all three categories
    categories_present = sum(1 for cat in ["lines", "equipment", "instruments"]
                            if len(data.get(cat, [])) > 0)
    completeness = categories_present / 3.0

    return (avg_confidence * 0.7) + (completeness * 0.3)


def main():
    """Process all three drawings."""
    drawings = [R4110_DATA, R4140_DATA, R4510_DATA]

    print("=" * 80)
    print("FRESHPET REFRIGERATION DRAWING EXTRACTION")
    print("Project: 07609-Freshpet")
    print("=" * 80)
    print()

    for data in drawings:
        print(f"Processing: {data['drawing_number']} - {data['title']}")
        print(f"  Sheet ID: {data['sheet_id']}")
        print(f"  Type: {data['drawing_type']}")
        print(f"  Complexity: {data['complexity']}")
        print(f"  Lines: {len(data.get('lines', []))}")
        print(f"  Equipment: {len(data.get('equipment', []))}")
        print(f"  Instruments: {len(data.get('instruments', []))}")
        print(f"  Quality Score: {calculate_quality_score(data):.2f}")
        print()

        try:
            save_extraction_to_db(data)
            print(f"  Status: SUCCESS - Saved to database")
        except Exception as e:
            logger.error(f"Failed to save {data['drawing_number']}: {e}")
            print(f"  Status: FAILED - {e}")

        print()

    print("=" * 80)
    print("EXTRACTION COMPLETE")
    print("=" * 80)
    print()

    # Summary query
    with get_db(readonly=True) as conn:
        print("Database Summary:")
        for sheet_id in [607, 608, 609]:
            row = conn.execute("""
                SELECT drawing_number,
                       (SELECT COUNT(*) FROM lines WHERE sheet_id = ?) as lines,
                       (SELECT COUNT(*) FROM equipment WHERE sheet_id = ?) as equipment,
                       (SELECT COUNT(*) FROM instruments WHERE sheet_id = ?) as instruments,
                       quality_score
                FROM sheets WHERE id = ?
            """, (sheet_id, sheet_id, sheet_id, sheet_id)).fetchone()

            if row:
                print(f"  {row[0]}: {row[1]} lines, {row[2]} equipment, "
                      f"{row[3]} instruments, quality={row[4]:.2f}")


if __name__ == "__main__":
    main()
