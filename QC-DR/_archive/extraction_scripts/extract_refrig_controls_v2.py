#!/usr/bin/env python3
"""
Extract refrigeration controls data from drawing sheets.
Enhanced version with better cable schedule parsing.
"""
import sqlite3
import re
from datetime import datetime
import PyPDF2

# Drawing sheet information
SHEETS = [
    {
        'id': 159,
        'path': 'D:/Projects/07308-BIRDCAGE/Refrigeration-Controls/RC50001-REFRIGERATION-CONTROLS-DETAIL-SHEET-Rev.7.pdf',
        'drawing_number': 'RC50001',
        'revision': '7',
        'type': 'DETAIL'
    },
    {
        'id': 160,
        'path': 'D:/Projects/07308-BIRDCAGE/Refrigeration-Controls/RC50002-REFRIGERATION-CONTROLS-DETAIL-SHEET-Rev.4.pdf',
        'drawing_number': 'RC50002',
        'revision': '4',
        'type': 'DETAIL'
    },
    {
        'id': 161,
        'path': 'D:/Projects/07308-BIRDCAGE/Refrigeration-Controls/RC50004-REFRIGERATION-CONTROLS-DETAIL-SHEET-Rev.1.pdf',
        'drawing_number': 'RC50004',
        'revision': '1',
        'type': 'DETAIL'
    },
    {
        'id': 162,
        'path': 'D:/Projects/07308-BIRDCAGE/Refrigeration-Controls/RC60000-REFRIGERATION-CONTROLS-CABLE-SCHEDULE-Rev.12.pdf',
        'drawing_number': 'RC60000',
        'revision': '12',
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

def classify_instrument_type(device_id, description):
    """Classify instrument based on device ID and description."""

    device_id_upper = device_id.upper()
    desc_upper = description.upper()

    # Pressure instruments
    if 'PT' in device_id_upper or 'PRESSURE TRANS' in desc_upper:
        return 'Pressure Transmitter'
    if 'PSH' in device_id_upper or 'PRESSURE SWITCH HIGH' in desc_upper:
        return 'Pressure Switch High'
    if 'PSL' in device_id_upper or 'PRESSURE SWITCH LOW' in desc_upper:
        return 'Pressure Switch Low'
    if 'PDSH' in device_id_upper or 'PRESSURE DIFF' in desc_upper and 'HIGH' in desc_upper:
        return 'Pressure Differential Switch High'

    # Temperature instruments
    if 'TT' in device_id_upper or 'TEMP TRANS' in desc_upper or 'TEMPERATURE TRANS' in desc_upper:
        return 'Temperature Transmitter'
    if 'TSH' in device_id_upper or 'TEMP SWITCH HIGH' in desc_upper:
        return 'Temperature Switch High'
    if 'TSL' in device_id_upper or 'TEMP SWITCH LOW' in desc_upper:
        return 'Temperature Switch Low'
    if 'TE' in device_id_upper and 'ELEMENT' in desc_upper:
        return 'Temperature Element'

    # Level instruments
    if 'LT' in device_id_upper or 'LEVEL TRANS' in desc_upper:
        return 'Level Transmitter'
    if 'LSH' in device_id_upper or 'LEVEL SWITCH HIGH' in desc_upper:
        return 'Level Switch High'
    if 'LSL' in device_id_upper or 'LEVEL SWITCH LOW' in desc_upper:
        return 'Level Switch Low'

    # Flow instruments
    if 'FT' in device_id_upper or 'FLOW TRANS' in desc_upper:
        return 'Flow Transmitter'
    if 'FSH' in device_id_upper or 'FLOW SWITCH HIGH' in desc_upper:
        return 'Flow Switch High'
    if 'FSL' in device_id_upper or 'FLOW SWITCH LOW' in desc_upper:
        return 'Flow Switch Low'

    # Control valves
    if 'PCV' in device_id_upper or ('PRESSURE CONTROL' in desc_upper and 'VALVE' in desc_upper):
        return 'Pressure Control Valve'
    if 'TCV' in device_id_upper or ('TEMP CONTROL' in desc_upper and 'VALVE' in desc_upper):
        return 'Temperature Control Valve'
    if 'LCV' in device_id_upper or ('LEVEL CONTROL' in desc_upper and 'VALVE' in desc_upper):
        return 'Level Control Valve'

    # VFD and motor control (not instruments but useful to track)
    if 'VFD' in desc_upper or 'VARIABLE FREQ' in desc_upper:
        return 'VFD'
    if 'MOTOR STARTER' in desc_upper or 'STARTER' in device_id_upper:
        return 'Motor Starter'

    # Gas detection
    if 'GAS DETECT' in desc_upper or 'NH3' in desc_upper and 'DETECT' in desc_upper:
        return 'Gas Detector'

    # Heater/pump interlocks
    if 'HEATER INTERLOCK' in desc_upper or 'MSH' in device_id_upper:
        return 'Heater Interlock'
    if 'PUMP INTERLOCK' in desc_upper:
        return 'Pump Interlock'

    return 'Control Device'

def parse_cable_schedule(text_data, sheet_id, drawing_number):
    """Parse cable schedule to extract instruments and control devices."""
    devices = []

    full_text = '\n'.join([page['text'] for page in text_data])

    # Split into lines
    lines = full_text.split('\n')

    # Look for device patterns in cable schedule
    # Pattern: DEVICE_ID followed by DESCRIPTION followed by DEVICE_TYPE
    # Example: NH3-EC2B-MSH01 EVAP CONDENSER HEATER INTERLOCK VFD

    for line in lines:
        # Skip header lines and short lines
        if len(line) < 20:
            continue

        # Look for device ID patterns (alphanumeric with dashes)
        # Common patterns: NH3-XXX-YYY, 2HMCC##-XXX-YYY, RCP#, etc.
        device_pattern = r'\b([A-Z0-9]{2,}[-][A-Z0-9]+[-][A-Z0-9]+)\b'
        matches = re.finditer(device_pattern, line)

        for match in matches:
            device_id = match.group(1)

            # Skip if it looks like a drawing reference
            if device_id.startswith('RC') or device_id.startswith('R7'):
                continue

            # Extract surrounding context (description)
            start_pos = max(0, match.start() - 100)
            end_pos = min(len(line), match.end() + 200)
            context = line[start_pos:end_pos]

            # Try to find description after the device ID
            description = ''
            rest_of_line = line[match.end():].strip()

            # Extract words until we hit another device ID or certain keywords
            desc_words = []
            for word in rest_of_line.split():
                if re.match(r'^[A-Z0-9]+[-][A-Z0-9]+', word):
                    break  # Hit another device ID
                if word in ['VFD', 'MOTOR', 'PUMP', 'INTERLOCK', 'STARTER', 'HEATER']:
                    desc_words.append(word)
                    if len(desc_words) >= 3:
                        break
                elif len(word) > 2:
                    desc_words.append(word)
                    if len(desc_words) >= 6:
                        break

            description = ' '.join(desc_words)

            # Classify device type
            inst_type = classify_instrument_type(device_id, description)

            # Calculate confidence based on quality of extraction
            confidence = 0.75
            if description and len(description) > 10:
                confidence = 0.85
            if inst_type != 'Control Device':
                confidence += 0.05

            devices.append({
                'sheet_id': sheet_id,
                'tag': device_id,
                'instrument_type': inst_type,
                'description': description[:200] if description else None,
                'drawing_number': drawing_number,
                'confidence': min(confidence, 0.95)
            })

    # Deduplicate by tag
    unique_devices = {}
    for device in devices:
        tag = device['tag']
        if tag not in unique_devices:
            unique_devices[tag] = device
        else:
            # Keep the one with better description
            if len(device.get('description', '') or '') > len(unique_devices[tag].get('description', '') or ''):
                unique_devices[tag] = device

    return list(unique_devices.values())

def extract_detail_sheet_notes(text_data, sheet_id, drawing_number):
    """Extract installation notes and requirements from detail sheets."""
    notes = []

    full_text = '\n'.join([page['text'] for page in text_data])

    # Look for numbered notes or installation requirements
    note_patterns = [
        r'(\d+\.\s*[A-Z][^.]+\.)',  # Numbered notes ending with period
        r'(NOTE:\s*[^.]+\.)',  # Explicit notes
        r'(INSTALLATION:\s*[^.]+\.)',  # Installation instructions
    ]

    for pattern in note_patterns:
        matches = re.finditer(pattern, full_text, re.MULTILINE)
        for match in matches:
            note_text = match.group(1).strip()
            if len(note_text) > 20:  # Skip very short notes
                notes.append(note_text)

    return notes

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
        print("  Created instruments table")

    # Insert instruments
    inserted = 0
    duplicates = 0

    for inst in instruments:
        try:
            cursor.execute("""
                INSERT INTO instruments
                (sheet_id, tag, instrument_type, description, drawing_number, confidence)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                inst['sheet_id'],
                inst['tag'],
                inst['instrument_type'],
                inst.get('description'),
                inst['drawing_number'],
                inst['confidence']
            ))
            inserted += 1
        except sqlite3.IntegrityError:
            duplicates += 1

    conn.commit()
    return inserted, duplicates

def store_notes(conn, sheet_id, drawing_number, notes):
    """Store extraction notes in database."""
    if not notes:
        return 0

    cursor = conn.cursor()

    # Check if drawing_notes table exists
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='drawing_notes'
    """)

    if not cursor.fetchone():
        cursor.execute("""
            CREATE TABLE drawing_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sheet_id INTEGER,
                drawing_number TEXT,
                note_type TEXT,
                note_text TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (sheet_id) REFERENCES sheets(id)
            )
        """)
        print("  Created drawing_notes table")

    # Insert notes
    inserted = 0
    for note in notes:
        cursor.execute("""
            INSERT INTO drawing_notes
            (sheet_id, drawing_number, note_type, note_text)
            VALUES (?, ?, ?, ?)
        """, (sheet_id, drawing_number, 'INSTALLATION', note))
        inserted += 1

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

    print("Refrigeration Controls Data Extraction v2")
    print("=" * 70)
    print()

    conn = sqlite3.connect(db_path)

    total_instruments = 0
    total_notes = 0
    extraction_summary = []

    for sheet in SHEETS:
        print(f"Processing Sheet {sheet['id']}: {sheet['drawing_number']} Rev.{sheet['revision']}")
        print(f"Type: {sheet['type']}")
        print("-" * 70)

        # Extract text from PDF
        text_data = extract_pdf_text(sheet['path'])

        if not text_data:
            print(f"  ERROR: Could not extract text from PDF")
            print()
            continue

        print(f"  Extracted text from {len(text_data)} pages")

        # Extract data based on sheet type
        if sheet['type'] == 'CABLE_SCHEDULE':
            # Parse cable schedule for devices
            devices = parse_cable_schedule(
                text_data, sheet['id'], sheet['drawing_number']
            )
            notes = []
        else:
            # Detail sheets - extract installation notes
            devices = []
            notes = extract_detail_sheet_notes(
                text_data, sheet['id'], sheet['drawing_number']
            )

        print(f"  Found {len(devices)} devices/instruments")
        print(f"  Found {len(notes)} installation notes")

        # Show sample of found devices
        if devices:
            print(f"\n  Sample devices:")
            for device in devices[:8]:
                desc = device.get('description', '')[:40]
                print(f"    - {device['tag']:<25} {device['instrument_type']:<30} {desc}")
            if len(devices) > 8:
                print(f"    ... and {len(devices) - 8} more")

        # Show sample of notes
        if notes:
            print(f"\n  Sample notes:")
            for note in notes[:3]:
                print(f"    - {note[:80]}...")
            if len(notes) > 3:
                print(f"    ... and {len(notes) - 3} more")

        # Store in database
        if devices:
            inserted, duplicates = store_instruments(conn, devices)
            print(f"\n  Inserted {inserted} devices into database")
            if duplicates:
                print(f"  Skipped {duplicates} duplicates")
            total_instruments += inserted

        if notes:
            notes_inserted = store_notes(conn, sheet['id'], sheet['drawing_number'], notes)
            print(f"  Inserted {notes_inserted} notes into database")
            total_notes += notes_inserted

        # Calculate statistics
        if devices or notes:
            avg_confidence = sum(d['confidence'] for d in devices) / len(devices) if devices else 0.0
            stats = {
                'avg_confidence': avg_confidence,
                'complexity': 'medium' if len(devices) < 30 else 'high'
            }

            # Update sheet metadata
            update_sheet_metadata(conn, sheet['id'], stats)

            extraction_summary.append({
                'sheet_id': sheet['id'],
                'drawing_number': sheet['drawing_number'],
                'revision': sheet['revision'],
                'type': sheet['type'],
                'devices': len(devices),
                'notes': len(notes),
                'inserted': inserted if devices else 0,
                'avg_confidence': avg_confidence
            })

        print()

    conn.close()

    # Print summary
    print("=" * 70)
    print("EXTRACTION SUMMARY")
    print("=" * 70)
    print(f"Total sheets processed: {len(SHEETS)}")
    print(f"Total devices/instruments extracted: {total_instruments}")
    print(f"Total installation notes extracted: {total_notes}")
    print()

    if extraction_summary:
        print("Details by sheet:")
        print()
        for summary in extraction_summary:
            print(f"  {summary['drawing_number']} Rev.{summary['revision']} ({summary['type']})")
            print(f"    Devices found: {summary['devices']}")
            print(f"    Notes found: {summary['notes']}")
            print(f"    Inserted to DB: {summary['inserted']}")
            if summary['avg_confidence'] > 0:
                print(f"    Avg confidence: {summary['avg_confidence']:.2f}")
            print()

    print("Extraction complete!")
    print("\nDatabase updated: D:/quality.db")

if __name__ == '__main__':
    main()
