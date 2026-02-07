#!/usr/bin/env python3
"""
Fix the database records where drawing_number contains the full filename including revision.
These are corrupted records that need to be cleaned up.
"""
import sqlite3
import re

def parse_drawing_number(filename):
    """Extract just the drawing number from a filename"""
    base = filename.rsplit('.', 1)[0]  # Remove .pdf

    # Remove revision suffix
    base = re.sub(r'(?:Rev\.?-?|_)[A-Z](?:-SUPERSEDED)?$', '', base, flags=re.IGNORECASE).rstrip('-_')

    return base

def main():
    db_path = 'D:\\quality.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Find all sheets where drawing_number contains -Rev (corrupted)
    cursor.execute("""
        SELECT id, file_name, drawing_number FROM sheets
        WHERE drawing_number LIKE '%-Rev%'
        ORDER BY project_id, discipline
    """)

    corrupted = cursor.fetchall()
    print(f"Found {len(corrupted)} corrupted records to fix")

    # Fix each one
    for sheet_id, file_name, old_drawing_num in corrupted:
        correct_drawing_num = parse_drawing_number(file_name)

        print(f"Fixing ID {sheet_id}: '{old_drawing_num}' -> '{correct_drawing_num}'")

        cursor.execute("""
            UPDATE sheets
            SET drawing_number = ?
            WHERE id = ?
        """, (correct_drawing_num, sheet_id))

    conn.commit()

    # Verify the fix
    cursor.execute("SELECT COUNT(*) FROM sheets WHERE drawing_number LIKE '%-Rev%'")
    remaining = cursor.fetchone()[0]
    print(f"\nAfter fix: {remaining} corrupted records remain")

    # Show final counts per project
    cursor.execute("""
        SELECT project_id, COUNT(DISTINCT drawing_number) as unique_drawings, COUNT(*) as total_sheets
        FROM sheets
        GROUP BY project_id
    """)

    print("\nFinal counts:")
    for project_id, unique, total in cursor.fetchall():
        print(f"  Project {project_id}: {unique} unique drawings, {total} total sheets")

    conn.close()

if __name__ == '__main__':
    main()
