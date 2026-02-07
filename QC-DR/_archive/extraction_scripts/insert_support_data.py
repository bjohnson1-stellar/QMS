import sqlite3
import re
from datetime import datetime

# Connection to database
conn = sqlite3.connect('D:/quality.db')
cursor = conn.cursor()

# Define the extracted support data
# Sheet 107: RS11010-REFRIGERATION-PLAN-SUPPORTS-FLOOR-AREA-1-Rev.6
sheet_107_data = {
    'sheet_id': 107,
    'drawing_number': 'RS11010',
    'title': 'REFRIGERATION PLAN SUPPORTS FLOOR AREA 1',
    'revision': '6',
    'drawing_type': 'plan',
    'complexity': 'medium',
    'supports': [
        # R502113J supports
        {'tag': 'R502113J', 'count': 24, 'area': 'AREA 1'},
        # R502113K supports
        {'tag': 'R502113K', 'count': 4, 'area': 'AREA 1'},
        # R502113N supports (with "J" suffix)
        {'tag': 'R502113N', 'count': 2, 'area': 'AREA 1', 'notes': 'With J suffix notation'},
    ]
}

# Sheet 108: RS11020-REFRIGERATION-PLAN-SUPPORTS-FLOOR-AREA-2-Rev.6
sheet_108_data = {
    'sheet_id': 108,
    'drawing_number': 'RS11020',
    'title': 'REFRIGERATION PLAN SUPPORTS FLOOR AREA 2',
    'revision': '6',
    'drawing_type': 'plan',
    'complexity': 'medium',
    'supports': [
        # R502113K supports (dominant in this area)
        {'tag': 'R502113K', 'count': 40, 'area': 'AREA 2'},
    ]
}

# Sheet 109: RS11030-REFRIGERATION-PLAN-SUPPORTS-FLOOR-AREA-3-Rev.6
sheet_109_data = {
    'sheet_id': 109,
    'drawing_number': 'RS11030',
    'title': 'REFRIGERATION PLAN SUPPORTS FLOOR AREA 3',
    'revision': '6',
    'drawing_type': 'plan',
    'complexity': 'medium',
    'supports': [
        # R502113K supports
        {'tag': 'R502113K', 'count': 35, 'area': 'AREA 3'},
    ]
}

def update_sheet_metadata(sheet_data):
    """Update sheet metadata with extraction info"""
    sheet_id = sheet_data['sheet_id']

    # Update sheets table
    cursor.execute("""
        UPDATE sheets
        SET drawing_type = ?,
            complexity = ?,
            extracted_at = ?,
            extraction_model = 'claude-sonnet-4.5',
            quality_score = ?
        WHERE id = ?
    """, (
        sheet_data['drawing_type'],
        sheet_data['complexity'],
        datetime.now().isoformat(),
        0.85,  # Good confidence for clear support plan drawings
        sheet_id
    ))

    print(f"Updated sheet {sheet_id}: {sheet_data['drawing_number']} Rev {sheet_data['revision']}")

def insert_support_details(sheet_data):
    """Insert support detail records"""
    sheet_id = sheet_data['sheet_id']

    for support in sheet_data['supports']:
        tag = support['tag']
        count = support['count']
        area = support.get('area', '')
        notes = support.get('notes', '')

        # Parse support tag to extract type info
        # Format: R502113J, R502113K, R502113N
        # R = Refrigeration, 502113 = detail number, J/K/N = variant
        match = re.match(r'(R)(\d+)([A-Z])', tag)
        if match:
            prefix = match.group(1)
            detail_num = match.group(2)
            variant = match.group(3)

            detail_label = f"{detail_num}{variant}"
            full_notes = f"Area: {area}. Count on sheet: {count}."
            if notes:
                full_notes += f" {notes}"

            # Insert support detail record
            cursor.execute("""
                INSERT INTO support_details
                (sheet_id, detail_type, detail_label, notes, confidence)
                VALUES (?, ?, ?, ?, ?)
            """, (
                sheet_id,
                'PIPE_SUPPORT_HANGER',
                detail_label,
                full_notes,
                0.90  # High confidence - clear tag identification
            ))

            print(f"  - Inserted support: {tag} (count: {count}, area: {area})")

# Process all three sheets
print("="*80)
print("EXTRACTING SUPPORT DATA FROM REFRIGERATION DRAWINGS")
print("="*80)
print()

for sheet_data in [sheet_107_data, sheet_108_data, sheet_109_data]:
    print(f"\nProcessing Sheet {sheet_data['sheet_id']}: {sheet_data['drawing_number']}")
    print("-" * 60)

    update_sheet_metadata(sheet_data)
    insert_support_details(sheet_data)

# Commit changes
conn.commit()

# Generate summary report
print("\n" + "="*80)
print("EXTRACTION SUMMARY")
print("="*80)

for sheet_data in [sheet_107_data, sheet_108_data, sheet_109_data]:
    sheet_id = sheet_data['sheet_id']

    # Count inserted records
    cursor.execute("""
        SELECT COUNT(*) FROM support_details
        WHERE sheet_id = ?
    """, (sheet_id,))
    support_count = cursor.fetchone()[0]

    # Get sheet info
    cursor.execute("""
        SELECT drawing_number, title, revision, extracted_at, quality_score
        FROM sheets WHERE id = ?
    """, (sheet_id,))
    sheet_info = cursor.fetchone()

    print(f"\nSheet {sheet_id}: {sheet_info[0]} Rev {sheet_info[2]}")
    print(f"  Title: {sheet_info[1]}")
    print(f"  Extracted at: {sheet_info[3]}")
    print(f"  Quality score: {sheet_info[4]}")
    print(f"  Support types: {support_count}")

    # Show support details
    cursor.execute("""
        SELECT detail_label, notes, confidence
        FROM support_details
        WHERE sheet_id = ?
        ORDER BY detail_label
    """, (sheet_id,))

    supports = cursor.fetchall()
    for detail_label, notes, confidence in supports:
        print(f"    - {detail_label}: {notes} (confidence: {confidence})")

print("\n" + "="*80)
print("EXTRACTION COMPLETE")
print("="*80)

# Close connection
conn.close()
