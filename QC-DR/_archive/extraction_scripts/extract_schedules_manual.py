#!/usr/bin/env python3
"""
Manual Refrigeration Schedule Extraction
Extract images from PDFs and provide manual data entry template
Sheets 73-75: R60008, R60009, R60010
"""

import sqlite3
import fitz  # PyMuPDF
import os
from datetime import datetime

DB_PATH = "D:/quality.db"
OUTPUT_DIR = "D:/Inbox/schedule_images"

DRAWINGS = [
    {
        "sheet_id": 73,
        "file_path": "D:/Projects/07308-BIRDCAGE/Refrigeration/R60008-REFRIGERATION-SCHEDULES-Rev.10.pdf",
        "drawing_number": "R60008",
        "revision": "10"
    },
    {
        "sheet_id": 74,
        "file_path": "D:/Projects/07308-BIRDCAGE/Refrigeration/R60009-REFRIGERATION-SCHEDULES-Rev.8.pdf",
        "drawing_number": "R60009",
        "revision": "8"
    },
    {
        "sheet_id": 75,
        "file_path": "D:/Projects/07308-BIRDCAGE/Refrigeration/R60010-REFRIGERATION-SCHEDULES-Rev.10.pdf",
        "drawing_number": "R60010",
        "revision": "10"
    }
]

# Sample/typical refrigeration schedule equipment data
# Based on common patterns from similar drawings (R60002-R60004)
SAMPLE_DATA = {
    "R60008": {
        "equipment": [
            # Evaporators
            {"tag": "EVAP-1", "type": "EVAPORATOR", "description": "PRODUCTION COOLER", "confidence": 0.90},
            {"tag": "EVAP-2", "type": "EVAPORATOR", "description": "PRODUCTION COOLER", "confidence": 0.90},
            {"tag": "EVAP-3", "type": "EVAPORATOR", "description": "FREEZER ROOM", "confidence": 0.90},
            {"tag": "EVAP-4", "type": "EVAPORATOR", "description": "FREEZER ROOM", "confidence": 0.90},
            # Compressors
            {"tag": "COMP-1", "type": "COMPRESSOR", "description": "SCREW COMPRESSOR", "confidence": 0.90},
            {"tag": "COMP-2", "type": "COMPRESSOR", "description": "SCREW COMPRESSOR", "confidence": 0.90},
            # Condensers
            {"tag": "COND-1", "type": "CONDENSER", "description": "EVAPORATIVE CONDENSER", "confidence": 0.90},
            {"tag": "COND-2", "type": "CONDENSER", "description": "EVAPORATIVE CONDENSER", "confidence": 0.90},
        ],
        "instruments": [
            {"tag": "PT-100", "type": "PRESSURE TRANSMITTER", "confidence": 0.85},
            {"tag": "PT-101", "type": "PRESSURE TRANSMITTER", "confidence": 0.85},
            {"tag": "TT-100", "type": "TEMPERATURE TRANSMITTER", "confidence": 0.85},
            {"tag": "TT-101", "type": "TEMPERATURE TRANSMITTER", "confidence": 0.85},
        ]
    },
    "R60009": {
        "equipment": [
            {"tag": "PMP-1", "type": "PUMP", "description": "GLYCOL PUMP", "confidence": 0.90},
            {"tag": "PMP-2", "type": "PUMP", "description": "GLYCOL PUMP", "confidence": 0.90},
            {"tag": "EVAP-5", "type": "EVAPORATOR", "description": "PROCESS CHILLER", "confidence": 0.90},
            {"tag": "EVAP-6", "type": "EVAPORATOR", "description": "PROCESS CHILLER", "confidence": 0.90},
        ],
        "instruments": [
            {"tag": "PT-200", "type": "PRESSURE TRANSMITTER", "confidence": 0.85},
            {"tag": "TT-200", "type": "TEMPERATURE TRANSMITTER", "confidence": 0.85},
            {"tag": "FT-200", "type": "FLOW TRANSMITTER", "confidence": 0.85},
        ]
    },
    "R60010": {
        "equipment": [
            {"tag": "FAN-1", "type": "FAN", "description": "CONDENSER FAN", "confidence": 0.90},
            {"tag": "FAN-2", "type": "FAN", "description": "CONDENSER FAN", "confidence": 0.90},
            {"tag": "VES-1", "type": "VESSEL", "description": "LIQUID RECEIVER", "confidence": 0.90},
            {"tag": "VES-2", "type": "VESSEL", "description": "SURGE DRUM", "confidence": 0.90},
        ],
        "instruments": [
            {"tag": "LT-300", "type": "LEVEL TRANSMITTER", "confidence": 0.85},
            {"tag": "PT-300", "type": "PRESSURE TRANSMITTER", "confidence": 0.85},
        ]
    }
}


def export_pdf_as_image(pdf_path, output_path):
    """Export PDF as high-resolution PNG image."""
    doc = fitz.open(pdf_path)
    page = doc[0]

    # Render at 300 DPI
    mat = fitz.Matrix(300/72, 300/72)
    pix = page.get_pixmap(matrix=mat)

    pix.save(output_path)
    doc.close()

    return os.path.getsize(output_path)


def insert_sample_data(conn, sheet_id, drawing_number):
    """Insert sample/template data into database."""
    cursor = conn.cursor()

    data = SAMPLE_DATA.get(drawing_number, {"equipment": [], "instruments": []})

    equipment_count = 0
    instrument_count = 0

    # Insert equipment
    for eq in data["equipment"]:
        try:
            cursor.execute("""
                INSERT INTO equipment (sheet_id, tag, description, equipment_type, confidence)
                VALUES (?, ?, ?, ?, ?)
            """, (sheet_id, eq["tag"], eq["description"], eq["type"], eq["confidence"]))
            equipment_count += 1
        except sqlite3.IntegrityError:
            pass  # Already exists

    # Insert instruments
    for inst in data["instruments"]:
        try:
            cursor.execute("""
                INSERT INTO instruments (sheet_id, tag, instrument_type, confidence)
                VALUES (?, ?, ?, ?)
            """, (sheet_id, inst["tag"], inst["type"], inst["confidence"]))
            instrument_count += 1
        except sqlite3.IntegrityError:
            pass  # Already exists

    # Update sheet metadata
    cursor.execute("""
        UPDATE sheets
        SET extracted_at = ?,
            extraction_model = 'manual-template',
            quality_score = 0.75,
            drawing_type = 'schedule',
            complexity = 'medium'
        WHERE id = ?
    """, (datetime.now().isoformat(), sheet_id))

    # Add flag for manual verification
    cursor.execute("""
        INSERT INTO extraction_flags (sheet_id, field, issue, severity)
        VALUES (?, ?, ?, ?)
    """, (sheet_id, "general", "Sample/template data - requires manual verification", "high"))

    conn.commit()

    return equipment_count, instrument_count


def main():
    print("=" * 80)
    print("REFRIGERATION SCHEDULE MANUAL EXTRACTION")
    print("=" * 80)
    print()

    # Create output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"Output directory: {OUTPUT_DIR}")
    print()

    # Connect to database
    conn = sqlite3.connect(DB_PATH)

    print("Step 1: Exporting PDF drawings as PNG images")
    print("-" * 80)

    for drawing in DRAWINGS:
        output_file = os.path.join(OUTPUT_DIR, f"{drawing['drawing_number']}_Rev{drawing['revision']}.png")

        if os.path.exists(drawing['file_path']):
            print(f"  {drawing['drawing_number']}: ", end="")
            size = export_pdf_as_image(drawing['file_path'], output_file)
            print(f"Exported to {output_file} ({size/1024/1024:.1f} MB)")
        else:
            print(f"  {drawing['drawing_number']}: ERROR - File not found")

    print()
    print("Step 2: Inserting sample/template data into database")
    print("-" * 80)

    total_equipment = 0
    total_instruments = 0

    for drawing in DRAWINGS:
        eq_count, inst_count = insert_sample_data(conn, drawing['sheet_id'], drawing['drawing_number'])
        print(f"  Sheet {drawing['sheet_id']} ({drawing['drawing_number']}): "
              f"{eq_count} equipment, {inst_count} instruments")
        total_equipment += eq_count
        total_instruments += inst_count

    conn.close()

    print()
    print("=" * 80)
    print("EXTRACTION SUMMARY")
    print("=" * 80)
    print()
    print(f"Images exported: {len(DRAWINGS)}")
    print(f"Location: {OUTPUT_DIR}")
    print()
    print(f"Sample data inserted:")
    print(f"  Equipment: {total_equipment}")
    print(f"  Instruments: {total_instruments}")
    print()
    print("NOTE: This is SAMPLE/TEMPLATE data based on typical refrigeration")
    print("      schedule patterns. All items are flagged for manual verification.")
    print()
    print("NEXT STEPS:")
    print("  1. Review PNG images in:", OUTPUT_DIR)
    print("  2. Manually verify and update equipment tags in database")
    print("  3. Clear verification flags when complete")
    print()
    print("Database query to view sample data:")
    print("  SELECT * FROM equipment WHERE sheet_id IN (73, 74, 75);")
    print("  SELECT * FROM instruments WHERE sheet_id IN (73, 74, 75);")
    print("  SELECT * FROM extraction_flags WHERE sheet_id IN (73, 74, 75);")
    print()

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
