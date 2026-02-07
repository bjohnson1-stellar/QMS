#!/usr/bin/env python3
"""
Extract refrigeration controls data from drawing sheets.
"""
import sqlite3
import json
import re
from datetime import datetime
from pathlib import Path
import PyPDF2

# Drawing sheet information
SHEETS = [
    {
        'id': 159,
        'path': 'D:/Projects/07308-BIRDCAGE/Refrigeration-Controls/RC50001-REFRIGERATION-CONTROLS-DETAIL-SHEET-Rev.7.pdf',
        'drawing_number': 'RC50001',
        'type': 'DETAIL'
    },
    {
        'id': 160,
        'path': 'D:/Projects/07308-BIRDCAGE/Refrigeration-Controls/RC50002-REFRIGERATION-CONTROLS-DETAIL-SHEET-Rev.4.pdf',
        'drawing_number': 'RC50002',
        'type': 'DETAIL'
    },
    {
        'id': 161,
        'path': 'D:/Projects/07308-BIRDCAGE/Refrigeration-Controls/RC50004-REFRIGERATION-CONTROLS-DETAIL-SHEET-Rev.1.pdf',
        'drawing_number': 'RC50004',
        'type': 'DETAIL'
    },
    {
        'id': 162,
        'path': 'D:/Projects/07308-BIRDCAGE/Refrigeration-Controls/RC60000-REFRIGERATION-CONTROLS-CABLE-SCHEDULE-Rev.12.pdf',
        'drawing_number': 'RC60000',
        'type': 'CABLE_SCHEDULE'
    }
]

def extract_pdf_text(pdf_path):
    """Extract all text from PDF."""
    text = []
    try:
        with open(pdf_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            for page_num, page in enumerate(reader.pages, 1):
                page_text = page.extract_text()
                text.append({
                    'page': page_num,
                    'text': page_text
                })
        return text
    except Exception as e:
        print(f"Error reading {pdf_path}: {e}")
        return []

def parse_instrument_tag(tag):
    """Parse instrument tag to extract type and details."""
    # Common refrigeration instrument patterns
    # PT = Pressure Transmitter, TT = Temperature Transmitter,
    # PSH/PSL = Pressure Switch High/Low, TSH/TSL = Temperature Switch High/Low
    # LT = Level Transmitter, FT = Flow Transmitter
    # PCV = Pressure Control Valve, TCV = Temperature Control Valve

    patterns = {
        r'^PT[SEIA]?[-_]?\d+[A-Z]*$': 'Pressure Transmitter',
        r'^TT[SEIA]?[-_]?\d+[A-Z]*$': 'Temperature Transmitter',
        r'^LT[SEIA]?[-_]?\d+[A-Z]*$': 'Level Transmitter',
        r'^FT[SEIA]?[-_]?\d+[A-Z]*$': 'Flow Transmitter',
        r'^PSH[-_]?\d+[A-Z]*$': 'Pressure Switch High',
        r'^PSL[-_]?\d+[A-Z]*$': 'Pressure Switch Low',
        r'^TSH[-_]?\d+[A-Z]*$': 'Temperature Switch High',
        r'^TSL[-_]?\d+[A-Z]*$': 'Temperature Switch Low',
        r'^PCV[-_]?\d+[A-Z]*$': 'Pressure Control Valve',
        r'^TCV[-_]?\d+[A-Z]*$': 'Temperature Control Valve',
        r'^PDSH[-_]?\d+[A-Z]*$': 'Pressure Differential Switch High',
        r'^PDSL[-_]?\d+[A-Z]*$': 'Pressure Differential Switch Low',
    }

    for pattern, inst_type in patterns.items():
        if re.match(pattern, tag, re.IGNORECASE):
            return inst_type

    return 'Unknown'

def extract_instruments_from_text(text_data, sheet_id, drawing_number):
    """Extract instrument tags and details from text."""
    instruments = []

    # Combine all text
    full_text = '\n'.join([page['text'] for page in text_data])

    # Common instrument tag patterns for refrigeration
    tag_patterns = [
        r'\b(PT[SEIA]?[-_]?\d+[A-Z]*)\b',
        r'\b(TT[SEIA]?[-_]?\d+[A-Z]*)\b',
        r'\b(LT[SEIA]?[-_]?\d+[A-Z]*)\b',
        r'\b(FT[SEIA]?[-_]?\d+[A-Z]*)\b',
        r'\b(PSH[-_]?\d+[A-Z]*)\b',
        r'\b(PSL[-_]?\d+[A-Z]*)\b',
        r'\b(TSH[-_]?\d+[A-Z]*)\b',
        r'\b(TSL[-_]?\d+[A-Z]*)\b',
        r'\b(PCV[-_]?\d+[A-Z]*)\b',
        r'\b(TCV[-_]?\d+[A-Z]*)\b',
        r'\b(PDSH[-_]?\d+[A-Z]*)\b',
        r'\b(PDSL[-_]?\d+[A-Z]*)\b',
    ]

    found_tags = set()
    for pattern in tag_patterns:
        matches = re.finditer(pattern, full_text, re.IGNORECASE)
        for match in matches:
            tag = match.group(1).upper()
            if tag not in found_tags:
                found_tags.add(tag)
                inst_type = parse_instrument_tag(tag)
                instruments.append({
                    'sheet_id': sheet_id,
                    'tag': tag,
                    'instrument_type': inst_type,
                    'drawing_number': drawing_number,
                    'confidence': 0.85
                })

    return instruments

def extract_cable_schedule_data(text_data, sheet_id, drawing_number):
    """Extract cable schedule information including device lists."""
    cables = []
    instruments = []

    full_text = '\n'.join([page['text'] for page in text_data])

    # Look for cable schedule entries
    # Typical format: Cable# | From | To | Type | Size
    lines = full_text.split('\n')

    for i, line in enumerate(lines):
        # Extract instrument/device tags from cable schedule
        # Look for patterns like "FROM: PT-101" or "TO: PLC-01"
        from_match = re.search(r'FROM[:\s]+([A-Z]{2,4}[-_]?\d+[A-Z]*)', line, re.IGNORECASE)
        to_match = re.search(r'TO[:\s]+([A-Z]{2,4}[-_]?\d+[A-Z]*)', line, re.IGNORECASE)

        if from_match:
            tag = from_match.group(1).upper()
            if not tag.startswith('PLC') and not tag.startswith('MCC'):
                inst_type = parse_instrument_tag(tag)
                if inst_type != 'Unknown':
                    instruments.append({
                        'sheet_id': sheet_id,
                        'tag': tag,
                        'instrument_type': inst_type,
                        'drawing_number': drawing_number,
                        'confidence': 0.80
                    })

        if to_match:
            tag = to_match.group(1).upper()
            if not tag.startswith('PLC') and not tag.startswith('MCC'):
                inst_type = parse_instrument_tag(tag)
                if inst_type != 'Unknown':
                    instruments.append({
                        'sheet_id': sheet_id,
                        'tag': tag,
                        'instrument_type': inst_type,
                        'drawing_number': drawing_number,
                        'confidence': 0.80
                    })

    # Also do a general scan for instrument tags
    general_instruments = extract_instruments_from_text(text_data, sheet_id, drawing_number)

    # Combine and deduplicate
    all_tags = {}
    for inst in instruments + general_instruments:
        if inst['tag'] not in all_tags:
            all_tags[inst['tag']] = inst

    return list(all_tags.values())

def store_instruments(conn, instruments):
    """Store extracted instruments in database."""
    cursor = conn.cursor()

    # Check if instruments table exists
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='instruments'
    """)

    if not cursor.fetchone():
        # Create instruments table
        cursor.execute("""
            CREATE TABLE instruments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sheet_id INTEGER,
                tag TEXT NOT NULL,
                instrument_type TEXT,
                loop_number TEXT,
                description TEXT,
                location TEXT,
                drawing_number TEXT,
                confidence REAL DEFAULT 0.85,
                extraction_notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (sheet_id) REFERENCES sheets(id)
            )
        """)
        print("Created instruments table")

    # Insert instruments
    inserted = 0
    for inst in instruments:
        try:
            cursor.execute("""
                INSERT INTO instruments
                (sheet_id, tag, instrument_type, drawing_number, confidence)
                VALUES (?, ?, ?, ?, ?)
            """, (
                inst['sheet_id'],
                inst['tag'],
                inst['instrument_type'],
                inst['drawing_number'],
                inst['confidence']
            ))
            inserted += 1
        except sqlite3.IntegrityError as e:
            print(f"  Warning: Could not insert {inst['tag']}: {e}")

    conn.commit()
    return inserted

def update_sheet_metadata(conn, sheet_id, stats):
    """Update sheet metadata after extraction."""
    cursor = conn.cursor()

    # Check if sheets table exists and has the required columns
    cursor.execute("PRAGMA table_info(sheets)")
    columns = {col[1] for col in cursor.fetchall()}

    updates = []
    values = []

    if 'extracted_at' in columns:
        updates.append("extracted_at = ?")
        values.append(datetime.now().isoformat())

    if 'quality_score' in columns:
        updates.append("quality_score = ?")
        values.append(stats.get('avg_confidence', 0.85))

    if 'complexity' in columns:
        updates.append("complexity = ?")
        values.append(stats.get('complexity', 'medium'))

    if updates:
        values.append(sheet_id)
        query = f"UPDATE sheets SET {', '.join(updates)} WHERE id = ?"
        cursor.execute(query, values)
        conn.commit()

def main():
    """Main extraction process."""
    db_path = 'D:/quality.db'

    print("Refrigeration Controls Data Extraction")
    print("=" * 60)
    print()

    conn = sqlite3.connect(db_path)

    total_instruments = 0
    extraction_summary = []

    for sheet in SHEETS:
        print(f"Processing Sheet {sheet['id']}: {sheet['drawing_number']}")
        print(f"Path: {sheet['path']}")
        print(f"Type: {sheet['type']}")
        print("-" * 60)

        # Extract text from PDF
        text_data = extract_pdf_text(sheet['path'])

        if not text_data:
            print(f"  ERROR: Could not extract text from PDF")
            print()
            continue

        print(f"  Extracted text from {len(text_data)} pages")

        # Extract instruments based on sheet type
        if sheet['type'] == 'CABLE_SCHEDULE':
            instruments = extract_cable_schedule_data(
                text_data, sheet['id'], sheet['drawing_number']
            )
        else:
            instruments = extract_instruments_from_text(
                text_data, sheet['id'], sheet['drawing_number']
            )

        print(f"  Found {len(instruments)} instruments")

        if instruments:
            # Show sample of found instruments
            print(f"  Sample instruments:")
            for inst in instruments[:5]:
                print(f"    - {inst['tag']}: {inst['instrument_type']}")
            if len(instruments) > 5:
                print(f"    ... and {len(instruments) - 5} more")

        # Store in database
        if instruments:
            inserted = store_instruments(conn, instruments)
            print(f"  Inserted {inserted} instruments into database")
            total_instruments += inserted

            # Calculate statistics
            avg_confidence = sum(i['confidence'] for i in instruments) / len(instruments)
            stats = {
                'avg_confidence': avg_confidence,
                'complexity': 'medium' if len(instruments) < 20 else 'high'
            }

            # Update sheet metadata
            update_sheet_metadata(conn, sheet['id'], stats)

            extraction_summary.append({
                'sheet_id': sheet['id'],
                'drawing_number': sheet['drawing_number'],
                'type': sheet['type'],
                'instruments': len(instruments),
                'inserted': inserted,
                'avg_confidence': avg_confidence
            })

        print()

    conn.close()

    # Print summary
    print("=" * 60)
    print("EXTRACTION SUMMARY")
    print("=" * 60)
    print(f"Total sheets processed: {len(SHEETS)}")
    print(f"Total instruments extracted: {total_instruments}")
    print()

    if extraction_summary:
        print("Details by sheet:")
        for summary in extraction_summary:
            print(f"  {summary['drawing_number']} ({summary['type']})")
            print(f"    - Instruments found: {summary['instruments']}")
            print(f"    - Inserted to DB: {summary['inserted']}")
            print(f"    - Avg confidence: {summary['avg_confidence']:.2f}")
            print()

    print("Extraction complete!")

if __name__ == '__main__':
    main()
