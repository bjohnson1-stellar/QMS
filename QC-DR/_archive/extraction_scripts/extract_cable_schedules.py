#!/usr/bin/env python3
"""
Extract cable schedule data from refrigeration control drawings.
Parses instrument tags, types, and loop numbers from tabular PDF data.
"""

import sqlite3
import re
from datetime import datetime
from PyPDF2 import PdfReader

# Sheet information
SHEETS = [
    {
        'id': 163,
        'path': 'D:/Projects/07308-BIRDCAGE/Refrigeration-Controls/RC60001-REFRIGERATION-CONTROLS-CABLE-SCHEDULE-Rev.12.pdf',
        'drawing_number': 'RC60001'
    },
    {
        'id': 164,
        'path': 'D:/Projects/07308-BIRDCAGE/Refrigeration-Controls/RC60002-REFRIGERATION-CONTROLS-CABLE-SCHEDULE-Rev.12.pdf',
        'drawing_number': 'RC60002'
    },
    {
        'id': 165,
        'path': 'D:/Projects/07308-BIRDCAGE/Refrigeration-Controls/RC60003-REFRIGERATION-CONTROLS-CABLE-SCHEDULE-Rev.12.pdf',
        'drawing_number': 'RC60003'
    },
    {
        'id': 166,
        'path': 'D:/Projects/07308-BIRDCAGE/Refrigeration-Controls/RC60004-REFRIGERATION-CONTROLS-CABLE-SCHEDULE-Rev.12.pdf',
        'drawing_number': 'RC60004'
    }
]

DB_PATH = 'D:/quality.db'

# Instrument type patterns - common refrigeration control tags
INSTRUMENT_PATTERNS = {
    r'^T[IESTZ]': 'Temperature',           # TI=Indicator, TE=Element, TS=Switch, TT=Transmitter, TZ=Zone
    r'^P[IESTZ]': 'Pressure',              # PI=Indicator, PE=Element, PS=Switch, PT=Transmitter
    r'^L[IESTZ]': 'Level',                 # LI, LE, LS, LT
    r'^F[IESTZ]': 'Flow',                  # FI, FE, FS, FT
    r'^[TPFL]CV': 'Control Valve',         # TCV, PCV, FCV, LCV
    r'^[TPFL]V': 'Valve',                  # TV, PV, FV, LV
    r'^HS': 'Hand Switch',                 # HS
    r'^ZS': 'Position Switch',             # ZS
    r'^XS': 'Safety Switch',               # XS
    r'^S': 'Solenoid',                     # S, SV
    r'^VS': 'Vibration Switch',            # VS
    r'^[A-Z]+I$': 'Indicator',             # Generic indicators
    r'^[A-Z]+T$': 'Transmitter',           # Generic transmitters
}

def classify_instrument_type(tag):
    """Determine instrument type from tag."""
    tag_upper = tag.upper().strip()

    for pattern, inst_type in INSTRUMENT_PATTERNS.items():
        if re.match(pattern, tag_upper):
            return inst_type

    # Default classification
    return 'Control Device'

def extract_loop_number(tag, context=''):
    """Extract loop number from tag or context."""
    # Try to extract numeric portion from tag
    # Common formats: TT-101, PI-2501A, HS-301
    match = re.search(r'-?(\d+)[A-Z]?$', tag)
    if match:
        return match.group(1)

    # Try full tag as loop
    match = re.search(r'^([A-Z]+-\d+)', tag)
    if match:
        return match.group(1)

    return None

def extract_text_from_pdf(pdf_path):
    """Extract all text from PDF."""
    try:
        reader = PdfReader(pdf_path)
        text = ''
        for page in reader.pages:
            text += page.extract_text() + '\n'
        return text
    except Exception as e:
        print(f"Error reading {pdf_path}: {e}")
        return ''

def parse_cable_schedule_instruments(text, drawing_number):
    """
    Parse instruments from cable schedule text.
    Cable schedules typically have columns like:
    - Tag Number / Device
    - From / To locations
    - Cable Type / Size
    - Description
    """
    instruments = []
    lines = text.split('\n')

    # Look for instrument tag patterns
    # Common refrigeration instrument tags
    tag_pattern = r'\b([TPLFHS][TSIECZV]+-?\d+[A-Z]?|[A-Z]{2,3}-?\d+[A-Z]?)\b'

    seen_tags = set()

    for i, line in enumerate(lines):
        # Find all potential instrument tags in the line
        matches = re.finditer(tag_pattern, line)

        for match in matches:
            tag = match.group(1)

            # Skip if already seen
            if tag in seen_tags:
                continue

            # Filter out obvious non-instruments
            if tag.startswith(('RC', 'SH', 'DWG', 'REV')):
                continue

            # Get context (current line + next few lines for description)
            context = '\n'.join(lines[i:min(i+3, len(lines))])

            # Classify instrument
            inst_type = classify_instrument_type(tag)
            loop_num = extract_loop_number(tag, context)

            # Calculate confidence based on context
            confidence = 0.7  # Base confidence

            # Increase confidence if we see related keywords
            if any(kw in context.lower() for kw in ['transmitter', 'switch', 'valve', 'indicator', 'sensor']):
                confidence += 0.1

            # Increase if tag matches standard format
            if re.match(r'^[TPLF][TSIECZV]-\d+[A-Z]?$', tag):
                confidence += 0.1

            # Decrease if tag looks unusual
            if len(tag) < 3 or len(tag) > 15:
                confidence -= 0.1

            confidence = min(1.0, max(0.0, confidence))

            instruments.append({
                'tag': tag,
                'type': inst_type,
                'loop_number': loop_num,
                'confidence': confidence,
                'context': context[:200]  # First 200 chars of context
            })

            seen_tags.add(tag)

    return instruments

def insert_instruments_to_db(sheet_id, instruments):
    """Insert extracted instruments into database."""
    conn = sqlite3.connect(DB_PATH)
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
                inst['type'],
                inst['loop_number'],
                inst['confidence']
            ))
            inserted += 1
        except sqlite3.IntegrityError:
            # Duplicate tag for this sheet
            skipped += 1
        except Exception as e:
            print(f"  Error inserting {inst['tag']}: {e}")
            skipped += 1

    conn.commit()
    conn.close()

    return inserted, skipped

def update_sheet_status(sheet_id, quality_score, item_count):
    """Update sheet extraction metadata."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        cursor.execute("""
            UPDATE sheets
            SET extracted_at = ?,
                quality_score = ?,
                complexity = ?
            WHERE id = ?
        """, (
            datetime.now().isoformat(),
            quality_score,
            'medium' if item_count > 20 else 'low',
            sheet_id
        ))

        conn.commit()
    except Exception as e:
        print(f"  Error updating sheet status: {e}")
    finally:
        conn.close()

def main():
    """Main extraction process."""
    print("Cable Schedule Extraction - Project 07308 BIRDCAGE")
    print("=" * 60)

    total_instruments = 0

    for sheet in SHEETS:
        sheet_id = sheet['id']
        pdf_path = sheet['path']
        drawing_num = sheet['drawing_number']

        print(f"\nProcessing Sheet {sheet_id}: {drawing_num}")
        print("-" * 60)

        # Extract text from PDF
        print(f"  Reading PDF: {pdf_path}")
        text = extract_text_from_pdf(pdf_path)

        if not text:
            print(f"  ERROR: Could not extract text from PDF")
            continue

        print(f"  Extracted {len(text)} characters of text")

        # Parse instruments
        print(f"  Parsing cable schedule data...")
        instruments = parse_cable_schedule_instruments(text, drawing_num)

        print(f"  Found {len(instruments)} instruments")

        if instruments:
            # Show sample
            print(f"\n  Sample instruments:")
            for inst in instruments[:5]:
                print(f"    - {inst['tag']:15} Type: {inst['type']:20} Loop: {inst['loop_number'] or 'N/A':10} Conf: {inst['confidence']:.2f}")

            if len(instruments) > 5:
                print(f"    ... and {len(instruments) - 5} more")

            # Insert to database
            print(f"\n  Inserting to database...")
            inserted, skipped = insert_instruments_to_db(sheet_id, instruments)
            print(f"    Inserted: {inserted}")
            if skipped > 0:
                print(f"    Skipped (duplicates/errors): {skipped}")

            # Calculate quality score
            avg_confidence = sum(i['confidence'] for i in instruments) / len(instruments)
            quality_score = round(avg_confidence, 2)

            # Update sheet status
            update_sheet_status(sheet_id, quality_score, len(instruments))
            print(f"    Quality Score: {quality_score:.2f}")

            total_instruments += inserted
        else:
            print(f"  WARNING: No instruments found")
            update_sheet_status(sheet_id, 0.5, 0)

    print("\n" + "=" * 60)
    print(f"Extraction Complete")
    print(f"Total instruments extracted: {total_instruments}")
    print("=" * 60)

if __name__ == '__main__':
    main()
