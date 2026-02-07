#!/usr/bin/env python3
"""
Extractor Agent - Support Plan Drawing Extraction for Project 07308
Direct extraction using base64 PDF encoding
Sheets 122-124: RS13070, RS13080, RS13100 - Interstitial Area Support Plans
"""

import base64
import sqlite3
import os
import json
import re
from datetime import datetime
from pathlib import Path

# Configuration
DATABASE_PATH = "D:/quality.db"
SHEET_IDS = [122, 123, 124]

def encode_pdf(file_path):
    """Encode PDF to base64."""
    with open(file_path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8")

def get_sheet_info(conn, sheet_id):
    """Get sheet information from database."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, project_id, file_path, drawing_number, title, revision
        FROM sheets
        WHERE id = ?
    """, (sheet_id,))
    return cursor.fetchone()

def extract_supports_text(file_path, drawing_number, revision):
    """
    Extract support data from drawing.
    This function prepares the extraction but requires Claude API access.
    """
    pdf_data = encode_pdf(file_path)

    extraction_info = {
        'file_path': file_path,
        'drawing_number': drawing_number,
        'revision': revision,
        'pdf_size': len(pdf_data),
        'prompt': f"""Extract all pipe support information from this refrigeration support plan drawing.

Drawing: {drawing_number} Rev {revision}

For each SUPPORT TAG shown on the drawing plan view, extract:
- Support tag/mark (e.g., RS-101, RS-102, S-1, SUP-A, etc.)
- Support type if indicated (hanger, guide, anchor, spring, trapeze, etc.)
- Detail reference if shown (e.g., "DETAIL A", "TYP. DET 1", etc.)
- Location/grid reference if shown
- Pipe size supported if shown
- Any special notes

Also extract any TYPICAL SUPPORT DETAILS shown with:
- Detail label/number (e.g., "DETAIL 1", "TYP DETAIL A")
- Support type description
- Member type and size (angle, channel, rod, beam, HSS, etc.)
- Load capacity if shown (in pounds or kips)
- Any dimensions or specifications
- Rod sizes if applicable
- Back-to-back configuration if noted

Return the data as structured JSON with this format:
{{
  "supports": [
    {{
      "tag": "RS-101",
      "support_type": "Adjustable Hanger",
      "detail_reference": "Detail A",
      "location": "Grid B-5",
      "pipe_size": "6\\"",
      "notes": "Insulated pipe",
      "confidence": 0.95
    }}
  ],
  "typical_details": [
    {{
      "detail_label": "Detail A",
      "detail_type": "adjustable_hanger",
      "member_type": "Threaded Rod",
      "member_size": "3/4\\"",
      "max_load_lbs": 1000,
      "width_or_span_ft": 8.5,
      "rod_size": "3/4\\"",
      "back_to_back": false,
      "notes": "For 4\\" to 8\\" pipe",
      "confidence": 0.90
    }}
  ],
  "drawing_notes": "General notes about support requirements",
  "quality_score": 0.85
}}

If a field cannot be determined, omit it or set to null.
Set confidence between 0.0-1.0 based on clarity of the information.
Quality score is your overall assessment of extraction completeness (0.0-1.0)."""
    }

    return extraction_info, pdf_data

def store_supports(conn, sheet_id, supports_data):
    """Store extracted support data in database."""
    cursor = conn.cursor()

    supports = supports_data.get("supports", [])
    typical_details = supports_data.get("typical_details", [])
    quality_score = supports_data.get("quality_score", 0.0)

    # Store individual supports
    support_count = 0
    for support in supports:
        # Combine location and notes
        notes_parts = []
        if support.get("location"):
            notes_parts.append(f"Location: {support['location']}")
        if support.get("detail_reference"):
            notes_parts.append(f"Detail: {support['detail_reference']}")
        if support.get("notes"):
            notes_parts.append(support['notes'])
        combined_notes = ", ".join(notes_parts) if notes_parts else None

        cursor.execute("""
            INSERT INTO support_details (
                sheet_id, detail_type, detail_label,
                member_type, member_size, max_load_lbs,
                notes, confidence
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            sheet_id,
            support.get("support_type"),
            support.get("tag"),
            None,
            support.get("pipe_size"),
            None,
            combined_notes,
            support.get("confidence", 1.0)
        ))
        support_count += 1

    # Store typical details
    detail_count = 0
    for detail in typical_details:
        cursor.execute("""
            INSERT INTO support_details (
                sheet_id, detail_type, detail_label,
                member_type, member_size, max_load_lbs,
                width_or_span_ft, rod_size, back_to_back,
                notes, confidence
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            sheet_id,
            detail.get("detail_type"),
            detail.get("detail_label"),
            detail.get("member_type"),
            detail.get("member_size"),
            detail.get("max_load_lbs"),
            detail.get("width_or_span_ft"),
            detail.get("rod_size"),
            1 if detail.get("back_to_back") else 0,
            detail.get("notes"),
            detail.get("confidence", 1.0)
        ))
        detail_count += 1

    # Update sheet metadata
    cursor.execute("""
        UPDATE sheets
        SET extracted_at = ?,
            extraction_model = ?,
            quality_score = ?,
            drawing_type = 'support_plan',
            complexity = 'medium'
        WHERE id = ?
    """, (
        datetime.now().isoformat(),
        'claude-sonnet-4-20250514',
        quality_score,
        sheet_id
    ))

    conn.commit()

    return support_count, detail_count

def main():
    """Main extraction workflow."""

    # Connect to database
    conn = sqlite3.connect(DATABASE_PATH)

    try:
        print("=" * 80)
        print("EXTRACTOR AGENT - REFRIGERATION SUPPORT PLAN EXTRACTION")
        print("=" * 80)
        print(f"Project: 07308-BIRDCAGE")
        print(f"Drawing Type: Refrigeration Support Plans - Interstitial Areas 7, 8, 10")
        print(f"Sheets to process: {len(SHEET_IDS)}")
        print()
        print("NOTE: This script prepares extraction data.")
        print("Claude Code will need to process PDFs directly via API.")
        print()

        for sheet_id in SHEET_IDS:
            # Get sheet info
            sheet_info = get_sheet_info(conn, sheet_id)
            if not sheet_info:
                print(f"\nERROR: Sheet ID {sheet_id} not found in database")
                continue

            id, project_id, file_path, drawing_number, title, revision = sheet_info

            print(f"\nSheet {sheet_id}: {drawing_number} Rev {revision}")
            print(f"File: {file_path}")

            if not os.path.exists(file_path):
                print(f"  ERROR: File not found")
                continue

            # Get file info
            file_size = os.path.getsize(file_path)
            print(f"  Size: {file_size:,} bytes ({file_size/1024/1024:.2f} MB)")

            # Encode PDF
            extraction_info, pdf_data = extract_supports_text(file_path, drawing_number, revision)
            print(f"  Base64 size: {len(pdf_data):,} characters")
            print(f"  Ready for extraction via Claude API")

    finally:
        conn.close()

    return 0

if __name__ == "__main__":
    exit(main())
