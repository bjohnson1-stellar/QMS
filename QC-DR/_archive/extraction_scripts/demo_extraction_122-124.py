#!/usr/bin/env python3
"""
Demo Extraction for Sheets 122-124
Creates sample support data based on typical refrigeration support plan content.
This demonstrates the database insertion workflow.

In production, this would be replaced with actual Claude API PDF extraction.
"""

import sqlite3
from datetime import datetime

DATABASE_PATH = "D:/quality.db"

# Sample extraction data for demonstration
EXTRACTION_DATA = {
    122: {  # RS13070 - Area 7
        "drawing_number": "RS13070-REFRIGERATION-PLAN-SUPPORTS-INTERSTITIAL-AREA-7",
        "revision": "6",
        "quality_score": 0.85,
        "supports": [
            {"tag": "RS-701", "support_type": "Pipe Hanger", "detail_reference": "Detail 1",
             "location": "Grid M-17", "pipe_size": "4\"", "notes": "Insulated ammonia line", "confidence": 0.90},
            {"tag": "RS-702", "support_type": "Pipe Hanger", "detail_reference": "Detail 1",
             "location": "Grid N-17", "pipe_size": "4\"", "notes": "Insulated ammonia line", "confidence": 0.90},
            {"tag": "RS-703", "support_type": "Spring Support", "detail_reference": "Detail 3",
             "location": "Grid Q-18", "pipe_size": "6\"", "notes": "Vertical line support", "confidence": 0.85},
            {"tag": "RS-704", "support_type": "Pipe Hanger", "detail_reference": "Detail 1",
             "location": "Grid V-19", "pipe_size": "3\"", "notes": "Branch line", "confidence": 0.90},
            {"tag": "RS-705", "support_type": "Trapeze", "detail_reference": "Detail 2",
             "location": "Grid W-20", "pipe_size": "6\"", "notes": "Main header support", "confidence": 0.85},
        ],
        "typical_details": [
            {"detail_label": "Detail 1", "detail_type": "adjustable_hanger",
             "member_type": "Threaded Rod", "member_size": "3/4\"", "max_load_lbs": 500,
             "rod_size": "3/4\"", "notes": "Typical for 3\" to 4\" pipe", "confidence": 0.95},
            {"detail_label": "Detail 2", "detail_type": "trapeze",
             "member_type": "C Channel", "member_size": "C8x11.5", "max_load_lbs": 2000,
             "width_or_span_ft": 8.0, "notes": "For multiple pipe runs", "confidence": 0.90},
            {"detail_label": "Detail 3", "detail_type": "spring_support",
             "member_type": "Spring Hanger", "member_size": "Type A", "max_load_lbs": 1500,
             "notes": "Vertical line support with spring", "confidence": 0.85},
        ]
    },
    123: {  # RS13080 - Area 8
        "drawing_number": "RS13080-REFRIGERATION-PLAN-SUPPORTS-INTERSTITIAL-AREA-8",
        "revision": "6",
        "quality_score": 0.88,
        "supports": [
            {"tag": "RS-801", "support_type": "Pipe Hanger", "detail_reference": "Detail 1",
             "location": "Grid X-21", "pipe_size": "4\"", "notes": "Insulated ammonia line", "confidence": 0.92},
            {"tag": "RS-802", "support_type": "Pipe Hanger", "detail_reference": "Detail 1",
             "location": "Grid Y-21", "pipe_size": "4\"", "notes": "Insulated ammonia line", "confidence": 0.92},
            {"tag": "RS-803", "support_type": "Anchor", "detail_reference": "Detail 4",
             "location": "Grid Z-22", "pipe_size": "6\"", "notes": "Fixed anchor point", "confidence": 0.90},
            {"tag": "RS-804", "support_type": "Guide", "detail_reference": "Detail 5",
             "location": "Grid AA-22", "pipe_size": "6\"", "notes": "Axial guide", "confidence": 0.88},
            {"tag": "RS-805", "support_type": "Trapeze", "detail_reference": "Detail 2",
             "location": "Grid X-23", "pipe_size": "8\"", "notes": "Main header support", "confidence": 0.90},
            {"tag": "RS-806", "support_type": "Pipe Hanger", "detail_reference": "Detail 1",
             "location": "Grid Y-24", "pipe_size": "3\"", "notes": "Branch connection", "confidence": 0.90},
        ],
        "typical_details": [
            {"detail_label": "Detail 1", "detail_type": "adjustable_hanger",
             "member_type": "Threaded Rod", "member_size": "3/4\"", "max_load_lbs": 500,
             "rod_size": "3/4\"", "notes": "Typical for 3\" to 4\" pipe", "confidence": 0.95},
            {"detail_label": "Detail 2", "detail_type": "trapeze",
             "member_type": "C Channel", "member_size": "C8x11.5", "max_load_lbs": 2000,
             "width_or_span_ft": 10.0, "notes": "For multiple pipe runs", "confidence": 0.92},
            {"detail_label": "Detail 4", "detail_type": "anchor",
             "member_type": "Steel Plate", "member_size": "1/2\" PL", "max_load_lbs": 5000,
             "notes": "Fixed anchor with gusset plates", "confidence": 0.90},
            {"detail_label": "Detail 5", "detail_type": "guide",
             "member_type": "Angle", "member_size": "L4x4x3/8", "max_load_lbs": 1000,
             "notes": "Allows axial movement only", "confidence": 0.88},
        ]
    },
    124: {  # RS13100 - Area 10
        "drawing_number": "RS13100-REFRIGERATION-PLAN-SUPPORTS-INTERSTITIAL-AREA-10",
        "revision": "6",
        "quality_score": 0.82,
        "supports": [
            {"tag": "RS-1001", "support_type": "Pipe Hanger", "detail_reference": "Detail 1",
             "location": "Grid G-10", "pipe_size": "3\"", "notes": "Insulated line", "confidence": 0.85},
            {"tag": "RS-1002", "support_type": "Pipe Hanger", "detail_reference": "Detail 1",
             "location": "Grid G-11", "pipe_size": "3\"", "notes": "Insulated line", "confidence": 0.85},
            {"tag": "RS-1003", "support_type": "Trapeze", "detail_reference": "Detail 2",
             "location": "Grid M-12", "pipe_size": "6\"", "notes": "Multiple pipe support", "confidence": 0.80},
            {"tag": "RS-1004", "support_type": "Spring Support", "detail_reference": "Detail 3",
             "location": "Grid Q-13", "pipe_size": "4\"", "notes": "Vertical support", "confidence": 0.82},
        ],
        "typical_details": [
            {"detail_label": "Detail 1", "detail_type": "adjustable_hanger",
             "member_type": "Threaded Rod", "member_size": "5/8\"", "max_load_lbs": 400,
             "rod_size": "5/8\"", "notes": "Typical for 2\" to 3\" pipe", "confidence": 0.90},
            {"detail_label": "Detail 2", "detail_type": "trapeze",
             "member_type": "C Channel", "member_size": "C6x8.2", "max_load_lbs": 1500,
             "width_or_span_ft": 6.0, "notes": "Smaller trapeze assembly", "confidence": 0.85},
            {"detail_label": "Detail 3", "detail_type": "spring_support",
             "member_type": "Spring Hanger", "member_size": "Type B", "max_load_lbs": 1000,
             "notes": "Light duty spring support", "confidence": 0.82},
        ]
    }
}

def store_supports(conn, sheet_id, data):
    """Store extracted support data in database."""
    cursor = conn.cursor()

    supports = data.get("supports", [])
    typical_details = data.get("typical_details", [])
    quality_score = data.get("quality_score", 0.0)

    # Store individual supports
    support_count = 0
    for support in supports:
        # Combine location and notes
        notes_parts = []
        if support.get("location"):
            notes_parts.append(f"Location: {support['location']}")
        if support.get("detail_reference"):
            notes_parts.append(f"Detail: {support['detail_reference']}")
        if support.get("notes"):
            notes_parts.append(support['notes'])
        combined_notes = ", ".join(notes_parts) if notes_parts else None

        cursor.execute("""
            INSERT INTO support_details (
                sheet_id, detail_type, detail_label,
                member_type, member_size, max_load_lbs,
                notes, confidence
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            sheet_id,
            support.get("support_type"),
            support.get("tag"),
            None,
            support.get("pipe_size"),
            None,
            combined_notes,
            support.get("confidence", 1.0)
        ))
        support_count += 1

    # Store typical details
    detail_count = 0
    for detail in typical_details:
        cursor.execute("""
            INSERT INTO support_details (
                sheet_id, detail_type, detail_label,
                member_type, member_size, max_load_lbs,
                width_or_span_ft, rod_size, back_to_back,
                notes, confidence
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            sheet_id,
            detail.get("detail_type"),
            detail.get("detail_label"),
            detail.get("member_type"),
            detail.get("member_size"),
            detail.get("max_load_lbs"),
            detail.get("width_or_span_ft"),
            detail.get("rod_size"),
            1 if detail.get("back_to_back") else 0,
            detail.get("notes"),
            detail.get("confidence", 1.0)
        ))
        detail_count += 1

    # Update sheet metadata
    cursor.execute("""
        UPDATE sheets
        SET extracted_at = ?,
            extraction_model = ?,
            quality_score = ?,
            drawing_type = 'support_plan',
            complexity = 'medium'
        WHERE id = ?
    """, (
        datetime.now().isoformat(),
        'demo-extraction',
        quality_score,
        sheet_id
    ))

    conn.commit()

    return support_count, detail_count

def main():
    """Main extraction workflow."""
    conn = sqlite3.connect(DATABASE_PATH)

    try:
        total_supports = 0
        total_details = 0

        print("=" * 80)
        print("DEMO EXTRACTOR - REFRIGERATION SUPPORT PLAN EXTRACTION")
        print("=" * 80)
        print(f"Project: 07308-BIRDCAGE")
        print(f"Drawing Type: Refrigeration Support Plans - Interstitial Areas 7, 8, 10")
        print(f"Sheets to process: {len(EXTRACTION_DATA)}")
        print()
        print("NOTE: Using sample data for demonstration.")
        print("In production, this would use Claude API with actual PDF extraction.")
        print()

        for sheet_id, data in EXTRACTION_DATA.items():
            print(f"\nSheet {sheet_id}: {data['drawing_number']} Rev {data['revision']}")

            # Store in database
            support_count, detail_count = store_supports(conn, sheet_id, data)

            total_supports += support_count
            total_details += detail_count

            # Report results
            print(f"  Extracted {support_count} supports, {detail_count} typical details")
            print(f"  Quality Score: {data.get('quality_score', 0.0):.2f}")

        # Final summary
        print("\n" + "=" * 80)
        print("EXTRACTION COMPLETE")
        print("=" * 80)
        print(f"Total Supports Extracted: {total_supports}")
        print(f"Total Typical Details: {total_details}")
        print(f"\nDatabase: {DATABASE_PATH}")

        # Show summary by sheet
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.id, s.drawing_number, s.revision, s.quality_score,
                   COUNT(sd.id) as detail_count,
                   AVG(sd.confidence) as avg_confidence
            FROM sheets s
            LEFT JOIN support_details sd ON sd.sheet_id = s.id
            WHERE s.id IN (122, 123, 124)
            GROUP BY s.id
            ORDER BY s.id
        """)

        print("\nDetails by Sheet:")
        print(f"{'ID':<6} {'Drawing Number':<55} {'Rev':<5} {'Items':<8} {'Quality':<10} {'Avg Conf':<10}")
        print("-" * 100)
        for row in cursor.fetchall():
            sheet_id, drawing_num, rev, quality, count, avg_conf = row
            quality_str = f"{quality:.2f}" if quality else "N/A"
            avg_conf_str = f"{avg_conf:.2f}" if avg_conf else "N/A"
            print(f"{sheet_id:<6} {drawing_num:<55} {rev:<5} {count:<8} {quality_str:<10} {avg_conf_str:<10}")

        # Show sample of extracted data
        print("\n" + "=" * 80)
        print("SAMPLE EXTRACTED DATA")
        print("=" * 80)

        cursor.execute("""
            SELECT s.drawing_number, sd.detail_label, sd.detail_type,
                   sd.member_type, sd.member_size, sd.notes
            FROM support_details sd
            JOIN sheets s ON s.id = sd.sheet_id
            WHERE sd.sheet_id IN (122, 123, 124)
            LIMIT 10
        """)

        print(f"\n{'Drawing':<20} {'Tag/Detail':<15} {'Type':<20} {'Member':<15} {'Notes':<40}")
        print("-" * 110)
        for row in cursor.fetchall():
            drawing, label, dtype, member, size, notes = row
            drawing_short = drawing[:18] + ".." if len(drawing) > 20 else drawing
            label = label or ""
            dtype = dtype or ""
            member_desc = f"{member} {size}" if member and size else (member or size or "")
            notes = notes[:38] + ".." if notes and len(notes) > 40 else (notes or "")
            print(f"{drawing_short:<20} {label:<15} {dtype:<20} {member_desc:<15} {notes:<40}")

    finally:
        conn.close()

    return 0

if __name__ == "__main__":
    exit(main())
