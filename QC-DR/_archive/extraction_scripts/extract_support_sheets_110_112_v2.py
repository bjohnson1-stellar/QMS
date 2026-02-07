"""
Extract support data from refrigeration plan support sheets 110-112.
These sheets show support locations with references to detail sheets.
"""
import sys
import sqlite3
import re
from datetime import datetime
from pathlib import Path
from collections import Counter

try:
    import fitz  # PyMuPDF
    USE_PYMUPDF = True
except ImportError:
    USE_PYMUPDF = False

def extract_pdf_text(pdf_path):
    """Extract text from PDF using PyMuPDF."""
    if not USE_PYMUPDF:
        print("ERROR: PyMuPDF not available", file=sys.stderr)
        return None

    try:
        doc = fitz.open(pdf_path)
        text = ""
        for page in doc:
            text += page.get_text()
        doc.close()
        return text
    except Exception as e:
        print(f"Error extracting PDF: {e}", file=sys.stderr)
        return None

def parse_support_references(text):
    """
    Parse support detail references from plan drawings.
    Format: R50211 [newline] 3 [newline] K
    Or: R5211 [newline] 3 [newline] L (typo in drawing)

    This means: See sheet R50211, detail 3, support type K
    """
    supports = []

    # Pattern 1: R50211 followed by detail number and support type letter
    # The text has newlines between these elements
    pattern1 = r'R50211\s+(\d+)\s+([A-Z])'
    matches1 = re.findall(pattern1, text, re.MULTILINE)

    # Pattern 2: Handle typo R5211 (missing 0)
    pattern2 = r'R5211\s+(\d+)\s+([A-Z])'
    matches2 = re.findall(pattern2, text, re.MULTILINE)

    # Combine all matches
    all_matches = matches1 + matches2

    # Count occurrences of each support type
    support_counter = Counter()

    for detail_num, support_type in all_matches:
        key = f"{detail_num}-{support_type}"
        support_counter[key] += 1

    # Create support entries
    for key, count in support_counter.items():
        detail_num, support_type = key.split('-')

        support_info = {
            'detail_type': 'support_reference',
            'detail_label': f'Type {support_type}',
            'member_type': f'See R50211 Detail {detail_num}',
            'notes': f'Support type {support_type} per R50211 detail {detail_num}, occurs {count} times on this sheet',
            'confidence': 0.95,
            'count': count
        }
        supports.append(support_info)

    return supports, support_counter

def extract_sheet_info(text, filename):
    """Extract drawing metadata from title block and filename."""
    info = {
        'drawing_number': None,
        'title': None,
        'revision': None,
    }

    # Extract from filename
    filename_match = re.search(r'(RS\d+)', filename)
    if filename_match:
        info['drawing_number'] = filename_match.group(1)

    rev_match = re.search(r'Rev\.?(\d+)', filename, re.IGNORECASE)
    if rev_match:
        info['revision'] = rev_match.group(1)

    # Try to extract title from text
    if 'FLOOR AREA 4' in text or 'AREA-4' in text or 'AREA 4' in text:
        info['title'] = 'REFRIGERATION PLAN SUPPORTS - FLOOR AREA 4'
    elif 'FLOOR AREA 5' in text or 'AREA-5' in text or 'AREA 5' in text:
        info['title'] = 'REFRIGERATION PLAN SUPPORTS - FLOOR AREA 5'
    elif 'FLOOR AREA 6' in text or 'AREA-6' in text or 'AREA 6' in text:
        info['title'] = 'REFRIGERATION PLAN SUPPORTS - FLOOR AREA 6'

    return info

def get_support_type_details(support_type):
    """
    Get support details from sheet 49 (R50211) for reference.
    Returns description of support type.
    """
    # Mapping from sheet 49 data
    type_map = {
        'J': 'Clevis Hanger - See Detail 3',
        'K': 'Trapeze Hanger Type K - See Detail 3',
        'L': 'Support Type L',
        'N': 'Trapeze L2x2x1/4, 500 lbs, 4ft span',
        'P': 'Trapeze L3x3x1/4, 1200 lbs, 4ft span',
        'Q': 'Trapeze L4x4x1/4, 2000 lbs, 4ft span',
        'R': 'Trapeze L4x4x3/8, 2900 lbs, 4ft span',
        'S': 'Trapeze L4x4x1/4 B2B, 4100 lbs, 4ft span',
        'T': 'Trapeze L4x4x3/8 B2B, 6000 lbs, 4ft span',
        'U': 'Trapeze L5x5x3/8 B2B, 9500 lbs, 4ft span',
        'V': 'Trapeze 3-rod L4x4x1/4, 2700 lbs',
        'W': 'Trapeze 3-rod L4x4x3/8, 3900 lbs',
        'X': 'Trapeze 3-rod L4x4x1/4 B2B, 5400 lbs',
        'Y': 'Trapeze 3-rod L4x4x3/8 B2B, 7900 lbs',
        'Z': 'Trapeze 3-rod L5x5x3/8 B2B, 12500 lbs',
    }

    return type_map.get(support_type, f'Support Type {support_type}')

def insert_support_details(conn, sheet_id, supports):
    """Insert support details into database."""
    cursor = conn.cursor()

    # Clear existing support details for this sheet
    cursor.execute("DELETE FROM support_details WHERE sheet_id = ?", (sheet_id,))

    insert_sql = """
        INSERT INTO support_details
        (sheet_id, detail_type, detail_label, member_type, member_size,
         max_load_lbs, width_or_span_ft, rod_size, back_to_back, notes, confidence)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    inserted = 0
    for support in supports:
        cursor.execute(insert_sql, (
            sheet_id,
            support.get('detail_type'),
            support.get('detail_label'),
            support.get('member_type'),
            support.get('member_size'),
            support.get('max_load_lbs'),
            support.get('width_or_span_ft'),
            support.get('rod_size'),
            support.get('back_to_back'),
            support.get('notes'),
            support.get('confidence', 1.0)
        ))
        inserted += 1

    conn.commit()
    return inserted

def update_sheet_metadata(conn, sheet_id, drawing_number, title, revision, drawing_type, complexity, quality_score, model_used):
    """Update sheet metadata after extraction."""
    cursor = conn.cursor()

    update_fields = []
    update_values = []

    if drawing_number:
        update_fields.append("drawing_number = ?")
        update_values.append(drawing_number)

    if title:
        update_fields.append("title = ?")
        update_values.append(title)

    if revision:
        update_fields.append("revision = ?")
        update_values.append(revision)

    update_fields.extend([
        "drawing_type = ?",
        "complexity = ?",
        "quality_score = ?",
        "extracted_at = ?",
        "extraction_model = ?"
    ])

    update_values.extend([
        drawing_type,
        complexity,
        quality_score,
        datetime.now().isoformat(),
        model_used
    ])

    update_values.append(sheet_id)

    sql = f"UPDATE sheets SET {', '.join(update_fields)} WHERE id = ?"

    cursor.execute(sql, update_values)
    conn.commit()

def process_sheet(conn, sheet_id, pdf_path):
    """Process a single support drawing sheet."""
    filename = Path(pdf_path).name
    print(f"\nProcessing Sheet {sheet_id}: {filename}")
    print("=" * 70)

    # Extract text
    text = extract_pdf_text(pdf_path)
    if not text:
        print("ERROR: Could not extract text from PDF")
        return 0

    print(f"Extracted {len(text)} characters")

    # Extract sheet info
    sheet_info = extract_sheet_info(text, filename)
    print(f"Drawing Number: {sheet_info['drawing_number']}")
    print(f"Title: {sheet_info['title']}")
    print(f"Revision: {sheet_info['revision']}")

    # Parse support references
    supports, counter = parse_support_references(text)
    total_supports = sum(counter.values())
    print(f"Found {len(supports)} unique support types")
    print(f"Total support locations: {total_supports}")

    # Insert into database
    count = insert_support_details(conn, sheet_id, supports)

    # Calculate quality score based on findings
    quality_score = 0.85
    if len(supports) > 0:
        quality_score = min(0.95, 0.85 + (len(supports) * 0.01))

    # Update sheet metadata
    update_sheet_metadata(
        conn, sheet_id,
        sheet_info['drawing_number'],
        sheet_info['title'],
        sheet_info['revision'],
        'support_plan',
        'medium',
        quality_score,
        'claude-sonnet-4.5'
    )

    print(f"Inserted {count} support detail records")
    print(f"Quality Score: {quality_score:.2f}")

    # Show extracted support types
    if supports:
        print(f"\nSupport Types Found:")
        for support in sorted(supports, key=lambda x: x['detail_label']):
            label = support['detail_label']
            count = support.get('count', 0)
            desc = get_support_type_details(label.split()[-1])  # Extract type letter
            print(f"  {label}: {count} locations - {desc}")

    return total_supports

def main():
    """Main extraction process."""
    DB_PATH = "D:/quality.db"

    sheets = [
        (110, "D:/Projects/07308-BIRDCAGE/Refrigeration/RS11040-REFRIGERATION-PLAN-SUPPORTS-FLOOR-AREA-4-Rev.6.pdf"),
        (111, "D:/Projects/07308-BIRDCAGE/Refrigeration/RS11050-REFRIGERATION-PLAN-SUPPORTS-FLOOR-AREA-5-Rev.6.pdf"),
        (112, "D:/Projects/07308-BIRDCAGE/Refrigeration/RS11060-REFRIGERATION-PLAN-SUPPORTS-FLOOR-AREA-6-Rev.6.pdf"),
    ]

    conn = sqlite3.connect(DB_PATH)

    try:
        total_locations = 0

        for sheet_id, pdf_path in sheets:
            locations = process_sheet(conn, sheet_id, pdf_path)
            total_locations += locations

        print("\n" + "=" * 70)
        print("EXTRACTION SUMMARY")
        print("=" * 70)
        print(f"Total Sheets Processed: {len(sheets)}")
        print(f"Total Support Locations: {total_locations}")

        # Query summary by sheet
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.id, s.drawing_number, s.title, s.quality_score, COUNT(sd.id) as support_count
            FROM sheets s
            LEFT JOIN support_details sd ON sd.sheet_id = s.id
            WHERE s.id IN (110, 111, 112)
            GROUP BY s.id
            ORDER BY s.id
        """)

        print(f"\nBy Sheet:")
        for row in cursor.fetchall():
            sheet_id, dwg_num, title, quality, count = row
            title_short = title[:50] + '...' if title and len(title) > 50 else title
            print(f"  Sheet {sheet_id} ({dwg_num})")
            print(f"    Title: {title_short}")
            print(f"    Support types: {count}, Quality: {quality:.2f}")

        # Query all support details
        cursor.execute("""
            SELECT detail_label, notes, COUNT(*) as count
            FROM support_details
            WHERE sheet_id IN (110, 111, 112)
            GROUP BY detail_label, notes
            ORDER BY detail_label
        """)

        print(f"\nSupport Type Summary Across All Sheets:")
        for row in cursor.fetchall():
            label, notes, count = row
            print(f"  {label}: {notes}")

    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        conn.rollback()
        return 1
    finally:
        conn.close()

    return 0

if __name__ == '__main__':
    sys.exit(main())
