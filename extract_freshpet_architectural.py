"""
Extract data from Freshpet architectural floor plan sheets.

Extracts equipment tags, room identifiers, and spatial references from
architectural floor plans.
"""

import json
import re
import sqlite3
from pathlib import Path
from typing import Dict, List, Any, Optional

# Try to import PDF processing library
try:
    import fitz  # PyMuPDF
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False

# Try to import Anthropic SDK
try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False


def extract_pdf_text(pdf_path: Path) -> str:
    """Extract text from PDF using PyMuPDF."""
    if not HAS_PYMUPDF:
        raise ImportError("PyMuPDF required. Install with: pip install PyMuPDF")

    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()
    return text


def call_claude(prompt: str, model: str = "sonnet") -> str:
    """Call Claude API for extraction."""
    if not HAS_ANTHROPIC:
        raise ImportError("anthropic SDK required. Install with: pip install anthropic")

    model_map = {
        "haiku": "claude-haiku-4-5-20251001",
        "sonnet": "claude-sonnet-4-5-20250929",
        "opus": "claude-opus-4-6",
    }
    model_id = model_map.get(model, model)

    client = anthropic.Anthropic()
    response = client.messages.create(
        model=model_id,
        max_tokens=8192,
        messages=[{"role": "user", "content": prompt}],
    )

    return response.content[0].text


def extract_floor_plan(pdf_text: str, sheet_id: int, drawing_number: str) -> Dict[str, Any]:
    """Extract data from architectural floor plan."""

    prompt = f"""Extract equipment and spatial data from this architectural floor plan drawing.

This is drawing {drawing_number} - an architectural floor plan showing equipment locations and spatial layout.

For each EQUIPMENT tag visible on the drawing (especially mechanical/refrigeration/plumbing equipment), provide:
- Tag number (e.g., P-101, V-201, RACK-1, etc.)
- Equipment type (pump, vessel, tank, refrigeration rack, air handler, etc.)
- Description (if available)
- Location description (room, area, or grid reference if noted)

For each distinct AREA or ROOM (if labeled), provide:
- Room number or area designation
- Room name/description
- Grid location bounds (if grid lines are visible, e.g., "A-C, 1-3")

For any DIMENSIONAL REFERENCES visible:
- Grid line identifiers (column lines like A, B, C or 1, 2, 3)
- Major dimensions if clearly labeled

Return as JSON with this structure:
{{
    "equipment": [
        {{"tag": "...", "equipment_type": "...", "description": "...", "location": "...", "confidence": 0.0-1.0}}
    ],
    "rooms": [
        {{"room_number": "...", "room_name": "...", "grid_location": "...", "confidence": 0.0-1.0}}
    ],
    "grid_lines": [
        {{"grid_id": "...", "grid_type": "column/row", "notes": "..."}}
    ],
    "notes": ["any critical architectural notes or legends visible"]
}}

Focus on extracting equipment tags that would appear in other discipline drawings (mechanical, plumbing, refrigeration).
Be conservative - only extract items you can clearly identify. Mark confidence lower if uncertain.

DRAWING TEXT:
{pdf_text[:12000]}  # First 12000 chars to stay within token limit
"""

    response_text = call_claude(prompt, model="sonnet")

    # Parse JSON response
    try:
        # Extract JSON from response (might be wrapped in markdown)
        json_match = re.search(r'```json\s*(\{.*\})\s*```', response_text, re.DOTALL)
        if json_match:
            response_text = json_match.group(1)

        data = json.loads(response_text)
        return data
    except json.JSONDecodeError as e:
        print(f"Failed to parse JSON response: {e}")
        print(f"Response: {response_text[:500]}")
        return {"equipment": [], "rooms": [], "grid_lines": [], "notes": []}


def save_to_database(sheet_id: int, extraction_data: Dict[str, Any], db_path: Path):
    """Save extracted data to database."""

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Save equipment tags
    equipment_inserted = 0
    for equip in extraction_data.get("equipment", []):
        cursor.execute("""
            INSERT INTO equipment (sheet_id, tag, description, equipment_type, confidence)
            VALUES (?, ?, ?, ?, ?)
        """, (
            sheet_id,
            equip.get("tag", "UNKNOWN"),
            equip.get("description"),
            equip.get("equipment_type"),
            equip.get("confidence", 0.7)
        ))
        equipment_inserted += 1

    # Save room/area information as notes
    rooms_inserted = 0
    for room in extraction_data.get("rooms", []):
        note_text = f"Room: {room.get('room_number', 'N/A')} - {room.get('room_name', 'N/A')}"
        if room.get("grid_location"):
            note_text += f" (Grid: {room['grid_location']})"

        cursor.execute("""
            INSERT INTO drawing_notes (sheet_id, note_type, note_text)
            VALUES (?, ?, ?)
        """, (
            sheet_id,
            "room_layout",
            note_text
        ))
        rooms_inserted += 1

    # Save grid lines as notes
    grid_lines_inserted = 0
    for grid in extraction_data.get("grid_lines", []):
        note_text = f"Grid Line {grid.get('grid_id')}: {grid.get('grid_type', 'unknown')}"
        if grid.get("notes"):
            note_text += f" - {grid['notes']}"

        cursor.execute("""
            INSERT INTO drawing_notes (sheet_id, note_type, note_text)
            VALUES (?, ?, ?)
        """, (
            sheet_id,
            "grid_reference",
            note_text
        ))
        grid_lines_inserted += 1

    # Save general notes
    notes_inserted = 0
    for note in extraction_data.get("notes", []):
        cursor.execute("""
            INSERT INTO drawing_notes (sheet_id, note_type, note_text)
            VALUES (?, ?, ?)
        """, (
            sheet_id,
            "architectural",
            note
        ))
        notes_inserted += 1

    # Update sheet status
    cursor.execute("""
        UPDATE sheets
        SET extracted_at = CURRENT_TIMESTAMP,
            extraction_model = ?,
            drawing_type = 'floor_plan'
        WHERE id = ?
    """, ("sonnet", sheet_id))

    conn.commit()
    conn.close()

    return {
        "equipment": equipment_inserted,
        "rooms": rooms_inserted,
        "grid_lines": grid_lines_inserted,
        "notes": notes_inserted
    }


def process_sheet(sheet_id: int, file_path: Path, db_path: Path, drawing_number: str) -> Dict[str, Any]:
    """Process a single architectural floor plan sheet."""

    print(f"\nProcessing sheet {sheet_id}: {file_path.name}")
    print("=" * 80)

    # Extract text from PDF
    print("Extracting PDF text...")
    pdf_text = extract_pdf_text(file_path)
    print(f"Extracted {len(pdf_text)} characters")

    # Extract floor plan data
    print("Extracting floor plan data with Sonnet...")
    extraction_data = extract_floor_plan(pdf_text, sheet_id, drawing_number)

    # Save to database
    print("Saving to database...")
    counts = save_to_database(sheet_id, extraction_data, db_path)

    result = {
        "status": "success",
        "drawing_type": "floor_plan",
        "model_used": "sonnet",
        **counts,
        "total_items": sum(counts.values())
    }

    print(f"OK Equipment: {counts['equipment']}")
    print(f"OK Rooms: {counts['rooms']}")
    print(f"OK Grid Lines: {counts['grid_lines']}")
    print(f"OK Notes: {counts['notes']}")

    return result


def main():
    """Main extraction script for Freshpet architectural sheets."""

    # Sheet definitions - using correct QMS data paths
    sheets = [
        {
            "id": 445,
            "path": Path(r"D:\qms\data\projects\07609-Freshpet\Architectural\A1141-PARTIAL-FIRST-FLOOR-PLAN---AREA-4-Rev.2.pdf"),
            "drawing_number": "A1141-PARTIAL-FIRST-FLOOR-PLAN---AREA-4"
        },
        {
            "id": 446,
            "path": Path(r"D:\qms\data\projects\07609-Freshpet\Architectural\A1161-PARTIAL-FIRST-FLOOR-PLAN---AREA-6-Rev.3.pdf"),
            "drawing_number": "A1161-PARTIAL-FIRST-FLOOR-PLAN---AREA-6"
        },
        {
            "id": 447,
            "path": Path(r"D:\qms\data\projects\07609-Freshpet\Architectural\A1201-OVERALL-SECOND-AND-INTERSTITIAL-SPACE-FLOOR-PLAN-Rev.1.pdf"),
            "drawing_number": "A1201-OVERALL-SECOND-AND-INTERSTITIAL-SPACE-FLOOR-PLAN"
        }
    ]

    db_path = Path(r"D:\qms\data\quality.db")

    print("Freshpet Architectural Drawing Extraction")
    print("=" * 80)
    print(f"Sheets to process: {len(sheets)}")
    print(f"Database: {db_path}")
    print()

    # Verify dependencies
    if not HAS_PYMUPDF:
        print("ERROR: PyMuPDF not installed. Install with: pip install PyMuPDF")
        return

    if not HAS_ANTHROPIC:
        print("ERROR: anthropic SDK not installed. Install with: pip install anthropic")
        return

    results = []
    for sheet in sheets:
        try:
            result = process_sheet(sheet["id"], sheet["path"], db_path, sheet["drawing_number"])
            results.append({
                "sheet_id": sheet["id"],
                "drawing_number": sheet["drawing_number"],
                **result
            })
        except Exception as e:
            print(f"ERROR processing sheet {sheet['id']}: {e}")
            import traceback
            traceback.print_exc()
            results.append({
                "sheet_id": sheet["id"],
                "drawing_number": sheet["drawing_number"],
                "status": "failed",
                "error": str(e)
            })

    # Summary
    print("\n" + "=" * 80)
    print("EXTRACTION SUMMARY")
    print("=" * 80)

    total_equipment = sum(r.get("equipment", 0) for r in results)
    total_rooms = sum(r.get("rooms", 0) for r in results)
    total_grid_lines = sum(r.get("grid_lines", 0) for r in results)
    total_notes = sum(r.get("notes", 0) for r in results)

    for result in results:
        status_icon = "OK" if result["status"] == "success" else "FAIL"
        print(f"{status_icon} {result['drawing_number'][:50]}: {result['status']}")
        if result["status"] == "success":
            print(f"   Equipment: {result.get('equipment', 0)}, "
                  f"Rooms: {result.get('rooms', 0)}, "
                  f"Grid Lines: {result.get('grid_lines', 0)}, "
                  f"Notes: {result.get('notes', 0)}")
        elif result["status"] == "failed":
            print(f"   Error: {result.get('error', 'Unknown')}")

    print(f"\nTotal Extracted:")
    print(f"  Equipment: {total_equipment}")
    print(f"  Rooms: {total_rooms}")
    print(f"  Grid Lines: {total_grid_lines}")
    print(f"  Notes: {total_notes}")
    print(f"  Total Items: {total_equipment + total_rooms + total_grid_lines + total_notes}")


if __name__ == "__main__":
    main()
