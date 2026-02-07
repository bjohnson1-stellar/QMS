#!/usr/bin/env python3
import sqlite3
import os
import json
import hashlib
import re
from pathlib import Path
from datetime import datetime
import sys

def get_file_hash(filepath):
    """Calculate MD5 hash of file"""
    md5_hash = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            md5_hash.update(chunk)
    return md5_hash.hexdigest()

def parse_filename(filename):
    """
    Extract drawing number, title, and revision from filename.
    Examples:
    - R7002-REFRIGERATION-P&ID-Rev.E.pdf -> drawing_number=R7002, title=REFRIGERATION-P&ID, revision=E
    - P-101_B.pdf -> drawing_number=P-101, revision=B
    - M01-Rev-A.pdf -> drawing_number=M01, revision=A
    """
    base = filename.rsplit('.', 1)[0]  # Remove .pdf

    # Try to extract revision (Rev.X, Rev-X, _X where X is a letter)
    revision = None
    revision_match = re.search(r'(?:Rev\.?-?|_)([A-Z])(?:-SUPERSEDED)?$', base, re.IGNORECASE)
    if revision_match:
        revision = revision_match.group(1).upper()
        # Remove revision from base
        base = re.sub(r'(?:Rev\.?-?|_)[A-Z](?:-SUPERSEDED)?$', '', base, flags=re.IGNORECASE).rstrip('-_')

    # Check if superseded
    is_superseded = 'SUPERSEDED' in filename.upper()

    # Rest is drawing number and title
    drawing_number = base
    title = base

    return {
        'drawing_number': drawing_number,
        'title': title,
        'revision': revision or 'A',  # Default to A if not found
        'is_superseded': is_superseded
    }

def get_page_count(filepath):
    """Get page count from PDF"""
    try:
        import fitz
        doc = fitz.open(filepath)
        count = len(doc)
        doc.close()
        return count
    except Exception as e:
        print(f"Warning: Could not get page count for {filepath}: {e}", file=sys.stderr)
        return None

def scan_project(project_id, project_number, project_path):
    """Scan a single project and return results"""
    results = {
        'project_id': project_id,
        'project_number': project_number,
        'path': project_path,
        'disciplines': {},
        'files': [],
        'total_pdfs_on_disk': 0,
        'already_indexed': 0,
        'newly_indexed': 0,
        'missing_from_disk': 0,
        'supersession_chains': []
    }

    # Scan each discipline folder
    for item in sorted(os.listdir(project_path)):
        item_path = os.path.join(project_path, item)

        # Skip non-directories and special folders
        if not os.path.isdir(item_path):
            continue
        if item.startswith('_') or item.startswith('.') or item == 'MANIFEST.json':
            continue
        if item in ['Specs', 'Specifications']:
            continue

        discipline_name = item

        # Get all PDFs in this discipline
        pdfs = []
        try:
            for pdf_file in sorted(os.listdir(item_path)):
                if pdf_file.lower().endswith('.pdf'):
                    full_path = os.path.join(item_path, pdf_file)
                    if os.path.isfile(full_path):
                        pdfs.append({
                            'filename': pdf_file,
                            'full_path': full_path,
                            'rel_path': os.path.join(discipline_name, pdf_file)
                        })
        except PermissionError:
            continue

        # Parse each PDF
        discipline_files = []
        for pdf_info in pdfs:
            parsed = parse_filename(pdf_info['filename'])
            file_size = os.path.getsize(pdf_info['full_path'])
            file_hash = get_file_hash(pdf_info['full_path'])

            file_record = {
                'project_id': project_id,
                'discipline': discipline_name,
                'file_name': pdf_info['filename'],
                'file_path': pdf_info['rel_path'],
                'drawing_number': parsed['drawing_number'],
                'title': parsed['title'],
                'revision': parsed['revision'],
                'is_superseded': parsed['is_superseded'],
                'file_size': file_size,
                'file_hash': file_hash,
                'page_count': get_page_count(pdf_info['full_path']),
                'full_path': pdf_info['full_path']
            }

            discipline_files.append(file_record)
            results['files'].append(file_record)
            results['total_pdfs_on_disk'] += 1

        if discipline_files:
            results['disciplines'][discipline_name] = {
                'total': len(discipline_files),
                'files': discipline_files
            }

    return results

def compare_with_database(db_path, scan_results):
    """Compare scanned files with database records"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    project_id = scan_results['project_id']

    # Get all sheets in database for this project
    cursor.execute(
        "SELECT id, drawing_number, revision, file_path, file_hash, extracted_at FROM sheets WHERE project_id = ?",
        (project_id,)
    )
    db_sheets = {
        (row['drawing_number'], row['revision']): row for row in cursor.fetchall()
    }

    # Track which files are already indexed
    indexed_count = 0
    newly_indexed = []
    missing_from_disk = []

    # Check disk files against database
    for file_record in scan_results['files']:
        key = (file_record['drawing_number'], file_record['revision'])

        if key in db_sheets:
            db_record = db_sheets[key]
            # Check if hash matches (file hasn't changed)
            if db_record['file_hash'] == file_record['file_hash']:
                indexed_count += 1
                file_record['status'] = 'indexed'
            else:
                newly_indexed.append(file_record)
                file_record['status'] = 'modified'
                print(f"  File modified: {file_record['file_name']} (hash changed)", file=sys.stderr)
        else:
            newly_indexed.append(file_record)
            file_record['status'] = 'unindexed'

    # Check database files against disk
    disk_files_set = {(f['drawing_number'], f['revision']) for f in scan_results['files']}
    for (drawing_number, revision), db_record in db_sheets.items():
        if (drawing_number, revision) not in disk_files_set:
            missing_from_disk.append({
                'drawing_number': drawing_number,
                'revision': revision,
                'file_path': db_record['file_path'],
                'extracted_at': db_record['extracted_at']
            })

    scan_results['already_indexed'] = indexed_count
    scan_results['newly_indexed'] = len(newly_indexed)
    scan_results['missing_from_disk'] = len(missing_from_disk)
    scan_results['newly_indexed_files'] = newly_indexed
    scan_results['missing_files'] = missing_from_disk

    conn.close()

def insert_new_sheets(db_path, scan_results):
    """Insert newly found sheets into the database"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    project_id = scan_results['project_id']
    newly_indexed_files = scan_results.get('newly_indexed_files', [])

    # Get all sheets for this project to determine is_current status
    cursor.execute(
        "SELECT drawing_number, revision FROM sheets WHERE project_id = ? ORDER BY drawing_number, revision",
        (project_id,)
    )
    existing_sheets = {row[0]: [] for row in cursor.fetchall()}
    cursor.execute(
        "SELECT drawing_number, revision FROM sheets WHERE project_id = ? ORDER BY drawing_number, revision",
        (project_id,)
    )
    for drawing_number, revision in cursor.fetchall():
        if drawing_number not in existing_sheets:
            existing_sheets[drawing_number] = []
        existing_sheets[drawing_number].append(revision)

    inserted_count = 0
    for file_record in newly_indexed_files:
        drawing_number = file_record['drawing_number']
        revision = file_record['revision']

        # Determine if this is the current revision
        all_revisions = sorted(existing_sheets.get(drawing_number, []) + [revision])
        is_current = 1 if revision == all_revisions[-1] else 0

        try:
            cursor.execute("""
                INSERT OR IGNORE INTO sheets (
                    project_id, discipline, file_name, file_path,
                    drawing_number, title, revision, is_current,
                    file_hash, file_size, page_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                project_id,
                file_record['discipline'],
                file_record['file_name'],
                file_record['file_path'],
                drawing_number,
                file_record['title'],
                revision,
                is_current,
                file_record['file_hash'],
                file_record['file_size'],
                file_record['page_count']
            ))
            inserted_count += 1
        except sqlite3.IntegrityError as e:
            print(f"Warning: Could not insert {file_record['file_name']}: {e}", file=sys.stderr)

    conn.commit()
    conn.close()

    return inserted_count

def update_discipline_counts(db_path, scan_results):
    """Update discipline sheet counts and processed counts"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    project_id = scan_results['project_id']

    for discipline_name, discipline_data in scan_results['disciplines'].items():
        sheet_count = discipline_data['total']

        # Count how many sheets have extracted_at set
        cursor.execute(
            "SELECT COUNT(*) FROM sheets WHERE project_id = ? AND discipline = ? AND extracted_at IS NOT NULL",
            (project_id, discipline_name)
        )
        processed_count = cursor.fetchone()[0]

        # Update or insert discipline record
        cursor.execute("""
            INSERT OR REPLACE INTO disciplines (
                project_id, name, folder_path, normalized_name,
                sheet_count, processed_count
            ) VALUES (
                ?, ?, ?, ?, ?, ?
            )
        """, (
            project_id,
            discipline_name,
            os.path.join(scan_results['path'], discipline_name),
            discipline_name,
            sheet_count,
            processed_count
        ))

    conn.commit()
    conn.close()

def create_manifest(scan_results):
    """Create MANIFEST.json for the project"""
    project_path = scan_results['path']
    manifest_path = os.path.join(project_path, 'MANIFEST.json')

    # Calculate totals
    total_sheets = sum(d['total'] for d in scan_results['disciplines'].values())
    total_current = 0
    total_superseded = 0

    conn = sqlite3.connect('D:\\quality.db')
    cursor = conn.cursor()

    disciplines_manifest = {}
    for discipline_name, discipline_data in sorted(scan_results['disciplines'].items()):
        # Count current vs superseded
        cursor.execute(
            "SELECT COUNT(*) FROM sheets WHERE project_id = ? AND discipline = ? AND is_current = 1",
            (scan_results['project_id'], discipline_name)
        )
        current = cursor.fetchone()[0]

        cursor.execute(
            "SELECT COUNT(*) FROM sheets WHERE project_id = ? AND discipline = ? AND is_current = 0",
            (scan_results['project_id'], discipline_name)
        )
        superseded = cursor.fetchone()[0]

        cursor.execute(
            "SELECT COUNT(*) FROM sheets WHERE project_id = ? AND discipline = ? AND extracted_at IS NOT NULL",
            (scan_results['project_id'], discipline_name)
        )
        extracted = cursor.fetchone()[0]

        total_current += current
        total_superseded += superseded

        disciplines_manifest[discipline_name] = {
            'total': discipline_data['total'],
            'current': current,
            'superseded': superseded,
            'extracted': extracted
        }

    conn.close()

    manifest = {
        'project': scan_results['project_number'],
        'name': Path(scan_results['path']).name.split('-', 1)[1] if '-' in Path(scan_results['path']).name else 'Unknown',
        'scanned_at': datetime.utcnow().isoformat() + 'Z',
        'disciplines': disciplines_manifest,
        'total_sheets': total_sheets,
        'total_current': total_current,
        'total_superseded': total_superseded
    }

    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)

    return manifest_path

def main():
    db_path = 'D:\\quality.db'

    projects = [
        {'id': 3, 'number': '07308', 'path': 'D:\\Projects\\07308-BIRDCAGE'},
        {'id': 4, 'number': '07600', 'path': 'D:\\Projects\\07600-Rosina'}
    ]

    all_results = []

    for proj in projects:
        print(f"\nScanning {proj['number']}-{proj['path'].split('-', 1)[1]}...", file=sys.stderr)

        # Scan the project
        scan_result = scan_project(proj['id'], proj['number'], proj['path'])

        # Compare with database
        compare_with_database(db_path, scan_result)

        # Insert new sheets
        inserted = insert_new_sheets(db_path, scan_result)
        scan_result['inserted_count'] = inserted

        # Update discipline counts
        update_discipline_counts(db_path, scan_result)

        # Create MANIFEST.json
        manifest_path = create_manifest(scan_result)
        scan_result['manifest_path'] = manifest_path

        all_results.append(scan_result)

        # Print summary
        print(f"\n{proj['number']}-{proj['path'].split('-', 1)[1]}", file=sys.stderr)
        print(f"  Disciplines found: {len(scan_result['disciplines'])}", file=sys.stderr)
        print(f"  Total PDFs on disk: {scan_result['total_pdfs_on_disk']}", file=sys.stderr)
        print(f"  Already indexed: {scan_result['already_indexed']}", file=sys.stderr)
        print(f"  Newly indexed: {scan_result['newly_indexed']}", file=sys.stderr)
        if inserted > 0:
            print(f"  Inserted into DB: {inserted}", file=sys.stderr)
        if scan_result['missing_from_disk'] > 0:
            print(f"  Missing from disk: {scan_result['missing_from_disk']}", file=sys.stderr)
        print(f"  MANIFEST.json: {manifest_path}", file=sys.stderr)

    # Output JSON for further processing
    print(json.dumps(all_results, indent=2, default=str))

if __name__ == '__main__':
    main()
