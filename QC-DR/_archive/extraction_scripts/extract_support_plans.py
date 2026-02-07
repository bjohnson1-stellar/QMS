"""
Extract support tags from refrigeration support plan sheets (131-134).
Uses Claude API for vision-based extraction from PDF pages.
"""

import sqlite3
import anthropic
import os
from pathlib import Path
import json
from datetime import datetime
import sys
import base64

# Check for required packages
try:
    import fitz  # PyMuPDF
except ImportError:
    print("Installing PyMuPDF...")
    os.system("pip install pymupdf -q")
    import fitz

# Configuration
DATABASE_PATH = "D:/quality.db"
API_KEY = os.environ.get("ANTHROPIC_API_KEY")

SHEETS = [
    {
        "id": 131,
        "path": "D:/Projects/07308-BIRDCAGE/Refrigeration/RS14070-REFRIGERATION-PLAN-SUPPORTS-ROOF-AREA-7-Rev.5.pdf",
        "drawing_type": "Support Plan",
        "location": "Roof Area 7"
    },
    {
        "id": 132,
        "path": "D:/Projects/07308-BIRDCAGE/Refrigeration/RS14080-REFRIGERATION-PLAN-SUPPORTS-ROOF-AREA-8-Rev.5.pdf",
        "drawing_type": "Support Plan",
        "location": "Roof Area 8"
    },
    {
        "id": 133,
        "path": "D:/Projects/07308-BIRDCAGE/Refrigeration/RS42101-REFRIGERATION-PLAN-MACHINE-ROOM-SUPPORTS-FLOOR-Rev.3.pdf",
        "drawing_type": "Support Plan",
        "location": "Machine Room Floor"
    },
    {
        "id": 134,
        "path": "D:/Projects/07308-BIRDCAGE/Refrigeration/RS42401-REFRIGERATION-PLAN-MACHINE-ROOM-SUPPORTS-ROOF-Rev.3.pdf",
        "drawing_type": "Support Plan",
        "location": "Machine Room Roof"
    }
]

EXTRACTION_PROMPT = """Extract all pipe support data from this refrigeration support plan drawing.

For each PIPE SUPPORT shown on the plan, provide:
- Support tag/number (look for labels like "1", "2", "S-1", "PS-101", etc.)
- Support type (if indicated by symbol or schedule: spring hanger, rigid hanger, guide, anchor, shoe, trapeze, etc.)
- Support detail reference (letters like "A", "B", "N", "P", "Q" that refer to standard details)
- Line number supported (pipe line number if shown)
- Grid location (if shown)
- Elevation (if shown)
- Any special notes

Look carefully at:
- Support symbols/markers on the plan view
- Support schedules or tables (often on the side or bottom)
- Detail callouts (circles with letters)
- Leader lines and annotations
- Title blocks for sheet information

Return ONLY a valid JSON array with no other text:
[
  {
    "tag": "1",
    "support_type": "trapeze hanger",
    "detail_ref": "P",
    "line_number": "2\"-R22-101",
    "grid_location": "A-1",
    "elevation": "EL. 42'-0\"",
    "notes": null,
    "confidence": 0.95
  }
]

If you cannot read a value clearly, set it to null and reduce confidence accordingly.
Support plans typically show dozens of support locations - be thorough and extract ALL visible supports."""


def pdf_to_images(pdf_path, max_pages=3):
    """Convert PDF pages to images for Claude vision API."""
    if not os.path.exists(pdf_path):
        print(f"ERROR: PDF not found: {pdf_path}")
        return []

    doc = fitz.open(pdf_path)
    images = []

    for page_num in range(min(len(doc), max_pages)):
        page = doc[page_num]
        # Render at 2x resolution for better text clarity
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
        img_data = pix.tobytes("png")
        images.append({
            "page": page_num + 1,
            "data": img_data,
            "width": pix.width,
            "height": pix.height
        })

    doc.close()
    return images


def extract_supports_with_claude(sheet_info):
    """Extract support data from PDF using Claude vision API."""
    print(f"\n{'='*80}")
    print(f"Processing Sheet {sheet_info['id']}: {Path(sheet_info['path']).name}")
    print(f"Location: {sheet_info['location']}")
    print(f"{'='*80}")

    if not API_KEY:
        print("ERROR: ANTHROPIC_API_KEY environment variable not set")
        return []

    # Convert PDF to images
    print("Converting PDF to images...")
    images = pdf_to_images(sheet_info['path'], max_pages=3)

    if not images:
        print("No images extracted from PDF")
        return []

    print(f"Extracted {len(images)} pages")

    # Process with Claude
    client = anthropic.Anthropic(api_key=API_KEY)

    all_supports = []

    for img_info in images:
        print(f"\nAnalyzing page {img_info['page']} ({img_info['width']}x{img_info['height']})...")

        img_b64 = base64.b64encode(img_info['data']).decode('utf-8')

        try:
            message = client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=4096,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": img_b64
                                }
                            },
                            {
                                "type": "text",
                                "text": EXTRACTION_PROMPT
                            }
                        ]
                    }
                ]
            )

            response_text = message.content[0].text
            print(f"Response length: {len(response_text)} chars")

            # Parse JSON from response
            import re
            # Remove markdown code blocks if present
            response_text = re.sub(r'^```json\s*', '', response_text.strip())
            response_text = re.sub(r'\s*```$', '', response_text.strip())

            # Find JSON array
            json_match = re.search(r'\[[\s\S]*\]', response_text)
            if json_match:
                supports = json.loads(json_match.group())
                print(f"Extracted {len(supports)} supports from page {img_info['page']}")

                # Add metadata to each support
                for support in supports:
                    support['page'] = img_info['page']
                    support['sheet_id'] = sheet_info['id']
                    support['location'] = sheet_info['location']

                all_supports.extend(supports)
            else:
                print(f"No JSON array found in response for page {img_info['page']}")
                print(f"Response preview: {response_text[:300]}...")

        except json.JSONDecodeError as e:
            print(f"JSON parse error on page {img_info['page']}: {e}")
            print(f"Response: {response_text[:500]}...")
        except Exception as e:
            print(f"Error processing page {img_info['page']}: {e}")
            import traceback
            traceback.print_exc()

    return all_supports


def ensure_table_exists(conn):
    """Ensure supports table exists in database."""
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS supports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sheet_id INTEGER NOT NULL,
            tag TEXT NOT NULL,
            support_type TEXT,
            detail_ref TEXT,
            line_number TEXT,
            grid_location TEXT,
            elevation TEXT,
            notes TEXT,
            page INTEGER,
            location TEXT,
            confidence REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (sheet_id) REFERENCES sheets(id)
        )
    """)

    conn.commit()


def store_supports_in_db(supports):
    """Store extracted supports in the database."""
    if not supports:
        return 0

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    ensure_table_exists(conn)

    # Clear existing supports for these sheets
    sheet_ids = list(set([s['sheet_id'] for s in supports]))
    placeholders = ','.join(['?' for _ in sheet_ids])
    cursor.execute(f"DELETE FROM supports WHERE sheet_id IN ({placeholders})", sheet_ids)

    inserted = 0
    for support in supports:
        try:
            cursor.execute("""
                INSERT INTO supports (
                    sheet_id, tag, support_type, detail_ref, line_number,
                    grid_location, elevation, notes, page, location, confidence
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                support.get('sheet_id'),
                support.get('tag'),
                support.get('support_type'),
                support.get('detail_ref'),
                support.get('line_number'),
                support.get('grid_location'),
                support.get('elevation'),
                support.get('notes'),
                support.get('page'),
                support.get('location'),
                support.get('confidence', 0.7)
            ))
            inserted += 1
        except Exception as e:
            print(f"Error inserting support {support.get('tag')}: {e}")

    conn.commit()
    conn.close()

    return inserted


def update_sheet_metadata(sheet_id, num_supports, avg_confidence):
    """Update sheet metadata after extraction."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE sheets
        SET extracted_at = CURRENT_TIMESTAMP,
            quality_score = ?,
            drawing_type = 'Support Plan',
            complexity = 'medium',
            extraction_notes = ?,
            extraction_model = 'claude-sonnet-4-5'
        WHERE id = ?
    """, (
        avg_confidence,
        f"Extracted {num_supports} supports",
        sheet_id
    ))

    conn.commit()
    conn.close()


def main():
    print("Support Plan Extraction - Sheets 131-134")
    print("="*80)
    print(f"Database: {DATABASE_PATH}")
    print(f"Sheets to process: {len(SHEETS)}")

    if not API_KEY:
        print("\nERROR: ANTHROPIC_API_KEY environment variable not set")
        print("Please set it before running this script.")
        return

    print()

    total_supports = 0
    results = []

    for sheet_info in SHEETS:
        # Extract supports
        supports = extract_supports_with_claude(sheet_info)

        if supports:
            # Store in database
            inserted = store_supports_in_db(supports)

            # Calculate statistics
            confidences = [s.get('confidence', 0.7) for s in supports]
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.7

            # Update sheet metadata
            update_sheet_metadata(sheet_info['id'], inserted, avg_confidence)

            total_supports += inserted

            results.append({
                'sheet_id': sheet_info['id'],
                'location': sheet_info['location'],
                'supports': inserted,
                'avg_confidence': avg_confidence
            })

            print(f"\nStored {inserted} supports (avg confidence: {avg_confidence:.2f})")
        else:
            print(f"\nNo supports extracted from sheet {sheet_info['id']}")
            results.append({
                'sheet_id': sheet_info['id'],
                'location': sheet_info['location'],
                'supports': 0,
                'avg_confidence': 0.0
            })

    # Summary
    print("\n" + "="*80)
    print("EXTRACTION SUMMARY")
    print("="*80)
    for result in results:
        print(f"Sheet {result['sheet_id']} ({result['location']}): {result['supports']} supports (confidence: {result['avg_confidence']:.2f})")
    print(f"\nTotal supports extracted: {total_supports}")

    # Show sample supports
    if total_supports > 0:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        print("\n" + "="*80)
        print("SAMPLE SUPPORTS (First 10)")
        print("="*80)

        cursor.execute("""
            SELECT sheet_id, tag, support_type, detail_ref, line_number,
                   grid_location, elevation, confidence
            FROM supports
            WHERE sheet_id IN (131, 132, 133, 134)
            ORDER BY sheet_id, tag
            LIMIT 10
        """)

        for row in cursor.fetchall():
            print(f"Sheet {row[0]}: Tag={row[1]}, Type={row[2]}, Detail={row[3]}, "
                  f"Line={row[4]}, Grid={row[5]}, Elev={row[6]}, Conf={row[7]:.2f}")

        conn.close()

    print("="*80)


if __name__ == "__main__":
    main()
