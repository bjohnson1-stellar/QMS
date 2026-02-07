#!/usr/bin/env python3
"""
Extractor Agent - Support Plan Drawing Extraction for Project 07308
Extracts support tags and details from refrigeration support plan drawings.
Sheets 116-118: RS13010, RS13020, RS13030 - Interstitial Area Support Plans
"""

import anthropic
import base64
import sqlite3
import os
import json
import re
from datetime import datetime
from pathlib import Path

# Configuration
DATABASE_PATH = "D:/quality.db"
SHEET_IDS = [116, 117, 118]
MODEL = "claude-sonnet-4-20250514"

def encode_pdf(file_path):
    """Encode PDF to base64 for API."""
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

def extract_supports_from_drawing(client, file_path, drawing_number, title):
    """Extract support data from a single drawing using Claude."""
    print(f"\nProcessing: {drawing_number}")
    print(f"File: {file_path}")

    # Encode PDF
    pdf_data = encode_pdf(file_path)

    # Extraction prompt
    prompt = f"""Extract all pipe support information from this refrigeration support plan drawing.

Drawing: {drawing_number}

For each SUPPORT TAG shown on the drawing plan view, extract:
- Support tag/mark (e.g., RS-101, RS-102, etc.)
- Support type if indicated (hanger, guide, anchor, spring, etc.)
- Detail reference if shown (e.g., "DETAIL A", "TYP. DET 1", etc.)
- Location/grid reference if shown
- Pipe size supported if shown
- Any special notes

Also extract any TYPICAL SUPPORT DETAILS shown with:
- Detail label/number
- Support type description
- Member type and size (angle, channel, rod, etc.)
- Load capacity if shown
- Any dimensions or specifications

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

    # Call Claude API
    message = client.messages.create(
        model=MODEL,
        max_tokens=16000,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": pdf_data,
                        },
                    },
                    {
                        "type": "text",
                        "text": prompt
                    }
                ],
            }
        ],
    )

    # Extract JSON from response
    response_text = message.content[0].text

    # Find JSON in response (handle markdown code blocks)
    json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)
    if json_match:
        json_str = json_match.group(1)
    else:
        # Try to find raw JSON
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
        else:
            raise ValueError("No JSON found in response")

    data = json.loads(json_str)

    return data, message.usage

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
            None,  # member_type not applicable for individual support tags
            support.get("pipe_size"),
            None,  # max_load_lbs not typically shown on plan view
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
                notes, confidence
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            sheet_id,
            detail.get("detail_type"),
            detail.get("detail_label"),
            detail.get("member_type"),
            detail.get("member_size"),
            detail.get("max_load_lbs"),
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
        MODEL,
        quality_score,
        sheet_id
    ))

    conn.commit()

    return support_count, detail_count

def main():
    """Main extraction workflow."""
    # Initialize Anthropic client
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY environment variable not set")
        return 1

    client = anthropic.Anthropic(api_key=api_key)

    # Connect to database
    conn = sqlite3.connect(DATABASE_PATH)

    try:
        total_supports = 0
        total_details = 0
        total_input_tokens = 0
        total_output_tokens = 0

        print("=" * 80)
        print("EXTRACTOR AGENT - REFRIGERATION SUPPORT PLAN EXTRACTION")
        print("=" * 80)
        print(f"Project: 07308-BIRDCAGE")
        print(f"Drawing Type: Refrigeration Support Plans - Interstitial Areas 1-3")
        print(f"Model: {MODEL}")
        print(f"Sheets to process: {len(SHEET_IDS)}")

        for sheet_id in SHEET_IDS:
            # Get sheet info
            sheet_info = get_sheet_info(conn, sheet_id)
            if not sheet_info:
                print(f"\nERROR: Sheet ID {sheet_id} not found in database")
                continue

            id, project_id, file_path, drawing_number, title, revision = sheet_info

            # Use file path as-is (already absolute)
            if not os.path.exists(file_path):
                print(f"\nERROR: File not found: {file_path}")
                continue

            # Extract data
            try:
                supports_data, usage = extract_supports_from_drawing(
                    client, file_path, drawing_number, title
                )

                # Store in database
                support_count, detail_count = store_supports(conn, sheet_id, supports_data)

                total_supports += support_count
                total_details += detail_count
                total_input_tokens += usage.input_tokens
                total_output_tokens += usage.output_tokens

                # Report results
                print(f"  Extracted {support_count} supports, {detail_count} typical details")
                print(f"  Quality Score: {supports_data.get('quality_score', 0.0):.2f}")
                print(f"  Tokens: {usage.input_tokens:,} in / {usage.output_tokens:,} out")

            except Exception as e:
                print(f"  ERROR: {str(e)}")
                import traceback
                traceback.print_exc()
                continue

        # Final summary
        print("\n" + "=" * 80)
        print("EXTRACTION COMPLETE")
        print("=" * 80)
        print(f"Total Supports Extracted: {total_supports}")
        print(f"Total Typical Details: {total_details}")
        print(f"Total Input Tokens: {total_input_tokens:,}")
        print(f"Total Output Tokens: {total_output_tokens:,}")
        print(f"\nDatabase: {DATABASE_PATH}")

        # Show summary by sheet
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.id, s.drawing_number, COUNT(sd.id) as detail_count
            FROM sheets s
            LEFT JOIN support_details sd ON sd.sheet_id = s.id
            WHERE s.id IN (116, 117, 118)
            GROUP BY s.id
            ORDER BY s.id
        """)

        print("\nDetails by Sheet:")
        for row in cursor.fetchall():
            print(f"  Sheet {row[0]} ({row[1]}): {row[2]} items")

    finally:
        conn.close()

    return 0

if __name__ == "__main__":
    exit(main())
