#!/usr/bin/env python3
"""
Extract refrigeration drawing data and insert into database.
Handles sheets 58, 59, 60 for project 07308-BIRDCAGE.
"""

import sqlite3
import sys
from datetime import datetime

DB_PATH = "D:/quality.db"

def extract_sheet_58(conn):
    """Extract safety sign details from R50401"""
    cursor = conn.cursor()

    details = [
        (58, '1', 'REFRIGERATION MACHINERY ROOM-AUTHORIZED PERSONNEL ONLY', 'NTS',
         'Safety sign for machinery room entrance',
         '24" x 11"',
         'COLOR: BLACK TEXT, YELLOW BACKGROUND. LOCATION: ALL ENTRANCES TO MACHINE ROOM. SIGNS SHALL HAVE ADHESIVE BACKING AND SHALL NOT BE SUPPORTED WITH SELF TAPPING SCREWS.',
         0.95),

        (58, '2', 'WARNING-WHEN ALARMS ARE ACTIVATED, AMMONIA HAS BEEN DETECTED', 'NTS',
         'Warning sign for ammonia detection',
         '24" x 12"',
         'COLOR: BLACK TEXT, ORANGE BACKGROUND. LOCATION: ALL ENTRANCES TO MACHINE ROOM. Leave room immediately when alarms are activated. Do not enter except by trained & authorized personnel. Do not enter without personal protective equipment.',
         0.95),

        (58, '3', 'PRINCIPAL MACHINERY ROOM ENTRANCE', 'NTS',
         'Principal entrance door signage layout',
         '73" height, multiple signs',
         'Signs to be located on principal machine room door. Multiple safety signs arranged vertically at specified heights (34", 62", 73", 33", 43", 57" from finished floor)',
         0.90),

        (58, '4', 'CUSTOMER EMERGENCY CONTACT SIGN WITH INVENTORY', 'NTS',
         'Emergency contact information and refrigerant inventory',
         '24" x 12"',
         'COLOR: BLACK TEXT, WHITE BACKGROUND. Contains emergency telephone numbers (911, National Response Center 1-800-424-8802, EPA), refrigerant inventory summary for anhydrous ammonia (R717), test pressure data, emergency procedures.',
         0.92),

        (58, '5', 'NFPA 704-AMMONIA DIAMOND WITH EXPLANATIONS', 'NTS',
         'NFPA hazard diamond for anhydrous ammonia',
         '24" x 12"',
         'Anhydrous Ammonia CAS# 7664-41-7. Health Hazard: 3, Fire Hazard: 1, Reactivity: 0. UN# 1005. Includes first aid procedures, personal protection requirements (respirator, safety goggles, gloves, boots, protective clothing), spill/leak practices. Rating 3-3-0 for indoor equipment, 3-1-0 for outdoor equipment.',
         0.95),

        (58, '6', 'SECONDARY MACHINERY ROOM ENTRANCE', 'NTS',
         'Secondary entrance door signage layout',
         '73" height, multiple signs',
         'Similar to Detail 3 but for secondary entrance. Multiple safety signs arranged vertically.',
         0.90),

        (58, '7', 'CAUTION-AMMONIA R-717', 'NTS',
         'Caution sign identifying refrigerant type',
         '12" x 7"',
         'COLOR: BLACK TEXT, YELLOW BACKGROUND. LOCATION: ALL ENTRANCES TO MACHINE ROOM. SIGNS SHALL HAVE ADHESIVE BACKING.',
         0.95),

        (58, '8', 'CAUTION-EYE AND EAR PROTECTION MUST BE WORN IN THIS AREA', 'NTS',
         'PPE requirement sign',
         '12" x 7"',
         'COLOR: BLACK TEXT, YELLOW BACKGROUND. LOCATION: ALL ENTRANCES TO MACHINE ROOM.',
         0.95),

        (58, '9', 'REFRIGERATION MACHINERY SHUTDOWN, EMERGENCY USE ONLY', 'NTS',
         'Emergency shutdown button sign',
         '9" x 5"',
         'COLOR: BLACK TEXT, ORANGE BACKGROUND. LOCATION: DESIGNATED PRINCIPAL EXTERIOR MACHINERY ROOM DOOR. Emergency stop button shuts down all refrigeration compressors and liquid pumps.',
         0.95),

        (58, '10', 'REFRIGERATION MACHINERY ROOM-VENTILATION, EMERGENCY USE ONLY', 'NTS',
         'Emergency ventilation button sign',
         '9" x 5"',
         'COLOR: BLACK TEXT, ORANGE BACKGROUND. LOCATION: DESIGNATED PRINCIPAL EXTERIOR MACHINERY ROOM DOOR. Ventilation is activated based on refrigeration leak levels by ammonia detectors.',
         0.95),
    ]

    cursor.executemany('''
        INSERT OR REPLACE INTO detail_drawings
        (sheet_id, detail_number, detail_title, detail_scale, description, dimensions, notes, confidence)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', details)

    return len(details)


def extract_sheet_59(conn):
    """Extract relief piping details from R50500"""
    cursor = conn.cursor()

    details = [
        (59, '1', 'RELIEF HEADER TO ATMOSPHERE (NON-CO2)', 'NTS',
         'Relief header termination details for atmospheric discharge',
         'Header size 2" max, 24" min to 60" max height',
         'Minimum 15\'-0" above grade. Minimum 20\'-0" from windows, ventilation intakes and exits. Minimum 7.25\' above roofs, platforms or catwalks. Terminate to avoid spraying refrigerant on personnel. Includes drain valve, bird screen, weep holes, guy wire anchors, and sensor mounting.',
         0.92),

        (59, '2', 'RELIEF HEADER SENSOR DETAIL', 'NTS',
         'Sensor installation in relief header',
         'Union, tee facing downward with threaded plug, 2" thread-o-let',
         'Install sensor per manufacturer recommendations. Hansen sensors max 24" from discharge. Calibration Technologies Inc. sensors located outdoors 3-5\' above roof. Includes nipple, bushing (size depends on sensor manufacturer), and threaded plug for fresh air access.',
         0.90),

        (59, '3', 'RELIEF VALVE INLET PIPING DETAIL', 'NTS',
         'Proper relief valve inlet piping configuration',
         'Various pipe sizes, vessel connection must be same or larger than relief valve',
         'Minimize length of inlet piping. Engineer to be notified if inlet piping exceeds 6" or has any more fittings. Vessel connection must be same or larger than relief valve or 3-way inlet. Shows acceptable and not acceptable configurations. Area of opening through pipe, fittings and relief devices shall be no less than area of relief valve inlet.',
         0.93),

        (59, '5', 'GUY WIRE ANCHOR DETAIL', 'NTS',
         'Guy wire anchoring for roof-mounted relief headers',
         '3/8" stainless steel cable, 2" galvanized pipe, 30° to 60° angle',
         'Three variations shown for beam structure, joist structure, and metal deck. Includes 1/2" galvanized plate, min 1/2" galv. U-bar, 3/16" welds. Fill leg to 12" height with spray foam. For galvanized supports apply cold-galvanized paint to field welds and marred surfaces.',
         0.88),

        (59, '7', 'HYDROSTATIC THERMOSYPHON RELIEF VENT', 'NTS',
         'Hydrostatic relief valve installation for thermosyphon systems',
         '3/4" Schedule 80 pipe, 3/4" angle valve',
         'Relief valve typically installed in TSS piping. Can be installed in TSR at engineer\'s discretion. Relief valve shall be installed on oil cooler side of isolation valve. Includes angle valve (locked open), isolation valve, union, pipe cap, and branch connection per specifications.',
         0.90),
    ]

    # General notes for relief piping
    notes_text = '''GENERAL NOTES:
1. Isolation valves not permitted on inlet side of relief valves.
2. Equipment connection must be equal to or larger than valve inlet.
3. Combustible material may not be stored within 20 feet of relief valve protected equipment.
4. Three way valves shall be installed with adequate access for removal.
5. Relief valves shall be installed with adequate access for removal.
6. All relief valve terminations: Min 15\'-0" above grade, Min 7\'-3" above roofs/platforms/catwalks, Min 20\'-0" from windows/intakes/exits.
7. Relief system designed for exact valves and piping as listed in schedule with no allowance for excess. Engineer to be notified if relief valves don\'t meet exact manufacturer, model, and pressure setting, or if piping lengths/fittings exceed scheduled segments.
8. Contractor to complete all information in asbuilt piping schedule and return to engineer.
9. Flanges for SRV removal not shown on P&IDs and to be installed per details.'''

    cursor.executemany('''
        INSERT OR REPLACE INTO detail_drawings
        (sheet_id, detail_number, detail_title, detail_scale, description, dimensions, notes, confidence)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', details)

    # Store general notes as a separate record
    cursor.execute('''
        INSERT OR REPLACE INTO detail_drawings
        (sheet_id, detail_number, detail_title, detail_scale, description, dimensions, notes, confidence)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (59, 'GN', 'GENERAL NOTES - RELIEF PIPING', 'N/A',
          'General requirements and restrictions for relief valve and piping installation',
          'N/A', notes_text, 0.95))

    return len(details) + 1


def extract_sheet_60(conn):
    """Extract vessel details from R50600"""
    cursor = conn.cursor()

    details = [
        (60, '1', 'THERMOSYPHON VESSEL', 'NTS',
         'Thermosyphon receiver vessel with multiple views',
         'See vessel schedule on drawing',
         'Shows top view, bottom view, side view, and end view of thermosyphon receiver. Includes nozzle schedule with connection sizes and locations. Multiple connection points shown with circular detail markers.',
         0.88),
    ]

    cursor.executemany('''
        INSERT OR REPLACE INTO detail_drawings
        (sheet_id, detail_number, detail_title, detail_scale, description, dimensions, notes, confidence)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', details)

    return len(details)


def update_sheet_metadata(conn, sheet_id, quality_score, complexity, item_count):
    """Update sheet extraction metadata"""
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE sheets
        SET extracted_at = ?,
            quality_score = ?,
            complexity = ?
        WHERE id = ?
    ''', (datetime.now().isoformat(), quality_score, complexity, sheet_id))


def main():
    print("Extraction: Refrigeration Details - Project 07308-BIRDCAGE")
    print("=" * 70)

    try:
        conn = sqlite3.connect(DB_PATH, timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL")

        # Sheet 58: Safety Details
        print("\nSheet 58: R50401 - REFRIGERATION DETAILS SAFETY")
        print("-" * 70)
        print("Drawing Type: Safety signage and hazard communication")
        print("Complexity: low")

        count_58 = extract_sheet_58(conn)
        update_sheet_metadata(conn, 58, 0.93, 'low', count_58)

        print(f"Extracted: {count_58} safety sign details (avg confidence: 0.93)")
        print("Quality Score: 0.93")

        # Sheet 59: Relief Piping
        print("\nSheet 59: R50500 - REFRIGERATION DETAILS RELIEF PIPE")
        print("-" * 70)
        print("Drawing Type: Relief piping installation details")
        print("Complexity: medium")

        count_59 = extract_sheet_59(conn)
        update_sheet_metadata(conn, 59, 0.91, 'medium', count_59)

        print(f"Extracted: {count_59} relief piping details (avg confidence: 0.91)")
        print("Quality Score: 0.91")

        # Sheet 60: Vessel Details
        print("\nSheet 60: R50600 - REFRIGERATION VESSEL DETAILS")
        print("-" * 70)
        print("Drawing Type: Vessel fabrication details")
        print("Complexity: medium")

        count_60 = extract_sheet_60(conn)
        update_sheet_metadata(conn, 60, 0.88, 'medium', count_60)

        print(f"Extracted: {count_60} vessel detail(s) (avg confidence: 0.88)")
        print("Quality Score: 0.88")

        # Commit all changes
        conn.commit()

        print("\n" + "=" * 70)
        print(f"Total Details Extracted: {count_58 + count_59 + count_60}")
        print("All extractions completed successfully.")

        # Summary by category
        print("\nExtraction Summary by Drawing:")
        print(f"  Safety Signs (Sheet 58):    {count_58} details")
        print(f"  Relief Piping (Sheet 59):   {count_59} details")
        print(f"  Vessel Details (Sheet 60):  {count_60} detail(s)")

        conn.close()
        return 0

    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
