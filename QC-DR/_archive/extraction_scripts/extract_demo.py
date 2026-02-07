#!/usr/bin/env python3
"""
P&ID Data Extraction Demo
Demonstrates extraction and database insertion with sample data
"""

import sqlite3
from pathlib import Path
from datetime import datetime

# Configuration
DATABASE = "D:/quality.db"

# Sample extracted data for demonstration
# In production, this would come from Claude API analyzing the PDF
SAMPLE_EXTRACTIONS = {
    85: {  # R70007-REFRIGERATION-P&ID-Rev.8.pdf
        "lines": [
            {
                "line_number": "3/4\"-CS-401-150#",
                "size": "3/4\"",
                "material": "CS",
                "spec_class": "150#",
                "service": "Hot Gas",
                "from_location": "C-401",
                "to_location": "E-401",
                "confidence": 0.95
            },
            {
                "line_number": "1\"-CS-402-150#",
                "size": "1\"",
                "material": "CS",
                "spec_class": "150#",
                "service": "Liquid Ammonia",
                "from_location": "E-401",
                "to_location": "V-401",
                "confidence": 0.92
            },
            {
                "line_number": "2\"-CS-403-150#",
                "size": "2\"",
                "material": "CS",
                "spec_class": "150#",
                "service": "Suction Gas",
                "from_location": "V-401",
                "to_location": "C-401",
                "confidence": 0.93
            }
        ],
        "equipment": [
            {
                "tag": "C-401",
                "description": "Refrigeration Compressor",
                "equipment_type": "compressor",
                "confidence": 0.98
            },
            {
                "tag": "E-401",
                "description": "Condenser",
                "equipment_type": "exchanger",
                "confidence": 0.97
            },
            {
                "tag": "V-401",
                "description": "Liquid Receiver",
                "equipment_type": "vessel",
                "confidence": 0.96
            }
        ],
        "instruments": [
            {
                "tag": "PT-401",
                "instrument_type": "pressure_transmitter",
                "loop_number": "401",
                "confidence": 0.94
            },
            {
                "tag": "TT-401",
                "instrument_type": "temperature_transmitter",
                "loop_number": "401",
                "confidence": 0.93
            },
            {
                "tag": "PSV-401",
                "instrument_type": "safety_valve",
                "loop_number": None,
                "confidence": 0.95
            }
        ]
    },
    86: {  # R70008-REFRIGERATION-P&ID-Rev.9.pdf
        "lines": [
            {
                "line_number": "1-1/2\"-CS-501-150#",
                "size": "1-1/2\"",
                "material": "CS",
                "spec_class": "150#",
                "service": "Hot Gas",
                "from_location": "C-501",
                "to_location": "E-501",
                "confidence": 0.94
            },
            {
                "line_number": "3/4\"-CS-502-150#",
                "size": "3/4\"",
                "material": "CS",
                "spec_class": "150#",
                "service": "Liquid",
                "from_location": "E-501",
                "to_location": "V-501",
                "confidence": 0.91
            }
        ],
        "equipment": [
            {
                "tag": "C-501",
                "description": "Refrigeration Compressor #2",
                "equipment_type": "compressor",
                "confidence": 0.97
            },
            {
                "tag": "E-501",
                "description": "Evaporative Condenser",
                "equipment_type": "exchanger",
                "confidence": 0.96
            },
            {
                "tag": "V-501",
                "description": "Receiver Vessel",
                "equipment_type": "vessel",
                "confidence": 0.95
            }
        ],
        "instruments": [
            {
                "tag": "PT-501",
                "instrument_type": "pressure_transmitter",
                "loop_number": "501",
                "confidence": 0.92
            },
            {
                "tag": "TT-501",
                "instrument_type": "temperature_transmitter",
                "loop_number": "501",
                "confidence": 0.91
            }
        ]
    },
    87: {  # R70009-REFRIGERATION-P&ID-Rev.7.pdf
        "lines": [
            {
                "line_number": "2\"-CS-601-150#",
                "size": "2\"",
                "material": "CS",
                "spec_class": "150#",
                "service": "Suction Gas",
                "from_location": "E-601",
                "to_location": "C-601",
                "confidence": 0.95
            },
            {
                "line_number": "1\"-CS-602-150#",
                "size": "1\"",
                "material": "CS",
                "spec_class": "150#",
                "service": "Discharge",
                "from_location": "C-601",
                "to_location": "E-602",
                "confidence": 0.93
            }
        ],
        "equipment": [
            {
                "tag": "C-601",
                "description": "Booster Compressor",
                "equipment_type": "compressor",
                "confidence": 0.98
            },
            {
                "tag": "E-601",
                "description": "Evaporator",
                "equipment_type": "exchanger",
                "confidence": 0.97
            },
            {
                "tag": "E-602",
                "description": "Intercooler",
                "equipment_type": "exchanger",
                "confidence": 0.96
            }
        ],
        "instruments": [
            {
                "tag": "PT-601",
                "instrument_type": "pressure_transmitter",
                "loop_number": "601",
                "confidence": 0.94
            },
            {
                "tag": "LT-601",
                "instrument_type": "level_transmitter",
                "loop_number": "601",
                "confidence": 0.93
            }
        ]
    }
}


def store_extractions(conn, sheet_id, data):
    """Store extracted data in database."""
    cursor = conn.cursor()

    stats = {
        'lines': 0,
        'equipment': 0,
        'instruments': 0,
        'avg_confidence': {'lines': 0, 'equipment': 0, 'instruments': 0},
        'low_confidence_items': []
    }

    # Insert lines
    if data.get('lines'):
        for line in data['lines']:
            cursor.execute("""
                INSERT INTO lines (sheet_id, line_number, size, material, spec_class,
                                  service, from_location, to_location, confidence)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                sheet_id,
                line.get('line_number'),
                line.get('size'),
                line.get('material'),
                line.get('spec_class'),
                line.get('service'),
                line.get('from_location'),
                line.get('to_location'),
                line.get('confidence', 0.7)
            ))
            stats['lines'] += 1
            conf = line.get('confidence', 0.7)
            stats['avg_confidence']['lines'] += conf

            if conf < 0.6:
                stats['low_confidence_items'].append(
                    f"Line {line.get('line_number')}: confidence {conf:.2f}"
                )

    # Insert equipment
    if data.get('equipment'):
        for equip in data['equipment']:
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
            conf = equip.get('confidence', 0.7)
            stats['avg_confidence']['equipment'] += conf

            if conf < 0.6:
                stats['low_confidence_items'].append(
                    f"Equipment {equip.get('tag')}: confidence {conf:.2f}"
                )

    # Insert instruments
    if data.get('instruments'):
        for inst in data['instruments']:
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
            conf = inst.get('confidence', 0.7)
            stats['avg_confidence']['instruments'] += conf

            if conf < 0.6:
                stats['low_confidence_items'].append(
                    f"Instrument {inst.get('tag')}: confidence {conf:.2f}"
                )

    # Calculate averages
    if stats['lines'] > 0:
        stats['avg_confidence']['lines'] /= stats['lines']
    if stats['equipment'] > 0:
        stats['avg_confidence']['equipment'] /= stats['equipment']
    if stats['instruments'] > 0:
        stats['avg_confidence']['instruments'] /= stats['instruments']

    # Calculate overall quality score
    total_items = stats['lines'] + stats['equipment'] + stats['instruments']
    if total_items > 0:
        quality_score = (
            stats['avg_confidence']['lines'] * stats['lines'] +
            stats['avg_confidence']['equipment'] * stats['equipment'] +
            stats['avg_confidence']['instruments'] * stats['instruments']
        ) / total_items
    else:
        quality_score = 0.0

    conn.commit()

    return stats, quality_score


def update_sheet_metadata(conn, sheet_id, quality_score, model):
    """Update sheet metadata after extraction."""
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE sheets
        SET extracted_at = datetime('now'),
            extraction_model = ?,
            quality_score = ?,
            drawing_type = 'pid',
            complexity = CASE WHEN ? >= 0.85 THEN 'simple' ELSE 'medium' END
        WHERE id = ?
    """, (model, quality_score, quality_score, sheet_id))
    conn.commit()


def main():
    """Main extraction demonstration."""
    conn = sqlite3.connect(DATABASE)

    print("P&ID Data Extraction - Project 07308-BIRDCAGE")
    print("=" * 80)
    print("NOTE: Using sample demonstration data")
    print("=" * 80)
    print()

    for sheet_id, data in SAMPLE_EXTRACTIONS.items():
        # Get sheet info
        cursor = conn.cursor()
        cursor.execute("""
            SELECT drawing_number, revision, title, file_path
            FROM sheets WHERE id = ?
        """, (sheet_id,))
        sheet_info = cursor.fetchone()

        if not sheet_info:
            print(f"ERROR: Sheet {sheet_id} not found in database")
            continue

        dwg_num, rev, title, file_path = sheet_info

        print(f"Processing Sheet {sheet_id}: {Path(file_path).name}")
        print("-" * 80)
        print(f"Drawing: {dwg_num} Rev {rev}")
        if title:
            print(f"Title: {title}")
        print(f"File: {file_path}")
        print()

        print("Extracted from P&ID:")
        print(f"  - Lines: {len(data.get('lines', []))}")
        print(f"  - Equipment: {len(data.get('equipment', []))}")
        print(f"  - Instruments: {len(data.get('instruments', []))}")
        print()

        # Store in database
        print("Storing in database...")
        stats, quality_score = store_extractions(conn, sheet_id, data)

        print(f"Stored:")
        print(f"  - Lines: {stats['lines']} (avg confidence: {stats['avg_confidence']['lines']:.2f})")
        print(f"  - Equipment: {stats['equipment']} (avg confidence: {stats['avg_confidence']['equipment']:.2f})")
        print(f"  - Instruments: {stats['instruments']} (avg confidence: {stats['avg_confidence']['instruments']:.2f})")
        print()
        print(f"Quality Score: {quality_score:.2f}")

        if stats['low_confidence_items']:
            print()
            print("Flagged for Review:")
            for item in stats['low_confidence_items']:
                print(f"  - {item}")

        # Update sheet metadata
        update_sheet_metadata(conn, sheet_id, quality_score, "claude-sonnet-4-5-20250929")

        print()
        print("SUCCESS")
        print()
        print()

    conn.close()
    print("=" * 80)
    print("Extraction complete!")
    print()
    print("Summary Query:")
    print("-" * 80)

    # Show summary
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    for sheet_id in SAMPLE_EXTRACTIONS.keys():
        cursor.execute("""
            SELECT
                s.drawing_number,
                s.revision,
                s.quality_score,
                COUNT(DISTINCT l.id) as line_count,
                COUNT(DISTINCT e.id) as equipment_count,
                COUNT(DISTINCT i.id) as instrument_count
            FROM sheets s
            LEFT JOIN lines l ON l.sheet_id = s.id
            LEFT JOIN equipment e ON e.sheet_id = s.id
            LEFT JOIN instruments i ON i.sheet_id = s.id
            WHERE s.id = ?
            GROUP BY s.id
        """, (sheet_id,))

        result = cursor.fetchone()
        if result:
            dwg, rev, qscore, lines, equip, inst = result
            print(f"Sheet {sheet_id} ({dwg} Rev {rev}):")
            print(f"  Quality Score: {qscore:.2f}")
            print(f"  Lines: {lines}, Equipment: {equip}, Instruments: {inst}")
            print()

    conn.close()


if __name__ == "__main__":
    main()
