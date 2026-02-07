#!/usr/bin/env python3
"""Insert extracted plumbing plan data into database."""

import sqlite3
from datetime import datetime

# Extracted data from the plumbing plan
extracted_data = {
    'lines': [
        {
            'line_number': 'SW-4-001',  # Sanitary waste 4" line 1
            'size': '4"',
            'service': 'sanitary waste',
            'from_location': 'Restroom fixture group',
            'to_location': 'Main vertical stack',
            'material': 'PVC',
            'spec_class': None,
            'confidence': 0.85
        },
        {
            'line_number': 'V-3-001',  # Vent 3" line 1
            'size': '3"',
            'service': 'vent',
            'from_location': 'Restroom fixtures',
            'to_location': 'Roof vent',
            'material': 'PVC',
            'spec_class': None,
            'confidence': 0.80
        },
        {
            'line_number': 'SW-4-002',  # Sanitary waste 4" line 2
            'size': '4"',
            'service': 'sanitary waste',
            'from_location': 'Main stack',
            'to_location': 'Building drain',
            'material': 'PVC',
            'spec_class': None,
            'confidence': 0.85
        },
        {
            'line_number': 'CW-1-001',  # Cold water supply
            'size': '1"',
            'service': 'cold water',
            'from_location': 'Main supply',
            'to_location': 'Restroom fixtures',
            'material': 'Copper',
            'spec_class': None,
            'confidence': 0.75
        }
    ],
    'equipment': [
        {
            'tag': 'WC-RESTROOM-1',
            'equipment_type': 'plumbing_fixture',
            'description': 'Water closets in restroom (multiple)',
            'confidence': 0.90
        },
        {
            'tag': 'LAV-RESTROOM-1',
            'equipment_type': 'plumbing_fixture',
            'description': 'Lavatories in restroom (multiple)',
            'confidence': 0.90
        },
        {
            'tag': 'FD-RESTROOM-1',
            'equipment_type': 'plumbing_fixture',
            'description': 'Floor drains in restroom area',
            'confidence': 0.85
        }
    ],
    'cleanouts': [
        {
            'location': 'Main stack base',
            'size': '4"',
            'cleanout_type': 'floor',
            'confidence': 0.75
        }
    ],
    'fixtures': [
        {
            'fixture_type': 'Water Closet',
            'location': 'Restroom Area 1',
            'quantity': 6,
            'notes': 'Wall-hung fixtures in restroom',
            'confidence': 0.90
        },
        {
            'fixture_type': 'Lavatory',
            'location': 'Restroom Area 1',
            'quantity': 6,
            'notes': 'Counter-mounted lavatories',
            'confidence': 0.90
        },
        {
            'fixture_type': 'Floor Drain',
            'location': 'Restroom Area 1',
            'quantity': 2,
            'notes': 'Floor drains for drainage',
            'confidence': 0.85
        }
    ],
    'valves': [],
    'notes': 'Partial first floor plan showing restroom plumbing. Main vertical stack runs through center of plan. Restroom contains multiple water closets and lavatories with associated waste and vent piping.'
}

def main():
    # Database connection
    conn = sqlite3.connect('D:/quality.db', timeout=30.0)
    cursor = conn.cursor()

    sheet_id = 2115
    confidences = []

    # Insert lines
    for line in extracted_data['lines']:
        cursor.execute("""
            INSERT INTO lines (sheet_id, line_number, size, material, spec_class,
                             from_location, to_location, service, confidence)
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
        confidences.append(line.get('confidence', 0.7))

    # Insert equipment
    for equip in extracted_data['equipment']:
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
        confidences.append(equip.get('confidence', 0.7))

    # Insert fixtures as equipment
    for fixture in extracted_data['fixtures']:
        tag = f"{fixture.get('fixture_type', 'FX').replace(' ', '')}-{fixture.get('location', 'UNKNOWN').replace(' ', '-')}"
        desc = f"{fixture.get('fixture_type', 'Unknown')} in {fixture.get('location', 'unknown location')}"
        if fixture.get('quantity'):
            desc += f" (qty: {fixture.get('quantity')})"
        if fixture.get('notes'):
            desc += f" - {fixture.get('notes')}"

        cursor.execute("""
            INSERT INTO equipment (sheet_id, tag, description, equipment_type, confidence)
            VALUES (?, ?, ?, ?, ?)
        """, (
            sheet_id,
            tag,
            desc,
            'plumbing_fixture',
            fixture.get('confidence', 0.7)
        ))
        confidences.append(fixture.get('confidence', 0.7))

    # Insert cleanouts
    for co in extracted_data['cleanouts']:
        tag = f"CO-{co.get('size', '').replace('\"', '')}-{co.get('location', 'UNKNOWN').replace(' ', '-')}"
        desc = f"{co.get('size', '')} {co.get('cleanout_type', '')} cleanout at {co.get('location', 'unknown')}"

        cursor.execute("""
            INSERT INTO equipment (sheet_id, tag, description, equipment_type, confidence)
            VALUES (?, ?, ?, ?, ?)
        """, (
            sheet_id,
            tag,
            desc,
            'cleanout',
            co.get('confidence', 0.7)
        ))
        confidences.append(co.get('confidence', 0.7))

    # Calculate average confidence
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.7

    # Update sheet metadata
    cursor.execute("""
        UPDATE sheets
        SET extracted_at = ?,
            quality_score = ?,
            complexity = 'medium',
            drawing_type = 'plumbing_plan',
            extraction_model = 'claude-sonnet-4-5-20250929'
        WHERE id = ?
    """, (datetime.now().isoformat(), avg_confidence, sheet_id))

    # Update processing queue if exists
    cursor.execute("""
        UPDATE processing_queue
        SET status = 'completed',
            completed_at = ?
        WHERE sheet_id = ? AND task = 'EXTRACT'
    """, (datetime.now().isoformat(), sheet_id))

    conn.commit()
    conn.close()

    # Print results
    print('Extraction: PP11011 Rev 2 (07650-BRV-PerroGrande/Plumbing)')
    print('='*60)
    print('Drawing Type: Plumbing Plan')
    print('Complexity: medium')
    print('Model Used: claude-sonnet-4-5-20250929')
    print()
    print('Extracted:')
    print(f'  - Lines: {len(extracted_data["lines"])} (avg confidence: {sum(l["confidence"] for l in extracted_data["lines"])/len(extracted_data["lines"]):.2f})')
    print(f'  - Equipment: {len(extracted_data["equipment"])} (avg confidence: {sum(e["confidence"] for e in extracted_data["equipment"])/len(extracted_data["equipment"]):.2f})')
    print(f'  - Fixtures: {len(extracted_data["fixtures"])} (avg confidence: {sum(f["confidence"] for f in extracted_data["fixtures"])/len(extracted_data["fixtures"]):.2f})')
    print(f'  - Cleanouts: {len(extracted_data["cleanouts"])}')
    print(f'  - Valves: {len(extracted_data["valves"])}')
    print()
    print(f'Quality Score: {avg_confidence:.2f}')
    print()
    print('Notes:')
    print(f'  {extracted_data["notes"]}')
    print()
    print('Total items extracted:', len(extracted_data["lines"]) + len(extracted_data["equipment"]) + len(extracted_data["fixtures"]) + len(extracted_data["cleanouts"]))
    print()
    print('Database updated successfully!')

if __name__ == '__main__':
    main()
