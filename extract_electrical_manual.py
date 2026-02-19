#!/usr/bin/env python3
"""
Manual extraction of electrical data from Freshpet drawings.
Based on examination of the PDF text content.
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


def extract_single_line_diagram(text, sheet_id, conn):
    """Extract data from single line diagram."""
    print("Extracting switchgear and panels...")

    # Pattern for panels like: P2-G16-6DP01 1200A, 480V, 3?, 3W, 35,000 AIC
    panel_pattern = r'(P2-[A-Z0-9]+-[A-Z0-9]+)\s+(\d+)A[,\s]+([\d/]+)V[,\s]+([^,]+),\s+([^,]+),\s+([\d,]+)\s+AIC'

    switchgear = []
    for match in re.finditer(panel_pattern, text):
        tag = match.group(1)
        current = int(match.group(2))
        voltage = match.group(3) + "V"
        phases_wires = match.group(4) + ", " + match.group(5)
        aic = match.group(6).replace(",", "")

        switchgear.append({
            "tag": tag,
            "equipment_type": "Panel" if "DP" in tag else "Switchboard",
            "voltage": voltage,
            "current_rating": current,
            "aic_rating": aic
        })

    # Insert switchgear
    count_sw = 0
    for sw in switchgear:
        conn.execute("""
            INSERT INTO electrical_switchgear
            (sheet_id, tag, equipment_type, voltage, current_rating, short_circuit_amps, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            sheet_id,
            sw["tag"],
            sw["equipment_type"],
            sw["voltage"],
            sw["current_rating"],
            int(sw["aic_rating"]) if sw["aic_rating"].isdigit() else None,
            0.85
        ))
        count_sw += 1

    # Pattern for transformers: P2-I15-6TL1A, 30KVA 480V TO 208/120V
    xfmr_pattern = r'(P2-[A-Z0-9]+-[A-Z0-9]+),\s+(\d+)KVA\s+(\d+)V\s+TO\s+([\d/]+)V\s+([^,]+),\s+([^,]+),\s+(\d+)Hz'

    transformers = []
    for match in re.finditer(xfmr_pattern, text):
        transformers.append({
            "tag": match.group(1),
            "kva": int(match.group(2)),
            "primary_v": match.group(3) + "V",
            "secondary_v": match.group(4) + "V",
            "phases": 3 if "3?" in match.group(5) else 1,
            "wires": 4 if "4W" in match.group(6) else 3,
            "frequency": int(match.group(7))
        })

    # Insert transformers
    count_xfmr = 0
    for xfmr in transformers:
        conn.execute("""
            INSERT INTO electrical_transformers
            (sheet_id, tag, kva_rating, primary_voltage, secondary_voltage,
             phases, wires, frequency, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            sheet_id,
            xfmr["tag"],
            xfmr["kva"],
            xfmr["primary_v"],
            xfmr["secondary_v"],
            xfmr["phases"],
            xfmr["wires"],
            xfmr["frequency"],
            0.90
        ))
        count_xfmr += 1

    conn.commit()
    print(f"  - Switchgear: {count_sw}")
    print(f"  - Transformers: {count_xfmr}")

    return {"switchgear": count_sw, "transformers": count_xfmr}


def extract_panel_schedule(text, sheet_id, conn, drawing_number):
    """Extract data from panel schedule."""
    print("Extracting panel schedule data...")

    # This is more complex - panel schedules have tables of circuits
    # For now, extract basic panel info

    # Pattern for panel header info
    # Example: "SERVICE 6 PANEL SCHEDULE"
    # Look for voltage, phases, etc.

    panels_found = []

    # Try to find panel name in text
    panel_name_pattern = r'PANEL\s+([A-Z0-9\-]+)'
    for match in re.finditer(panel_name_pattern, text):
        panel_name = match.group(1)
        if panel_name not in panels_found:
            panels_found.append(panel_name)

    # If no specific panel names, use drawing number
    if not panels_found:
        if "SERVICE 6" in text or "SERVICE-6" in text:
            panels_found = ["SERVICE-6"]
        else:
            panels_found = [drawing_number]

    count_panels = 0
    panel_ids = {}

    for panel_name in panels_found:
        # Extract voltage if present
        voltage = "480V"  # default
        if "208/120V" in text:
            voltage = "208/120V"
        elif "480V" in text:
            voltage = "480V"

        cursor = conn.execute("""
            INSERT INTO electrical_panels
            (sheet_id, panel_name, voltage, phases, wires, confidence)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            sheet_id,
            panel_name,
            voltage,
            3,  # assume 3-phase
            4,  # assume 4-wire
            0.70  # lower confidence since we're inferring
        ))
        panel_ids[panel_name] = cursor.lastrowid
        count_panels += 1

    # Extract circuit info (basic pattern matching)
    # Circuits typically appear as numbered rows in a table
    # Pattern: circuit number, description, breaker size, etc.

    # Simple pattern: look for numbers that might be circuit numbers
    circuit_pattern = r'^\s*(\d+)\s+([A-Za-z0-9\s\-]+?)\s+(\d+)A'

    circuits = []
    for line in text.split('\n'):
        match = re.match(circuit_pattern, line)
        if match:
            circuits.append({
                "circuit_number": match.group(1),
                "description": match.group(2).strip(),
                "breaker_trip": int(match.group(3))
            })

    count_circuits = 0
    if panels_found and circuits:
        panel_id = panel_ids[panels_found[0]]
        for c in circuits:
            conn.execute("""
                INSERT INTO electrical_circuits
                (panel_id, sheet_id, circuit_number, circuit_description, breaker_trip, confidence)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                panel_id,
                sheet_id,
                c["circuit_number"],
                c["description"],
                c["breaker_trip"],
                0.65
            ))
            count_circuits += 1

    conn.commit()
    print(f"  - Panels: {count_panels}")
    print(f"  - Circuits: {count_circuits}")

    return {"panels": count_panels, "circuits": count_circuits}


def main():
    """Main extraction process."""

    db_path = Path("D:/qms/data/quality.db")
    conn = sqlite3.connect(str(db_path))

    drawings = [
        {
            "sheet_id": 508,
            "file_path": "D:/qms/data/projects/07609-Freshpet/Electrical/E6602-ELECTRICAL-SINGLE-LINE-DIAGRAM-Rev.1.pdf",
            "drawing_type": "single-line-diagram",
            "drawing_number": "E6602"
        },
        {
            "sheet_id": 509,
            "file_path": "D:/qms/data/projects/07609-Freshpet/Electrical/E6606-PANEL-SCHEDULES---SERVICE-6-Rev.1.pdf",
            "drawing_type": "panel-schedule",
            "drawing_number": "E6606"
        },
        {
            "sheet_id": 510,
            "file_path": "D:/qms/data/projects/07609-Freshpet/Electrical/E6607-PANEL-SCHEDULES---SERVICE-6-Rev.2.pdf",
            "drawing_type": "panel-schedule",
            "drawing_number": "E6607"
        }
    ]

    results = []

    for drawing in drawings:
        print(f"\n{'='*80}")
        print(f"Extracting: {drawing['drawing_number']} (Sheet ID: {drawing['sheet_id']})")
        print(f"Type: {drawing['drawing_type']}")
        print(f"{'='*80}")

        # Extract text
        file_path = Path(drawing["file_path"])
        if not file_path.exists():
            print(f"ERROR: File not found: {file_path}")
            continue

        text = extract_pdf_text(file_path)
        print(f"Extracted {len(text)} characters of text")

        # Extract based on type
        if drawing["drawing_type"] == "single-line-diagram":
            counts = extract_single_line_diagram(text, drawing["sheet_id"], conn)
        elif drawing["drawing_type"] == "panel-schedule":
            counts = extract_panel_schedule(text, drawing["sheet_id"], conn, drawing["drawing_number"])
        else:
            counts = {}

        # Update sheet
        conn.execute("""
            UPDATE sheets
            SET extracted_at = CURRENT_TIMESTAMP,
                extraction_model = 'pattern-matching',
                quality_score = 0.75
            WHERE id = ?
        """, (drawing["sheet_id"],))
        conn.commit()

        results.append({
            "drawing_number": drawing["drawing_number"],
            "counts": counts
        })

    # Summary
    print("\n" + "="*80)
    print("EXTRACTION COMPLETE")
    print("="*80)

    for r in results:
        print(f"\n{r['drawing_number']}:")
        for key, count in r['counts'].items():
            print(f"  - {key}: {count}")

    conn.close()


if __name__ == "__main__":
    main()
