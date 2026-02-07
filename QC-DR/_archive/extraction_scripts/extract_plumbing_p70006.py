#!/usr/bin/env python3
"""
Extract plumbing data from P70006 Process Waste Riser Diagram
Sheet ID: 2109
"""

import sqlite3
from datetime import datetime

# Database connection
db_path = "D:/quality.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

sheet_id = 2109
model_used = "claude-sonnet-4.5"

# Drawing metadata
drawing_type = "riser"
complexity = "complex"

# Extracted pipe data - main risers and branches
pipes = [
    # Main 10" PW riser
    {"size": "10\"", "type": "PW", "service": "Process Waste", "from_location": "Area 7", "to_location": "Area 10", "confidence": 0.95},

    # 8" PW risers and branches
    {"size": "8\"", "type": "PW", "service": "Process Waste", "from_location": "HD-1", "to_location": "Main Riser", "confidence": 0.92},
    {"size": "8\"", "type": "SW", "service": "Sanitary Waste", "from_location": "FS-1", "to_location": "Connection", "confidence": 0.90},

    # 6" PW branches
    {"size": "6\"", "type": "PW", "service": "Process Waste", "from_location": "Multiple FD-1", "to_location": "8\" Riser", "confidence": 0.90},
    {"size": "6\"", "type": "PW", "service": "Process Waste", "from_location": "Branch", "to_location": "Main", "confidence": 0.88},

    # 4" PW connections (primary connection size)
    {"size": "4\"", "type": "PW", "service": "Process Waste", "from_location": "FD-1", "to_location": "6\" Branch", "confidence": 0.90},
    {"size": "4\"", "type": "PW", "service": "Process Waste", "from_location": "HD-1", "to_location": "Branch", "confidence": 0.88},
    {"size": "4\"", "type": "PW", "service": "Process Waste", "from_location": "FCO-1", "to_location": "Branch", "confidence": 0.88},
    {"size": "4\"", "type": "PV", "service": "Process Vent", "from_location": "Branch", "to_location": "V.T.R.", "confidence": 0.85},

    # 3" PW and PV branches
    {"size": "3\"", "type": "PW", "service": "Process Waste", "from_location": "CO", "to_location": "Branch", "confidence": 0.85},
    {"size": "3\"", "type": "PV", "service": "Process Vent", "from_location": "Branch", "to_location": "V.T.R.", "confidence": 0.82},

    # 2" PW connections
    {"size": "2\"", "type": "PW", "service": "Process Waste", "from_location": "Branch", "to_location": "Main", "confidence": 0.80},
]

# Fixture/drain data (counts by type visible on drawing)
fixtures = [
    {"fixture_type": "FD-1", "description": "Floor Drain Type 1", "waste_size": "4\"", "qty": 85, "notes": "Process waste floor drains throughout areas 7 and 10", "confidence": 0.92},
    {"fixture_type": "HD-1", "description": "Hub Drain Type 1", "waste_size": "4\"/8\"", "qty": 18, "notes": "Hub drains, various sizes", "confidence": 0.90},
    {"fixture_type": "FCO-1", "description": "Floor Cleanout Type 1", "waste_size": "4\"", "qty": 15, "notes": "Floor cleanouts for maintenance access", "confidence": 0.88},
    {"fixture_type": "FS-1", "description": "Floor Sink Type 1", "waste_size": "6\"", "qty": 1, "notes": "Connected to 8\" SW sanitary waste", "confidence": 0.95},
    {"fixture_type": "V.T.R.", "description": "Vent Through Roof", "vent_size": "Various", "qty": 12, "notes": "Vent terminations at roof level", "confidence": 0.90},
    {"fixture_type": "AAV", "description": "Air Admittance Valve (Studor Vent)", "vent_size": "N/A", "qty": 2, "notes": "Alternative venting devices", "confidence": 0.88},
]

# Cleanouts identified on drawing
cleanouts = [
    {"tag": "CO", "type": "Floor Cleanout", "location": "Various", "pipe_size": "3\"/4\"", "confidence": 0.85},
    {"tag": "FCO-1", "type": "Floor Cleanout Type 1", "location": "Various", "pipe_size": "4\"", "confidence": 0.88},
]

# Riser connections (major vertical or horizontal runs)
risers = [
    {"size": "10\"", "type": "PW", "from_location": "Lower Level", "to_location": "Continuation P7007", "fixture_tag": "Main Riser", "confidence": 0.95},
    {"size": "8\"", "type": "PW", "from_location": "HD-1 Collection", "to_location": "10\" Main", "fixture_tag": "HD Branch", "confidence": 0.90},
    {"size": "6\"", "type": "PW", "from_location": "FD-1 Collection", "to_location": "8\" Branch", "fixture_tag": "FD Branch", "confidence": 0.88},
]

# Insert pipe data
print(f"\nExtracting data from Sheet {sheet_id}: P70006 Rev.1")
print("=" * 80)
print(f"Drawing Type: Plumbing Riser Diagram")
print(f"System: Process Waste and Vent")
print(f"Complexity: {complexity}")
print(f"Model Used: {model_used}")
print()

pipe_count = 0
for pipe in pipes:
    cursor.execute("""
        INSERT INTO plumbing_pipes (sheet_id, pipe_size, pipe_type, service, from_location, to_location, confidence)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (sheet_id, pipe["size"], pipe["type"], pipe["service"], pipe["from_location"], pipe["to_location"], pipe["confidence"]))
    pipe_count += 1

print(f"Extracted Pipes/Branches: {pipe_count}")

# Insert fixture data
fixture_count = 0
total_fixture_qty = 0
for fixture in fixtures:
    cursor.execute("""
        INSERT INTO plumbing_fixtures (sheet_id, fixture_type, description, waste_size, vent_size, qty, notes, confidence)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (sheet_id, fixture["fixture_type"], fixture["description"],
          fixture.get("waste_size"), fixture.get("vent_size"),
          fixture["qty"], fixture.get("notes"), fixture["confidence"]))
    fixture_count += 1
    total_fixture_qty += fixture["qty"]

print(f"Extracted Fixture Types: {fixture_count} (Total Qty: {total_fixture_qty})")

# Insert cleanout data
cleanout_count = 0
for cleanout in cleanouts:
    cursor.execute("""
        INSERT INTO plumbing_cleanouts (sheet_id, cleanout_tag, cleanout_type, location, pipe_size, confidence)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (sheet_id, cleanout["tag"], cleanout["type"], cleanout["location"], cleanout["pipe_size"], cleanout["confidence"]))
    cleanout_count += 1

print(f"Extracted Cleanout Types: {cleanout_count}")

# Insert riser data
riser_count = 0
for riser in risers:
    cursor.execute("""
        INSERT INTO plumbing_risers (sheet_id, pipe_size, pipe_type, from_location, to_location, fixture_tag, confidence)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (sheet_id, riser["size"], riser["type"], riser["from_location"], riser["to_location"], riser["fixture_tag"], riser["confidence"]))
    riser_count += 1

print(f"Extracted Main Risers: {riser_count}")

# Calculate overall quality score
all_confidences = []
for item in pipes + fixtures + cleanouts + risers:
    all_confidences.append(item["confidence"])

quality_score = sum(all_confidences) / len(all_confidences) if all_confidences else 0.0

print()
print(f"Overall Quality Score: {quality_score:.2f}")

# Update sheet metadata
cursor.execute("""
    UPDATE sheets
    SET extracted_at = ?,
        extraction_model = ?,
        drawing_type = ?,
        complexity = ?,
        quality_score = ?
    WHERE id = ?
""", (datetime.now().isoformat(), model_used, drawing_type, complexity, quality_score, sheet_id))

# Update processing queue if it exists
cursor.execute("""
    UPDATE processing_queue
    SET status = 'completed',
        completed_at = ?
    WHERE sheet_id = ? AND task = 'EXTRACT'
""", (datetime.now().isoformat(), sheet_id))

# Commit changes
conn.commit()

print()
print("=" * 80)
print("EXTRACTION SUMMARY")
print("=" * 80)
print(f"Sheet ID: {sheet_id}")
print(f"Drawing: P70006 - PLUMBING PROCESS WASTE RISER DIAGRAM Rev.1")
print(f"Project: 07650-BRV-PerroGrande")
print()
print(f"Extracted Components:")
print(f"  - Pipe/Branch Segments: {pipe_count}")
print(f"  - Fixture Types: {fixture_count} ({total_fixture_qty} total fixtures)")
print(f"  - Cleanout Types: {cleanout_count}")
print(f"  - Main Risers: {riser_count}")
print()
print(f"Quality Score: {quality_score:.2f}")
print(f"Average Confidence: {quality_score:.2f}")
print()

# Show any issues/notes
print("NOTES:")
print("  - Drawing shows continuation to P7007 (reference noted)")
print("  - Primary system: Process Waste (PW) with separate Process Vent (PV)")
print("  - One connection to Sanitary Waste (SW) for floor sink FS-1")
print("  - Extensive network covering Areas 7 and 10")
print("  - FD-1 (Floor Drain) is the most common fixture type (85+ instances)")
print("  - Multiple vent terminations (V.T.R.) and 2 air admittance valves")
print("  - Pipe sizes range from 2\" to 10\"")
print("  - All data confidence levels are high (0.80-0.95)")
print()
print("STATUS: Extraction completed successfully")
print("Database updated: sheets.extracted_at = " + datetime.now().isoformat())

conn.close()
