"""
Extract structured data from Freshpet utility drawings U4001, U4002, U4003.
Sheet IDs: 695, 696, 697
"""

import sqlite3
from datetime import datetime

# Database connection
db_path = r"D:\qms\data\quality.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Extraction timestamp
extracted_at = datetime.now().isoformat()
extraction_model = "sonnet-4.5"

# Common piping systems across all three drawings
common_piping = [
    # Existing piping (marked with E prefix)
    {"line_number": "E6\"-CA", "size": "6\"", "material": None, "service": "CA", "spec_class": None},
    {"line_number": "E8\"-PCW", "size": "8\"", "material": None, "service": "PCW", "spec_class": None},
    {"line_number": "E6\"-DCW", "size": "6\"", "material": None, "service": "DCW", "spec_class": None},
    {"line_number": "E4\"-PC", "size": "4\"", "material": None, "service": "PC", "spec_class": None},
    {"line_number": "E2\"-HPC", "size": "2\"", "material": None, "service": "HPC", "spec_class": None},
    {"line_number": "E10\"-HPS", "size": "10\"", "material": None, "service": "HPS", "spec_class": None},
    {"line_number": "E6\"-NG", "size": "6\"", "material": None, "service": "NG", "spec_class": None},

    # Future piping
    {"line_number": "6\"-PHPHWS (FUTURE)", "size": "6\"", "material": None, "service": "PHPHWS", "spec_class": None},
    {"line_number": "6\"-CSW (FUTURE)", "size": "6\"", "material": None, "service": "CSW", "spec_class": None},
    {"line_number": "6\"-PHSW (FUTURE)", "size": "6\"", "material": None, "service": "PHSW", "spec_class": None},

    # Sanitary and foam lines
    {"line_number": "2\"-FOAM", "size": "2\"", "material": None, "service": "FOAM", "spec_class": None},
    {"line_number": "2\"-SANI", "size": "2\"", "material": None, "service": "SANI", "spec_class": None},
]

# Sheet-specific data
sheet_data = {
    695: {  # U4001
        "sheet_id": 695,
        "drawing_type": "Utility Plan",
        "complexity": "medium",
        "quality_score": 0.90,
        "additional_lines": [],
        "equipment": [],
        "notes": [
            {"note_type": "general", "note_text": "SEE U4321 FOR CONTINUATION"},
            {"note_type": "general", "note_text": "SEE U4002 FOR CONTINUATION"},
            {"note_type": "installation", "note_text": "ALL EXTERIOR ROUTED SANI AND FOAM PIPING SHALL BE HEAT TRACED, INSULATED AND JACKETED"},
        ]
    },
    696: {  # U4002
        "sheet_id": 696,
        "drawing_type": "Utility Plan",
        "complexity": "medium",
        "quality_score": 0.88,
        "additional_lines": [
            {"line_number": "4\"-HPS", "size": "4\"", "material": None, "service": "HPS", "spec_class": None},
            {"line_number": "6\"-PCW", "size": "6\"", "material": None, "service": "PCW", "spec_class": None},
            {"line_number": "4\"-NG", "size": "4\"", "material": None, "service": "NG", "spec_class": None},
            {"line_number": "E3/4\"-STEAM MAIN TRAP", "size": "3/4\"", "material": None, "service": "STEAM", "spec_class": None},
        ],
        "equipment": [
            {"tag": "CV-4", "equipment_type": "Control Valve", "description": None, "location": "Pipe bridge area"},
        ],
        "notes": [
            {"note_type": "general", "note_text": "SEE U4001 FOR CONTINUATION"},
            {"note_type": "general", "note_text": "SEE U4003 FOR CONTINUATION"},
            {"note_type": "dimension", "note_text": "17'-10 3/4\" BOP SERVICES (12 TYPICAL)"},
            {"note_type": "installation", "note_text": "2\" SANI CONCENTRATE SUPPORTED ON PIPE BRIDGE HEAT TRACED AND INSULATED ALONG FULL EXTERIOR LENGTH FROM CUB TO PHASE 2A ENTRY POINT"},
            {"note_type": "installation", "note_text": "2\" FOAM CONCENTRATE SUPPORTED ON PIPE BRIDGE HEAT TRACED AND INSULATED ALONG FULL EXTERIOR LENGTH FROM CUB TO PHASE 2A ENTRY POINT"},
            {"note_type": "installation", "note_text": "ALL EXTERIOR ROUTED SANI AND FOAM PIPING SHALL BE HEAT TRACED, INSULATED AND JACKETED"},
            {"note_type": "equipment", "note_text": "FUTURE AUTOMATED STEAM SHUT-OFF VALVE"},
        ]
    },
    697: {  # U4003
        "sheet_id": 697,
        "drawing_type": "Utility Plan",
        "complexity": "high",
        "quality_score": 0.75,  # Lower due to dense equipment layout
        "additional_lines": [],
        "equipment": [],  # Dense equipment layout but tags not clearly visible in extracted text
        "notes": [
            {"note_type": "general", "note_text": "SEE U4002 FOR CONTINUATION"},
            {"note_type": "general", "note_text": "SEE U4004 FOR CONTINUATION"},
            {"note_type": "dimension", "note_text": "17'-10 3/4\" BOP SERVICES (12 TYPICAL)"},
            {"note_type": "installation", "note_text": "ALL EXTERIOR ROUTED SANI AND FOAM PIPING SHALL BE HEAT TRACED, INSULATED AND JACKETED"},
        ]
    }
}

# Update sheet records
for sheet_id, data in sheet_data.items():
    cursor.execute("""
        UPDATE sheets
        SET drawing_type = ?,
            complexity = ?,
            extracted_at = ?,
            extraction_model = ?,
            quality_score = ?
        WHERE id = ?
    """, (
        data["drawing_type"],
        data["complexity"],
        extracted_at,
        extraction_model,
        data["quality_score"],
        sheet_id
    ))
    print(f"Updated sheet {sheet_id} metadata")

# Insert lines data
lines_inserted = 0
for sheet_id, data in sheet_data.items():
    # Insert common piping for each sheet
    for line in common_piping:
        cursor.execute("""
            INSERT INTO lines (sheet_id, line_number, size, material, service, spec_class, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            sheet_id,
            line["line_number"],
            line["size"],
            line["material"],
            line["service"],
            line["spec_class"],
            0.95  # High confidence for clearly labeled piping
        ))
        lines_inserted += 1

    # Insert sheet-specific additional lines
    for line in data.get("additional_lines", []):
        cursor.execute("""
            INSERT INTO lines (sheet_id, line_number, size, material, service, spec_class, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            sheet_id,
            line["line_number"],
            line["size"],
            line["material"],
            line["service"],
            line["spec_class"],
            0.90
        ))
        lines_inserted += 1

print(f"Inserted {lines_inserted} line records")

# Insert equipment data
equipment_inserted = 0
for sheet_id, data in sheet_data.items():
    for equip in data.get("equipment", []):
        # First check if equipment exists in utility_equipment table
        cursor.execute("""
            INSERT INTO utility_equipment (sheet_id, equipment_mark, equipment_type, location, confidence)
            VALUES (?, ?, ?, ?, ?)
        """, (
            sheet_id,
            equip["tag"],
            equip["equipment_type"],
            equip.get("location"),
            0.85
        ))
        utility_equip_id = cursor.lastrowid

        # Also add to general equipment table for cross-referencing
        cursor.execute("""
            INSERT INTO equipment (sheet_id, tag, equipment_type, description, confidence)
            VALUES (?, ?, ?, ?, ?)
        """, (
            sheet_id,
            equip["tag"],
            equip["equipment_type"],
            equip.get("description"),
            0.85
        ))
        equipment_inserted += 1

print(f"Inserted {equipment_inserted} equipment records")

# Insert drawing notes
notes_inserted = 0
for sheet_id, data in sheet_data.items():
    for note in data.get("notes", []):
        cursor.execute("""
            INSERT INTO drawing_notes (sheet_id, note_type, note_text)
            VALUES (?, ?, ?)
        """, (
            sheet_id,
            note["note_type"],
            note["note_text"]
        ))
        notes_inserted += 1

print(f"Inserted {notes_inserted} drawing notes")

# Insert extraction notes for tracking
for sheet_id, data in sheet_data.items():
    cursor.execute("""
        INSERT INTO extraction_notes (sheet_id, note_type, description, confidence)
        VALUES (?, ?, ?, ?)
    """, (
        sheet_id,
        "extraction_summary",
        f"Extracted {len(common_piping) + len(data.get('additional_lines', []))} lines, "
        f"{len(data.get('equipment', []))} equipment items, "
        f"{len(data.get('notes', []))} notes from utility plan drawing",
        data["quality_score"]
    ))

print(f"Inserted extraction tracking notes")

# Commit all changes
conn.commit()
print("\n=== EXTRACTION COMPLETE ===")
print(f"Processed 3 utility drawings for project 07609 (Freshpet)")
print(f"- Sheet 695 (U4001): {data['quality_score']:.2f} quality score")
print(f"- Sheet 696 (U4002): {sheet_data[696]['quality_score']:.2f} quality score")
print(f"- Sheet 697 (U4003): {sheet_data[697]['quality_score']:.2f} quality score")
print(f"\nTotal extracted:")
print(f"- {lines_inserted} pipe lines")
print(f"- {equipment_inserted} equipment items")
print(f"- {notes_inserted} drawing notes")

conn.close()
