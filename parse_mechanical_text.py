"""
Parse extracted mechanical drawing text and load equipment data into database.

Based on text extraction from PDFs, identifies equipment tags and attributes.
"""

import re
import sqlite3
from pathlib import Path

DB_PATH = r"D:\qms\data\quality.db"

# Equipment tag patterns for mechanical drawings
EQUIPMENT_PATTERNS = {
    "AHU": r"SA-AHU-\d+",           # Air Handling Units
    "FAN": r"EF-FAN-\d+",           # Exhaust Fans
    "DCU": r"SA-DCU-\d+[AB]?",      # Dehumidification Units
    "DDX": r"SA-DDX-\d+[AB]?",      # Dehumidifiers / DX Units
    "ATB": r"SA-ATB-\d+[AB]?",      # Air Terminal Boxes
    "DH": r"DH-\d+",                # Dehumidifiers
}

def parse_equipment_from_text(text: str, drawing_number: str) -> list:
    """Extract equipment tags from drawing text."""
    equipment = []

    # Find all equipment tags
    for eq_type, pattern in EQUIPMENT_PATTERNS.items():
        matches = re.findall(pattern, text)
        for tag in set(matches):  # Remove duplicates
            equipment.append({
                "equipment_mark": tag,
                "equipment_type": expand_equipment_type(eq_type),
                "notes": f"Found on {drawing_number}",
            })

    return equipment


def expand_equipment_type(abbrev: str) -> str:
    """Expand equipment type abbreviations."""
    types = {
        "AHU": "Air Handling Unit",
        "FAN": "Exhaust Fan",
        "DCU": "Dehumidification Control Unit",
        "DDX": "Direct Expansion Dehumidifier",
        "ATB": "Air Terminal Box",
        "DH": "Dehumidifier",
    }
    return types.get(abbrev, abbrev)


def parse_cfm_near_tag(text: str, tag: str) -> int:
    """Try to find CFM value near an equipment tag."""
    # Look for CFM within 200 characters after the tag
    tag_pos = text.find(tag)
    if tag_pos == -1:
        return None

    search_text = text[tag_pos:tag_pos + 200]
    cfm_match = re.search(r'(\d{1,3},?\d{0,3})\s*CFM', search_text)
    if cfm_match:
        cfm_str = cfm_match.group(1).replace(',', '')
        return int(cfm_str)

    return None


def load_sheet_equipment(sheet_id: int, drawing_number: str, text_file: Path, conn: sqlite3.Connection):
    """Parse text file and load equipment for a sheet."""

    text = text_file.read_text(encoding='utf-8')

    # Extract equipment
    equipment_list = parse_equipment_from_text(text, drawing_number)

    # Try to find CFM values for each piece of equipment
    for eq in equipment_list:
        cfm = parse_cfm_near_tag(text, eq["equipment_mark"])
        if cfm:
            eq["cfm"] = cfm

    # Insert into database
    inserted = 0
    for eq in equipment_list:
        # Check if already exists
        existing = conn.execute(
            "SELECT id FROM mechanical_equipment WHERE sheet_id = ? AND equipment_mark = ?",
            (sheet_id, eq["equipment_mark"])
        ).fetchone()

        if not existing:
            conn.execute("""
                INSERT INTO mechanical_equipment (
                    sheet_id, equipment_mark, equipment_type, cfm, notes, confidence
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                sheet_id,
                eq["equipment_mark"],
                eq["equipment_type"],
                eq.get("cfm"),
                eq.get("notes"),
                0.75,  # Text-based extraction confidence
            ))
            inserted += 1

    return inserted, len(equipment_list)


def main():
    """Process all three mechanical drawings."""

    sheets = [
        {
            "id": 551,
            "drawing_number": "M1401-MECHANICAL-OVERALL-ROOF-PLAN",
            "text_file": Path(r"D:\qms\data\projects\07609-Freshpet\Mechanical\M1401-MECHANICAL-OVERALL-ROOF-PLAN-Rev.1.txt"),
        },
        {
            "id": 552,
            "drawing_number": "M3001-MECHANICAL-SECTIONS",
            "text_file": Path(r"D:\qms\data\projects\07609-Freshpet\Mechanical\M3001-MECHANICAL-SECTIONS-Rev.1.txt"),
        },
        {
            "id": 553,
            "drawing_number": "M4001-ENLARGED-FIRST-FLOOR-MECHANICAL-PLAN",
            "text_file": Path(r"D:\qms\data\projects\07609-Freshpet\Mechanical\M4001-ENLARGED-FIRST-FLOOR-MECHANICAL-PLAN-Rev.1.txt"),
        },
    ]

    print("=" * 70)
    print("PARSING MECHANICAL EQUIPMENT FROM TEXT EXTRACTION")
    print("=" * 70)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    total_inserted = 0
    total_found = 0

    for sheet in sheets:
        print(f"\nSheet {sheet['id']}: {sheet['drawing_number']}")
        print("-" * 70)

        if not sheet["text_file"].exists():
            print(f"  ERROR: Text file not found: {sheet['text_file']}")
            continue

        inserted, found = load_sheet_equipment(
            sheet["id"],
            sheet["drawing_number"],
            sheet["text_file"],
            conn
        )

        print(f"  Found: {found} equipment items")
        print(f"  Inserted: {inserted} new items")

        # Show what was found
        equipment = conn.execute("""
            SELECT equipment_mark, equipment_type, cfm
            FROM mechanical_equipment
            WHERE sheet_id = ?
            ORDER BY equipment_mark
        """, (sheet["id"],)).fetchall()

        if equipment:
            print(f"\n  Equipment on this sheet:")
            for eq in equipment:
                cfm_str = f" ({eq['cfm']} CFM)" if eq['cfm'] else ""
                print(f"    - {eq['equipment_mark']}: {eq['equipment_type']}{cfm_str}")

        total_inserted += inserted
        total_found += found

        # Update sheet status
        conn.execute("""
            UPDATE sheets
            SET extracted_at = CURRENT_TIMESTAMP,
                extraction_model = 'text_parsing',
                quality_score = 0.75,
                drawing_type = 'Mechanical Plan',
                complexity = 'medium'
            WHERE id = ?
        """, (sheet["id"],))

    conn.commit()
    conn.close()

    print(f"\n{'=' * 70}")
    print("SUMMARY")
    print(f"{'=' * 70}")
    print(f"Total equipment found: {total_found}")
    print(f"Total new items inserted: {total_inserted}")
    print(f"\nNote: Confidence score is 0.75 (text-based extraction)")
    print("For better results, visual inspection of PDFs is recommended.")


if __name__ == "__main__":
    main()
