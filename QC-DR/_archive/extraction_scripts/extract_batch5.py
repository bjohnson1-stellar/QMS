import sqlite3
from datetime import datetime

# Database connection
conn = sqlite3.connect('D:/quality.db')
cursor = conn.cursor()

# Sheet mapping
sheets = {
    167: 'RC60005',
    168: 'RC60006',
    169: 'RC60007',
    170: 'RC60008',
    171: 'RC60009'
}

# Extracted instruments from cable schedules
instruments = [
    # Sheet 167 (RC60005)
    # Temperature Transmitters
    (167, 'NH3-AHU1-105-2-TT01', 'TT', None, 0.85),
    (167, 'NH3-AHU1-105-3-TT01', 'TT', None, 0.85),
    (167, 'NH3-AHU2-101-2-TT01', 'TT', None, 0.85),
    (167, 'NH3-AHU1-105-1-TT01', 'TT', None, 0.85),
    (167, 'NH3-AHU1-101-4-TT01', 'TT', None, 0.85),
    (167, 'NH3-AHU1-103-1-TT01', 'TT', None, 0.85),
    (167, 'NH3-AHU1-101-1-TT01', 'TT', None, 0.85),
    (167, 'NH3-AHU1-101-2-TT01', 'TT', None, 0.85),
    (167, 'NH3-AHU1-101-3-TT01', 'TT', None, 0.85),
    (167, 'NH3-AHU1-104-1-TT01', 'TT', None, 0.85),
    (167, 'CU1-1-TT01', 'TT', None, 0.85),
    (167, 'CU1-1-SHTS-1', 'TT', None, 0.85),
    (167, 'CU1-2-TT01', 'TT', None, 0.85),
    (167, 'CU1-2-SHTS-1', 'TT', None, 0.85),
    # Pressure Transmitters
    (167, 'CU1-1-SHST-1', 'PT', None, 0.85),
    (167, 'CU1-2-SHST-1', 'PT', None, 0.85),
    # Humidity/Temp Sensors
    (167, 'RM7-101-TTRH', 'TTRH', None, 0.85),
    (167, 'RM7-102-TTRH', 'TTRH', None, 0.85),
    (167, 'NH3-RM1-101-RH01', 'RH', None, 0.85),
    (167, 'NH3-RM1-101-RH02', 'RH', None, 0.85),
    (167, 'NH3-RM1-101-RH03', 'RH', None, 0.85),

    # Sheet 168 (RC60006)
    # Flow Sensors
    (168, 'GLY-HEX1-FS01', 'FS', None, 0.85),
    # Pressure Transmitters
    (168, 'NH3-RMAU2-103-2-PT01', 'PT', None, 0.85),
    (168, 'NH3-RMAU2-103-2-PT02', 'PT', None, 0.85),
    (168, 'NH3-RMAU2-103-2-PT03', 'PT', None, 0.85),
    (168, 'NH3-HEX2-PT01', 'PT', None, 0.85),
    (168, 'NH3-HEX2-PT02', 'PT', None, 0.85),
    # Level Sensors
    (168, 'NH3-SD1-LS01', 'LS', None, 0.85),
    (168, 'NH3-SD1-LT01', 'LT', None, 0.85),

    # Sheet 169 (RC60007)
    # Ammonia Detectors (many)
    (169, 'RM2-101-AD01', 'AD', None, 0.85),
    (169, 'RM2-107-AD01', 'AD', None, 0.85),
    (169, 'RM2-108-AD01', 'AD', None, 0.85),
    (169, 'RM2-119-AD01', 'AD', None, 0.85),
    (169, 'RM3-107-AD01', 'AD', None, 0.85),
    (169, 'RM1-101-AD01', 'AD', None, 0.85),
    (169, 'RM1-101-AD02', 'AD', None, 0.85),
    (169, 'RM1-103-AD01', 'AD', None, 0.85),
    (169, 'RM10-204-1-AD01', 'AD', None, 0.85),
    (169, 'RM8-101-AD01', 'AD', None, 0.85),
    (169, 'RM8-101-AD02', 'AD', None, 0.85),
    (169, 'RM7-108-AD01', 'AD', None, 0.85),
    (169, 'RM7-109-AD01', 'AD', None, 0.85),
    (169, 'RM7-110-AD01', 'AD', None, 0.85),
    (169, 'RM7-111-AD01', 'AD', None, 0.85),
    (169, 'RM7-107-AD01', 'AD', None, 0.85),
    (169, 'RM7-102-AD01', 'AD', None, 0.85),
    (169, 'RM7-102-AD02', 'AD', None, 0.85),
    (169, 'RM7-101-AD01', 'AD', None, 0.85),
    (169, 'RM7-101-AD02', 'AD', None, 0.85),
    (169, 'RM1-104-AD01', 'AD', None, 0.85),
    (169, 'RM1-105-AD01', 'AD', None, 0.85),
    (169, 'RM1-106-AD01', 'AD', None, 0.85),
    (169, 'RM4-109I-AD01', 'AD', None, 0.85),
    (169, 'RM4-109I-AD02', 'AD', None, 0.85),
    (169, 'RM4-109-VL', 'AD', None, 0.85),
    (169, 'RM6-109-AD01', 'AD', None, 0.85),
    (169, 'RM6-109-AD02', 'AD', None, 0.85),
    (169, 'RM6-109-AD03', 'AD', None, 0.85),
    (169, 'RM4-113-AD02', 'AD', None, 0.85),
    (169, 'RM4-109A-AD01', 'AD', None, 0.85),
    (169, 'RM4-109B-AD01', 'AD', None, 0.85),
    (169, 'RM4-109C-AD01', 'AD', None, 0.85),
    (169, 'RM4-110-AD01', 'AD', None, 0.85),
    (169, 'RM4-111-AD01', 'AD', None, 0.85),
    (169, 'RM4-113-AD01', 'AD', None, 0.85),
    (169, 'RM3-106-AD01', 'AD', None, 0.85),
    (169, 'RM3-106-AD02', 'AD', None, 0.85),
    (169, 'RM3-106-AD03', 'AD', None, 0.85),
    (169, 'RM3-109-AD01', 'AD', None, 0.85),
    (169, 'RM2-102-AD01', 'AD', None, 0.85),
    # Thermostats
    (169, 'RM8-103A-H1', 'TT', None, 0.85),
    (169, 'RM8-103A-H2', 'TT', None, 0.85),

    # Sheet 170 (RC60008)
    # Control Valves
    (170, 'NH3-RMAU2-103-2-CV01', 'CV', None, 0.85),
    (170, 'NH3-RMAU2-103-2-CV02', 'CV', None, 0.85),
    (170, 'NH3-RMAU2-103-2-CV03', 'CV', None, 0.85),
    (170, 'NH3-RMAU2-103-2-CV05', 'CV', None, 0.85),
    (170, 'NH3-RMAU5-106-2-CV04', 'CV', None, 0.85),
    (170, 'NH3-RMAU3-101-2-CV04', 'CV', None, 0.85),
    (170, 'NH3-RMAU5-106-1-CV04', 'CV', None, 0.85),
    (170, 'NH3-RMAU3-101-1-CV04', 'CV', None, 0.85),
    (170, 'NH3-RMAU2-103-1-CV01', 'CV', None, 0.85),
    (170, 'NH3-RMAU2-103-1-CV02', 'CV', None, 0.85),
    (170, 'NH3-RMAU2-103-1-CV03', 'CV', None, 0.85),
    (170, 'NH3-RMAU2-103-1-CV05', 'CV', None, 0.85),
    # Pressure Transmitters
    (170, 'NH3-RMAU2-103-1-PT01', 'PT', None, 0.85),
    (170, 'NH3-RMAU2-103-1-PT02', 'PT', None, 0.85),
    (170, 'NH3-RMAU2-103-1-PT03', 'PT', None, 0.85),

    # Sheet 171 (RC60009)
    # Temperature Transmitters
    (171, 'RM8-103A-MR-TT01', 'TT', None, 0.85),
    (171, 'GLY-HEX1-TT01', 'TT', None, 0.85),
    (171, 'GLY-HEX1-TT02', 'TT', None, 0.85),
    (171, 'H2O-HEX2-TT01', 'TT', None, 0.85),
    (171, 'H2O-HEX2-TT02', 'TT', None, 0.85),
    (171, 'H2O-HEX2-TT03', 'TT', None, 0.85),
    (171, 'H2O-HEX2-TT04', 'TT', None, 0.85),
    (171, 'H2O-HEX2-TT05', 'TT', None, 0.85),
    # Pressure Transmitters
    (171, 'NH3-SD1-PT01', 'PT', None, 0.85),
    (171, 'GLY-HEX1-PT02', 'PT', None, 0.85),
    (171, 'GLY-HEX1-PT03', 'PT', None, 0.85),
    (171, 'GLY-HEX1-PT04', 'PT', None, 0.85),
    (171, 'H2O-HEX2-PT01', 'PT', None, 0.85),
    (171, 'H2O-HEX2-PT02', 'PT', None, 0.85),
    (171, 'H2O-HEX2-PT03', 'PT', None, 0.85),
    (171, 'H2O-HEX2-PT04', 'PT', None, 0.85),
    (171, 'H2O-HEX2-PT05', 'PT', None, 0.85),
    (171, 'H2O-RO-PT01', 'PT', None, 0.85),
    (171, 'H2O-RO-PT02', 'PT', None, 0.85),
    # Flow Meters
    (171, 'H2O-HEX2-FM01', 'FM', None, 0.85),
    (171, 'H2O-HEX2-FM02', 'FM', None, 0.85),
    (171, 'H2O-HEX2-FM03', 'FM', None, 0.85),
    (171, 'H2O-HEX2-FM04', 'FM', None, 0.85),
    (171, 'H2O-RO-FS01', 'FS', None, 0.85),
    # Level Switches
    (171, 'H2O-HEX2-LS01', 'LS', None, 0.85),
    (171, 'H2O-HEX2-LS02', 'LS', None, 0.85),
    (171, 'H2O-HEX2-LLC1', 'LS', None, 0.85),
    (171, 'H2O-HEX2-LLC2', 'LS', None, 0.85),
    # Ammonia Detectors
    (171, 'RM8-103A-MR-AD01', 'AD', None, 0.85),
    (171, 'RM8-103A-MR-AD02', 'AD', None, 0.85),
    (171, 'RM8-103A-MR-AD03', 'AD', None, 0.85),
    (171, 'RM8-103A-MR-AD04', 'AD', None, 0.85),
    (171, 'RM8-103C-MR-AD05', 'AD', None, 0.85),
]

# Insert instruments
insert_count = 0
for sheet_id, tag, inst_type, loop_num, confidence in instruments:
    try:
        cursor.execute('''
            INSERT INTO instruments (sheet_id, tag, instrument_type, loop_number, confidence)
            VALUES (?, ?, ?, ?, ?)
        ''', (sheet_id, tag, inst_type, loop_num, confidence))
        insert_count += 1
    except sqlite3.IntegrityError:
        print(f"Duplicate instrument: {tag} on sheet {sheet_id}")

# Update sheet metadata
for sheet_id, sheet_name in sheets.items():
    cursor.execute('''
        UPDATE sheets
        SET extracted_at = ?,
            quality_score = 0.85,
            complexity = 'medium'
        WHERE id = ?
    ''', (datetime.now().isoformat(), sheet_id))

conn.commit()

# Generate report
print("Extraction Complete - Final Batch (Project 07308)")
print("=" * 70)
print(f"\nTotal Instruments Inserted: {insert_count}")

for sheet_id, sheet_name in sheets.items():
    cursor.execute('SELECT COUNT(*) FROM instruments WHERE sheet_id = ?', (sheet_id,))
    count = cursor.fetchone()[0]
    print(f"\nSheet {sheet_id} ({sheet_name}):")
    print(f"  Total Instruments: {count}")

    # Count by type
    cursor.execute('''
        SELECT instrument_type, COUNT(*)
        FROM instruments
        WHERE sheet_id = ?
        GROUP BY instrument_type
    ''', (sheet_id,))

    print("  Breakdown by Type:")
    for inst_type, type_count in cursor.fetchall():
        print(f"    {inst_type}: {type_count}")

# Overall project summary
print("\n" + "=" * 70)
print("Project 07308 Summary (All Sheets):")
cursor.execute('''
    SELECT COUNT(*) FROM instruments
    WHERE sheet_id IN (167, 168, 169, 170, 171)
''')
total = cursor.fetchone()[0]
print(f"Total Instruments Extracted: {total}")

cursor.execute('''
    SELECT instrument_type, COUNT(*)
    FROM instruments
    WHERE sheet_id IN (167, 168, 169, 170, 171)
    GROUP BY instrument_type
    ORDER BY COUNT(*) DESC
''')
print("\nInstrument Type Distribution:")
for inst_type, count in cursor.fetchall():
    print(f"  {inst_type}: {count}")

conn.close()
print("\n" + "=" * 70)
print("Database updated successfully!")
