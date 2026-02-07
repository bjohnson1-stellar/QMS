#!/usr/bin/env python3
"""
Extract data from refrigeration plan and elevation drawings
Sheets 31, 32, 33 from project 07308-BIRDCAGE

Sheet 31: R14080 REFRIGERATION PLAN PIPE AND DUCT ROOF AREA 8 Rev 5
Sheet 32: R14100 REFRIGERATION PLAN PIPE AND DUCT ROOF AREA 10 Rev 3
Sheet 33: R31101 REFRIGERATION MACHINE ROOM ELEVATIONS Rev 3
"""

import sqlite3
import re
import fitz  # PyMuPDF
from datetime import datetime
from collections import defaultdict

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


def parse_refrigeration_data(text, drawing_number, drawing_type):
    """Parse refrigeration equipment, lines, and instruments from text"""

    lines = []
    equipment = []
    instruments = []

    # Patterns for refrigeration tags
    # Equipment: COMP, COND, RCVR, EC (evaporative condenser), HPR, TSV, etc.
    equip_pattern = r'\b([A-Z]{2,5}-?\d+[A-Z]?)\b'

    # Line numbers: variations like RL-123, L-456, etc.
    line_pattern = r'\b([RL]-\d+|[RL]\d+|\d+"?\s*[RL])\b'

    # Instrument tags: PT, TT, FT, PSV, TSV, etc.
    inst_pattern = r'\b([PTFLH][TSIV]{1,2}-?\d+)\b'

    # Size patterns: 2", 4", 6", etc.
    size_pattern = r'\b(\d+)"?\s*(?:INCH|IN)?\b'

    # Extract potential equipment tags
    seen_tags = set()
    for match in re.finditer(equip_pattern, text):
        tag = match.group(1)

        # Filter for likely equipment tags
        if tag in seen_tags:
            continue

        # Common refrigeration equipment prefixes
        if any(tag.startswith(prefix) for prefix in [
            'COMP', 'C-', 'EC-', 'EC', 'COND', 'RCVR',  'HPR', 'TSV', 'HTR',
            'PMP', 'P-', 'AP-', 'HEX', 'CU-', 'VLV', 'PSV', 'SV-'
        ]):
            seen_tags.add(tag)

            # Determine equipment type
            eq_type = 'unknown'
            if tag.startswith('COMP') or tag.startswith('C-'):
                eq_type = 'compressor'
            elif tag.startswith('EC'):
                eq_type = 'evaporative_condenser'
            elif tag.startswith('COND'):
                eq_type = 'condenser'
            elif tag.startswith('RCVR'):
                eq_type = 'receiver'
            elif tag.startswith('HPR'):
                eq_type = 'high_pressure_receiver'
            elif tag.startswith('TSV'):
                eq_type = 'thermosyphon_vessel'
            elif tag.startswith('HTR'):
                eq_type = 'recirculator'
            elif tag.startswith('PMP') or tag.startswith('P-'):
                eq_type = 'pump'
            elif tag.startswith('HEX'):
                eq_type = 'heat_exchanger'
            elif tag.startswith('CU'):
                eq_type = 'cooling_unit'
            elif tag.startswith('PSV') or tag.startswith('SV'):
                eq_type = 'safety_valve'
            elif tag.startswith('VLV'):
                eq_type = 'valve'

            equipment.append({
                'tag': tag,
                'equipment_type': eq_type,
                'description': f'{eq_type.replace("_", " ").title()} {tag}',
                'confidence': 0.75
            })

    # Extract instrument tags
    seen_inst = set()
    for match in re.finditer(inst_pattern, text):
        tag = match.group(1)

        if tag in seen_inst:
            continue
        seen_inst.add(tag)

        # Determine instrument type
        inst_type = 'unknown'
        if tag.startswith('PT'):
            inst_type = 'pressure_transmitter'
        elif tag.startswith('TT'):
            inst_type = 'temperature_transmitter'
        elif tag.startswith('FT'):
            inst_type = 'flow_transmitter'
        elif tag.startswith('LT'):
            inst_type = 'level_transmitter'
        elif tag.startswith('PSV'):
            inst_type = 'pressure_safety_valve'
        elif tag.startswith('TSV'):
            inst_type = 'temperature_safety_valve'
        elif tag.startswith('PI'):
            inst_type = 'pressure_indicator'
        elif tag.startswith('TI'):
            inst_type = 'temperature_indicator'

        instruments.append({
            'tag': tag,
            'instrument_type': inst_type,
            'loop_number': re.sub(r'[A-Z-]', '', tag),
            'confidence': 0.75
        })

    # Extract line numbers
    seen_lines = set()
    for match in re.finditer(line_pattern, text):
        line_num = match.group(1)

        if line_num in seen_lines:
            continue
        seen_lines.add(line_num)

        lines.append({
            'line_number': line_num,
            'size': '',
            'material': 'R-717',  # Assumed ammonia refrigeration
            'service': 'refrigerant',
            'confidence': 0.70
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
            pass  # Duplicate

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
            pass  # Duplicate

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
            pass  # Duplicate

    conn.commit()
    return counts


def update_sheet_metadata(conn, sheet_id, drawing_type, complexity, quality_score):
    """Update sheet metadata"""
    cur = conn.cursor()

    cur.execute("""
        UPDATE sheets
        SET extracted_at = ?,
            extraction_model = 'text-extraction-pymupdf',
            drawing_type = ?,
            complexity = ?,
            quality_score = ?
        WHERE id = ?
    """, (datetime.now().isoformat(), drawing_type, complexity, quality_score, sheet_id))

    conn.commit()


def main():
    """Main extraction process"""
    print("=" * 80)
    print("REFRIGERATION DRAWING EXTRACTION - Sheets 31, 32, 33")
    print("Project: 07308-BIRDCAGE")
    print("=" * 80)

    conn = sqlite3.connect(DB_PATH)

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

        # Extract text from PDF
        print(f"  Extracting text from PDF...")
        text = extract_text_from_pdf(sheet['path'])
        print(f"  Extracted {len(text)} characters")

        # Parse data
        print(f"  Parsing refrigeration data...")
        data = parse_refrigeration_data(text, sheet['drawing_number'], sheet['type'])

        # Insert into database
        print(f"  Inserting data into database...")
        counts = insert_data(conn, sheet['id'], data)

        # Update sheet metadata
        complexity = 'medium' if sheet['type'] == 'plan' else 'medium'
        quality_score = 0.75  # Text-based extraction has moderate confidence

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

        # Show sample equipment
        if data['equipment']:
            print(f"\n  Sample Equipment:")
            for eq in data['equipment'][:10]:
                print(f"    {eq['tag']:15s} - {eq['equipment_type']:25s} (conf: {eq['confidence']:.2f})")

        # Show sample instruments
        if data['instruments']:
            print(f"\n  Sample Instruments:")
            for inst in data['instruments'][:10]:
                print(f"    {inst['tag']:15s} - {inst['instrument_type']:25s} (conf: {inst['confidence']:.2f})")

    conn.close()

    # Final summary
    print("\n" + "=" * 80)
    print("EXTRACTION COMPLETE")
    print("=" * 80)
    print(f"Sheets Processed:  {all_stats['sheets_processed']}")
    print(f"Total Lines:       {all_stats['total_lines']}")
    print(f"Total Equipment:   {all_stats['total_equipment']}")
    print(f"Total Instruments: {all_stats['total_instruments']}")

    # Query database for final counts
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
            SELECT quality_score, drawing_type, complexity, extraction_model
            FROM sheets WHERE id = ?
        """, (sheet['id'],))
        result = cur.fetchone()

        print(f"\n{sheet['drawing_number']} (Sheet {sheet['id']}):")
        print(f"  Lines:       {line_count}")
        print(f"  Equipment:   {equip_count}")
        print(f"  Instruments: {inst_count}")

        if result:
            quality, dwg_type, complexity, model = result
            print(f"  Quality:     {quality:.2f}")
            print(f"  Type:        {dwg_type}")
            print(f"  Complexity:  {complexity}")
            print(f"  Model:       {model}")

    conn.close()

    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
