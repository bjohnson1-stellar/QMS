"""
Extract instruments and equipment from Refrigeration-Controls drawings.
Analyzes text extracted from PDFs to identify equipment and instruments.
"""
import sqlite3
import re
import subprocess
from datetime import datetime

# Configuration
DATABASE = "D:/quality.db"
MODEL = "claude-sonnet-4-5-20250929"

SHEETS = [
    {
        "id": 153,
        "path": "D:/Projects/07308-BIRDCAGE/Refrigeration-Controls/RC14050-REFRIGERATION-CONTROLS-PLAN-PIPE-AND-DUCT-ROOF-AREA-5-Rev.4.pdf",
        "drawing_number": "RC14050",
        "title": "REFRIGERATION CONTROLS PLAN PIPE AND DUCT ROOF-AREA 5",
        "revision": "4"
    },
    {
        "id": 154,
        "path": "D:/Projects/07308-BIRDCAGE/Refrigeration-Controls/RC14060-REFRIGERATION-CONTROLS-PLAN-PIPE-AND-DUCT-ROOF-AREA-6-Rev.4.pdf",
        "drawing_number": "RC14060",
        "title": "REFRIGERATION CONTROLS PLAN PIPE AND DUCT ROOF-AREA 6",
        "revision": "4"
    },
    {
        "id": 155,
        "path": "D:/Projects/07308-BIRDCAGE/Refrigeration-Controls/RC14070-REFRIGERATION-CONTROLS-PLAN-PIPE-AND-DUCT-ROOF-AREA-7-Rev.4.pdf",
        "drawing_number": "RC14070",
        "title": "REFRIGERATION CONTROLS PLAN PIPE AND DUCT ROOF-AREA 7",
        "revision": "4"
    }
]

def extract_text_from_pdf(pdf_path):
    """Extract text from PDF using pdftotext."""
    try:
        result = subprocess.run(
            ["pdftotext", pdf_path, "-"],
            capture_output=True,
            check=True,
            text=True
        )
        return result.stdout
    except Exception as e:
        print(f"Error extracting text: {e}")
        return ""

def parse_equipment_and_instruments(text):
    """Parse equipment and instrument tags from extracted text."""
    equipment = []
    instruments = []

    # Patterns for equipment
    # RMAU pattern: RMAU5-106-1, RMAU5-106-2
    rmau_pattern = r'RMAU\d+-\d+-\d+'
    rmau_matches = re.findall(rmau_pattern, text)
    for match in set(rmau_matches):
        equipment.append({
            'tag': match,
            'equipment_type': 'RMAU',
            'description': 'Refrigeration Makeup Air Unit',
            'confidence': 0.95
        })

    # HEX pattern: HEX5-106-1, HEX5-106-2
    hex_pattern = r'HEX\d+-\d+-\d+'
    hex_matches = re.findall(hex_pattern, text)
    for match in set(hex_matches):
        equipment.append({
            'tag': match,
            'equipment_type': 'HEX',
            'description': 'Heat Exchanger',
            'confidence': 0.95
        })

    # AHU pattern: NH3 AHU7-108-1-CG01, AHU6-109-1, etc.
    # More flexible pattern to catch various formats
    ahu_pattern = r'(?:NH3\s+)?AHU\d+-\d+-\d+(?:-[A-Z0-9]+)?'
    ahu_matches = re.findall(ahu_pattern, text)
    for match in set(ahu_matches):
        # Clean up the match
        clean_match = match.strip()
        equipment.append({
            'tag': clean_match,
            'equipment_type': 'AHU',
            'description': 'Air Handling Unit',
            'confidence': 0.95
        })

    # Extract control group (CG) from equipment tags
    cg_pattern = r'([A-Z0-9-]+)\s+(CG\d+)'
    cg_matches = re.findall(cg_pattern, text)
    for equipment_tag, cg_tag in cg_matches:
        instruments.append({
            'tag': cg_tag,
            'instrument_type': 'CG',
            'loop_number': equipment_tag.strip(),
            'confidence': 0.90
        })

    # CV pattern: CV01, CV02, CV03, CV04
    cv_pattern = r'\b(CV\d+)\b'
    cv_matches = re.findall(cv_pattern, text)

    # Try to associate CV with nearby equipment
    lines = text.split('\n')
    for i, line in enumerate(lines):
        cv_in_line = re.findall(cv_pattern, line)
        if cv_in_line:
            # Look for equipment in same or nearby lines
            context = ' '.join(lines[max(0, i-2):min(len(lines), i+3)])
            rmau_in_context = re.findall(rmau_pattern, context)
            hex_in_context = re.findall(hex_pattern, context)
            ahu_in_context = re.findall(ahu_pattern, context)

            equipment_ref = None
            if rmau_in_context:
                equipment_ref = rmau_in_context[0]
            elif hex_in_context:
                equipment_ref = hex_in_context[0]
            elif ahu_in_context:
                equipment_ref = ahu_in_context[0]

            for cv in cv_in_line:
                instruments.append({
                    'tag': cv,
                    'instrument_type': 'CV',
                    'loop_number': equipment_ref,
                    'confidence': 0.85
                })

    # CP pattern: CP1, CP2, etc.
    cp_pattern = r'\b(CP\d+)\b'
    cp_matches = re.findall(cp_pattern, text)

    # Try to associate CP with nearby equipment
    for i, line in enumerate(lines):
        cp_in_line = re.findall(cp_pattern, line)
        if cp_in_line:
            # Look for equipment in same or nearby lines
            context = ' '.join(lines[max(0, i-2):min(len(lines), i+3)])
            rmau_in_context = re.findall(rmau_pattern, context)
            hex_in_context = re.findall(hex_pattern, context)
            ahu_in_context = re.findall(ahu_pattern, context)

            equipment_ref = None
            if rmau_in_context:
                equipment_ref = rmau_in_context[0]
            elif hex_in_context:
                equipment_ref = hex_in_context[0]
            elif ahu_in_context:
                equipment_ref = ahu_in_context[0]

            for cp in cp_in_line:
                instruments.append({
                    'tag': cp,
                    'instrument_type': 'CP',
                    'loop_number': equipment_ref,
                    'confidence': 0.85
                })

    # Remove duplicates while preserving order
    seen_equipment = set()
    unique_equipment = []
    for eq in equipment:
        if eq['tag'] not in seen_equipment:
            seen_equipment.add(eq['tag'])
            unique_equipment.append(eq)

    seen_instruments = set()
    unique_instruments = []
    for inst in instruments:
        key = (inst['tag'], inst['loop_number'])
        if key not in seen_instruments:
            seen_instruments.add(key)
            unique_instruments.append(inst)

    return unique_equipment, unique_instruments

def insert_equipment(conn, sheet_id, equipment_list):
    """Insert equipment into database."""
    cursor = conn.cursor()
    count = 0

    for eq in equipment_list:
        tag = eq.get('tag', '').strip()
        if not tag:
            continue

        equipment_type = eq.get('equipment_type', '').strip()
        description = eq.get('description', '').strip()
        confidence = eq.get('confidence', 0.9)

        try:
            cursor.execute("""
                INSERT INTO equipment (sheet_id, tag, equipment_type, description, confidence)
                VALUES (?, ?, ?, ?, ?)
            """, (sheet_id, tag, equipment_type, description, confidence))
            count += 1
            print(f"    Added: {tag:25s} ({equipment_type})")
        except sqlite3.IntegrityError:
            print(f"    Skip (duplicate): {tag}")

    return count

def insert_instruments(conn, sheet_id, instrument_list):
    """Insert instruments into database."""
    cursor = conn.cursor()
    count = 0

    for inst in instrument_list:
        tag = inst.get('tag', '').strip()
        if not tag:
            continue

        instrument_type = inst.get('instrument_type', '').strip()
        loop_number = inst.get('loop_number', '').strip() or None
        confidence = inst.get('confidence', 0.9)

        try:
            cursor.execute("""
                INSERT INTO instruments (sheet_id, tag, instrument_type, loop_number, confidence)
                VALUES (?, ?, ?, ?, ?)
            """, (sheet_id, tag, instrument_type, loop_number, confidence))
            count += 1
            loop_str = f" (loop: {loop_number})" if loop_number else ""
            print(f"    Added: {tag:25s} ({instrument_type}){loop_str}")
        except sqlite3.IntegrityError:
            print(f"    Skip (duplicate): {tag}")

    return count

def update_sheet_metadata(conn, sheet_id, drawing_type, complexity, quality_score):
    """Update sheet metadata after extraction."""
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE sheets
        SET extracted_at = ?,
            extraction_model = ?,
            drawing_type = ?,
            complexity = ?,
            quality_score = ?
        WHERE id = ?
    """, (datetime.now().isoformat(), MODEL, drawing_type, complexity, quality_score, sheet_id))

def main():
    """Main extraction process."""
    print("=" * 80)
    print("REFRIGERATION-CONTROLS EXTRACTION")
    print("Project: 07308-BIRDCAGE")
    print("Method: Text-based pattern matching")
    print("=" * 80)
    print()

    conn = sqlite3.connect(DATABASE)

    total_equipment = 0
    total_instruments = 0

    for sheet in SHEETS:
        print(f"Processing Sheet {sheet['id']}: {sheet['drawing_number']} Rev {sheet['revision']}")
        print(f"  {sheet['title']}")

        # Extract text from PDF
        print(f"  Extracting text from PDF...")
        text = extract_text_from_pdf(sheet['path'])

        if not text:
            print(f"  ERROR: Could not extract text")
            continue

        # Parse equipment and instruments
        print(f"  Parsing equipment and instruments...")
        equipment_list, instrument_list = parse_equipment_and_instruments(text)

        print(f"  Found {len(equipment_list)} equipment items, {len(instrument_list)} instruments")

        # Insert equipment
        if equipment_list:
            print(f"  Equipment:")
            eq_count = insert_equipment(conn, sheet['id'], equipment_list)
            total_equipment += eq_count

        # Insert instruments
        if instrument_list:
            print(f"  Instruments:")
            inst_count = insert_instruments(conn, sheet['id'], instrument_list)
            total_instruments += inst_count

        # Calculate quality score
        all_items = equipment_list + instrument_list
        if all_items:
            avg_confidence = sum(item.get('confidence', 0.9) for item in all_items) / len(all_items)
            quality_score = round(avg_confidence, 2)
        else:
            quality_score = 0.0

        # Update sheet metadata
        drawing_type = 'plan'
        complexity = 'medium'
        update_sheet_metadata(conn, sheet['id'], drawing_type, complexity, quality_score)

        print(f"  Drawing Type: {drawing_type}")
        print(f"  Complexity: {complexity}")
        print(f"  Quality Score: {quality_score}")
        print()

        conn.commit()

    conn.close()

    print("=" * 80)
    print("EXTRACTION SUMMARY")
    print("=" * 80)
    print(f"Sheets Processed:   {len(SHEETS)}")
    print(f"Total Equipment:    {total_equipment}")
    print(f"Total Instruments:  {total_instruments}")
    print(f"Database:           {DATABASE}")
    print()

if __name__ == "__main__":
    main()
