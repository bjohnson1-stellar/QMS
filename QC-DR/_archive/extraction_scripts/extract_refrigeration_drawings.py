import PyPDF2
import sqlite3
import re
from datetime import datetime
from pathlib import Path
from collections import defaultdict

def extract_text_from_pdf(pdf_path):
    """Extract all text from a PDF file."""
    try:
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            text = ''
            for page in reader.pages:
                text += page.extract_text() + '\n'
            return text
    except Exception as e:
        print(f"  Error reading PDF: {e}")
        return ''

def parse_refrigeration_lines(text):
    """
    Parse refrigeration line identifiers from text.
    Common formats in refrigeration drawings:
    - HTRL, HTRS, HRL, HRS (Hot Refrigerant Lines)
    - RL-XXX (Refrigerant Liquid)
    - RS-XXX (Refrigerant Suction)
    - With size: 3/4" HTRL, 1 1/2" HTRS
    """
    lines = []
    seen = set()

    # Pattern variations for refrigeration lines
    patterns = [
        # Common Stellar format: 3/4" HTRL, 1 1/2" HTRS
        r'(\d+(?:\s+\d+/\d+|\s*\d+)?)\s*["\']?\s*(HTR[LS]|HR[LS]|R[LSDH]|CW|BW|CWR|CWS)(?:-(\d{2,4}))?',
        # Standard format: Size with line type: 1-1/4" RL-101, 2" RS-201
        r'(\d+(?:-\d+/\d+)?)\s*["\']?\s*(R[LSDH]|CW|BW|CWR|CWS)-(\d{2,4})',
        # Just line identifier: RL-101, RS-201, HTRL, HTRS
        r'\b(HTR[LS]|HR[LS]|R[LSDH]|CW|BW|CWR|CWS)(?:-(\d{2,4}))?\b',
        # Full format with spec: 1-1/2"-RL-101-SCH40
        r'(\d+(?:-\d+/\d+)?)["\']?-?(R[LSDH]|CW|BW)-(\d{2,4})-?([A-Z0-9]+)?',
    ]

    for pattern in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            groups = match.groups()
            full_match = match.group(0)

            # Parse based on match structure
            size = None
            service = None
            number = None
            spec = None

            if 'HTRL' in full_match.upper() or 'HRL' in full_match.upper():
                service = 'HTRL'
                service_name = 'Hot Refrigerant Liquid'
            elif 'HTRS' in full_match.upper() or 'HRS' in full_match.upper():
                service = 'HTRS'
                service_name = 'Hot Refrigerant Suction'
            elif 'RL' in full_match.upper():
                service = 'RL'
                service_name = 'Refrigerant Liquid'
            elif 'RS' in full_match.upper():
                service = 'RS'
                service_name = 'Refrigerant Suction'
            elif 'RD' in full_match.upper():
                service = 'RD'
                service_name = 'Refrigerant Discharge'
            elif 'RH' in full_match.upper():
                service = 'RH'
                service_name = 'Refrigerant Hot Gas'
            elif 'CW' in full_match.upper():
                service = 'CW'
                service_name = 'Chilled Water'
            else:
                continue

            # Extract size if present
            size_match = re.search(r'(\d+(?:\s+\d+/\d+|\s*\d+)?)\s*["\']', full_match)
            if size_match:
                size = size_match.group(1).strip() + '"'

            # Extract number if present
            number_match = re.search(r'-(\d{2,4})', full_match)
            if number_match:
                number = number_match.group(1)

            # Build line identifier
            if number:
                line_id = f"{service}-{number}"
                if size:
                    full_line = f"{size} {service}-{number}"
                else:
                    full_line = f"{service}-{number}"
            else:
                line_id = service
                if size:
                    full_line = f"{size} {service}"
                else:
                    full_line = service

            if line_id not in seen:
                seen.add(line_id)
                lines.append({
                    'line_number': full_line,
                    'size': size,
                    'service': service_name,
                    'confidence': 0.80
                })

    return lines

def parse_equipment(text):
    """
    Parse equipment tags from refrigeration drawings.
    Common formats:
    - COND-XX, EVAP-XX, COMP-XX, RECV-XX
    - ACU-XX (Air Conditioning Unit)
    - AHU-XX (Air Handling Unit)
    - PUMP-XX, V-XXX, E-XXX
    """
    equipment = []
    seen = set()

    patterns = [
        (r'\b(COND)-(\d{1,3}[A-Z]?)\b', 'Condenser'),
        (r'\b(EVAP)-(\d{1,3}[A-Z]?)\b', 'Evaporator'),
        (r'\b(COMP)-(\d{1,3}[A-Z]?)\b', 'Compressor'),
        (r'\b(COMPR)-(\d{1,3}[A-Z]?)\b', 'Compressor'),
        (r'\b(RECV)-(\d{1,3}[A-Z]?)\b', 'Receiver'),
        (r'\b(PUMP)-(\d{1,3}[A-Z]?)\b', 'Pump'),
        (r'\b(ACU)-(\d{1,3}[A-Z]?)\b', 'Air Conditioning Unit'),
        (r'\b(AHU)-(\d{1,3}[A-Z]?)\b', 'Air Handling Unit'),
        (r'\b(V)-(\d{3}[A-Z]?)\b', 'Vessel'),
        (r'\b(E)-(\d{3}[A-Z]?)\b', 'Heat Exchanger'),
        (r'\b(ACC)-(\d{1,3}[A-Z]?)\b', 'Accumulator'),
        (r'\b(ACCUM)-(\d{1,3}[A-Z]?)\b', 'Accumulator'),
        (r'\b(SEP)-(\d{1,3}[A-Z]?)\b', 'Separator'),
        (r'\b(RTU)-(\d{1,3}[A-Z]?)\b', 'Roof Top Unit'),
    ]

    for pattern, equip_type in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            prefix = match.group(1)
            number = match.group(2)
            tag = f"{prefix}-{number}"

            if tag not in seen:
                seen.add(tag)
                equipment.append({
                    'tag': tag,
                    'equipment_type': equip_type,
                    'confidence': 0.85
                })

    return equipment

def parse_instruments(text):
    """
    Parse instrument tags.
    Common formats:
    - TT-XXX, PT-XXX, FT-XXX, LT-XXX (Transmitters)
    - TSH-XXX, PSV-XXX (Switches/Safety Valves)
    - TCV-XXX, PCV-XXX (Control Valves)
    """
    instruments = []
    seen = set()

    patterns = [
        (r'\b(TT)-(\d{3,4}[A-Z]?)\b', 'Temperature Transmitter'),
        (r'\b(PT)-(\d{3,4}[A-Z]?)\b', 'Pressure Transmitter'),
        (r'\b(FT)-(\d{3,4}[A-Z]?)\b', 'Flow Transmitter'),
        (r'\b(LT)-(\d{3,4}[A-Z]?)\b', 'Level Transmitter'),
        (r'\b(TSH)-(\d{3,4}[A-Z]?)\b', 'Temperature Switch High'),
        (r'\b(TSL)-(\d{3,4}[A-Z]?)\b', 'Temperature Switch Low'),
        (r'\b(PSH)-(\d{3,4}[A-Z]?)\b', 'Pressure Switch High'),
        (r'\b(PSL)-(\d{3,4}[A-Z]?)\b', 'Pressure Switch Low'),
        (r'\b(PSV)-(\d{3,4}[A-Z]?)\b', 'Pressure Safety Valve'),
        (r'\b(TCV)-(\d{3,4}[A-Z]?)\b', 'Temperature Control Valve'),
        (r'\b(PCV)-(\d{3,4}[A-Z]?)\b', 'Pressure Control Valve'),
        (r'\b(FCV)-(\d{3,4}[A-Z]?)\b', 'Flow Control Valve'),
        (r'\b(TI)-(\d{3,4}[A-Z]?)\b', 'Temperature Indicator'),
        (r'\b(PI)-(\d{3,4}[A-Z]?)\b', 'Pressure Indicator'),
    ]

    for pattern, inst_type in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            prefix = match.group(1)
            number = match.group(2)
            tag = f"{prefix}-{number}"

            if tag not in seen:
                seen.add(tag)

                # Extract loop number (usually the first 3 digits)
                loop_match = re.match(r'(\d{3})', number)
                loop_number = loop_match.group(1) if loop_match else None

                instruments.append({
                    'tag': tag,
                    'instrument_type': inst_type,
                    'loop_number': loop_number,
                    'confidence': 0.85
                })

    return instruments

def assess_drawing_complexity(lines, equipment, instruments, text_length):
    """Assess drawing complexity based on extracted items."""
    total_items = len(lines) + len(equipment) + len(instruments)

    if total_items > 50:
        complexity = 'complex'
    elif total_items > 20:
        complexity = 'medium'
    else:
        complexity = 'simple'

    # Quality score based on text extraction success
    if text_length > 5000:
        quality = 0.85
    elif text_length > 2000:
        quality = 0.75
    elif text_length > 500:
        quality = 0.65
    else:
        quality = 0.50

    # Adjust based on items found
    if total_items > 0:
        quality = min(quality + 0.10, 1.0)

    return complexity, quality

def extract_drawing_data(sheet_id, pdf_path, drawing_number):
    """Extract lines, equipment, and instruments from a drawing."""
    print(f"\nProcessing Sheet {sheet_id}: {drawing_number}")
    print("-" * 80)
    print(f"Reading: {Path(pdf_path).name}")

    text = extract_text_from_pdf(pdf_path)

    if not text:
        print("  Warning: No text extracted from PDF")
        return None

    print(f"  Extracted {len(text)} characters of text")

    # Parse components
    lines = parse_refrigeration_lines(text)
    equipment = parse_equipment(text)
    instruments = parse_instruments(text)

    complexity, quality_score = assess_drawing_complexity(
        lines, equipment, instruments, len(text)
    )

    print(f"\nExtraction Results:")
    print(f"  Drawing Type: refrigeration_plan")
    print(f"  Complexity: {complexity}")
    print(f"  Quality Score: {quality_score:.2f}")
    print(f"  Lines: {len(lines)}")
    print(f"  Equipment: {len(equipment)}")
    print(f"  Instruments: {len(instruments)}")

    # Show samples
    if lines:
        print(f"\n  Sample Lines:")
        for line in lines[:5]:
            print(f"    - {line['line_number']}: {line.get('service', 'N/A')}")

    if equipment:
        print(f"\n  Sample Equipment:")
        for equip in equipment[:5]:
            print(f"    - {equip['tag']}: {equip['equipment_type']}")

    if instruments:
        print(f"\n  Sample Instruments:")
        for inst in instruments[:5]:
            print(f"    - {inst['tag']}: {inst['instrument_type']}")

    return {
        'lines': lines,
        'equipment': equipment,
        'instruments': instruments,
        'drawing_type': 'refrigeration_plan',
        'complexity': complexity,
        'quality_score': quality_score
    }

def store_extractions(db_path, sheet_id, data):
    """Store extracted data in database."""
    if data is None:
        return {'lines': 0, 'equipment': 0, 'instruments': 0, 'quality_score': 0.0}

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Store lines
        for line in data['lines']:
            cursor.execute("""
                INSERT INTO lines (sheet_id, line_number, size, service, confidence)
                VALUES (?, ?, ?, ?, ?)
            """, (
                sheet_id,
                line['line_number'],
                line.get('size'),
                line.get('service'),
                line['confidence']
            ))

        # Store equipment
        for equip in data['equipment']:
            cursor.execute("""
                INSERT INTO equipment (sheet_id, tag, equipment_type, confidence)
                VALUES (?, ?, ?, ?)
            """, (
                sheet_id,
                equip['tag'],
                equip['equipment_type'],
                equip['confidence']
            ))

        # Store instruments
        for inst in data['instruments']:
            cursor.execute("""
                INSERT INTO instruments (sheet_id, tag, instrument_type, loop_number, confidence)
                VALUES (?, ?, ?, ?, ?)
            """, (
                sheet_id,
                inst['tag'],
                inst['instrument_type'],
                inst.get('loop_number'),
                inst['confidence']
            ))

        # Update sheet metadata
        cursor.execute("""
            UPDATE sheets
            SET extracted_at = ?,
                extraction_model = 'pyPDF2-regex-parser',
                drawing_type = ?,
                complexity = ?,
                quality_score = ?
            WHERE id = ?
        """, (
            datetime.now().isoformat(),
            data['drawing_type'],
            data['complexity'],
            data['quality_score'],
            sheet_id
        ))

        conn.commit()

        return {
            'lines': len(data['lines']),
            'equipment': len(data['equipment']),
            'instruments': len(data['instruments']),
            'quality_score': data['quality_score']
        }

    finally:
        conn.close()

def main():
    db_path = "D:/quality.db"

    sheets = [
        {
            'id': 22,
            'path': 'D:/Projects/07308-BIRDCAGE/Refrigeration/R13100-REFRIGERATION-PLAN-PIPE-AND-DUCT-INTERSTITIAL-AREA-10-Rev.5.pdf',
            'drawing_number': 'R13100-REFRIGERATION-PLAN-PIPE-AND-DUCT-INTERSTITIAL-AREA-10'
        },
        {
            'id': 23,
            'path': 'D:/Projects/07308-BIRDCAGE/Refrigeration/R14000-REFRIGERATION-PLAN-PIPE-AND-DUCT-ROOF-OVERALL-Rev.6.pdf',
            'drawing_number': 'R14000-REFRIGERATION-PLAN-PIPE-AND-DUCT-ROOF-OVERALL'
        },
        {
            'id': 24,
            'path': 'D:/Projects/07308-BIRDCAGE/Refrigeration/R14010-REFRIGERATION-PLAN-PIPE-AND-DUCT-ROOF-AREA-1-Rev.5.pdf',
            'drawing_number': 'R14010-REFRIGERATION-PLAN-PIPE-AND-DUCT-ROOF-AREA-1'
        }
    ]

    print("=" * 80)
    print("REFRIGERATION PLAN EXTRACTION - PROJECT 07308")
    print("Sheets: 22, 23, 24 (Interstitial and Roof Plans)")
    print("=" * 80)

    results = []

    for sheet in sheets:
        data = extract_drawing_data(sheet['id'], sheet['path'], sheet['drawing_number'])

        if data:
            print("\nStoring extracted data in database...")
            stats = store_extractions(db_path, sheet['id'], data)
            results.append(stats)
            print("  Data stored successfully")

    # Summary
    print("\n" + "=" * 80)
    print("EXTRACTION SUMMARY")
    print("=" * 80)

    if results:
        total_lines = sum(r['lines'] for r in results)
        total_equipment = sum(r['equipment'] for r in results)
        total_instruments = sum(r['instruments'] for r in results)
        avg_quality = sum(r['quality_score'] for r in results) / len(results)

        print(f"\nTotal Extracted:")
        print(f"  Lines: {total_lines}")
        print(f"  Equipment: {total_equipment}")
        print(f"  Instruments: {total_instruments}")
        print(f"  Average Quality Score: {avg_quality:.2f}")
        print(f"\nSheets processed: {len(results)}")
        print(f"Database: {db_path}")
    else:
        print("\nNo data extracted.")

    print()

if __name__ == '__main__':
    main()
