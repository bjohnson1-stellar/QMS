#!/usr/bin/env python3
"""
Insert manually extracted data from sheet 2107 into database.
"""

import sqlite3
import json
from datetime import datetime

DB_PATH = "D:/quality.db"
DATA_FILE = "D:/extracted_data_2107.json"

def insert_data():
    """Insert extracted data into the database."""

    # Load extracted data
    with open(DATA_FILE, 'r') as f:
        data = json.load(f)

    sheet_id = data['sheet_id']
    print(f"Inserting data for Sheet {sheet_id} ({data['sheet_number']} Rev {data['revision']})")
    print("=" * 80)

    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    cursor = conn.cursor()

    stats = {
        "lines": 0,
        "equipment": 0,
        "low_confidence_items": []
    }

    confidences = []

    # Insert lines
    print("\nInserting lines...")
    for line in data['lines']:
        confidence = line.get('confidence', 0.7)
        cursor.execute("""
            INSERT INTO lines (sheet_id, line_number, size, material, spec_class,
                             from_location, to_location, service, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            sheet_id,
            line['line_number'],
            line['size'],
            line.get('material'),
            line.get('spec_class'),
            line['from_location'],
            line['to_location'],
            line['service'],
            confidence
        ))
        stats['lines'] += 1
        confidences.append(confidence)
        print(f"  - {line['line_number']}: {line['size']} {line['service']} (confidence: {confidence:.2f})")

        if confidence < 0.6:
            stats['low_confidence_items'].append(
                f"Line {line['line_number']}: {confidence:.2f}"
            )

    # Insert equipment
    print("\nInserting equipment...")
    for equip in data['equipment']:
        confidence = equip.get('confidence', 0.7)
        cursor.execute("""
            INSERT INTO equipment (sheet_id, tag, description, equipment_type, confidence)
            VALUES (?, ?, ?, ?, ?)
        """, (
            sheet_id,
            equip['tag'],
            equip['description'],
            equip['equipment_type'],
            confidence
        ))
        stats['equipment'] += 1
        confidences.append(confidence)
        print(f"  - {equip['tag']}: {equip['description']} (confidence: {confidence:.2f})")

        if confidence < 0.6:
            stats['low_confidence_items'].append(
                f"Equipment {equip['tag']}: {confidence:.2f}"
            )

    # Calculate average confidence
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.7

    # Update sheet metadata
    print("\nUpdating sheet metadata...")
    cursor.execute("""
        UPDATE sheets
        SET extracted_at = ?,
            quality_score = ?,
            complexity = ?,
            drawing_type = ?,
            extraction_model = 'claude-sonnet-4-5-manual'
        WHERE id = ?
    """, (
        datetime.now().isoformat(),
        avg_confidence,
        data['complexity'],
        data['drawing_type'],
        sheet_id
    ))

    # Update processing queue if exists
    cursor.execute("""
        UPDATE processing_queue
        SET status = 'completed',
            completed_at = ?
        WHERE sheet_id = ? AND task = 'EXTRACT'
    """, (datetime.now().isoformat(), sheet_id))

    # Check if update affected any rows
    if cursor.rowcount > 0:
        print(f"  - Updated processing queue status to 'completed'")
    else:
        print(f"  - No processing queue entry found (sheet may not have been queued)")

    conn.commit()
    conn.close()

    # Print summary
    print("\n" + "=" * 80)
    print("EXTRACTION SUMMARY")
    print("=" * 80)
    print(f"Sheet ID: {sheet_id}")
    print(f"Sheet Number: {data['sheet_number']} Rev {data['revision']}")
    print(f"Drawing Type: {data['drawing_type']}")
    print(f"Complexity: {data['complexity']}")
    print(f"\nItems Inserted:")
    print(f"  - Lines: {stats['lines']}")
    print(f"  - Equipment: {stats['equipment']}")
    print(f"  - Total: {stats['lines'] + stats['equipment']}")
    print(f"\nQuality Score: {avg_confidence:.2f}")

    if stats['low_confidence_items']:
        print(f"\nLow Confidence Items Flagged for Review:")
        for item in stats['low_confidence_items']:
            print(f"  - {item}")
    else:
        print(f"\nNo low confidence items.")

    if data.get('extraction_notes'):
        print(f"\nExtraction Notes:")
        print(f"  {data['extraction_notes']}")

    print("\n" + "=" * 80)
    print("EXTRACTION COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    try:
        insert_data()
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
