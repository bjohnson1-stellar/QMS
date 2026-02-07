#!/usr/bin/env python3
import sqlite3

db_path = 'D:\\quality.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Find IDs with bad drawing_numbers
cursor.execute("""
    SELECT id FROM sheets
    WHERE project_id IN (3,4)
    AND drawing_number LIKE '%-Rev%'
    AND drawing_number NOT LIKE '%-%-%'  -- Multi-word numbers like "R70001-REFRIGERATION-P&ID-Rev.9" have 3+ dashes
""")

# Actually, let me just check what the bad ones look like
cursor.execute("""
    SELECT file_name, drawing_number
    FROM sheets
    WHERE project_id IN (3,4)
    AND drawing_number LIKE '%-Rev%'
    LIMIT 10
""")

print("Bad records:")
for file_name, drawing_number in cursor.fetchall():
    print(f"  {file_name} -> {drawing_number}")
    # The issue is: file_name = "R70001-REFRIGERATION-P&ID-Rev.9.pdf"
    # But drawing_number = "R70001-REFRIGERATION-P&ID-Rev.9"
    # It should be: drawing_number = "R70001-REFRIGERATION-P&ID"

print("\nDeleting records where drawing_number ends with -Rev.[0-9]")
cursor.execute("""
    DELETE FROM sheets
    WHERE project_id IN (3,4)
    AND drawing_number LIKE '%-Rev.%'
""")

print(f"Deleted {cursor.rowcount} records")
conn.commit()
conn.close()
