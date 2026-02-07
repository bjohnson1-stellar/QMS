#!/usr/bin/env python3
"""
Reference Standard Content Extractor

Extracts text content from purchased reference standard PDFs and loads
into the quality.db database for full-text searching and cross-linking.

Usage:
    python extract_reference.py ISO9001-2015.pdf --standard-id ISO-9001-2015
    python extract_reference.py "D:/Quality Documents/References/ASME-B31.3-2022.pdf" --standard-id ASME-B31.3-2022
"""

import argparse
import hashlib
import os
import re
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Import shared utilities
from sis_common import get_db_path, get_logger, SIS_PATHS

DB_PATH = str(get_db_path())
logger = get_logger('extract_reference')

# Clause patterns for different standards
CLAUSE_PATTERNS = {
    'ISO': r'^(\d+(?:\.\d+)*)\s+(.+?)(?:\n|$)',           # 4.1 Understanding the organization
    'ASME': r'^((?:BPV|B31|QW|QG)[\s-]?\d+(?:\.\d+)*)\s*(.+?)(?:\n|$)',  # QW-200 General
    'AWS': r'^(\d+(?:\.\d+)*)\s+(.+?)(?:\n|$)',           # 5.3.1 Base Metal
    'NFPA': r'^(\d+(?:\.\d+)*)\s+(.+?)(?:\n|$)',          # 110.3 Application
    'API': r'^(\d+(?:\.\d+)*)\s+(.+?)(?:\n|$)',           # 5.1 General
    'DEFAULT': r'^(\d+(?:\.\d+)*)\s+(.+?)(?:\n|$)'
}

# Block type detection patterns
BLOCK_PATTERNS = [
    (r'^NOTE\s*\d*[:\s]', 'Note'),
    (r'^WARNING[:\s]', 'Warning'),
    (r'^CAUTION[:\s]', 'Caution'),
    (r'^EXCEPTION[:\s]', 'Note'),
    (r'^\([a-z]\)\s', 'NumberedList'),
    (r'^[a-z]\)\s', 'NumberedList'),
    (r'^\d+\)\s', 'NumberedList'),
    (r'^[\u2022\u2023\u25E6\u2043\u2219•·]\s', 'BulletList'),
    (r'^-\s+(?=[A-Z])', 'BulletList'),
    (r'^Table\s+\d+', 'Table'),
    (r'^Figure\s+\d+', 'Figure'),
    (r'^EXAMPLE[:\s]', 'Example'),
]


def extract_text_with_pdftotext(pdf_path: str) -> str:
    """Extract text from PDF using pdftotext."""
    try:
        result = subprocess.run(
            ['pdftotext', '-layout', pdf_path, '-'],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error extracting PDF: {e.stderr}")
        sys.exit(1)
    except FileNotFoundError:
        print("pdftotext not found. Install poppler-utils or use alternative method.")
        sys.exit(1)


def detect_publisher(standard_id: str) -> str:
    """Detect publisher from standard ID."""
    prefixes = ['ISO', 'ASME', 'AWS', 'NFPA', 'API', 'OSHA', 'ASTM', 'ANSI', 'IEC', 'IEEE', 'NEC', 'UL']
    for prefix in prefixes:
        if standard_id.upper().startswith(prefix):
            return prefix
    return 'DEFAULT'


def detect_block_type(text: str) -> str:
    """Detect the type of content block."""
    for pattern, block_type in BLOCK_PATTERNS:
        if re.match(pattern, text, re.IGNORECASE):
            return block_type
    return 'Paragraph'


def parse_clauses(text: str, publisher: str) -> list:
    """Parse text into clauses and content blocks."""
    pattern = CLAUSE_PATTERNS.get(publisher, CLAUSE_PATTERNS['DEFAULT'])

    clauses = []
    current_clause = None
    current_content = []

    lines = text.split('\n')
    page_num = 1

    for line in lines:
        # Track page breaks (form feed character)
        if '\f' in line:
            page_num += line.count('\f')
            line = line.replace('\f', '')

        # Skip empty lines but preserve paragraph breaks
        if not line.strip():
            if current_content:
                current_content.append('')
            continue

        # Check for new clause
        match = re.match(pattern, line.strip())
        if match:
            # Save previous clause
            if current_clause:
                clauses.append({
                    'number': current_clause['number'],
                    'title': current_clause['title'],
                    'content': current_content,
                    'start_page': current_clause['start_page']
                })

            # Start new clause
            current_clause = {
                'number': match.group(1).strip(),
                'title': match.group(2).strip(),
                'start_page': page_num
            }
            current_content = []

            # Check if there's content after the clause header on same line
            remaining = line[match.end():].strip()
            if remaining:
                current_content.append(remaining)
        else:
            # Add to current clause content
            if current_clause:
                current_content.append(line.strip())

    # Don't forget last clause
    if current_clause:
        clauses.append({
            'number': current_clause['number'],
            'title': current_clause['title'],
            'content': current_content,
            'start_page': current_clause['start_page']
        })

    return clauses


def split_into_blocks(content_lines: list) -> list:
    """Split content into typed blocks."""
    blocks = []
    current_block = []
    current_type = 'Paragraph'

    for line in content_lines:
        if not line:
            # Empty line - end current block
            if current_block:
                blocks.append({
                    'type': current_type,
                    'content': '\n'.join(current_block)
                })
                current_block = []
                current_type = 'Paragraph'
            continue

        line_type = detect_block_type(line)

        if line_type != current_type and current_block:
            # Type changed - save current block
            blocks.append({
                'type': current_type,
                'content': '\n'.join(current_block)
            })
            current_block = []

        current_type = line_type
        current_block.append(line)

    # Save final block
    if current_block:
        blocks.append({
            'type': current_type,
            'content': '\n'.join(current_block)
        })

    return blocks


def load_to_database(standard_id: str, clauses: list, pdf_path: str):
    """Load extracted content into database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Get or create reference record
        cursor.execute("SELECT id FROM qm_references WHERE standard_id = ?", (standard_id,))
        row = cursor.fetchone()

        if not row:
            print(f"Error: Standard {standard_id} not found in qm_references.")
            print("Run /sis-intake first to register the standard.")
            return False

        reference_id = row[0]

        # Clear existing content for this standard
        cursor.execute("""
            DELETE FROM ref_content_blocks
            WHERE clause_id IN (SELECT id FROM ref_clauses WHERE reference_id = ?)
        """, (reference_id,))

        cursor.execute("DELETE FROM ref_clauses WHERE reference_id = ?", (reference_id,))

        # Clear FTS entries
        cursor.execute("DELETE FROM ref_content_fts WHERE standard_id = ?", (standard_id,))

        total_blocks = 0
        seen_clauses = {}  # Track duplicates

        for clause in clauses:
            # Handle duplicate clause numbers by adding suffix
            clause_num = clause['number']
            if clause_num in seen_clauses:
                seen_clauses[clause_num] += 1
                clause_num = f"{clause_num}_{seen_clauses[clause_num]}"
            else:
                seen_clauses[clause_num] = 1
            # Insert clause
            cursor.execute("""
                INSERT INTO ref_clauses (reference_id, clause_number, clause_title)
                VALUES (?, ?, ?)
            """, (reference_id, clause_num, clause['title']))

            clause_id = cursor.lastrowid

            # Split into blocks and insert
            blocks = split_into_blocks(clause['content'])

            for i, block in enumerate(blocks):
                if not block['content'].strip():
                    continue

                cursor.execute("""
                    INSERT INTO ref_content_blocks
                    (clause_id, block_type, content, page_number, display_order)
                    VALUES (?, ?, ?, ?, ?)
                """, (clause_id, block['type'], block['content'], clause['start_page'], i))

                # Add to FTS index
                cursor.execute("""
                    INSERT INTO ref_content_fts
                    (standard_id, clause_number, clause_title, block_type, content)
                    VALUES (?, ?, ?, ?, ?)
                """, (standard_id, clause_num, clause['title'], block['type'], block['content']))

                total_blocks += 1

        # Update extraction status
        cursor.execute("""
            UPDATE qm_references
            SET content_extracted = 1,
                extraction_date = ?,
                extraction_method = 'pdftotext'
            WHERE id = ?
        """, (datetime.now().isoformat(), reference_id))

        conn.commit()

        print(f"\n[OK] Loaded {len(clauses)} clauses with {total_blocks} content blocks")
        print(f"[OK] FTS index updated for searching")
        print(f"[OK] Standard marked as content_extracted=1")

        return True

    except Exception as e:
        conn.rollback()
        print(f"Error loading to database: {e}")
        return False
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description='Extract reference standard content to database')
    parser.add_argument('pdf_path', help='Path to the PDF file')
    parser.add_argument('--standard-id', required=True, help='Standard ID (e.g., ISO-9001-2015)')
    parser.add_argument('--dry-run', action='store_true', help='Parse only, do not load to database')

    args = parser.parse_args()

    pdf_path = args.pdf_path
    standard_id = args.standard_id

    if not os.path.exists(pdf_path):
        print(f"Error: File not found: {pdf_path}")
        sys.exit(1)

    print(f"Extracting: {pdf_path}")
    print(f"Standard ID: {standard_id}")

    # Extract text
    print("\n1. Extracting text from PDF...")
    text = extract_text_with_pdftotext(pdf_path)
    print(f"   Extracted {len(text):,} characters")

    # Detect publisher and parse
    publisher = detect_publisher(standard_id)
    print(f"\n2. Parsing clauses (publisher pattern: {publisher})...")
    clauses = parse_clauses(text, publisher)
    print(f"   Found {len(clauses)} clauses")

    if clauses:
        print(f"\n   Sample clauses found:")
        for clause in clauses[:5]:
            print(f"   - {clause['number']}: {clause['title'][:50]}...")

    if args.dry_run:
        print("\n[DRY RUN] Would load to database but --dry-run specified")
        return

    # Load to database
    print(f"\n3. Loading to database...")
    success = load_to_database(standard_id, clauses, pdf_path)

    if success:
        print(f"\n" + "="*60)
        print(f"EXTRACTION COMPLETE: {standard_id}")
        print(f"="*60)
        print(f"\nYou can now search with:")
        print(f'  sqlite3 D:/quality.db "SELECT * FROM ref_content_fts WHERE content MATCH \'quality\'"')


if __name__ == '__main__':
    main()
