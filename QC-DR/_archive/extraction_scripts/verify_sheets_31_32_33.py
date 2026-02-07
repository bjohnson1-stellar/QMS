#!/usr/bin/env python3
"""Verify extraction results for sheets 31, 32, 33"""

import sqlite3

DB_PATH = "D:/quality.db"

def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    print("=" * 80)
    print("VERIFICATION REPORT: Sheets 31, 32, 33 Extraction")
    print("=" * 80)

    # Get sheet information
    cur.execute("""
        SELECT id, drawing_number, title, revision,
               drawing_type, complexity, quality_score,
               extraction_model, extracted_at
        FROM sheets
        WHERE id IN (31, 32, 33)
        ORDER BY id
    """)

    sheets = cur.fetchall()

    for sheet in sheets:
        sheet_id, dwg_num, title, rev, dwg_type, complexity, quality, model, extracted = sheet

        print(f"\n{'=' * 80}")
        print(f"{dwg_num} Rev {rev} (Sheet ID: {sheet_id})")
        print(f"{'=' * 80}")
        print(f"Title:      {title}")
        print(f"Type:       {dwg_type}")
        print(f"Complexity: {complexity}")
        print(f"Quality:    {quality:.2f}")
        print(f"Model:      {model}")
        print(f"Extracted:  {extracted}")

        # Equipment
        cur.execute("""
            SELECT tag, equipment_type, description, confidence
            FROM equipment
            WHERE sheet_id = ?
            ORDER BY tag
        """, (sheet_id,))
        equipment = cur.fetchall()

        print(f"\nEQUIPMENT ({len(equipment)} items):")
        if equipment:
            print(f"  {'Tag':<15} {'Type':<30} {'Confidence':>10}")
            print(f"  {'-'*15} {'-'*30} {'-'*10}")
            for tag, eq_type, desc, conf in equipment:
                print(f"  {tag:<15} {eq_type:<30} {conf:>10.2f}")
        else:
            print("  (none)")

        # Lines - filtered for actual piping
        cur.execute("""
            SELECT line_number, size, service, confidence
            FROM lines
            WHERE sheet_id = ?
              AND (service LIKE '%Refrigerant%'
                   OR service LIKE '%Gas%'
                   OR service LIKE '%Pressure%'
                   OR service LIKE '%Liquid%'
                   OR service LIKE '%Suction%')
            ORDER BY line_number
        """, (sheet_id,))
        lines = cur.fetchall()

        print(f"\nREFRIGERANT LINES ({len(lines)} items):")
        if lines:
            print(f"  {'Line Number':<20} {'Size':<10} {'Service':<40}")
            print(f"  {'-'*20} {'-'*10} {'-'*40}")
            for line_num, size, service, conf in lines:
                print(f"  {line_num:<20} {size:<10} {service:<40}")
        else:
            print("  (none)")

        # Instruments
        cur.execute("""
            SELECT tag, instrument_type, loop_number, confidence
            FROM instruments
            WHERE sheet_id = ?
            ORDER BY tag
        """, (sheet_id,))
        instruments = cur.fetchall()

        print(f"\nINSTRUMENTS ({len(instruments)} items):")
        if instruments:
            for tag, inst_type, loop, conf in instruments:
                print(f"  {tag:<15} {inst_type:<30} Loop: {loop}")
        else:
            print("  (none)")

    # Summary
    print(f"\n{'=' * 80}")
    print("SUMMARY")
    print(f"{'=' * 80}")

    for sheet_id in [31, 32, 33]:
        cur.execute("SELECT drawing_number FROM sheets WHERE id = ?", (sheet_id,))
        dwg_num = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM equipment WHERE sheet_id = ?", (sheet_id,))
        eq_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM lines WHERE sheet_id = ?", (sheet_id,))
        line_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM instruments WHERE sheet_id = ?", (sheet_id,))
        inst_count = cur.fetchone()[0]

        print(f"\n{dwg_num}:")
        print(f"  Equipment:   {eq_count:3d}")
        print(f"  Lines:       {line_count:3d}")
        print(f"  Instruments: {inst_count:3d}")

    # Total across all three sheets
    cur.execute("SELECT COUNT(*) FROM equipment WHERE sheet_id IN (31, 32, 33)")
    total_eq = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM lines WHERE sheet_id IN (31, 32, 33)")
    total_lines = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM instruments WHERE sheet_id IN (31, 32, 33)")
    total_inst = cur.fetchone()[0]

    print(f"\nTOTAL:")
    print(f"  Equipment:   {total_eq:3d}")
    print(f"  Lines:       {total_lines:3d}")
    print(f"  Instruments: {total_inst:3d}")

    print(f"\n{'=' * 80}")

    conn.close()

if __name__ == "__main__":
    main()
