"""
Extract support data from refrigeration plan support sheets 110-112.
"""
import sys
import sqlite3
import re
from datetime import datetime
from pathlib import Path

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

def analyze_support_plan(text, drawing_number):
    """
    Analyze refrigeration plan support drawing text.
    These are plan views showing support locations and tags.
    """
    supports = []

    # Support tag patterns for refrigeration plans
    # Looking for patterns like: S-1, S-2, SUP-1, SUPT-1, SP-1, etc.
    support_tag_patterns = [
        r'\b(S-\d+[A-Z]?)\b',
        r'\b(SUP-\d+[A-Z]?)\b',
        r'\b(SUPT-\d+[A-Z]?)\b',
        r'\b(SP-\d+[A-Z]?)\b',
        r'\b(HNGR-\d+[A-Z]?)\b',
        r'\b(STD-\d+[A-Z]?)\b',
    ]

    # Look for detail references (letters that refer to detail sheets)
    detail_ref_patterns = [
        r'TYP\.\s*([A-Z])',
        r'DETAIL\s*([A-Z])',
        r'SEE\s*DETAIL\s*([A-Z])',
        r'\(([A-Z])\)',  # Single letter in parentheses
    ]

    # Extract all unique support tags
    found_tags = set()
    for pattern in support_tag_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        found_tags.update(matches)

    # For each support tag, try to find associated detail reference
    for tag in sorted(found_tags):
        support_info = {
            'detail_label': tag,
            'detail_type': 'support_location',
            'confidence': 0.85
        }

        # Try to find detail reference near the tag
        # Look in context around the tag
        tag_pos = text.find(tag)
        if tag_pos >= 0:
            context_start = max(0, tag_pos - 100)
            context_end = min(len(text), tag_pos + 100)
            context = text[context_start:context_end]

            for pattern in detail_ref_patterns:
                match = re.search(pattern, context)
                if match:
                    detail_ref = match.group(1)
                    support_info['notes'] = f'References detail {detail_ref}'
                    support_info['confidence'] = 0.90
                    break

        supports.append(support_info)

    return supports

def extract_sheet_info(text):
    """Extract drawing metadata from title block."""
    info = {
        'drawing_number': None,
        'title': None,
        'revision': None,
    }

    # Try to find drawing number
    drawing_patterns = [
        r'(RS\d+)',
        r'DRAWING\s*NO\.?\s*[:\-]?\s*([A-Z0-9\-]+)',
    ]

    for pattern in drawing_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            info['drawing_number'] = match.group(1)
            break

    # Try to find revision
    rev_patterns = [
        r'REV\.?\s*[:\-]?\s*(\d+)',
        r'REVISION\s*[:\-]?\s*(\d+)',
    ]

    for pattern in rev_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            info['revision'] = match.group(1)
            break

    return info

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

def update_sheet_metadata(conn, sheet_id, drawing_type, complexity, quality_score, model_used):
    """Update sheet metadata after extraction."""
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE sheets
        SET drawing_type = ?,
            complexity = ?,
            quality_score = ?,
            extracted_at = ?,
            extraction_model = ?
        WHERE id = ?
    """, (drawing_type, complexity, quality_score, datetime.now().isoformat(), model_used, sheet_id))

    conn.commit()

def process_sheet(conn, sheet_id, pdf_path):
    """Process a single support drawing sheet."""
    print(f"\nProcessing Sheet {sheet_id}: {Path(pdf_path).name}")
    print("=" * 70)

    # Extract text
    text = extract_pdf_text(pdf_path)
    if not text:
        print("ERROR: Could not extract text from PDF")
        return 0

    print(f"Extracted {len(text)} characters")

    # Extract sheet info
    sheet_info = extract_sheet_info(text)
    print(f"Drawing Number: {sheet_info['drawing_number']}")
    print(f"Revision: {sheet_info['revision']}")

    # Analyze for supports
    supports = analyze_support_plan(text, sheet_info['drawing_number'])
    print(f"Found {len(supports)} support locations")

    # Insert into database
    count = insert_support_details(conn, sheet_id, supports)

    # Calculate quality score based on findings
    quality_score = 0.80
    if len(supports) > 0:
        quality_score = min(0.95, 0.80 + (len(supports) * 0.01))

    # Update sheet metadata
    update_sheet_metadata(conn, sheet_id, 'support_plan', 'medium', quality_score, 'claude-sonnet-4.5')

    print(f"Inserted {count} support details")
    print(f"Quality Score: {quality_score:.2f}")

    # Show sample of extracted supports
    if supports:
        print(f"\nSample Support Tags:")
        for support in supports[:5]:
            label = support['detail_label']
            notes = support.get('notes', 'No detail reference')
            conf = support.get('confidence', 0.0)
            print(f"  {label}: {notes} (confidence: {conf:.2f})")
        if len(supports) > 5:
            print(f"  ... and {len(supports) - 5} more")

    return count

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
        total_supports = 0

        for sheet_id, pdf_path in sheets:
            count = process_sheet(conn, sheet_id, pdf_path)
            total_supports += count

        print("\n" + "=" * 70)
        print("EXTRACTION SUMMARY")
        print("=" * 70)
        print(f"Total Sheets Processed: {len(sheets)}")
        print(f"Total Support Details: {total_supports}")

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
            print(f"  Sheet {sheet_id} ({dwg_num}): {count} supports, quality: {quality:.2f}")

        # Query summary by type
        cursor.execute("""
            SELECT detail_type, COUNT(*) as count
            FROM support_details
            WHERE sheet_id IN (110, 111, 112)
            GROUP BY detail_type
            ORDER BY count DESC
        """)

        print(f"\nBy Detail Type:")
        for row in cursor.fetchall():
            print(f"  {row[0]}: {row[1]}")

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
