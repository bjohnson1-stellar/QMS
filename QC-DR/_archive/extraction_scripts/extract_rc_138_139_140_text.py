#!/usr/bin/env python3
"""
Extract data from Refrigeration-Controls drawing sheets 138, 139, 140 for project 07308.
Uses PyMuPDF text extraction and pattern matching.
"""

import sqlite3
import re
import os
from datetime import datetime

try:
    import fitz  # PyMuPDF
except ImportError:
    print("Installing PyMuPDF...")
    import subprocess
    import sys
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'PyMuPDF'])
    import fitz

# Sheet information for Refrigeration-Controls discipline - Areas 3, 4, 5
SHEETS = [
    {
        'id': 138,
        'path': 'D:/Projects/07308-BIRDCAGE/Refrigeration-Controls/RC11030-REFRIGERATION-CONTROLS-PLAN-PIPE-AND-DUCT-FLOOR-AREA-3-Rev.6.pdf',
        'drawing_number': 'RC11030',
        'type': 'plan',
        'title': 'REFRIGERATION-CONTROLS-PLAN-PIPE-AND-DUCT-FLOOR-AREA-3',
        'revision': '6',
        'area': 'Area 3'
    },
    {
        'id': 139,
        'path': 'D:/Projects/07308-BIRDCAGE/Refrigeration-Controls/RC11040-REFRIGERATION-CONTROLS-PLAN-PIPE-AND-DUCT-FLOOR---AREA-4-Rev.9.pdf',
        'drawing_number': 'RC11040',
        'type': 'plan',
        'title': 'REFRIGERATION-CONTROLS-PLAN-PIPE-AND-DUCT-FLOOR-AREA-4',
        'revision': '9',
        'area': 'Area 4'
    },
    {
        'id': 140,
        'path': 'D:/Projects/07308-BIRDCAGE/Refrigeration-Controls/RC11050-REFRIGERATION-CONTROLS-PLAN-PIPE-AND-DUCT-FLOOR---AREA-5-Rev.7.pdf',
        'drawing_number': 'RC11050',
        'type': 'plan',
        'title': 'REFRIGERATION-CONTROLS-PLAN-PIPE-AND-DUCT-FLOOR-AREA-5',
        'revision': '7',
        'area': 'Area 5'
    }
]

DB_PATH = 'D:/quality.db'

# Instrument tag patterns - Refrigeration typical tags
instrument_pattern = re.compile(r'\b([A-Z]{2,4})-?(\d{3,5}[A-Z]?)\b')

# Equipment tag patterns
equipment_pattern = re.compile(r'\b([A-Z]{1,3})-(\d{2,4}[A-Z]?)\b')

# Known instrument prefixes for refrigeration controls
instrument_prefixes = {
    'TT': 'Temperature Transmitter',
    'TE': 'Temperature Element',
    'TI': 'Temperature Indicator',
    'TIC': 'Temperature Indicator Controller',
    'PT': 'Pressure Transmitter',
    'PI': 'Pressure Indicator',
    'PE': 'Pressure Element',
    'PIC': 'Pressure Indicator Controller',
    'FT': 'Flow Transmitter',
    'FI': 'Flow Indicator',
    'FE': 'Flow Element',
    'LT': 'Level Transmitter',
    'LI': 'Level Indicator',
    'LE': 'Level Element',
    'PCV': 'Pressure Control Valve',
    'TCV': 'Temperature Control Valve',
    'FCV': 'Flow Control Valve',
    'LCV': 'Level Control Valve',
    'PSV': 'Pressure Safety Valve',
    'PRV': 'Pressure Relief Valve',
    'TSH': 'Temperature Switch High',
    'TSHH': 'Temperature Switch High High',
    'TSL': 'Temperature Switch Low',
    'TSLL': 'Temperature Switch Low Low',
    'PSH': 'Pressure Switch High',
    'PSHH': 'Pressure Switch High High',
    'PSL': 'Pressure Switch Low',
    'PSLL': 'Pressure Switch Low Low',
    'FSH': 'Flow Switch High',
    'FSL': 'Flow Switch Low',
    'LSH': 'Level Switch High',
    'LSHH': 'Level Switch High High',
    'LSL': 'Level Switch Low',
    'LSLL': 'Level Switch Low Low',
    'EV': 'Expansion Valve',
    'SV': 'Solenoid Valve',
    'HPS': 'High Pressure Switch',
    'LPS': 'Low Pressure Switch'
}

# Known equipment prefixes for refrigeration
equipment_prefixes = {
    'P': 'Pump',
    'C': 'Compressor',
    'V': 'Vessel',
    'TK': 'Tank',
    'E': 'Exchanger',
    'H': 'Heater',
    'CL': 'Cooler',
    'EC': 'Evaporative Condenser',
    'AC': 'Air Cooler',
    'RC': 'Refrigeration Condenser',
    'COND': 'Condenser',
    'EVAP': 'Evaporator',
    'ACC': 'Accumulator',
    'SEP': 'Separator',
    'REC': 'Receiver',
    'CH': 'Chiller'
}

def extract_text_from_pdf(pdf_path):
    """Extract all text from PDF using PyMuPDF."""
    doc = fitz.open(pdf_path)
    full_text = ""
    for page in doc:
        full_text += page.get_text()
    doc.close()
    return full_text

def parse_instruments(text):
    """Extract instrument tags from text using pattern matching."""
    instruments = {}

    for match in instrument_pattern.finditer(text):
        prefix = match.group(1)
        number = match.group(2)

        # Only consider known instrument prefixes
        if prefix in instrument_prefixes:
            tag = f"{prefix}-{number}"
            if tag not in instruments:
                instruments[tag] = {
                    'tag': tag,
                    'instrument_type': instrument_prefixes[prefix],
                    'loop_number': number,
                    'confidence': 0.85
                }

    return list(instruments.values())

def parse_equipment(text):
    """Extract equipment tags from text using pattern matching."""
    equipment_list = {}

    for match in equipment_pattern.finditer(text):
        prefix = match.group(1)
        number = match.group(2)

        # Only consider known equipment prefixes
        if prefix in equipment_prefixes:
            tag = f"{prefix}-{number}"
            # Don't add if it's actually an instrument
            if prefix not in instrument_prefixes and tag not in equipment_list:
                equipment_list[tag] = {
                    'tag': tag,
                    'equipment_type': equipment_prefixes[prefix],
                    'description': f"{equipment_prefixes[prefix]} {number}",
                    'confidence': 0.80
                }

    return list(equipment_list.values())

def insert_instruments(conn, sheet_id, instruments):
    """Insert instruments into database."""
    cursor = conn.cursor()
    inserted = 0
    skipped = 0

    for inst in instruments:
        try:
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
            inserted += 1
        except sqlite3.IntegrityError:
            skipped += 1

    conn.commit()
    return inserted, skipped

def insert_equipment(conn, sheet_id, equipment_list):
    """Insert equipment into database."""
    cursor = conn.cursor()
    inserted = 0
    skipped = 0

    for equip in equipment_list:
        try:
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
            inserted += 1
        except sqlite3.IntegrityError:
            skipped += 1

    conn.commit()
    return inserted, skipped

def update_sheet_metadata(conn, sheet_id, quality_score, complexity):
    """Update sheet extraction metadata."""
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE sheets
        SET extracted_at = ?,
            extraction_model = 'pymupdf-pattern-matching',
            quality_score = ?,
            drawing_type = 'plan',
            complexity = ?
        WHERE id = ?
    """, (
        datetime.now().isoformat(),
        quality_score,
        complexity,
        sheet_id
    ))
    conn.commit()

def main():
    """Main extraction process."""

    print("=" * 80)
    print("REFRIGERATION-CONTROLS DRAWING DATA EXTRACTION")
    print("Project: 07308-BIRDCAGE")
    print("Discipline: Refrigeration-Controls")
    print("Sheets: 138, 139, 140 (Areas 3, 4, 5)")
    print("Method: Text extraction with pattern matching")
    print("=" * 80)
    print()

    conn = sqlite3.connect(DB_PATH)

    total_instruments = 0
    total_equipment = 0
    successful = 0

    for sheet in SHEETS:
        print(f"Processing Sheet {sheet['id']}: {sheet['drawing_number']} Rev {sheet['revision']}")
        print(f"  Area: {sheet['area']}")
        print(f"  File: {sheet['path']}")
        print("-" * 80)

        # Check file exists
        if not os.path.exists(sheet['path']):
            print(f"  ERROR: File not found!")
            print()
            continue

        try:
            # Extract text from PDF
            print("  Extracting text from PDF...")
            text = extract_text_from_pdf(sheet['path'])
            print(f"  Extracted {len(text)} characters of text")

            # Parse instruments and equipment
            print("  Parsing instruments and equipment...")
            instruments = parse_instruments(text)
            equipment = parse_equipment(text)

            print(f"  Found {len(instruments)} instruments, {len(equipment)} equipment items")

            # Insert into database
            print("  Inserting into database...")
            inst_inserted, inst_skipped = insert_instruments(conn, sheet['id'], instruments)
            equip_inserted, equip_skipped = insert_equipment(conn, sheet['id'], equipment)

            # Calculate quality score and complexity
            total_items = len(instruments) + len(equipment)
            if total_items > 0:
                avg_confidence = (sum(i['confidence'] for i in instruments) +
                                sum(e['confidence'] for e in equipment)) / total_items
                quality_score = round(avg_confidence, 2)
            else:
                quality_score = 0.0

            if total_items > 50:
                complexity = 'complex'
            elif total_items > 20:
                complexity = 'medium'
            else:
                complexity = 'simple'

            # Update sheet metadata
            update_sheet_metadata(conn, sheet['id'], quality_score, complexity)

            print("  Extracted:")
            print(f"    - Instruments: {len(instruments)} (inserted: {inst_inserted}, skipped: {inst_skipped})")
            print(f"    - Equipment: {len(equipment)} (inserted: {equip_inserted}, skipped: {equip_skipped})")
            print(f"    - Quality Score: {quality_score}")
            print(f"    - Complexity: {complexity}")
            print()

            # Show sample extractions
            if instruments:
                print("  Sample Instruments:")
                for inst in instruments[:5]:
                    print(f"    - {inst['tag']}: {inst['instrument_type']} (Loop: {inst['loop_number']})")
                if len(instruments) > 5:
                    print(f"    ... and {len(instruments) - 5} more")
                print()

            if equipment:
                print("  Sample Equipment:")
                for equip in equipment[:5]:
                    print(f"    - {equip['tag']}: {equip['equipment_type']}")
                if len(equipment) > 5:
                    print(f"    ... and {len(equipment) - 5} more")
                print()

            total_instruments += len(instruments)
            total_equipment += len(equipment)
            successful += 1

        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback
            traceback.print_exc()
            print()

    conn.close()

    # Summary
    print("=" * 80)
    print("EXTRACTION SUMMARY")
    print("=" * 80)
    print(f"Total Instruments Extracted: {total_instruments}")
    print(f"Total Equipment Extracted: {total_equipment}")
    print(f"Sheets Processed Successfully: {successful}/{len(SHEETS)}")
    print()
    print(f"Database: {DB_PATH}")
    print("=" * 80)

    return 0 if successful == len(SHEETS) else 1

if __name__ == '__main__':
    import sys
    sys.exit(main())
