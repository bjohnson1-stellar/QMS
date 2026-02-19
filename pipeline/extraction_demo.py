"""
Demonstration of refrigeration drawing extraction process.

This script demonstrates the extraction workflow and expected output format
without requiring API access.
"""

from pathlib import Path
from qms.core import get_db, get_logger
from qms.pipeline.refrigeration_extractor import RefrigExtractionResult

logger = get_logger(__name__)


def create_mock_extraction_result(sheet_id: int, drawing_number: str) -> RefrigExtractionResult:
    """
    Create a mock extraction result demonstrating typical extraction output.

    This shows what would be extracted from a refrigeration plan drawing.
    """
    result = RefrigExtractionResult(
        sheet_id=sheet_id,
        drawing_number=drawing_number,
        status="success",
        confidence=0.87,
        extraction_model="sonnet",
        processing_time_ms=12500,
    )

    # Example refrigerant lines from a typical plan
    result.lines = [
        {
            "line_number": "LS-101",
            "size": "4\"",
            "service": "SUCTION",
            "material": "SCH 40 SMLS STL",
            "spec_class": "NH3-A",
            "refrigerant": "NH3",
            "from_location": "EVAP-101",
            "to_location": "COMP-1",
            "insulation": "2\" Armaflex",
            "slope": "1/4\" per ft minimum",
            "notes": None,
            "confidence": 0.95
        },
        {
            "line_number": "LD-102",
            "size": "2\"",
            "service": "LIQUID",
            "material": "SCH 80 SMLS STL",
            "spec_class": "NH3-A",
            "refrigerant": "NH3",
            "from_location": "REC-1",
            "to_location": "EVAP-101",
            "insulation": "1\" Armaflex",
            "slope": None,
            "notes": None,
            "confidence": 0.92
        },
        {
            "line_number": "LHG-103",
            "size": "1-1/2\"",
            "service": "HOT GAS",
            "material": "SCH 40 SMLS STL",
            "spec_class": "NH3-A",
            "refrigerant": "NH3",
            "from_location": "COMP-1",
            "to_location": "EVAP-101",
            "insulation": "1\" Armaflex",
            "slope": None,
            "notes": "Defrost line",
            "confidence": 0.88
        },
        {
            "line_number": "LS-104",
            "size": "6\"",
            "service": "SUCTION",
            "material": "SCH 40 SMLS STL",
            "spec_class": "NH3-A",
            "refrigerant": "NH3",
            "from_location": "EVAP-102",
            "to_location": "COMP-1",
            "insulation": "2\" Armaflex",
            "slope": "1/4\" per ft minimum",
            "notes": "Main suction header",
            "confidence": 0.93
        },
    ]

    # Example equipment
    result.equipment = [
        {
            "tag": "COMP-1",
            "equipment_type": "COMPRESSOR",
            "description": "Ammonia Screw Compressor Package",
            "location": "Grid B-4",
            "capacity": "200 TR",
            "notes": None,
            "confidence": 0.95
        },
        {
            "tag": "EVAP-101",
            "equipment_type": "EVAPORATOR",
            "description": "Low-Temp Air Unit Cooler",
            "location": "Freezer Room 1",
            "capacity": "50 TR",
            "notes": "Electric defrost",
            "confidence": 0.92
        },
        {
            "tag": "EVAP-102",
            "equipment_type": "EVAPORATOR",
            "description": "Low-Temp Air Unit Cooler",
            "location": "Freezer Room 2",
            "capacity": "75 TR",
            "notes": "Electric defrost",
            "confidence": 0.91
        },
        {
            "tag": "REC-1",
            "equipment_type": "RECEIVER",
            "description": "High Pressure Receiver",
            "location": "Grid A-2",
            "capacity": "500 gal",
            "notes": None,
            "confidence": 0.89
        },
    ]

    # Example instruments
    result.instruments = [
        {
            "tag": "PT-101",
            "instrument_type": "PRESSURE TRANSMITTER",
            "service": "Suction Pressure",
            "loop_number": "PIC-101",
            "location": "COMP-1 inlet",
            "set_point": "25 psig",
            "notes": None,
            "confidence": 0.90
        },
        {
            "tag": "TT-102",
            "instrument_type": "TEMPERATURE TRANSMITTER",
            "service": "Suction Temperature",
            "loop_number": "TIC-102",
            "location": "COMP-1 inlet",
            "set_point": "-20°F",
            "notes": None,
            "confidence": 0.88
        },
        {
            "tag": "PSV-101",
            "instrument_type": "PRESSURE SAFETY VALVE",
            "service": "Receiver Relief",
            "loop_number": None,
            "location": "REC-1",
            "set_point": "300 psig",
            "notes": "Size per ASME Section VIII",
            "confidence": 0.93
        },
        {
            "tag": "LT-103",
            "instrument_type": "LEVEL TRANSMITTER",
            "service": "Receiver Level",
            "loop_number": "LIC-103",
            "location": "REC-1",
            "set_point": "50%",
            "notes": None,
            "confidence": 0.87
        },
    ]

    # Extraction notes
    result.notes = [
        "Drawing shows overall refrigeration system layout for duct floor",
        "All piping is ammonia (NH3) service",
        "Insulation specifications noted on legend",
        "Some line numbers partially obscured - marked with lower confidence",
    ]

    return result


def demonstrate_extraction():
    """Demonstrate the extraction process with mock data."""
    print("\n" + "=" * 80)
    print("REFRIGERATION DRAWING EXTRACTION DEMONSTRATION")
    print("=" * 80)

    # Get sheet information from database
    with get_db(readonly=True) as conn:
        sheets = conn.execute(
            """SELECT id, drawing_number, revision, discipline
               FROM sheets
               WHERE id IN (595, 596, 597)
               ORDER BY id"""
        ).fetchall()

    print("\nTarget Sheets:")
    for sheet in sheets:
        print(f"  Sheet {sheet['id']}: {sheet['drawing_number']} Rev {sheet['revision']}")
        print(f"    Discipline: {sheet['discipline']}")

    print("\n" + "-" * 80)
    print("Mock Extraction Result (demonstrating expected output)")
    print("-" * 80)

    # Create mock result for first sheet
    result = create_mock_extraction_result(595, "R1310.1-REFRIGERATION-PLAN-DUCT-FLOOR-OVERALL")

    print(f"\nSheet: {result.drawing_number}")
    print(f"Status: {result.status}")
    print(f"Confidence: {result.confidence:.2f}")
    print(f"Model: {result.extraction_model}")
    print(f"Processing time: {result.processing_time_ms}ms\n")

    print(f"Lines Extracted: {len(result.lines)}")
    print("-" * 40)
    for line in result.lines:
        print(f"  {line['line_number']:12} {line['size']:6} {line['service']:12} "
              f"{line['refrigerant']:6} (confidence: {line['confidence']:.2f})")
        print(f"    From: {line['from_location']} → To: {line['to_location']}")
        print(f"    Material: {line['material']}")
        if line['notes']:
            print(f"    Notes: {line['notes']}")

    print(f"\nEquipment Extracted: {len(result.equipment)}")
    print("-" * 40)
    for equip in result.equipment:
        print(f"  {equip['tag']:12} {equip['equipment_type']:15} {equip.get('capacity', 'N/A'):10}")
        print(f"    Description: {equip['description']}")
        print(f"    Location: {equip.get('location', 'N/A')}")
        print(f"    Confidence: {equip['confidence']:.2f}")

    print(f"\nInstruments Extracted: {len(result.instruments)}")
    print("-" * 40)
    for inst in result.instruments:
        print(f"  {inst['tag']:12} {inst['instrument_type']:30}")
        print(f"    Service: {inst.get('service', 'N/A')}")
        print(f"    Location: {inst.get('location', 'N/A')}")
        if inst.get('set_point'):
            print(f"    Set point: {inst['set_point']}")
        print(f"    Confidence: {inst['confidence']:.2f}")

    print(f"\nExtraction Notes:")
    print("-" * 40)
    for note in result.notes:
        print(f"  - {note}")

    print("\n" + "=" * 80)
    print("EXTRACTION PROCESS OVERVIEW")
    print("=" * 80)

    print("""
The refrigeration extraction process follows these steps:

1. CLASSIFY DRAWING
   - Determine drawing type (Plan, Isometric, Detail, Schedule)
   - Estimate complexity based on content
   - Select appropriate AI model (Sonnet for most refrigeration plans)

2. READ WITH VISION MODEL
   - Convert PDF to base64
   - Send to Claude vision API with structured extraction prompt
   - Request JSON output with lines, equipment, and instruments

3. EXTRACT DATA BY TYPE

   REFRIGERANT LINES:
   - Line number/tag (LS-101, LD-202, LHG-301, etc.)
   - Size (pipe diameter in inches)
   - Service type (SUCTION, DISCHARGE, LIQUID, HOT GAS, DEFROST)
   - Material specification (SCH 40 SMLS STL, SCH 80, etc.)
   - Refrigerant type (NH3, R-507, R-404A, etc.)
   - From/To locations (equipment connections)
   - Insulation requirements
   - Slope requirements

   EQUIPMENT:
   - Tag number (COMP-1, EVAP-101, COND-201, REC-1, etc.)
   - Equipment type (COMPRESSOR, EVAPORATOR, CONDENSER, RECEIVER, etc.)
   - Description and capacity
   - Physical location or grid reference

   INSTRUMENTS:
   - Tag number (PT-101, TT-202, LT-301, PSV-401, etc.)
   - Instrument type (PRESSURE TRANSMITTER, TEMPERATURE TRANSMITTER, etc.)
   - Associated service or loop number
   - Location and set points

4. VALIDATE EXTRACTIONS
   - Check for required fields
   - Verify values are reasonable
   - Calculate confidence scores per item
   - Flag low-confidence items for review

5. STORE IN DATABASE
   - Insert into lines table (sheet_id, line_number, size, material, etc.)
   - Insert into equipment table (sheet_id, tag, type, description, etc.)
   - Insert into instruments table (sheet_id, tag, type, service, etc.)
   - Update sheet record with extraction timestamp and quality score

6. UPDATE PROCESSING QUEUE
   - Mark extraction task as completed
   - Calculate overall quality score
   - Flag items needing manual review
""")

    print("\n" + "=" * 80)
    print("DATABASE SCHEMA")
    print("=" * 80)

    with get_db(readonly=True) as conn:
        print("\nLINES Table:")
        schema = conn.execute("PRAGMA table_info(lines)").fetchall()
        for col in schema:
            print(f"  {col[1]:25} {col[2]:12} {'NOT NULL' if col[3] else 'NULL'}")

        print("\nEQUIPMENT Table:")
        schema = conn.execute("PRAGMA table_info(equipment)").fetchall()
        for col in schema:
            print(f"  {col[1]:25} {col[2]:12} {'NOT NULL' if col[3] else 'NULL'}")

        print("\nINSTRUMENTS Table:")
        schema = conn.execute("PRAGMA table_info(instruments)").fetchall()
        for col in schema:
            print(f"  {col[1]:25} {col[2]:12} {'NOT NULL' if col[3] else 'NULL'}")

    print("\n" + "=" * 80)
    print("REQUIREMENTS FOR PRODUCTION EXTRACTION")
    print("=" * 80)
    print("""
To run actual extraction (not demonstration):

1. Set ANTHROPIC_API_KEY environment variable:
   - Windows: setx ANTHROPIC_API_KEY "sk-ant-..."
   - Linux/Mac: export ANTHROPIC_API_KEY="sk-ant-..."

2. Install Anthropic SDK if not already installed:
   pip install anthropic>=0.25.0

3. Run extraction:
   python -c "from qms.pipeline.refrigeration_extractor import extract_batch; \\
              extract_batch([595, 596, 597], model='sonnet', dry_run=False)"

4. Or integrate into pipeline CLI:
   qms pipeline extract-refrigeration 595 596 597
""")


if __name__ == "__main__":
    demonstrate_extraction()
