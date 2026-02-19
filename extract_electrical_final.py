#!/usr/bin/env python3
"""
Final comprehensive electrical data extraction.
Handles the complex panel schedule table format.
"""

import sqlite3
import re
from pathlib import Path
import PyPDF2


def extract_pdf_text(pdf_path):
    """Extract text from PDF."""
    with open(pdf_path, 'rb') as f:
        pdf = PyPDF2.PdfReader(f)
        text_parts = []
        for page in pdf.pages:
            text_parts.append(page.extract_text())
    return "\n".join(text_parts)


def parse_panel_schedule_line(text, sheet_id, conn):
    """
    Parse the complex panel schedule format where circuits are listed like:
    13 WELDING OUTLET ROOM 1402, 1401 3 150 60 3-#6, 1-#10G, 3/4"C 12.0

    Returns count of circuits inserted.
    """

    # First extract panel info
    # Pattern: FED FROM: <panel_tag>
    fed_from_pattern = r'FED FROM:\s*(P2-[A-Z0-9]+-[A-Z0-9]+|[A-Z0-9\-]+)'
    location_pattern = r'LOCATION:\s*([A-Z0-9\s\-,]+?)(?:ENCLOSURE|SURFACE)'
    voltage_pattern = r'VOLTAGE:\s*([\d/]+)V'

    panel_tag = None
    location = None
    voltage = None

    match = re.search(fed_from_pattern, text)
    if match:
        panel_tag = match.group(1)

    match = re.search(location_pattern, text)
    if match:
        location = match.group(1).strip()

    match = re.search(voltage_pattern, text)
    if match:
        voltage = match.group(1) + "V"

    if not panel_tag:
        # Use a generic name based on sheet
        panel_tag = f"PANEL-{sheet_id}"

    # Get or create panel
    cursor = conn.execute("""
        SELECT id FROM electrical_panels
        WHERE sheet_id = ? AND (panel_name = ? OR fed_from = ?)
        LIMIT 1
    """, (sheet_id, panel_tag, panel_tag))
    row = cursor.fetchone()

    if row:
        panel_id = row[0]
        # Update with details
        conn.execute("""
            UPDATE electrical_panels
            SET location = COALESCE(?, location),
                voltage = COALESCE(?, voltage),
                fed_from = COALESCE(?, fed_from)
            WHERE id = ?
        """, (location, voltage, panel_tag, panel_id))
    else:
        cursor = conn.execute("""
            INSERT INTO electrical_panels
            (sheet_id, panel_name, location, voltage, phases, wires, fed_from, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            sheet_id,
            panel_tag,
            location,
            voltage,
            3,
            4 if voltage and "208" in voltage else 3,
            panel_tag,
            0.75
        ))
        panel_id = cursor.lastrowid

    # Now extract circuits
    # Circuit pattern: CKT# DESCRIPTION #_OF_POLES FRAME TRIP WIRE_CONDUIT LOAD
    # Example: 13 WELDING OUTLET ROOM 1402, 1401 3 150 60 3-#6, 1-#10G, 3/4"C 12.0

    # Split text into lines and look for circuit data
    lines = text.split('\n')

    circuits = []

    for line in lines:
        # Look for lines that start with a circuit number followed by description
        # Pattern: starts with 1-2 digit number, has equipment/description, then specs

        # Try to match: number description poles frame trip wire_info load
        pattern = r'^\s*(\d{1,2})\s+([A-Z][\w\s\-,\.]+?)\s+(\d)\s+(\d+)\s+(\d+)\s+([\d#\-,/\"\s\w]+?)\s+([\d.]+)\s*$'
        match = re.match(pattern, line)

        if match:
            ckt_num = match.group(1)
            description = match.group(2).strip()
            poles = int(match.group(3))
            frame = int(match.group(4))
            trip = int(match.group(5))
            wire_conduit = match.group(6).strip()
            load = float(match.group(7))

            # Extract wire size and conduit
            wire_size = None
            conduit_size = None

            # Wire: 3-#6 or 3-#1/0
            wire_match = re.search(r'(\d+-#[\w/]+)', wire_conduit)
            if wire_match:
                wire_size = wire_match.group(1)

            # Conduit: 3/4"C or 1 1/2"C
            conduit_match = re.search(r'([\d\s/]+)"C', wire_conduit)
            if conduit_match:
                conduit_size = conduit_match.group(1).strip() + '"'

            circuits.append({
                "circuit_number": ckt_num,
                "description": description,
                "poles": poles,
                "frame": frame,
                "trip": trip,
                "wire_size": wire_size,
                "conduit_size": conduit_size,
                "load_kva": load
            })

    # Insert circuits
    count = 0
    for c in circuits:
        conn.execute("""
            INSERT INTO electrical_circuits
            (panel_id, sheet_id, circuit_number, circuit_description,
             num_poles, breaker_frame, breaker_trip, wire_size, conduit_size,
             load_kva, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            panel_id,
            sheet_id,
            c["circuit_number"],
            c["description"],
            c["poles"],
            c["frame"],
            c["trip"],
            c["wire_size"],
            c["conduit_size"],
            c["load_kva"],
            0.80
        ))
        count += 1

    conn.commit()
    return count, panel_tag


def extract_all_electrical_data(sheet_id, file_path, drawing_number, conn):
    """Extract all electrical data from a drawing."""

    print(f"\n{'='*80}")
    print(f"Extracting: {drawing_number} (Sheet ID: {sheet_id})")
    print(f"{'='*80}")

    # Extract text
    pdf_path = Path(file_path)
    if not pdf_path.exists():
        print(f"ERROR: File not found: {file_path}")
        return {}

    text = extract_pdf_text(pdf_path)
    print(f"Extracted {len(text)} characters of text")

    # Parse circuits
    circuit_count, panel_name = parse_panel_schedule_line(text, sheet_id, conn)

    print(f"\nExtracted from {panel_name}:")
    print(f"  - Circuits: {circuit_count}")

    # Update sheet
    conn.execute("""
        UPDATE sheets
        SET extracted_at = CURRENT_TIMESTAMP,
            extraction_model = 'pattern-matching-final',
            quality_score = 0.80
        WHERE id = ?
    """, (sheet_id,))
    conn.commit()

    return {
        "panel_name": panel_name,
        "circuits": circuit_count
    }


def main():
    """Main extraction."""

    db_path = Path("D:/qms/data/quality.db")
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    drawings = [
        {
            "sheet_id": 509,
            "file_path": "D:/qms/data/projects/07609-Freshpet/Electrical/E6606-PANEL-SCHEDULES---SERVICE-6-Rev.1.pdf",
            "drawing_number": "E6606"
        },
        {
            "sheet_id": 510,
            "file_path": "D:/qms/data/projects/07609-Freshpet/Electrical/E6607-PANEL-SCHEDULES---SERVICE-6-Rev.2.pdf",
            "drawing_number": "E6607"
        }
    ]

    print("="*80)
    print("FINAL ELECTRICAL DATA EXTRACTION")
    print("="*80)

    results = []
    for drawing in drawings:
        result = extract_all_electrical_data(
            drawing["sheet_id"],
            drawing["file_path"],
            drawing["drawing_number"],
            conn
        )
        results.append(result)

    # Summary
    print("\n" + "="*80)
    print("EXTRACTION SUMMARY")
    print("="*80)

    # Query all data
    cursor = conn.execute("""
        SELECT
            s.id,
            s.drawing_number,
            s.drawing_type,
            COUNT(DISTINCT xfmr.id) as transformers,
            COUNT(DISTINCT sw.id) as switchgear,
            COUNT(DISTINCT p.id) as panels,
            COUNT(DISTINCT c.id) as circuits
        FROM sheets s
        LEFT JOIN electrical_transformers xfmr ON xfmr.sheet_id = s.id
        LEFT JOIN electrical_switchgear sw ON sw.sheet_id = s.id
        LEFT JOIN electrical_panels p ON p.sheet_id = s.id
        LEFT JOIN electrical_circuits c ON c.sheet_id = s.id
        WHERE s.id IN (508, 509, 510)
        GROUP BY s.id
        ORDER BY s.id
    """)

    print("\nFinal counts by drawing:")
    for row in cursor:
        print(f"\n{row['drawing_number']} ({row['drawing_type']}):")
        print(f"  - Transformers: {row['transformers']}")
        print(f"  - Switchgear: {row['switchgear']}")
        print(f"  - Panels: {row['panels']}")
        print(f"  - Circuits: {row['circuits']}")

    conn.close()


if __name__ == "__main__":
    main()
