#!/usr/bin/env python3
"""
Enhanced extraction for refrigeration plan and elevation drawings
Sheets 31, 32, 33 from project 07308-BIRDCAGE
"""

import sqlite3
import re
import fitz
from datetime import datetime

DB_PATH = "D:/quality.db"

SHEETS = [
    {
        'id': 31,
        'path': 'D:/Projects/07308-BIRDCAGE/Refrigeration/R14080-REFRIGERATION-PLAN-PIPE-AND-DUCT-ROOF-AREA-8-Rev.5.pdf',
        'drawing_number': 'R14080',
        'revision': '5',
        'title': 'REFRIGERATION PLAN PIPE AND DUCT ROOF AREA 8',
        'type': 'plan'
    },
    {
        'id': 32,
        'path': 'D:/Projects/07308-BIRDCAGE/Refrigeration/R14100-REFRIGERATION-PLAN-PIPE-AND-DUCT-ROOF-AREA-10-Rev.3.pdf',
        'drawing_number': 'R14100',
        'revision': '3',
        'title': 'REFRIGERATION PLAN PIPE AND DUCT ROOF AREA 10',
        'type': 'plan'
    },
    {
        'id': 33,
        'path': 'D:/Projects/07308-BIRDCAGE/Refrigeration/R31101-REFRIGERATION-MACHINE-ROOM-ELEVATIONS-Rev.3.pdf',
        'drawing_number': 'R31101',
        'revision': '3',
        'title': 'REFRIGERATION MACHINE ROOM ELEVATIONS',
        'type': 'elevation'
    }
]


def extract_text_from_pdf(pdf_path):
    """Extract all text from PDF"""
    doc = fitz.open(pdf_path)
    all_text = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text()
        all_text.append(text)

    doc.close()
    return "\n".join(all_text)


def parse_refrigeration_data(text, drawing_number):
    """Enhanced parsing for refrigeration equipment and lines"""

    lines = []
    equipment = []
    instruments = []

    # Split text into lines for easier processing
    text_lines = text.split('\n')

    # Equipment tags - more specific patterns
    equip_patterns = [
        (r'\b(EC\d+[A-Z]?)\b', 'evaporative_condenser'),
        (r'\b(COMP-?\d+[A-Z]?)\b', 'compressor'),
        (r'\b(C\d+)\b', 'compressor'),
        (r'\b(EF\d+)\b', 'exhaust_fan'),
        (r'\b(GV\d+)\b', 'gravity_vent'),
        (r'\b(CG\d+-\d+-\d+)\b', 'cooling_unit'),
        (r'\b(HPR-?\d+[A-Z]?)\b', 'high_pressure_receiver'),
        (r'\b(TSV-?\d+[A-Z]?)\b', 'thermosyphon_vessel'),
        (r'\b(HTR-?\d+[A-Z]?)\b', 'recirculator'),
        (r'\b(PMP-?\d+[A-Z]?)\b', 'pump'),
        (r'\b(AP-?\d+)\b', 'auto_purger'),
        (r'\b(HEX-?\d+[A-Z]?)\b', 'heat_exchanger'),
        (r'\b(CU-?\d+)\b', 'cooling_unit'),
        (r'\b(RCVR-?\d+[A-Z]?)\b', 'receiver'),
    ]

    seen_equipment = set()
    for pattern, eq_type in equip_patterns:
        for match in re.finditer(pattern, text, re.MULTILINE):
            tag = match.group(1)
            if tag not in seen_equipment:
                seen_equipment.add(tag)
                equipment.append({
                    'tag': tag,
                    'equipment_type': eq_type,
                    'description': f'{eq_type.replace("_", " ").title()} {tag}',
                    'confidence': 0.85
                })

    # Line descriptions with sizes and service types
    # Format: SIZE" SERVICE
    # Examples: 4" HTRL, 6" HTRS, 2 1/2" HGD, 3/4" HTRL
    line_pattern = r'(\d+(?:\s*\d+/\d+)?"?)\s+([A-Z]{2,5})'

    seen_lines = set()
    for match in re.finditer(line_pattern, text):
        size = match.group(1).strip()
        service_code = match.group(2)

        # Decode service codes
        service_map = {
            'HTRL': 'High Temperature Refrigerant Liquid',
            'HTRS': 'High Temperature Refrigerant Suction',
            'HGD': 'Hot Gas Discharge',
            'HPL': 'High Pressure Liquid',
            'LPS': 'Low Pressure Suction',
            'HPS': 'High Pressure Suction',
            'MTRL': 'Medium Temperature Refrigerant Liquid',
            'MTRS': 'Medium Temperature Refrigerant Suction',
            'LTRL': 'Low Temperature Refrigerant Liquid',
            'LTRS': 'Low Temperature Refrigerant Suction',
        }

        service = service_map.get(service_code, service_code)

        line_key = f"{size}-{service_code}"
        if line_key not in seen_lines:
            seen_lines.add(line_key)
            lines.append({
                'line_number': f'{size} {service_code}',
                'size': size.replace('"', '').strip(),
                'material': 'R-717',
                'service': service,
                'confidence': 0.85
            })

    # Drawing references can indicate connections
    # Format: B1 / R14030, etc.
    ref_pattern = r'\b(R\d{5})\b'
    for match in re.finditer(ref_pattern, text):
        ref = match.group(1)
        # These are drawing references, not equipment, but useful for notes

    # Instrument tags
    inst_patterns = [
        (r'\b(PT-?\d+[A-Z]?)\b', 'pressure_transmitter'),
        (r'\b(TT-?\d+[A-Z]?)\b', 'temperature_transmitter'),
        (r'\b(FT-?\d+[A-Z]?)\b', 'flow_transmitter'),
        (r'\b(LT-?\d+[A-Z]?)\b', 'level_transmitter'),
        (r'\b(PSV-?\d+[A-Z]?)\b', 'pressure_safety_valve'),
        (r'\b(TSV-?\d+[A-Z]?)\b', 'temperature_safety_valve'),
        (r'\b(PI-?\d+[A-Z]?)\b', 'pressure_indicator'),
        (r'\b(TI-?\d+[A-Z]?)\b', 'temperature_indicator'),
    ]

    seen_instruments = set()
    for pattern, inst_type in inst_patterns:
        for match in re.finditer(pattern, text, re.MULTILINE):
            tag = match.group(1)
            if tag not in seen_instruments:
                seen_instruments.add(tag)
                instruments.append({
                    'tag': tag,
                    'instrument_type': inst_type,
                    'loop_number': re.sub(r'[A-Z-]', '', tag),
                    'confidence': 0.85
                })

    return {'lines': lines, 'equipment': equipment, 'instruments': instruments}


def insert_data(conn, sheet_id, data):
    """Insert extracted data into database"""
    cur = conn.cursor()

    counts = {'lines': 0, 'equipment': 0, 'instruments': 0}

    # Insert lines
    for line in data['lines']:
        try:
            cur.execute("""
                INSERT INTO lines (sheet_id, line_number, size, material, service, confidence)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                sheet_id,
                line['line_number'],
                line.get('size', ''),
                line.get('material', ''),
                line.get('service', ''),
                line.get('confidence', 0.7)
            ))
            counts['lines'] += 1
        except sqlite3.IntegrityError:
            pass

    # Insert equipment
    for equip in data['equipment']:
        try:
            cur.execute("""
                INSERT INTO equipment (sheet_id, tag, equipment_type, description, confidence)
                VALUES (?, ?, ?, ?, ?)
            """, (
                sheet_id,
                equip['tag'],
                equip['equipment_type'],
                equip['description'],
                equip.get('confidence', 0.75)
            ))
            counts['equipment'] += 1
        except sqlite3.IntegrityError:
            pass

    # Insert instruments
    for inst in data['instruments']:
        try:
            cur.execute("""
                INSERT INTO instruments (sheet_id, tag, instrument_type, loop_number, confidence)
                VALUES (?, ?, ?, ?, ?)
            """, (
                sheet_id,
                inst['tag'],
                inst['instrument_type'],
                inst.get('loop_number', ''),
                inst.get('confidence', 0.75)
            ))
            counts['instruments'] += 1
        except sqlite3.IntegrityError:
            pass

    conn.commit()
    return counts


def update_sheet_metadata(conn, sheet_id, drawing_type, complexity, quality_score):
    """Update sheet metadata"""
    cur = conn.cursor()

    cur.execute("""
        UPDATE sheets
        SET extracted_at = ?,
            extraction_model = 'text-extraction-pymupdf-enhanced',
            drawing_type = ?,
            complexity = ?,
            quality_score = ?
        WHERE id = ?
    """, (datetime.now().isoformat(), drawing_type, complexity, quality_score, sheet_id))

    conn.commit()


def main():
    """Main extraction process"""
    print("=" * 80)
    print("REFRIGERATION DRAWING EXTRACTION (Enhanced) - Sheets 31, 32, 33")
    print("Project: 07308-BIRDCAGE")
    print("=" * 80)

    conn = sqlite3.connect(DB_PATH)

    # First, clear existing data for these sheets to avoid duplicates
    print("\nClearing existing extractions...")
    cur = conn.cursor()
    for sheet in SHEETS:
        cur.execute("DELETE FROM lines WHERE sheet_id = ?", (sheet['id'],))
        cur.execute("DELETE FROM equipment WHERE sheet_id = ?", (sheet['id'],))
        cur.execute("DELETE FROM instruments WHERE sheet_id = ?", (sheet['id'],))
    conn.commit()
    print("Cleared.")

    all_stats = {
        'sheets_processed': 0,
        'total_lines': 0,
        'total_equipment': 0,
        'total_instruments': 0
    }

    for sheet in SHEETS:
        print(f"\n{sheet['drawing_number']} Rev {sheet['revision']} (Sheet ID: {sheet['id']})")
        print(f"  {sheet['title']}")
        print(f"  Type: {sheet['type']}")
        print("-" * 80)

        # Extract text
        print(f"  Extracting text from PDF...")
        text = extract_text_from_pdf(sheet['path'])
        print(f"  Extracted {len(text)} characters")

        # Parse data
        print(f"  Parsing refrigeration data...")
        data = parse_refrigeration_data(text, sheet['drawing_number'])

        # Insert into database
        print(f"  Inserting data into database...")
        counts = insert_data(conn, sheet['id'], data)

        # Update sheet metadata
        complexity = 'medium'
        quality_score = 0.80  # Enhanced extraction

        update_sheet_metadata(conn, sheet['id'], sheet['type'], complexity, quality_score)

        # Update stats
        all_stats['sheets_processed'] += 1
        all_stats['total_lines'] += counts['lines']
        all_stats['total_equipment'] += counts['equipment']
        all_stats['total_instruments'] += counts['instruments']

        # Print results
        print(f"\n  RESULTS:")
        print(f"    Lines:       {counts['lines']}")
        print(f"    Equipment:   {counts['equipment']}")
        print(f"    Instruments: {counts['instruments']}")

        # Show details
        if data['lines']:
            print(f"\n  Lines Found:")
            for line in data['lines']:
                print(f"    {line['line_number']:20s} - {line['service']}")

        if data['equipment']:
            print(f"\n  Equipment Found:")
            for eq in data['equipment']:
                print(f"    {eq['tag']:15s} - {eq['equipment_type']:30s}")

        if data['instruments']:
            print(f"\n  Instruments Found:")
            for inst in data['instruments']:
                print(f"    {inst['tag']:15s} - {inst['instrument_type']:30s}")

    conn.close()

    # Final summary
    print("\n" + "=" * 80)
    print("EXTRACTION COMPLETE")
    print("=" * 80)
    print(f"Sheets Processed:  {all_stats['sheets_processed']}")
    print(f"Total Lines:       {all_stats['total_lines']}")
    print(f"Total Equipment:   {all_stats['total_equipment']}")
    print(f"Total Instruments: {all_stats['total_instruments']}")

    # Database verification
    print("\n" + "=" * 80)
    print("DATABASE VERIFICATION")
    print("=" * 80)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    for sheet in SHEETS:
        cur.execute("SELECT COUNT(*) FROM lines WHERE sheet_id = ?", (sheet['id'],))
        line_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM equipment WHERE sheet_id = ?", (sheet['id'],))
        equip_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM instruments WHERE sheet_id = ?", (sheet['id'],))
        inst_count = cur.fetchone()[0]

        cur.execute("""
            SELECT quality_score, drawing_type, complexity, extraction_model, extracted_at
            FROM sheets WHERE id = ?
        """, (sheet['id'],))
        result = cur.fetchone()

        print(f"\n{sheet['drawing_number']} Rev {sheet['revision']} (Sheet {sheet['id']}):")
        print(f"  Lines:       {line_count}")
        print(f"  Equipment:   {equip_count}")
        print(f"  Instruments: {inst_count}")

        if result:
            quality, dwg_type, complexity, model, extracted_at = result
            print(f"  Quality:     {quality:.2f}")
            print(f"  Type:        {dwg_type}")
            print(f"  Complexity:  {complexity}")
            print(f"  Model:       {model}")
            print(f"  Extracted:   {extracted_at}")

    conn.close()

    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
