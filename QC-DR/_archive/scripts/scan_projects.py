#!/usr/bin/env python3
r"""
Scanner Agent - Indexes projects and creates MANIFEST.json files
Scans D:\Projects directory for project folders and PDFs
"""

import os
import sys
import json
import sqlite3
import hashlib
import re
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# Database configuration
DB_PATH = r"D:\quality.db"

# Standard disciplines to look for
STANDARD_DISCIPLINES = {
    'Mechanical', 'Structural', 'Electrical', 'Piping', 'Civil',
    'Architectural', 'Process', 'Instrumentation', 'HVAC',
    'Fire-Protection', 'Fire Protection', 'Plumbing', 'Refrigeration',
    'Refrigeration-Controls', 'Utilities', 'Utility', 'General',
    '600-00_Ref'  # Special reference folder found in Vital project
}

def parse_project_folder(folder_name):
    """Parse folder name to extract project number and name."""
    match = re.match(r'(\d{5})-(.+)', folder_name)
    if match:
        return match.group(1), match.group(2)
    return None, None

def extract_revision(filename):
    """Extract revision from filename."""
    # Look for patterns like -Rev.1, -Rev.A, _R0, _R1, Rev A, etc.
    patterns = [
        r'-Rev\.(\d+)\.pdf$',      # -Rev.1.pdf
        r'-Rev\.([A-Z])\.pdf$',    # -Rev.A.pdf
        r'_R(\d+)\.pdf$',          # _R0.pdf
        r'-([A-Z])\.pdf$',         # -A.pdf (at end)
        r'Rev\.(\d+)\.pdf$',       # Rev.1.pdf
        r'Rev\.([A-Z])\.pdf$',     # Rev.A.pdf
        r'Rev\s+([A-Z])\.pdf$',    # Rev A.pdf
    ]

    for pattern in patterns:
        match = re.search(pattern, filename)
        if match:
            return match.group(1)
    return "0"  # Default to revision 0

def extract_drawing_number(filename):
    """Extract drawing number from filename."""
    # Remove .pdf extension
    base = filename.replace('.pdf', '')

    # Get the first part before first dash
    parts = base.split('-')
    if parts:
        drawing_num = parts[0]
        # Remove revision info if present
        drawing_num = re.sub(r'_R\d+$', '', drawing_num)
        return drawing_num
    return base

def is_superseded(filename):
    """Check if file is marked as superseded."""
    return '-SUPERSEDED' in filename.upper()

def calculate_file_hash(filepath):
    """Calculate SHA256 hash of file."""
    try:
        sha256_hash = hashlib.sha256()
        with open(filepath, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    except Exception as e:
        print(f"  Warning: Could not hash {filepath}: {e}")
        return None

def discover_disciplines(project_path):
    """Discover all discipline folders in project."""
    disciplines = {}

    try:
        for item in os.listdir(project_path):
            item_path = os.path.join(project_path, item)
            if os.path.isdir(item_path):
                # Check if this is a standard discipline or has PDFs
                pdf_files = [f for f in os.listdir(item_path) if f.endswith('.pdf')]

                if item in STANDARD_DISCIPLINES or pdf_files:
                    disciplines[item] = {
                        'path': item_path,
                        'pdf_files': pdf_files
                    }
    except Exception as e:
        print(f"  Error discovering disciplines: {e}")

    return disciplines

def catalog_sheets(discipline_path, discipline_name):
    """Catalog all sheets in a discipline folder."""
    sheets = []
    superseded = []

    try:
        pdf_files = [f for f in os.listdir(discipline_path) if f.endswith('.pdf')]

        for pdf_file in pdf_files:
            file_path = os.path.join(discipline_path, pdf_file)

            drawing_num = extract_drawing_number(pdf_file)
            revision = extract_revision(pdf_file)
            is_super = is_superseded(pdf_file)
            file_hash = calculate_file_hash(file_path)

            sheet_info = {
                'file_name': pdf_file,
                'file_path': file_path,
                'drawing': drawing_num,
                'revision': revision,
                'is_superseded': is_super,
                'file_hash': file_hash
            }

            if is_super:
                superseded.append(sheet_info)
            else:
                sheets.append(sheet_info)

    except Exception as e:
        print(f"  Error cataloging sheets in {discipline_name}: {e}")

    return sheets, superseded

def insert_project(number, name, path):
    """Insert or update project in database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        cursor.execute('''
            INSERT OR REPLACE INTO projects (number, name, path, status)
            VALUES (?, ?, ?, 'active')
        ''', (number, name, path))

        conn.commit()

        # Get the project ID
        cursor.execute('SELECT id FROM projects WHERE number = ?', (number,))
        result = cursor.fetchone()
        if result:
            return result[0]
        return None
    except Exception as e:
        print(f"Error inserting project: {e}")
        return None
    finally:
        conn.close()

def insert_discipline(project_id, name, folder_path, prefix=None):
    """Insert or update discipline in database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        cursor.execute('''
            INSERT OR REPLACE INTO disciplines (project_id, name, folder_path, prefix, sheet_count)
            VALUES (?, ?, ?, ?, 0)
        ''', (project_id, name, folder_path, prefix))

        conn.commit()

        # Get the discipline ID
        cursor.execute('''
            SELECT id FROM disciplines WHERE project_id = ? AND name = ?
        ''', (project_id, name))
        result = cursor.fetchone()
        if result:
            return result[0]
        return None
    except Exception as e:
        print(f"Error inserting discipline: {e}")
        return None
    finally:
        conn.close()

def insert_sheets(project_id, discipline_id, sheets):
    """Insert sheets into database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        for sheet in sheets:
            cursor.execute('''
                INSERT OR REPLACE INTO sheets
                (project_id, discipline_id, file_path, file_name, drawing_number, revision, is_current, file_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                project_id, discipline_id, sheet['file_path'], sheet['file_name'],
                sheet['drawing'], sheet['revision'], 1 if not sheet['is_superseded'] else 0, sheet['file_hash']
            ))

        conn.commit()
        return len(sheets)
    except Exception as e:
        print(f"Error inserting sheets: {e}")
        return 0
    finally:
        conn.close()

def learn_patterns(project_id, disciplines_info):
    """Learn project-specific patterns."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Extract drawing prefixes
        prefixes = {}
        for disc_name, disc_data in disciplines_info.items():
            sheets = disc_data.get('sheets', [])
            if sheets:
                # Get the drawing prefix from first sheet
                drawing = sheets[0]['drawing']
                # Extract prefix (letters before numbers)
                match = re.match(r'([A-Z]+)', drawing)
                if match:
                    prefix = match.group(1)
                    prefixes[disc_name] = prefix

        # Insert patterns
        for discipline, prefix in prefixes.items():
            try:
                cursor.execute('''
                    INSERT INTO project_patterns (project_id, pattern_type, pattern, discipline)
                    VALUES (?, 'DRAWING_PREFIX', ?, ?)
                ''', (project_id, prefix, discipline))
            except sqlite3.IntegrityError:
                # Pattern already exists, skip
                pass

        conn.commit()
        if prefixes:
            print("    Learned {} drawing prefixes".format(len(prefixes)))
    except Exception as e:
        print("Error learning patterns: {}".format(e))
    finally:
        conn.close()

def create_manifest(project_number, project_name, project_path, disciplines_info):
    """Create MANIFEST.json file for project."""
    manifest = {
        "project_number": project_number,
        "project_name": project_name,
        "path": project_path,
        "scanned_at": datetime.now().isoformat() + "Z",
        "disciplines": {},
        "totals": {
            "disciplines": 0,
            "current_sheets": 0,
            "superseded_sheets": 0
        }
    }

    total_current = 0
    total_superseded = 0

    for disc_name, disc_data in sorted(disciplines_info.items()):
        sheets = disc_data.get('sheets', [])
        superseded = disc_data.get('superseded', [])

        manifest["disciplines"][disc_name] = {
            "folder": disc_name,
            "prefix": disc_data.get('prefix', ''),
            "sheet_count": len(sheets),
            "sheets": [
                {
                    "drawing": s['drawing'],
                    "revision": s['revision'],
                    "file": s['file_name']
                }
                for s in sorted(sheets, key=lambda x: x['drawing'])
            ],
            "superseded": [
                {
                    "drawing": s['drawing'],
                    "revision": s['revision'],
                    "file": s['file_name']
                }
                for s in sorted(superseded, key=lambda x: x['drawing'])
            ] if superseded else []
        }

        total_current += len(sheets)
        total_superseded += len(superseded)

    manifest["totals"]["disciplines"] = len(disciplines_info)
    manifest["totals"]["current_sheets"] = total_current
    manifest["totals"]["superseded_sheets"] = total_superseded

    # Write manifest file
    manifest_path = os.path.join(project_path, "MANIFEST.json")
    try:
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f, indent=2)
        print("    MANIFEST.json created")
        return manifest
    except Exception as e:
        print("    Error creating MANIFEST.json: {}".format(e))
        return None

def scan_project(project_path, project_number, project_name):
    """Scan a single project."""
    print("\n{}-{}".format(project_number, project_name))
    print("  Path: {}".format(project_path))

    # Discover disciplines
    disciplines_raw = discover_disciplines(project_path)
    print("  Disciplines: {}".format(len(disciplines_raw)))

    if not disciplines_raw:
        print("    No disciplines found")
        return

    # Insert project into database
    project_id = insert_project(project_number, project_name, project_path)
    if not project_id:
        print("    ERROR: Could not insert project")
        return

    # Process each discipline
    disciplines_info = {}
    total_sheets = 0
    total_superseded = 0

    for disc_name in sorted(disciplines_raw.keys()):
        disc_data = disciplines_raw[disc_name]
        disc_path = disc_data['path']

        # Catalog sheets
        sheets, superseded = catalog_sheets(disc_path, disc_name)

        # Insert discipline into database
        discipline_id = insert_discipline(project_id, disc_name, disc_path)
        if discipline_id:
            sheets_inserted = insert_sheets(project_id, discipline_id, sheets + superseded)

        # Extract prefix from drawing numbers
        prefix = ''
        if sheets:
            match = re.match(r'([A-Z]+)', sheets[0]['drawing'])
            if match:
                prefix = match.group(1)

        disciplines_info[disc_name] = {
            'sheets': sheets,
            'superseded': superseded,
            'prefix': prefix
        }

        sheet_count = len(sheets)
        superseded_count = len(superseded)
        total_sheets += sheet_count
        total_superseded += superseded_count

        status_str = "{} sheets".format(sheet_count)
        if superseded_count > 0:
            status_str += " ({} superseded)".format(superseded_count)
        print("  [{}] {}: {}".format(total_sheets + total_superseded, disc_name, status_str))

    # Learn patterns
    learn_patterns(project_id, disciplines_info)

    # Create MANIFEST
    manifest = create_manifest(project_number, project_name, project_path, disciplines_info)

    # Summary
    print("  Total: {} current sheets, {} superseded".format(total_sheets, total_superseded))

def main():
    """Main scanning function."""
    projects_dir = r"D:\Projects"

    print("="*70)
    print("Scanner Agent - Project Indexing")
    print("="*70)

    if not os.path.exists(projects_dir):
        print("Error: Projects directory not found: {}".format(projects_dir))
        return

    # Scan all project folders
    projects_found = 0
    project_folders = []

    try:
        for item in sorted(os.listdir(projects_dir)):
            item_path = os.path.join(projects_dir, item)
            if os.path.isdir(item_path):
                number, name = parse_project_folder(item)
                if number and name:
                    project_folders.append((item_path, number, name))
                    projects_found += 1
    except Exception as e:
        print("Error scanning projects directory: {}".format(e))
        return

    print("\nProjects Found: {}".format(projects_found))

    # Process each project
    for project_path, project_number, project_name in project_folders:
        scan_project(project_path, project_number, project_name)

    # Final summary
    print("\n" + "="*70)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('SELECT COUNT(*) FROM projects')
    project_count = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM disciplines')
    discipline_count = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM sheets WHERE is_current = 1')
    sheet_count = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM sheets WHERE is_current = 0')
    superseded_count = cursor.fetchone()[0]

    conn.close()

    print("Database Updated:")
    print("  {} projects".format(project_count))
    print("  {} disciplines".format(discipline_count))
    print("  {} current sheets".format(sheet_count))
    print("  {} superseded sheets".format(superseded_count))
    print("="*70)

if __name__ == "__main__":
    main()
