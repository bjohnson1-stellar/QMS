"""
Extract data from sheets 4, 5, 6 using PDF text extraction.
"""
import fitz
import sqlite3
import re
from datetime import datetime
from collections import defaultdict

DATABASE_PATH = "D:/quality.db"

SHEETS = [
    {"id": 4, "path": "D:/Projects/07308-BIRDCAGE/Refrigeration/R11010-REFRIGERATION-PLAN-PIPE-AND-DUCT-FLOOR-AREA1-Rev.6.pdf"},
    {"id": 5, "path": "D:/Projects/07308-BIRDCAGE/Refrigeration/R11020-REFRIGERATION-PLAN-PIPE-AND-DUCT-FLOOR-AREA-2-Rev.7.pdf"},
    {"id": 6, "path": "D:/Projects/07308-BIRDCAGE/Refrigeration/R11030-REFRIGERATION-PLAN-PIPE-AND-DUCT-FLOOR-AREA-3-Rev.6.pdf"}
]

def extract_text_from_pdf(pdf_path):
    """Extract all text from PDF."""
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()
    return text

def parse_refrigeration_lines(text):
    """Extract refrigeration line information from text."""
    lines = []

    # Pattern for refrigeration lines with size and service type
    # Examples: 1 1/2" HTRS, 3/4" HTRL, 2" CD, 1" DC, 3" HTS, 1 5/8" LTS
    # HTRS = Hot Gas Suction, HTRL = Hot Gas Liquid, CD = Condensate Drain
    # DC = Drain Condensate, HTS = Hot Gas?, LTS = Liquid?
    # HGD = Hot Gas Discharge

    line_pattern = r'(\d+(?:\s+\d+/\d+)?)"?\s+(HTRS|HTRL|CD|DC|HTS|LTS|HGD|SR|LL|RL)'

    service_map = {
        'HTRS': 'Hot Gas Suction Return',
        'HTRL': 'Hot Gas Return Liquid',
        'HGD': 'Hot Gas Discharge',
        'CD': 'Condensate Drain',
        'DC': 'Drain Condensate',
        'HTS': 'Hot Gas Supply',
        'LTS': 'Liquid Supply',
        'SR': 'Suction Return',
        'LL': 'Liquid Line',
        'RL': 'Refrigerant Line'
    }

    matches = re.findall(line_pattern, text)

    line_dict = defaultdict(int)
    for size, service_code in matches:
        size_clean = size.strip()
        service = service_map.get(service_code, service_code)
        line_number = f"{size_clean}\"-{service_code}"
        line_dict[line_number] += 1

    # Create unique lines with counts
    for line_number, count in line_dict.items():
        size, service_code = line_number.split('-')
        size = size.replace('"', '').strip()
        service = service_map.get(service_code, service_code)

        lines.append({
            'line_number': line_number,
            'size': size,
            'material': 'Copper',  # Typical for refrigeration
            'spec_class': None,
            'from_location': None,
            'to_location': None,
            'service': service,
            'confidence': 0.85,
            'occurrences': count
        })

    return lines

def parse_equipment(text):
    """Extract equipment tags from text."""
    equipment = []

    # Pattern for AHU tags: AHU1-101-1, AHU1-102-2, etc.
    ahu_pattern = r'AHU(\d+)-(\d+)-(\d+)'
    ahu_matches = re.findall(ahu_pattern, text)

    ahu_dict = set()
    for area, room, unit in ahu_matches:
        tag = f"AHU{area}-{room}-{unit}"
        ahu_dict.add(tag)

    for tag in sorted(ahu_dict):
        equipment.append({
            'tag': tag,
            'description': f'Air Handling Unit {tag}',
            'equipment_type': 'Air Handling Unit',
            'confidence': 0.90
        })

    # Pattern for HTR (Heater) tags: HTR110-1, HTR110-2, etc.
    htr_pattern = r'HTR(\d+)-(\d+)'
    htr_matches = re.findall(htr_pattern, text)

    htr_dict = set()
    for num1, num2 in htr_matches:
        tag = f"HTR{num1}-{num2}"
        htr_dict.add(tag)

    for tag in sorted(htr_dict):
        equipment.append({
            'tag': tag,
            'description': f'Heater {tag}',
            'equipment_type': 'Heater',
            'confidence': 0.85
        })

    return equipment

def parse_instruments(text):
    """Extract instrument tags from text."""
    instruments = []

    # Common instrument patterns
    # PT = Pressure Transmitter, TT = Temperature Transmitter, etc.
    inst_pattern = r'([A-Z]{2})-?(\d{3,4})'

    inst_prefixes = {
        'PT': 'Pressure Transmitter',
        'TT': 'Temperature Transmitter',
        'FT': 'Flow Transmitter',
        'LT': 'Level Transmitter',
        'PS': 'Pressure Switch',
        'TS': 'Temperature Switch',
        'FS': 'Flow Switch',
        'LS': 'Level Switch'
    }

    matches = re.findall(inst_pattern, text)

    inst_dict = set()
    for prefix, number in matches:
        if prefix in inst_prefixes:
            tag = f"{prefix}-{number}"
            inst_type = inst_prefixes[prefix]
            inst_dict.add((tag, inst_type))

    for tag, inst_type in sorted(inst_dict):
        instruments.append({
            'tag': tag,
            'instrument_type': inst_type,
            'loop_number': tag.split('-')[1] if '-' in tag else None,
            'confidence': 0.75
        })

    return instruments

def store_extractions(conn, sheet_id, extracted_data):
    """Store extracted data in database."""
    cursor = conn.cursor()

    stats = {
        'lines': 0,
        'equipment': 0,
        'instruments': 0
    }

    # Insert lines (only store unique ones, not duplicates)
    seen_lines = set()
    for line in extracted_data.get('lines', []):
        line_key = line['line_number']
        if line_key not in seen_lines:
            cursor.execute("""
                INSERT INTO lines (sheet_id, line_number, size, material,
                                 spec_class, from_location, to_location, service, confidence)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                sheet_id,
                line.get('line_number'),
                line.get('size'),
                line.get('material'),
                line.get('spec_class'),
                line.get('from_location'),
                line.get('to_location'),
                line.get('service'),
                line.get('confidence', 0.7)
            ))
            stats['lines'] += 1
            seen_lines.add(line_key)

    # Insert equipment
    for equip in extracted_data.get('equipment', []):
        cursor.execute("""
            INSERT INTO equipment (sheet_id, tag, description, equipment_type, confidence)
            VALUES (?, ?, ?, ?, ?)
        """, (
            sheet_id,
            equip.get('tag'),
            equip.get('description'),
            equip.get('equipment_type'),
            equip.get('confidence', 0.7)
        ))
        stats['equipment'] += 1

    # Insert instruments
    for inst in extracted_data.get('instruments', []):
        cursor.execute("""
            INSERT INTO instruments (sheet_id, tag, instrument_type, loop_number, confidence)
            VALUES (?, ?, ?, ?, ?)
        """, (
            sheet_id,
            inst.get('tag'),
            inst.get('instrument_type'),
            inst.get('loop_number'),
            inst.get('confidence', 0.7)
        ))
        stats['instruments'] += 1

    # Calculate quality score
    all_confidences = []
    for line in extracted_data.get('lines', []):
        all_confidences.append(line.get('confidence', 0.7))
    for equip in extracted_data.get('equipment', []):
        all_confidences.append(equip.get('confidence', 0.7))
    for inst in extracted_data.get('instruments', []):
        all_confidences.append(inst.get('confidence', 0.7))

    quality_score = sum(all_confidences) / len(all_confidences) if all_confidences else 0.7

    # Update sheet metadata
    cursor.execute("""
        UPDATE sheets
        SET extracted_at = ?,
            extraction_model = ?,
            quality_score = ?,
            complexity = ?,
            drawing_type = ?
        WHERE id = ?
    """, (
        datetime.now().isoformat(),
        'text-extraction-pymupdf',
        quality_score,
        extracted_data.get('complexity', 'medium'),
        'plan',
        sheet_id
    ))

    conn.commit()

    return stats, quality_score

def main():
    print("Refrigeration Plan Extraction - Text-Based Approach")
    print("=" * 70)
    print()

    conn = sqlite3.connect(DATABASE_PATH)

    for sheet in SHEETS:
        sheet_id = sheet['id']
        pdf_path = sheet['path']

        # Get sheet info from database
        cursor = conn.cursor()
        cursor.execute("SELECT file_name, drawing_number FROM sheets WHERE id = ?", (sheet_id,))
        row = cursor.fetchone()

        if not row:
            print(f"Sheet {sheet_id}: NOT FOUND IN DATABASE")
            continue

        file_name, drawing_number = row
        print(f"Sheet {sheet_id}: {drawing_number}")
        print(f"File: {file_name}")
        print("-" * 70)

        try:
            # Extract text from PDF
            print("  Extracting text from PDF...")
            text = extract_text_from_pdf(pdf_path)
            print(f"  Extracted {len(text)} characters")

            # Parse data
            print("  Parsing refrigeration lines...")
            lines = parse_refrigeration_lines(text)

            print("  Parsing equipment...")
            equipment = parse_equipment(text)

            print("  Parsing instruments...")
            instruments = parse_instruments(text)

            # Determine complexity based on item count
            total_items = len(lines) + len(equipment) + len(instruments)
            if total_items < 10:
                complexity = 'simple'
            elif total_items < 30:
                complexity = 'medium'
            else:
                complexity = 'high'

            extracted_data = {
                'lines': lines,
                'equipment': equipment,
                'instruments': instruments,
                'complexity': complexity
            }

            # Store in database
            print("  Storing in database...")
            stats, quality_score = store_extractions(conn, sheet_id, extracted_data)

            # Report results
            print()
            print(f"  Extraction Results:")
            print(f"    - Drawing Type: Plan")
            print(f"    - Complexity: {complexity}")
            print(f"    - Lines: {stats['lines']}")
            print(f"    - Equipment: {stats['equipment']}")
            print(f"    - Instruments: {stats['instruments']}")
            print(f"    - Quality Score: {quality_score:.2f}")
            print()
            print("  Status: COMPLETED")
            print()

        except Exception as e:
            print(f"  ERROR: {str(e)}")
            import traceback
            traceback.print_exc()
            print()

    conn.close()

    print("=" * 70)
    print("Extraction Complete")

if __name__ == "__main__":
    main()
