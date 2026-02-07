#!/usr/bin/env python3
"""
Extract data from refrigeration detail drawings using text extraction and pattern matching.
Project: 07308-BIRDCAGE, Sheets 43-45
"""

import os
import sys
import re
import sqlite3
from datetime import datetime
import fitz  # PyMuPDF

DB_PATH = "D:/quality.db"

SHEETS = [
    {
        "id": 43,
        "path": "D:/Projects/07308-BIRDCAGE/Refrigeration/R50012-REFRIGERATION-DETAILS-GENERAL-Rev.3.pdf",
        "drawing_number": "R50012",
        "title": "REFRIGERATION-DETAILS-GENERAL",
        "revision": "3"
    },
    {
        "id": 44,
        "path": "D:/Projects/07308-BIRDCAGE/Refrigeration/R50100-REFRIGERATION-DETAILS-PIPE-AND-EQUIPMENT-Rev.3.pdf",
        "drawing_number": "R50100",
        "title": "REFRIGERATION-DETAILS-PIPE-AND-EQUIPMENT",
        "revision": "3"
    },
    {
        "id": 45,
        "path": "D:/Projects/07308-BIRDCAGE/Refrigeration/R50101-REFRIGERATION-DETAILS-PIPE-AND-EQUIPMENT-Rev.3.pdf",
        "drawing_number": "R50101",
        "title": "REFRIGERATION-DETAILS-PIPE-AND-EQUIPMENT",
        "revision": "3"
    }
]

# Enhanced regex patterns for refrigeration drawings
PATTERNS = {
    # Line numbers - various formats
    'line_full': re.compile(r'(\d+(?:\.\d+)?)"?\s*[-/]?\s*([A-Z]{2,4})\s*[-/]?\s*(\d+)\s*[-/]?\s*([A-Z0-9]+)', re.IGNORECASE),
    'line_simple': re.compile(r'(\d+)"?\s*([A-Z]{2,4})[-\s]?(\d+)(?:\s|$)', re.IGNORECASE),
    'line_with_sch': re.compile(r'(\d+(?:[/\-]\d+)?)"?\s*(SCH\s*\d+[A-Z]*)', re.IGNORECASE),

    # Equipment tags
    'equipment': re.compile(r'\b([A-Z]{1,3})[-\s]?(\d{3,4}[A-Z]?)\b'),

    # Instruments and valves
    'instrument': re.compile(r'\b([PTFL][TISCV]{1,2})[-\s]?(\d{3,4}[A-Z]?)\b'),
    'psv': re.compile(r'\b(PSV|PRV|SV)[-\s]?(\d{3,4}[A-Z]?)\b', re.IGNORECASE),
    'valve': re.compile(r'\b([A-Z]{1,3}V)[-\s]?(\d{3,4}[A-Z]?)\b'),

    # Welds
    'weld': re.compile(r'\b(W|WLD|WELD)[-\s]?(\d+)\b', re.IGNORECASE),

    # Pipe specs
    'schedule': re.compile(r'\b(SCH|SCHEDULE)\s*(\d+[A-Z]*)\b', re.IGNORECASE),
    'nps': re.compile(r'\b(NPS)\s*(\d+(?:\.\d+)?)\b', re.IGNORECASE),
}

# Material codes
MATERIALS = {
    'CS': 'Carbon Steel',
    'SS': 'Stainless Steel',
    'A53': 'Carbon Steel A53',
    'A106': 'Carbon Steel A106',
    'A312': 'Stainless Steel A312',
    'CU': 'Copper',
    'AL': 'Aluminum',
}

# Equipment prefixes
EQUIPMENT_TYPES = {
    'P': 'Pump', 'V': 'Vessel', 'TK': 'Tank', 'E': 'Exchanger',
    'C': 'Compressor', 'R': 'Receiver', 'ACC': 'Accumulator',
    'SEP': 'Separator', 'F': 'Filter', 'S': 'Strainer',
    'CV': 'Control Valve', 'PRV': 'Pressure Relief Valve',
    'PCV': 'Pressure Control Valve', 'LCV': 'Level Control Valve',
    'TCV': 'Temperature Control Valve', 'FCV': 'Flow Control Valve',
}

# Instrument prefixes
INSTRUMENT_TYPES = {
    'PT': 'Pressure Transmitter', 'FT': 'Flow Transmitter',
    'TT': 'Temperature Transmitter', 'LT': 'Level Transmitter',
    'PI': 'Pressure Indicator', 'FI': 'Flow Indicator',
    'TI': 'Temperature Indicator', 'LI': 'Level Indicator',
    'PSV': 'Pressure Safety Valve', 'PRV': 'Pressure Relief Valve',
    'PCV': 'Pressure Control Valve', 'LCV': 'Level Control Valve',
    'TCV': 'Temperature Control Valve', 'FCV': 'Flow Control Valve',
    'TS': 'Temperature Switch', 'PS': 'Pressure Switch',
}


def extract_text_from_pdf(pdf_path):
    """Extract all text from PDF."""
    try:
        doc = fitz.open(pdf_path)
        text = ""
        for page in doc:
            text += page.get_text()
        doc.close()
        return text
    except Exception as e:
        print(f"ERROR: Could not read PDF: {e}")
        return ""


def parse_line_number(text_line):
    """Try to parse line number from text."""
    # Try full format
    match = PATTERNS['line_full'].search(text_line)
    if match:
        size, material, number, spec = match.groups()
        return {
            'line_number': f"{size}\"-{material}-{number}-{spec}",
            'size': f"{size}\"",
            'material': MATERIALS.get(material.upper(), material.upper()),
            'spec_class': spec.upper()
        }

    # Try simple format
    match = PATTERNS['line_simple'].search(text_line)
    if match:
        size, material, number = match.groups()
        return {
            'line_number': f"{size}\"-{material}-{number}",
            'size': f"{size}\"",
            'material': MATERIALS.get(material.upper(), material.upper()),
            'spec_class': None
        }

    # Try schedule format
    match = PATTERNS['line_with_sch'].search(text_line)
    if match:
        size, schedule = match.groups()
        return {
            'line_number': f"{size}\" {schedule}",
            'size': f"{size}\"",
            'material': schedule,
            'spec_class': None
        }

    return None


def extract_lines(text):
    """Extract pipe/line information."""
    lines = []
    seen = set()

    for line in text.split('\n'):
        line = line.strip()
        if not line or len(line) < 5:
            continue

        parsed = parse_line_number(line)
        if parsed and parsed['line_number'] not in seen:
            lines.append({
                **parsed,
                'from_location': None,
                'to_location': None,
                'service': None,
                'confidence': 0.75
            })
            seen.add(parsed['line_number'])

    return lines


def extract_equipment(text):
    """Extract equipment tags."""
    equipment = []
    seen = set()

    for match in PATTERNS['equipment'].finditer(text):
        prefix = match.group(1).upper()
        number = match.group(2)
        tag = f"{prefix}-{number}"

        if tag not in seen and (prefix in EQUIPMENT_TYPES or len(prefix) <= 2):
            equipment.append({
                'tag': tag,
                'equipment_type': EQUIPMENT_TYPES.get(prefix, prefix),
                'description': None,
                'confidence': 0.80 if prefix in EQUIPMENT_TYPES else 0.65
            })
            seen.add(tag)

    return equipment


def extract_instruments(text):
    """Extract instrument and valve tags."""
    instruments = []
    seen = set()

    # PSV/PRV (high priority)
    for match in PATTERNS['psv'].finditer(text):
        prefix = match.group(1).upper()
        number = match.group(2)
        tag = f"{prefix}-{number}"

        if tag not in seen:
            instruments.append({
                'tag': tag,
                'instrument_type': INSTRUMENT_TYPES.get(prefix, f"{prefix} Valve"),
                'loop_number': None,
                'confidence': 0.85
            })
            seen.add(tag)

    # Standard instruments
    for match in PATTERNS['instrument'].finditer(text):
        prefix = match.group(1).upper()
        number = match.group(2)
        tag = f"{prefix}-{number}"

        if tag not in seen:
            inst_type = INSTRUMENT_TYPES.get(prefix)
            if inst_type:
                instruments.append({
                    'tag': tag,
                    'instrument_type': inst_type,
                    'loop_number': None,
                    'confidence': 0.80
                })
                seen.add(tag)

    # Control valves
    for match in PATTERNS['valve'].finditer(text):
        prefix = match.group(1).upper()
        number = match.group(2)
        tag = f"{prefix}-{number}"

        if tag not in seen and 'V' in prefix:
            instruments.append({
                'tag': tag,
                'instrument_type': INSTRUMENT_TYPES.get(prefix, f"{prefix} Valve"),
                'loop_number': None,
                'confidence': 0.75
            })
            seen.add(tag)

    return instruments


def extract_welds(text):
    """Extract weld information."""
    welds = []
    seen = set()

    for match in PATTERNS['weld'].finditer(text):
        prefix = match.group(1).upper()
        number = match.group(2)
        weld_id = f"{prefix}-{number}"

        if weld_id not in seen:
            welds.append({
                'weld_id': weld_id,
                'weld_type': None,
                'size': None,
                'joint_type': None,
                'nde_required': None,
                'confidence': 0.70
            })
            seen.add(weld_id)

    return welds


def process_sheet(sheet_info):
    """Process a single drawing sheet."""
    print(f"\nProcessing Sheet {sheet_info['id']}: {sheet_info['drawing_number']} Rev {sheet_info['revision']}")
    print("=" * 80)

    # Check if file exists
    if not os.path.exists(sheet_info['path']):
        print(f"ERROR: File not found: {sheet_info['path']}")
        return None

    # Extract text
    print("Extracting text from PDF...")
    text = extract_text_from_pdf(sheet_info['path'])

    if not text:
        print("WARNING: No text extracted from PDF")
        return None

    print(f"Extracted {len(text)} characters")

    # Extract data
    print("Extracting data...")
    lines = extract_lines(text)
    equipment = extract_equipment(text)
    instruments = extract_instruments(text)
    welds = extract_welds(text)

    print(f"Found: {len(lines)} lines, {len(equipment)} equipment, {len(instruments)} instruments, {len(welds)} welds")

    # Calculate quality score
    all_items = lines + equipment + instruments + welds
    quality_score = sum(item['confidence'] for item in all_items) / len(all_items) if all_items else 0.0

    return {
        'sheet_id': sheet_info['id'],
        'lines': lines,
        'equipment': equipment,
        'instruments': instruments,
        'welds': welds,
        'quality_score': quality_score
    }


def store_in_database(data):
    """Store extraction data in database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    sheet_id = data['sheet_id']

    try:
        # Clear existing data
        cursor.execute("DELETE FROM lines WHERE sheet_id = ?", (sheet_id,))
        cursor.execute("DELETE FROM equipment WHERE sheet_id = ?", (sheet_id,))
        cursor.execute("DELETE FROM instruments WHERE sheet_id = ?", (sheet_id,))
        cursor.execute("DELETE FROM welds WHERE sheet_id = ?", (sheet_id,))

        # Insert lines
        for line in data['lines']:
            cursor.execute("""
                INSERT INTO lines (sheet_id, line_number, size, material, spec_class,
                                 from_location, to_location, service, confidence)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (sheet_id, line['line_number'], line['size'], line['material'],
                  line['spec_class'], line['from_location'], line['to_location'],
                  line['service'], line['confidence']))

        # Insert equipment
        for eq in data['equipment']:
            cursor.execute("""
                INSERT INTO equipment (sheet_id, tag, equipment_type, description, confidence)
                VALUES (?, ?, ?, ?, ?)
            """, (sheet_id, eq['tag'], eq['equipment_type'], eq['description'], eq['confidence']))

        # Insert instruments
        for inst in data['instruments']:
            cursor.execute("""
                INSERT INTO instruments (sheet_id, tag, instrument_type, loop_number, confidence)
                VALUES (?, ?, ?, ?, ?)
            """, (sheet_id, inst['tag'], inst['instrument_type'], inst['loop_number'], inst['confidence']))

        # Insert welds
        for weld in data['welds']:
            cursor.execute("""
                INSERT INTO welds (sheet_id, weld_id, weld_type, size, joint_type, nde_required, confidence)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (sheet_id, weld['weld_id'], weld['weld_type'], weld['size'],
                  weld['joint_type'], weld['nde_required'], weld['confidence']))

        # Update sheet metadata
        cursor.execute("""
            UPDATE sheets
            SET extracted_at = ?,
                extraction_model = 'text-pattern-match',
                quality_score = ?,
                drawing_type = 'detail',
                complexity = 'medium'
            WHERE id = ?
        """, (datetime.now().isoformat(), data['quality_score'], sheet_id))

        conn.commit()
        return True

    except Exception as e:
        print(f"ERROR: Database operation failed: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


def print_summary(data):
    """Print extraction summary."""
    print(f"\nExtraction Summary:")
    print(f"  Lines: {len(data['lines'])}")
    if data['lines'][:3]:
        print("    Sample:")
        for line in data['lines'][:3]:
            print(f"      - {line['line_number']}")

    print(f"  Equipment: {len(data['equipment'])}")
    if data['equipment'][:5]:
        print("    Sample:")
        for eq in data['equipment'][:5]:
            print(f"      - {eq['tag']}: {eq['equipment_type']}")

    print(f"  Instruments: {len(data['instruments'])}")
    if data['instruments'][:5]:
        print("    Sample:")
        for inst in data['instruments'][:5]:
            print(f"      - {inst['tag']}: {inst['instrument_type']}")

    print(f"  Welds: {len(data['welds'])}")
    if data['welds'][:3]:
        print("    Sample:")
        for weld in data['welds'][:3]:
            print(f"      - {weld['weld_id']}")

    print(f"  Quality Score: {data['quality_score']:.2f}")


def main():
    """Main extraction process."""
    print("=" * 80)
    print("REFRIGERATION DETAIL DRAWING EXTRACTION")
    print("Project: 07308-BIRDCAGE")
    print("Method: Text extraction with pattern matching")
    print("=" * 80)

    results = []

    for sheet in SHEETS:
        data = process_sheet(sheet)

        if data:
            print_summary(data)

            success = store_in_database(data)

            results.append({
                'sheet_id': sheet['id'],
                'drawing_number': sheet['drawing_number'],
                'success': success,
                'total_items': len(data['lines']) + len(data['equipment']) + len(data['instruments']) + len(data['welds']),
                'quality_score': data['quality_score']
            })
        else:
            results.append({
                'sheet_id': sheet['id'],
                'drawing_number': sheet['drawing_number'],
                'success': False,
                'total_items': 0,
                'quality_score': 0.0
            })

    # Final summary
    print("\n" + "=" * 80)
    print("FINAL SUMMARY")
    print("=" * 80)

    for result in results:
        status = "SUCCESS" if result['success'] else "FAILED"
        print(f"\nSheet {result['sheet_id']} ({result['drawing_number']}): {status}")
        print(f"  Total Items: {result['total_items']}")
        print(f"  Quality Score: {result['quality_score']:.2f}")

    total_items = sum(r['total_items'] for r in results)
    successful = sum(1 for r in results if r['success'])

    print(f"\nSheets Processed: {len(results)}")
    print(f"Successful: {successful}/{len(results)}")
    print(f"Total Items Extracted: {total_items}")
    print("=" * 80)


if __name__ == '__main__':
    main()
