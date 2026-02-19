#!/usr/bin/env python3
"""
Improved extraction focusing on panel schedule circuit tables.
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


def extract_panel_circuits_improved(text, sheet_id, conn, drawing_number):
    """
    Extract circuit data from panel schedule using improved pattern matching.
    Looking for lines like:
    29 28 27 26 ... P2-S15-6UPS1 3 150 150 3-#1/0, 1-#6G, 1 1/2"C 92.8
    """
    print("Extracting panel circuits with improved patterns...")

    # First, determine panel name from title
    panel_name = None
    if "SERVICE 6" in text or "SERVICE-6" in text:
        panel_name = "SERVICE-6"
    elif "SERVICE 7" in text or "SERVICE-7" in text:
        panel_name = "SERVICE-7"
    else:
        # Try to extract from drawing number
        match = re.search(r'E\d+', drawing_number)
        if match:
            panel_name = match.group(0)

    if not panel_name:
        panel_name = drawing_number

    # Extract voltage from context
    voltage = "480V"  # default
    if "208/120V" in text[:2000]:  # Check in header area
        voltage = "208/120V"

    # Look for panel header info
    # Pattern: TOTAL CONNECTED... 836 A TOTAL EST. DEMAND CURR. 586 A
    total_connected_pattern = r'TOTAL CONNECTED[^\d]*(\d+)\s*A'
    total_demand_pattern = r'TOTAL EST\. DEMAND CURR\.\s*(\d+)\s*A'

    total_connected = None
    total_demand = None

    match = re.search(total_connected_pattern, text)
    if match:
        total_connected = float(match.group(1))

    match = re.search(total_demand_pattern, text)
    if match:
        total_demand = float(match.group(1))

    # Create or update panel
    cursor = conn.execute("""
        SELECT id FROM electrical_panels WHERE sheet_id = ? AND panel_name = ?
    """, (sheet_id, panel_name))
    row = cursor.fetchone()

    if row:
        panel_id = row[0]
        # Update with totals if found
        if total_connected or total_demand:
            conn.execute("""
                UPDATE electrical_panels
                SET total_connected_current = ?,
                    total_demand_current = ?,
                    voltage = ?
                WHERE id = ?
            """, (total_connected, total_demand, voltage, panel_id))
    else:
        # Insert new panel
        cursor = conn.execute("""
            INSERT INTO electrical_panels
            (sheet_id, panel_name, voltage, phases, wires,
             total_connected_current, total_demand_current, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            sheet_id,
            panel_name,
            voltage,
            3,  # assume 3-phase
            4 if voltage == "208/120V" else 3,
            total_connected,
            total_demand,
            0.80
        ))
        panel_id = cursor.lastrowid

    # Extract circuits
    # Pattern for circuit lines with equipment tags like P2-xxx-xxx
    # Format: [circuit_numbers] equipment_tag poles frame trip wire/conduit load
    circuit_pattern = r'(P2-[A-Z0-9]+-[A-Z0-9]+)\s+(\d+)\s+(\d+)\s+(\d+)\s+([^\d]+?)\s+([\d.]+)'

    circuits = []
    for match in re.finditer(circuit_pattern, text):
        equipment_tag = match.group(1)
        poles = int(match.group(2))
        frame = int(match.group(3))
        trip = int(match.group(4))
        wire_conduit = match.group(5).strip()
        load_amps = float(match.group(6))

        # Extract wire size from wire_conduit string
        wire_size = None
        conduit_size = None

        # Wire size pattern: 3-#1/0 or 3-#350
        wire_match = re.search(r'(\d+-#[\d/]+)', wire_conduit)
        if wire_match:
            wire_size = wire_match.group(1)

        # Conduit size pattern: 1 1/2"C or 2"C
        conduit_match = re.search(r'(\d+(?:\s+\d+/\d+)?"C)', wire_conduit)
        if conduit_match:
            conduit_size = conduit_match.group(1)

        circuits.append({
            "equipment_tag": equipment_tag,
            "poles": poles,
            "frame": frame,
            "trip": trip,
            "wire_size": wire_size,
            "conduit_size": conduit_size,
            "load_amps": load_amps
        })

    # Insert circuits
    count_circuits = 0
    for i, c in enumerate(circuits, 1):
        conn.execute("""
            INSERT INTO electrical_circuits
            (panel_id, sheet_id, circuit_number, equipment_tag, num_poles,
             breaker_frame, breaker_trip, wire_size, conduit_size, load_amps, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            panel_id,
            sheet_id,
            str(i),  # Use sequential numbering since circuit numbers aren't clearly labeled
            c["equipment_tag"],
            c["poles"],
            c["frame"],
            c["trip"],
            c["wire_size"],
            c["conduit_size"],
            c["load_amps"],
            0.85
        ))
        count_circuits += 1

    conn.commit()

    return {
        "panel_name": panel_name,
        "circuits": count_circuits,
        "total_connected": total_connected,
        "total_demand": total_demand
    }


def main():
    """Main extraction process for panel schedules."""

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
    print("IMPROVED PANEL SCHEDULE EXTRACTION")
    print("="*80)

    for drawing in drawings:
        print(f"\nProcessing: {drawing['drawing_number']} (Sheet ID: {drawing['sheet_id']})")

        file_path = Path(drawing["file_path"])
        if not file_path.exists():
            print(f"ERROR: File not found: {file_path}")
            continue

        text = extract_pdf_text(file_path)
        print(f"Extracted {len(text)} characters")

        result = extract_panel_circuits_improved(
            text,
            drawing["sheet_id"],
            conn,
            drawing["drawing_number"]
        )

        print(f"\nResults for {result['panel_name']}:")
        print(f"  - Circuits extracted: {result['circuits']}")
        if result['total_connected']:
            print(f"  - Total connected current: {result['total_connected']} A")
        if result['total_demand']:
            print(f"  - Total demand current: {result['total_demand']} A")

        # Update sheet extraction status
        conn.execute("""
            UPDATE sheets
            SET extracted_at = CURRENT_TIMESTAMP,
                extraction_model = 'pattern-matching-v2',
                quality_score = 0.80
            WHERE id = ?
        """, (drawing["sheet_id"],))
        conn.commit()

    print("\n" + "="*80)
    print("EXTRACTION COMPLETE")
    print("="*80)

    # Summary query
    print("\nSummary of all extracted data:")
    cursor = conn.execute("""
        SELECT s.drawing_number, s.title,
               COUNT(DISTINCT ec.id) as circuit_count
        FROM sheets s
        LEFT JOIN electrical_circuits ec ON ec.sheet_id = s.id
        WHERE s.id IN (508, 509, 510)
        GROUP BY s.id
        ORDER BY s.id
    """)
    for row in cursor:
        print(f"  {row['drawing_number']}: {row['circuit_count']} circuits")

    conn.close()


if __name__ == "__main__":
    main()
