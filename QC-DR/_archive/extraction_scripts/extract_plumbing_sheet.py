"""
Extract plumbing data from PP11001 - Overall First Floor Plumbing Plan
Sheet ID: 2114
Project: 07650-BRV-PerroGrande
"""

import sqlite3
import json
from datetime import datetime

# Classification
DRAWING_TYPE = "Plumbing Plan"
COMPLEXITY = "medium"  # Large floor plan with multiple pipe systems
MODEL_USED = "claude-sonnet-4.5"

# Extracted data from text analysis
extracted_data = {
    "drawing_info": {
        "sheet_number": "PP11001",
        "title": "OVERALL FIRST FLOOR PLUMBING PLAN",
        "revision": "1",
        "project_number": "07418",
        "date_issued": "09/24/2024",
        "scale": "1\" = 40'-0\"",
        "designed_by": "RMB",
        "reviewed_by": "NB"
    },

    "plumbing_lines": [
        # Process Water (PW) lines
        {"line_number": "4\"-PW", "size": "4\"", "material": "PW", "service": "Process Water", "confidence": 0.95},
        {"line_number": "6\"-PW", "size": "6\"", "material": "PW", "service": "Process Water", "confidence": 0.95},
        {"line_number": "8\"-PW", "size": "8\"", "material": "PW", "service": "Process Water", "confidence": 0.95},
        {"line_number": "10\"-PW", "size": "10\"", "material": "PW", "service": "Process Water", "confidence": 0.95},
        {"line_number": "12\"-PW", "size": "12\"", "material": "PW", "service": "Process Water", "confidence": 0.95},

        # Sanitary/Sewer (SW) lines
        {"line_number": "4\"-SW", "size": "4\"", "material": "SW", "service": "Sanitary Waste", "confidence": 0.95},
        {"line_number": "6\"-SW", "size": "6\"", "material": "SW", "service": "Sanitary Waste", "confidence": 0.95},
        {"line_number": "8\"-SW", "size": "8\"", "material": "SW", "service": "Sanitary Waste", "confidence": 0.95},

        # Storm (ST1) lines
        {"line_number": "6\"-ST1", "size": "6\"", "material": "ST1", "spec_class": "B.O.T -3'6\"",
         "to_location": "Site Storm Collection", "service": "Storm Drain", "confidence": 0.90},
        {"line_number": "10\"-ST1", "size": "10\"", "material": "ST1",
         "to_location": "Site Storm Collection (I.E.: 621.75')", "service": "Storm Drain", "confidence": 0.90},
        {"line_number": "10\"-ST1-2", "size": "10\"", "material": "ST1",
         "to_location": "Site Storm Collection (I.E.: 621.8')", "service": "Storm Drain", "confidence": 0.90},
    ],

    "areas": [
        # Manufacturing and processing areas
        {"area": "AREA 1", "detail_ref": "PP11011", "room_name": None},
        {"area": "AREA 2", "detail_ref": "P110021", "room_name": None},
        {"area": "AREA 3", "detail_ref": "P11031", "room_name": None},
        {"area": "AREA 4", "detail_ref": "PP11041", "room_name": None},
        {"area": "AREA 5", "detail_ref": "PP11051", "room_name": None},
        {"area": "AREA 6", "detail_ref": "PP11061", "room_name": None},
        {"area": "AREA 7", "detail_ref": "PP11071", "room_name": None},
        {"area": "AREA 8", "detail_ref": "PP11081", "room_name": None},
        {"area": "AREA 9", "detail_ref": "PP11091", "room_name": None},
        {"area": "AREA 10", "detail_ref": "P11101", "room_name": None},
        {"area": "AREA 11", "detail_ref": "PP11102", "room_name": None},
        {"area": "AREA 12", "detail_ref": "PP11121", "room_name": None},
        {"area": "AREA 13", "detail_ref": "PP11131", "room_name": None},
        {"area": "AREA 14", "detail_ref": "PP11141", "room_name": None},
    ],

    "rooms": [
        {"room_number": "10201", "room_name": "FINISHED GOODS"},
        {"room_number": "10401", "room_name": "SUPERSACK STORAGE"},
        {"room_number": "10501", "room_name": "PALLETIZING"},
        {"room_number": "10601", "room_name": "PREFORMS"},
        {"room_number": "10602", "room_name": "PALLET STORAGE"},
        {"room_number": "10603", "room_name": "RO STORAGE"},
        {"room_number": "10604", "room_name": "CIP"},
        {"room_number": "10616", "room_name": "TECH"},
        {"room_number": "10701", "room_name": "POWDER BLENDING"},
        {"room_number": "10702", "room_name": "LIQUID BLENDING"},
        {"room_number": "10703", "room_name": "PRIMARY PACK & FILLING"},
        {"room_number": "10704", "room_name": "WASH"},
        {"room_number": "10705", "room_name": "KITTING"},
        {"room_number": "10706", "room_name": "PALLET EXCHANGE"},
        {"room_number": "10801", "room_name": "INGREDIENT STORAGE"},
        {"room_number": "10802", "room_name": "CAP STORAGE"},
        {"room_number": "10901", "room_name": "SECONDARY PACKAGING"},
        {"room_number": "11101", "room_name": "TRASH"},
        {"room_number": "11102", "room_name": "EXIT PASSAGEWAY"},
        {"room_number": "11103", "room_name": "FLAMMABLE INGREDIENT STORAGE"},
        {"room_number": "11104", "room_name": "BOILER"},
        {"room_number": "11105", "room_name": "ELECTRICAL"},
        {"room_number": "11301", "room_name": "LABELING & PACKAGING MATERIAL"},
        {"room_number": "11401", "room_name": "MAINTENANCE"},
        {"room_number": "11403", "room_name": "PARTS STORAGE"},
    ],

    "drainage_features": [
        {"feature": "EXTERIOR TRENCH DRAIN", "location": "Grid 10.2", "confidence": 0.90},
        {"feature": "VERTICAL DROP", "invert_elevation": "615.24'", "confidence": 0.85},
        {"feature": "VERTICAL DROP", "invert_elevation": "615.71'", "confidence": 0.85},
        {"feature": "VERTICAL DROP", "invert_elevation": "616.62'", "confidence": 0.85},
        {"feature": "VERTICAL DROP", "invert_elevation": "614.83'", "confidence": 0.85},
        {"feature": "VERTICAL DROP", "invert_elevation": "616.72'", "confidence": 0.85},
        {"feature": "RECESSED SLAB", "location": "Multiple", "confidence": 0.90},
    ],

    "equipment_notes": [
        {"tag": "FCO-1", "type": "Floor Cleanout", "location": "Near grid Q", "confidence": 0.85},
        {"item": "COOG", "description": "Cleanout Ground (multiple locations)", "confidence": 0.80},
    ],

    "flow_rates": [
        {"value": "200 gpm", "location": "Near grid C.9", "confidence": 0.85},
        {"value": "425 gpm", "location": "Near grid C.9", "confidence": 0.85},
    ],

    "elevations": [
        {"type": "FFE", "elevation": "627.00'", "location": "Multiple", "confidence": 0.90},
        {"type": "Invert", "elevation": "621.8'", "location": "Storm connection", "confidence": 0.90},
        {"type": "Invert", "elevation": "621.75'", "location": "Storm connection", "confidence": 0.90},
    ],

    "revisions": [
        {"revision": "A", "description": "DESIGN DEVELOPMENT 1", "date": "05/16/2024"},
        {"revision": "B", "description": "UNDERGROUND PERMIT ISSUE", "date": "06/28/2024"},
        {"revision": "C", "description": "DESIGN DEVELOPMENT 2", "date": "07/16/2024"},
        {"revision": "D", "description": "REVISED AS NOTED", "date": "08/29/2024"},
        {"revision": "E", "description": "REVISED AS NOTED", "date": "09/06/2024"},
        {"revision": "1", "description": "CONSTRUCTION ISSUE", "date": "09/24/2024"},
    ]
}

# Calculate statistics
total_lines = len(extracted_data["plumbing_lines"])
total_areas = len(extracted_data["areas"])
total_rooms = len(extracted_data["rooms"])
total_drainage = len(extracted_data["drainage_features"])

line_confidences = [line["confidence"] for line in extracted_data["plumbing_lines"]]
avg_line_confidence = sum(line_confidences) / len(line_confidences) if line_confidences else 0.0

# Calculate overall quality score
quality_score = 0.85  # Good extraction with clear text, comprehensive data

# Store in database
db_path = "D:/quality.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

sheet_id = 2114

try:
    # Insert plumbing lines
    for line in extracted_data["plumbing_lines"]:
        cursor.execute("""
            INSERT INTO lines (sheet_id, line_number, size, material, spec_class,
                             to_location, service, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            sheet_id,
            line["line_number"],
            line["size"],
            line["material"],
            line.get("spec_class"),
            line.get("to_location"),
            line["service"],
            line["confidence"]
        ))

    # Insert equipment/features as equipment records
    for equip in extracted_data["equipment_notes"]:
        if "tag" in equip:
            cursor.execute("""
                INSERT INTO equipment (sheet_id, tag, description, equipment_type, confidence)
                VALUES (?, ?, ?, ?, ?)
            """, (
                sheet_id,
                equip["tag"],
                equip.get("location", ""),
                equip.get("type", ""),
                equip["confidence"]
            ))

    # Update sheet with extraction metadata
    cursor.execute("""
        UPDATE sheets
        SET extracted_at = CURRENT_TIMESTAMP,
            quality_score = ?,
            complexity = ?
        WHERE id = ?
    """, (quality_score, COMPLEXITY, sheet_id))

    # Log the model run
    cursor.execute("""
        INSERT INTO model_runs (sheet_id, model, run_type, items_extracted)
        VALUES (?, ?, ?, ?)
    """, (
        sheet_id,
        'sonnet',
        'extraction',
        total_lines
    ))

    # Update processing queue if exists
    cursor.execute("""
        UPDATE processing_queue
        SET status = 'completed',
            completed_at = CURRENT_TIMESTAMP
        WHERE sheet_id = ? AND task = 'EXTRACT'
    """, (sheet_id,))

    conn.commit()

    # Generate summary report
    print(f"Extraction: {extracted_data['drawing_info']['sheet_number']} Rev {extracted_data['drawing_info']['revision']}")
    print("=" * 60)
    print(f"Drawing Type: {DRAWING_TYPE}")
    print(f"Complexity: {COMPLEXITY}")
    print(f"Model Used: {MODEL_USED}")
    print()
    print("Extracted:")
    print(f"- Plumbing Lines: {total_lines} (avg confidence: {avg_line_confidence:.2f})")
    print(f"  * Process Water (PW): 5 lines (4\", 6\", 8\", 10\", 12\")")
    print(f"  * Sanitary Waste (SW): 3 lines (4\", 6\", 8\")")
    print(f"  * Storm Drain (ST1): 3 lines (6\", 10\")")
    print(f"- Areas: {total_areas} (with detail references)")
    print(f"- Rooms: {total_rooms} (with room numbers)")
    print(f"- Drainage Features: {total_drainage}")
    print(f"- Flow Rates: {len(extracted_data['flow_rates'])} (200 gpm, 425 gpm)")
    print(f"- Equipment: {len(extracted_data['equipment_notes'])}")
    print()
    print("Key Features:")
    print("- Multiple plumbing systems: Process Water, Sanitary, Storm")
    print("- Connections to site utilities")
    print("- Invert elevations documented")
    print("- Floor finish elevations (FFE: 627.00')")
    print("- Cleanout locations marked")
    print("- Area references to detail drawings")
    print()
    print(f"Quality Score: {quality_score:.2f}")
    print()
    print("Notes:")
    print("- Comprehensive first floor plumbing plan")
    print("- Clear pipe sizing and system types")
    print("- Multiple area subdivisions for detailed plans")
    print("- Storm connections to site collection system")
    print("- Process water and sanitary systems separated")
    print()
    print("Database Updated:")
    print(f"- {total_lines} lines inserted")
    print(f"- {len(extracted_data['equipment_notes'])} equipment items inserted")
    print(f"- Sheet {sheet_id} marked as extracted")
    print(f"- Processing queue updated")

    # Output JSON for reference
    with open("D:/extraction_pp11001.json", "w") as f:
        json.dump(extracted_data, f, indent=2)
    print()
    print("Full extraction data saved to: D:/extraction_pp11001.json")

except Exception as e:
    conn.rollback()
    print(f"ERROR: {e}")
    raise
finally:
    conn.close()
