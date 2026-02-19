#!/usr/bin/env python3
"""
Extract electrical data from Freshpet drawings using Sonnet model.
Following the extraction agent process from .planning/extraction-agent.md
"""

import json
import sqlite3
import sys
from pathlib import Path

# Check for anthropic SDK
try:
    import anthropic
except ImportError:
    print("ERROR: anthropic SDK required. Install with: pip install anthropic")
    sys.exit(1)

# Try to import PyPDF2 for text extraction
try:
    import PyPDF2
except ImportError:
    print("ERROR: PyPDF2 required. Install with: pip install PyPDF2")
    sys.exit(1)


def extract_pdf_text(pdf_path: Path) -> str:
    """Extract text from PDF file."""
    text_parts = []
    with open(pdf_path, 'rb') as f:
        pdf_reader = PyPDF2.PdfReader(f)
        for page_num, page in enumerate(pdf_reader.pages, 1):
            text = page.extract_text()
            text_parts.append(f"--- Page {page_num} ---\n{text}\n")
    return "\n".join(text_parts)


def call_sonnet(prompt: str) -> str:
    """Call Claude Sonnet for extraction."""
    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=8192,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text


def build_extraction_prompt(drawing_type: str, drawing_number: str, raw_text: str) -> str:
    """Build extraction prompt based on drawing type."""

    if drawing_type == "single-line-diagram":
        return f"""Extract all electrical data from this SINGLE LINE DIAGRAM drawing.

Drawing: {drawing_number}

For each TRANSFORMER, provide:
- Tag number
- kVA rating
- Primary voltage
- Secondary voltage
- Phases
- Wires
- Frequency

For each SWITCHGEAR/BREAKER item, provide:
- Tag number
- Equipment type (e.g., "Main Breaker", "Distribution Panel", "MCC")
- Voltage
- Current rating (amps)
- Frame size
- Trip rating
- Short circuit rating (if shown)

For each MOTOR or LOAD, provide:
- Tag number
- HP rating (if applicable)
- Voltage

Return as JSON with this structure:
{{
  "transformers": [
    {{"tag": "...", "kva_rating": 123, "primary_voltage": "...", "secondary_voltage": "...", "phases": 3, "wires": 4, "frequency": 60}}
  ],
  "switchgear": [
    {{"tag": "...", "equipment_type": "...", "voltage": "...", "current_rating": 123, "frame_size": 456, "trip_rating": 789}}
  ],
  "motors": [
    {{"tag": "...", "hp_rating": 10, "voltage": "480V"}}
  ],
  "abbreviations": [
    {{"abbreviation": "MCC", "definition": "Motor Control Center"}}
  ]
}}

PDF Text:
{raw_text[:20000]}
"""

    elif drawing_type == "panel-schedule":
        return f"""Extract all electrical panel schedule data from this drawing.

Drawing: {drawing_number}

For each PANEL, provide:
- Panel name
- Location
- Voltage
- Phases
- Wires
- Bus rating
- Fed from (source panel/transformer)
- Enclosure type
- AIC rating
- Total connected current
- Total demand current

For each CIRCUIT in the panel schedules, provide:
- Circuit number (e.g., "1", "3", "5-7")
- Description
- Equipment tag (if serving specific equipment)
- Location
- Number of poles (1, 2, or 3)
- Breaker frame size
- Breaker trip size
- Wire size
- Conduit size
- Load (kVA or amps)
- Notes

Return as JSON with this structure:
{{
  "panels": [
    {{
      "panel_name": "...",
      "location": "...",
      "voltage": "...",
      "phases": 3,
      "wires": 4,
      "bus_rating": "...",
      "fed_from": "...",
      "enclosure_type": "...",
      "aic_rating": "...",
      "total_connected_current": 123.45,
      "total_demand_current": 100.00
    }}
  ],
  "circuits": [
    {{
      "panel_name": "...",
      "circuit_number": "1",
      "circuit_description": "...",
      "equipment_tag": "...",
      "location": "...",
      "num_poles": 1,
      "breaker_frame": 20,
      "breaker_trip": 20,
      "wire_size": "#12",
      "conduit_size": "3/4\"",
      "load_amps": 12.5,
      "notes": "..."
    }}
  ]
}}

PDF Text:
{raw_text[:20000]}
"""

    return ""


def extract_drawing(sheet_id: int, file_path: str, drawing_type: str, drawing_number: str, conn: sqlite3.Connection) -> dict:
    """Extract data from a single drawing."""
    print(f"\n{'='*80}")
    print(f"Extracting: {drawing_number} (Sheet ID: {sheet_id})")
    print(f"Type: {drawing_type}")
    print(f"{'='*80}")

    # Step 1: Extract text from PDF
    print("Step 1: Extracting text from PDF...")
    pdf_path = Path(file_path)
    if not pdf_path.exists():
        print(f"ERROR: File not found: {file_path}")
        return {"status": "error", "message": "File not found"}

    raw_text = extract_pdf_text(pdf_path)
    print(f"Extracted {len(raw_text)} characters of text")

    # Step 2: Build prompt
    print("\nStep 2: Building extraction prompt...")
    prompt = build_extraction_prompt(drawing_type, drawing_number, raw_text)

    # Step 3: Call Sonnet for extraction
    print("Step 3: Running extraction with Sonnet...")
    response = call_sonnet(prompt)

    # Parse JSON response
    try:
        # Try to extract JSON from response
        if "```json" in response:
            json_start = response.find("```json") + 7
            json_end = response.find("```", json_start)
            json_str = response[json_start:json_end].strip()
        elif "```" in response:
            json_start = response.find("```") + 3
            json_end = response.find("```", json_start)
            json_str = response[json_start:json_end].strip()
        else:
            json_str = response.strip()

        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        print(f"ERROR parsing JSON: {e}")
        print(f"Response: {response[:500]}")
        return {"status": "error", "message": f"JSON parse error: {e}"}

    # Step 4: Store in database
    print("\nStep 4: Storing extracted data in database...")

    counts = {}

    # Insert transformers
    if "transformers" in data:
        for t in data["transformers"]:
            conn.execute("""
                INSERT INTO electrical_transformers
                (sheet_id, tag, kva_rating, primary_voltage, secondary_voltage,
                 phases, wires, frequency, confidence)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                sheet_id,
                t.get("tag"),
                t.get("kva_rating"),
                t.get("primary_voltage"),
                t.get("secondary_voltage"),
                t.get("phases"),
                t.get("wires"),
                t.get("frequency"),
                0.85
            ))
        counts["transformers"] = len(data["transformers"])

    # Insert switchgear
    if "switchgear" in data:
        for s in data["switchgear"]:
            conn.execute("""
                INSERT INTO electrical_switchgear
                (sheet_id, tag, equipment_type, voltage, current_rating,
                 frame_size, trip_rating, short_circuit_rating, confidence)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                sheet_id,
                s.get("tag"),
                s.get("equipment_type"),
                s.get("voltage"),
                s.get("current_rating"),
                s.get("frame_size"),
                s.get("trip_rating"),
                s.get("short_circuit_rating"),
                0.85
            ))
        counts["switchgear"] = len(data["switchgear"])

    # Insert motors
    if "motors" in data:
        for m in data["motors"]:
            conn.execute("""
                INSERT INTO electrical_motors
                (sheet_id, tag, hp_rating, voltage, confidence)
                VALUES (?, ?, ?, ?, ?)
            """, (
                sheet_id,
                m.get("tag"),
                m.get("hp_rating"),
                m.get("voltage"),
                0.85
            ))
        counts["motors"] = len(data["motors"])

    # Insert panels
    if "panels" in data:
        panel_ids = {}
        for p in data["panels"]:
            cursor = conn.execute("""
                INSERT INTO electrical_panels
                (sheet_id, panel_name, location, voltage, phases, wires,
                 bus_rating, fed_from, enclosure_type, aic_rating,
                 total_connected_current, total_demand_current, confidence)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                sheet_id,
                p.get("panel_name"),
                p.get("location"),
                p.get("voltage"),
                p.get("phases"),
                p.get("wires"),
                p.get("bus_rating"),
                p.get("fed_from"),
                p.get("enclosure_type"),
                p.get("aic_rating"),
                p.get("total_connected_current"),
                p.get("total_demand_current"),
                0.85
            ))
            panel_ids[p.get("panel_name")] = cursor.lastrowid
        counts["panels"] = len(data["panels"])

        # Insert circuits
        if "circuits" in data:
            for c in data["circuits"]:
                panel_id = panel_ids.get(c.get("panel_name"))
                conn.execute("""
                    INSERT INTO electrical_circuits
                    (panel_id, sheet_id, circuit_number, circuit_description,
                     equipment_tag, location, num_poles, breaker_frame, breaker_trip,
                     wire_size, conduit_size, load_amps, notes, confidence)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    panel_id,
                    sheet_id,
                    c.get("circuit_number"),
                    c.get("circuit_description"),
                    c.get("equipment_tag"),
                    c.get("location"),
                    c.get("num_poles"),
                    c.get("breaker_frame"),
                    c.get("breaker_trip"),
                    c.get("wire_size"),
                    c.get("conduit_size"),
                    c.get("load_amps"),
                    c.get("notes"),
                    0.85
                ))
            counts["circuits"] = len(data["circuits"])

    # Insert abbreviations
    if "abbreviations" in data:
        for a in data["abbreviations"]:
            conn.execute("""
                INSERT INTO electrical_abbreviations
                (sheet_id, abbreviation, definition, confidence)
                VALUES (?, ?, ?, ?)
            """, (
                sheet_id,
                a.get("abbreviation"),
                a.get("definition"),
                0.90
            ))
        counts["abbreviations"] = len(data["abbreviations"])

    # Update sheet status
    conn.execute("""
        UPDATE sheets
        SET extracted_at = CURRENT_TIMESTAMP,
            extraction_model = 'sonnet',
            quality_score = ?
        WHERE id = ?
    """, (0.85, sheet_id))

    conn.commit()

    # Print summary
    print("\nExtracted:")
    for key, count in counts.items():
        print(f"  - {key}: {count}")

    return {"status": "success", "counts": counts, "data": data}


def main():
    """Main extraction process."""

    # Connect to database
    db_path = Path("D:/qms/data/quality.db")
    if not db_path.exists():
        print(f"ERROR: Database not found: {db_path}")
        sys.exit(1)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    # Define the drawings to extract
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
        result = extract_drawing(
            drawing["sheet_id"],
            drawing["file_path"],
            drawing["drawing_type"],
            drawing["drawing_number"],
            conn
        )
        results.append({
            "drawing_number": drawing["drawing_number"],
            "result": result
        })

    # Final summary
    print("\n" + "="*80)
    print("EXTRACTION COMPLETE")
    print("="*80)

    for r in results:
        print(f"\n{r['drawing_number']}: {r['result']['status']}")
        if r['result']['status'] == 'success':
            counts = r['result'].get('counts', {})
            for key, count in counts.items():
                print(f"  - {key}: {count}")

    conn.close()


if __name__ == "__main__":
    main()
