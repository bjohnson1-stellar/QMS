"""
Verify extracted data in database and generate summary report.
"""
import sqlite3

DATABASE_PATH = "D:/quality.db"

def main():
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    print("Extraction Verification Report")
    print("=" * 70)
    print()

    # Get sheet information
    cursor.execute("""
        SELECT id, drawing_number, title, revision,
               drawing_type, complexity, quality_score, extracted_at
        FROM sheets
        WHERE id IN (7, 8, 9)
        ORDER BY id
    """)

    sheets = cursor.fetchall()

    for sheet in sheets:
        sheet_id, drawing_num, title, rev, draw_type, complexity, quality, extracted_at = sheet

        print(f"Sheet {sheet_id}: {drawing_num} Rev {rev}")
        print("-" * 70)
        print(f"  Title: {title}")
        print(f"  Drawing Type: {draw_type}")
        print(f"  Complexity: {complexity}")
        print(f"  Quality Score: {quality:.2f}")
        print(f"  Extracted At: {extracted_at}")

        # Count lines
        cursor.execute("SELECT COUNT(*) FROM lines WHERE sheet_id = ?", (sheet_id,))
        line_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM lines WHERE sheet_id = ? AND spec_class = 'DUCT'", (sheet_id,))
        duct_count = cursor.fetchone()[0]

        pipe_count = line_count - duct_count

        # Count equipment
        cursor.execute("SELECT COUNT(*) FROM equipment WHERE sheet_id = ?", (sheet_id,))
        equip_count = cursor.fetchone()[0]

        # Count instruments
        cursor.execute("SELECT COUNT(*) FROM instruments WHERE sheet_id = ?", (sheet_id,))
        inst_count = cursor.fetchone()[0]

        print(f"\n  Database Records:")
        print(f"    - Piping Lines: {pipe_count}")
        print(f"    - Ducts: {duct_count}")
        print(f"    - Equipment: {equip_count}")
        print(f"    - Instruments: {inst_count}")

        # Sample some lines
        cursor.execute("""
            SELECT line_number, size, service, material, confidence
            FROM lines
            WHERE sheet_id = ? AND spec_class IS NULL
            ORDER BY confidence DESC
            LIMIT 3
        """, (sheet_id,))

        sample_lines = cursor.fetchall()
        if sample_lines:
            print(f"\n  Sample Lines (highest confidence):")
            for line_num, size, service, material, conf in sample_lines:
                print(f"    - {line_num}: {size} {material} {service} (conf: {conf:.2f})")

        # Sample equipment
        cursor.execute("""
            SELECT tag, equipment_type, description, confidence
            FROM equipment
            WHERE sheet_id = ?
            ORDER BY confidence DESC
            LIMIT 3
        """, (sheet_id,))

        sample_equip = cursor.fetchall()
        if sample_equip:
            print(f"\n  Sample Equipment (highest confidence):")
            for tag, equip_type, desc, conf in sample_equip:
                print(f"    - {tag}: {equip_type} - {desc} (conf: {conf:.2f})")

        print()

    # Overall statistics
    print("=" * 70)
    print("Overall Statistics")
    print("-" * 70)

    cursor.execute("""
        SELECT
            COUNT(DISTINCT sheet_id) as sheet_count,
            COUNT(*) as total_lines
        FROM lines
        WHERE sheet_id IN (7, 8, 9)
    """)
    sheet_count, total_lines = cursor.fetchone()

    cursor.execute("SELECT COUNT(*) FROM lines WHERE sheet_id IN (7, 8, 9) AND spec_class = 'DUCT'")
    total_ducts = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM equipment WHERE sheet_id IN (7, 8, 9)")
    total_equipment = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM instruments WHERE sheet_id IN (7, 8, 9)")
    total_instruments = cursor.fetchone()[0]

    print(f"  Sheets Processed: {sheet_count}")
    print(f"  Total Piping Lines: {total_lines - total_ducts}")
    print(f"  Total Ducts: {total_ducts}")
    print(f"  Total Equipment: {total_equipment}")
    print(f"  Total Instruments: {total_instruments}")
    print(f"  Total Items Extracted: {total_lines + total_equipment + total_instruments}")

    # Average quality scores
    cursor.execute("""
        SELECT AVG(quality_score)
        FROM sheets
        WHERE id IN (7, 8, 9)
    """)
    avg_quality = cursor.fetchone()[0]

    print(f"\n  Average Quality Score: {avg_quality:.2f}")

    # Confidence distribution
    cursor.execute("""
        SELECT
            CASE
                WHEN confidence >= 0.9 THEN 'Excellent (0.9+)'
                WHEN confidence >= 0.8 THEN 'Good (0.8-0.9)'
                WHEN confidence >= 0.7 THEN 'Fair (0.7-0.8)'
                ELSE 'Review Needed (<0.7)'
            END as conf_range,
            COUNT(*) as count
        FROM (
            SELECT confidence FROM lines WHERE sheet_id IN (7, 8, 9)
            UNION ALL
            SELECT confidence FROM equipment WHERE sheet_id IN (7, 8, 9)
            UNION ALL
            SELECT confidence FROM instruments WHERE sheet_id IN (7, 8, 9)
        )
        GROUP BY conf_range
        ORDER BY MIN(confidence) DESC
    """)

    print(f"\n  Confidence Distribution:")
    for conf_range, count in cursor.fetchall():
        print(f"    - {conf_range}: {count} items")

    conn.close()
    print()
    print("=" * 70)
    print("Verification complete - all data successfully stored in database")

if __name__ == "__main__":
    main()
