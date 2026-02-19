"""
Direct electrical drawing extraction using pattern matching.
Extracts equipment, circuits, and panels from Freshpet electrical drawings.
"""
import sqlite3
import re
from pathlib import Path
import fitz  # PyMuPDF
from datetime import datetime

DATABASE = r"D:\qms\data\quality.db"

SHEETS = [
    {
        "id": 523,
        "path": r"D:\qms\data\projects\07609-Freshpet\Electrical\EP1401-OVERALL-ROOF-POWER-PLAN-Rev.1.pdf",
        "drawing_number": "EP1401",
        "title": "OVERALL ROOF POWER PLAN"
    },
    {
        "id": 524,
        "path": r"D:\qms\data\projects\07609-Freshpet\Electrical\EP1402-LIGHTNING-PROTECTION-SYSTEM-PLAN-Rev.1.pdf",
        "drawing_number": "EP1402",
        "title": "LIGHTNING PROTECTION SYSTEM PLAN"
    },
    {
        "id": 525,
        "path": r"D:\qms\data\projects\07609-Freshpet\Electrical\EP4001-ELECTRICAL-ENLARGED-PLANS-Rev.1.pdf",
        "drawing_number": "EP4001",
        "title": "ELECTRICAL ENLARGED PLANS"
    }
]

# Equipment type mapping based on tag prefix
EQUIPMENT_TYPES = {
    "SA-AHU": "Air Handling Unit",
    "SA-DCU": "Dedicated Cooling Unit",
    "EF-FAN": "Exhaust Fan",
    "CU-EC": "Evaporative Cooler",
    "CU-HVU": "HVAC Unit",
    "CU-RFH": "Roof Heater",
    "CU-PUMP": "Pump",
    "CU-HSC": "Heat Pump/Chiller",
    "CU-BLR": "Boiler",
    "CU-MTR": "Motor",
    "SUH": "Space Unit Heater"
}

def extract_pdf_text(pdf_path: str) -> str:
    """Extract all text from PDF."""
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text()
    return text

def parse_wire_spec(wire_text: str) -> dict:
    """Parse wire specification like '1-#8, 1-#8, 1-#8G,3/4\"C'."""
    result = {
        "wire_count": 0,
        "wire_size": None,
        "conduit_size": None,
        "notes": wire_text
    }

    # Count wires
    wire_count = wire_text.count("-#")
    if wire_count > 0:
        result["wire_count"] = wire_count

    # Extract wire size (first occurrence)
    wire_match = re.search(r'#(\d+)', wire_text)
    if wire_match:
        result["wire_size"] = f"#{wire_match.group(1)}"

    # Extract conduit size
    conduit_match = re.search(r'(\d+/?\d*)"C', wire_text)
    if conduit_match:
        result["conduit_size"] = f"{conduit_match.group(1)}\""

    return result

def extract_equipment(text: str) -> list:
    """Extract equipment tags from text."""
    equipment = []
    seen = set()

    # Pattern: PREFIX-TYPE-NUMBER
    pattern = r'([A-Z]{2,3}-[A-Z]{2,4}-\d{3,4}[A-Z]?)'
    for match in re.finditer(pattern, text):
        tag = match.group(1)
        if tag in seen:
            continue
        seen.add(tag)

        # Determine equipment type
        prefix = tag.split('-')[0:2]
        prefix_key = '-'.join(prefix)
        equipment_type = EQUIPMENT_TYPES.get(prefix_key, "Electrical Equipment")

        equipment.append({
            "tag": tag,
            "equipment_type": equipment_type,
            "location": None,
            "voltage": None,
            "amperage": None,
            "notes": None
        })

    return sorted(equipment, key=lambda x: x["tag"])

def extract_circuits(text: str) -> list:
    """Extract circuit references from text."""
    circuits = []
    seen = set()

    # Pattern: P#-XXX-XXX/## optionally followed by wire spec
    pattern = r'(P\d+-[A-Z0-9]+-[A-Z0-9]+)/(\d+)\s*([^\n]*?)(?=P\d+-|$|\n)'
    lines = text.split('\n')

    for i, line in enumerate(lines):
        # Find circuit references
        circ_pattern = r'(P\d+-[A-Z0-9]+-[A-Z0-9]+/\d+)'
        matches = re.findall(circ_pattern, line)

        for circ_ref in matches:
            if circ_ref in seen:
                continue
            seen.add(circ_ref)

            # Split panel and circuit
            if '/' in circ_ref:
                panel_name, circuit_num = circ_ref.rsplit('/', 1)
            else:
                continue

            # Look for wire spec on same or next line
            wire_spec = None
            wire_info = {}

            # Check current line and next few lines for wire specs
            context = '\n'.join(lines[i:min(i+3, len(lines))])
            wire_match = re.search(r'(\d+-#\d+[^,\n]*(?:,\s*\d+-#\d+[^,\n]*)*)', context)
            if wire_match:
                wire_spec = wire_match.group(1).strip()
                wire_info = parse_wire_spec(wire_spec)

            circuits.append({
                "panel_name": panel_name,
                "circuit_number": circuit_num,
                "equipment_tag": None,  # Would need proximity analysis
                "location": None,
                "wire_size": wire_info.get("wire_size"),
                "conduit_size": wire_info.get("conduit_size"),
                "notes": wire_spec
            })

    return sorted(circuits, key=lambda x: (x["panel_name"], int(x["circuit_number"])))

def extract_panels(circuits: list) -> list:
    """Extract unique panels from circuit references."""
    panels = {}

    for circuit in circuits:
        panel_name = circuit["panel_name"]
        if panel_name not in panels:
            # Parse panel name for voltage hints
            voltage = None
            if "5M" in panel_name or "6M" in panel_name:
                voltage = "480V"
            elif "5L" in panel_name or "6L" in panel_name:
                voltage = "277V"

            panels[panel_name] = {
                "panel_name": panel_name,
                "location": None,
                "voltage": voltage,
                "phases": 3 if voltage else None,
                "bus_rating": None,
                "fed_from": None,
                "notes": None
            }

    return sorted(panels.values(), key=lambda x: x["panel_name"])

def insert_equipment(conn, sheet_id: int, items: list) -> int:
    """Insert equipment records."""
    count = 0
    for item in items:
        try:
            conn.execute("""
                INSERT INTO electrical_equipment
                (sheet_id, tag, equipment_type, location, area, voltage, amperage, notes, confidence)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                sheet_id,
                item["tag"],
                item["equipment_type"],
                item["location"],
                None,  # area
                item["voltage"],
                item["amperage"],
                item["notes"],
                0.75  # Pattern matching confidence
            ))
            count += 1
        except sqlite3.IntegrityError as e:
            # Duplicate tag on same sheet
            print(f"    Skipping duplicate equipment: {item['tag']}")

    return count

def insert_panels(conn, sheet_id: int, items: list) -> dict:
    """Insert panel records and return panel_id map."""
    count = 0
    panel_ids = {}

    for item in items:
        cursor = conn.execute("""
            INSERT INTO electrical_panels
            (sheet_id, panel_name, location, voltage, phases, bus_rating, fed_from, panel_notes, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            sheet_id,
            item["panel_name"],
            item["location"],
            item["voltage"],
            item["phases"],
            item["bus_rating"],
            item["fed_from"],
            item["notes"],
            0.75
        ))
        panel_ids[item["panel_name"]] = cursor.lastrowid
        count += 1

    return panel_ids, count

def insert_circuits(conn, sheet_id: int, items: list, panel_ids: dict) -> int:
    """Insert circuit records."""
    count = 0

    for item in items:
        panel_name = item["panel_name"]
        panel_id = panel_ids.get(panel_name)

        if not panel_id:
            print(f"    WARNING: Panel {panel_name} not found for circuit {item['circuit_number']}")
            continue

        conn.execute("""
            INSERT INTO electrical_circuits
            (panel_id, sheet_id, circuit_number, equipment_tag, location,
             wire_size, conduit_size, notes, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            panel_id,
            sheet_id,
            item["circuit_number"],
            item["equipment_tag"],
            item["location"],
            item["wire_size"],
            item["conduit_size"],
            item["notes"],
            0.75
        ))
        count += 1

    return count

def process_sheet(sheet_info: dict):
    """Process a single sheet."""
    print(f"\n{'=' * 80}")
    print(f"Sheet {sheet_info['id']}: {sheet_info['drawing_number']} - {sheet_info['title']}")
    print(f"{'=' * 80}")

    # Extract text
    print("  [1/5] Extracting text from PDF...")
    text = extract_pdf_text(sheet_info['path'])
    print(f"        {len(text)} characters extracted")

    # Parse equipment
    print("  [2/5] Parsing equipment tags...")
    equipment = extract_equipment(text)
    print(f"        Found {len(equipment)} unique equipment tags")

    # Parse circuits
    print("  [3/5] Parsing circuit references...")
    circuits = extract_circuits(text)
    print(f"        Found {len(circuits)} circuit references")

    # Parse panels
    print("  [4/5] Deriving panel information...")
    panels = extract_panels(circuits)
    print(f"        Found {len(panels)} unique panels")

    # Insert into database
    print("  [5/5] Inserting into database...")
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row

    try:
        # Insert equipment
        eq_count = insert_equipment(conn, sheet_info['id'], equipment)
        print(f"        Inserted {eq_count} equipment records")

        # Insert panels
        panel_ids, panel_count = insert_panels(conn, sheet_info['id'], panels)
        print(f"        Inserted {panel_count} panel records")

        # Insert circuits
        circuit_count = insert_circuits(conn, sheet_info['id'], circuits, panel_ids)
        print(f"        Inserted {circuit_count} circuit records")

        # Update sheet metadata
        conn.execute("""
            UPDATE sheets
            SET extracted_at = ?,
                extraction_model = 'pattern-matching',
                quality_score = 0.75,
                complexity = 'medium'
            WHERE id = ?
        """, (datetime.utcnow().isoformat(), sheet_info['id']))

        conn.commit()
        print(f"        OK Database commit successful")

    except Exception as e:
        conn.rollback()
        print(f"        ERROR ERROR: {e}")
        raise
    finally:
        conn.close()

    print(f"\n  Summary:")
    print(f"    Equipment: {eq_count}")
    print(f"    Panels: {panel_count}")
    print(f"    Circuits: {circuit_count}")
    print(f"    Status: COMPLETE")

def main():
    print("=" * 80)
    print("ELECTRICAL DRAWING EXTRACTION - Pattern Matching")
    print("=" * 80)
    print(f"Project: 07609-Freshpet")
    print(f"Sheets: {len(SHEETS)}")
    print(f"Database: {DATABASE}")
    print(f"Method: Regex pattern matching")
    print(f"Confidence: 0.75 (automated extraction)")

    total_equipment = 0
    total_panels = 0
    total_circuits = 0

    for i, sheet in enumerate(SHEETS, 1):
        print(f"\n\n[{i}/{len(SHEETS)}]")
        try:
            # Get counts before
            conn = sqlite3.connect(DATABASE)
            before_eq = conn.execute("SELECT COUNT(*) FROM electrical_equipment WHERE sheet_id = ?",
                                     (sheet['id'],)).fetchone()[0]
            before_panel = conn.execute("SELECT COUNT(*) FROM electrical_panels WHERE sheet_id = ?",
                                        (sheet['id'],)).fetchone()[0]
            before_circuit = conn.execute("SELECT COUNT(*) FROM electrical_circuits WHERE sheet_id = ?",
                                          (sheet['id'],)).fetchone()[0]
            conn.close()

            # Process
            process_sheet(sheet)

            # Get counts after
            conn = sqlite3.connect(DATABASE)
            after_eq = conn.execute("SELECT COUNT(*) FROM electrical_equipment WHERE sheet_id = ?",
                                    (sheet['id'],)).fetchone()[0]
            after_panel = conn.execute("SELECT COUNT(*) FROM electrical_panels WHERE sheet_id = ?",
                                       (sheet['id'],)).fetchone()[0]
            after_circuit = conn.execute("SELECT COUNT(*) FROM electrical_circuits WHERE sheet_id = ?",
                                         (sheet['id'],)).fetchone()[0]
            conn.close()

            new_eq = after_eq - before_eq
            new_panel = after_panel - before_panel
            new_circuit = after_circuit - before_circuit

            total_equipment += new_eq
            total_panels += new_panel
            total_circuits += new_circuit

        except Exception as e:
            print(f"\n  ERROR FAILED: {e}")
            import traceback
            traceback.print_exc()

    print("\n\n" + "=" * 80)
    print("EXTRACTION COMPLETE")
    print("=" * 80)
    print(f"Total Equipment Records: {total_equipment}")
    print(f"Total Panel Records: {total_panels}")
    print(f"Total Circuit Records: {total_circuits}")
    print(f"Grand Total: {total_equipment + total_panels + total_circuits} records")
    print("=" * 80)

if __name__ == "__main__":
    main()
