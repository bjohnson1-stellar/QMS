#!/usr/bin/env python3
"""
Simple architectural data extraction from Freshpet wall section drawings.

Extracts text and stores basic information without requiring AI API calls.
Processes sheets 454, 455, 456 (A3111, A3112, A3113).
"""

import sys
import re
from pathlib import Path
from datetime import datetime

# Add qms to path
sys.path.insert(0, str(Path(__file__).parent))

from qms.core import get_db, get_logger
from qms.pipeline.extractor import extract_pdf_text

logger = get_logger("extract_freshpet_arch_simple")


def extract_notes_from_text(text: str) -> list:
    """
    Extract notes from drawing text using pattern matching.

    Args:
        text: Extracted PDF text.

    Returns:
        List of note dictionaries.
    """
    notes = []

    # Split into lines
    lines = text.split('\n')

    # Look for numbered notes (e.g., "1. ", "2. ", etc.)
    note_pattern = re.compile(r'^\s*(\d+)\.\s+(.+)', re.MULTILINE)

    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue

        # Numbered notes
        match = note_pattern.match(line)
        if match:
            note_num = match.group(1)
            note_text = match.group(2).strip()
            notes.append({
                "note_type": "numbered",
                "note_text": f"{note_num}. {note_text}",
            })
            continue

        # General notes (lines that look like specifications)
        if any(keyword in line.upper() for keyword in [
            'CMU', 'CONCRETE', 'INSULATION', 'STEEL', 'GYPSUM',
            'MASONRY', 'METAL', 'WALL', 'ROOF', 'FOUNDATION'
        ]):
            if len(line) > 20 and len(line) < 200:  # Reasonable note length
                notes.append({
                    "note_type": "general",
                    "note_text": line,
                })

    return notes


def extract_abbreviations_from_text(text: str) -> list:
    """
    Extract abbreviations from drawing text.

    Args:
        text: Extracted PDF text.

    Returns:
        List of abbreviation dictionaries.
    """
    abbreviations = []

    # Common architectural abbreviations pattern: "ABBR - Full Text" or "ABBR = Full Text"
    abbr_pattern = re.compile(r'([A-Z]{2,})\s*[-=:]\s*([A-Za-z\s]+)')

    for match in abbr_pattern.finditer(text):
        abbr = match.group(1).strip()
        full = match.group(2).strip()

        # Filter out obvious non-abbreviations
        if len(abbr) <= 6 and len(full) > len(abbr):
            abbreviations.append({
                "abbreviation": abbr,
                "full_text": full,
            })

    return abbreviations


def simple_extract_architectural(sheet_id: int, drawing_number: str, file_path: str, conn) -> dict:
    """
    Extract data from architectural drawing without AI.

    Args:
        sheet_id: Sheet ID from database.
        drawing_number: Drawing number.
        file_path: Path to PDF file.
        conn: Database connection.

    Returns:
        Dictionary with extraction results.
    """
    result = {
        "sheet_id": sheet_id,
        "drawing_number": drawing_number,
        "status": "pending",
        "notes": 0,
        "abbreviations": 0,
        "text_length": 0,
        "errors": [],
    }

    try:
        # Extract text from PDF
        pdf_path = Path(file_path)
        if not pdf_path.exists():
            result["status"] = "failed"
            result["errors"].append(f"File not found: {file_path}")
            return result

        text = extract_pdf_text(pdf_path)
        if not text.strip():
            result["status"] = "failed"
            result["errors"].append("No text extracted from PDF")
            return result

        result["text_length"] = len(text)
        logger.info("Extracted %d characters from %s", len(text), pdf_path.name)

        # Extract notes
        notes = extract_notes_from_text(text)
        logger.info("Found %d notes", len(notes))

        # Store notes
        for note in notes:
            try:
                conn.execute("""
                    INSERT INTO drawing_notes (
                        sheet_id, note_type, note_text
                    ) VALUES (?, ?, ?)
                """, (
                    sheet_id,
                    note.get("note_type", "general"),
                    note.get("note_text"),
                ))
                result["notes"] += 1
            except Exception as e:
                logger.warning("Failed to insert note: %s", e)

        # Extract abbreviations
        abbreviations = extract_abbreviations_from_text(text)
        logger.info("Found %d abbreviations", len(abbreviations))

        # Store abbreviations
        for abbr in abbreviations:
            try:
                conn.execute("""
                    INSERT INTO drawing_abbreviations (
                        sheet_id, abbreviation, full_text, category, confidence
                    ) VALUES (?, ?, ?, ?, ?)
                """, (
                    sheet_id,
                    abbr.get("abbreviation"),
                    abbr.get("full_text"),
                    "architectural",
                    0.7,  # Lower confidence for pattern-based extraction
                ))
                result["abbreviations"] += 1
            except Exception as e:
                logger.warning("Failed to insert abbreviation: %s", e)

        # Store extraction note
        conn.execute("""
            INSERT INTO extraction_notes (
                sheet_id, note_type, description, confidence
            ) VALUES (?, ?, ?, ?)
        """, (
            sheet_id,
            "text_extraction",
            f"Extracted {len(text)} chars, {result['notes']} notes, {result['abbreviations']} abbreviations using pattern matching",
            0.7,
        ))

        # Update sheet record
        conn.execute("""
            UPDATE sheets
            SET extracted_at = ?,
                quality_score = 0.7,
                extraction_model = 'pattern_matching',
                drawing_type = 'Wall Section'
            WHERE id = ?
        """, (datetime.now().isoformat(), sheet_id))

        result["status"] = "success"
        logger.info(
            "Sheet %d complete: %d notes, %d abbreviations",
            sheet_id, result["notes"], result["abbreviations"]
        )

    except Exception as e:
        result["status"] = "failed"
        result["errors"].append(str(e))
        logger.error("Extraction error for sheet %d: %s", sheet_id, e, exc_info=True)

    return result


def main():
    """Extract data from three Freshpet architectural sheets."""

    # Sheet IDs to process
    sheet_ids = [454, 455, 456]

    logger.info("Starting simple extraction for %d architectural sheets", len(sheet_ids))
    logger.info("Note: Using pattern-based extraction (no AI API required)")

    # Get file paths from database
    with get_db(readonly=True) as conn:
        rows = conn.execute("""
            SELECT id, drawing_number, file_path, title
            FROM sheets
            WHERE id IN (?, ?, ?)
            ORDER BY id
        """, sheet_ids).fetchall()

    if len(rows) != 3:
        logger.error("Expected 3 sheets, found %d", len(rows))
        return 1

    # Process each sheet
    results = []
    with get_db() as conn:
        for i, row in enumerate(rows, 1):
            sheet_id = row["id"]
            drawing_number = row["drawing_number"]
            file_path = row["file_path"]

            logger.info("")
            logger.info("=" * 80)
            logger.info("[%d/3] Processing: %s (sheet ID %d)", i, drawing_number, sheet_id)
            logger.info("File: %s", file_path)
            logger.info("=" * 80)

            # Extract data
            result = simple_extract_architectural(sheet_id, drawing_number, file_path, conn)
            results.append(result)

            # Print result
            if result["status"] == "success":
                logger.info("SUCCESS")
                logger.info("  - Text extracted: %d characters", result["text_length"])
                logger.info("  - Notes stored: %d", result["notes"])
                logger.info("  - Abbreviations stored: %d", result["abbreviations"])
            else:
                logger.error("FAILED: %s", result["errors"])

        # Commit all changes
        conn.commit()
        logger.info("")
        logger.info("All changes committed to database")

    # Summary
    logger.info("")
    logger.info("=" * 80)
    logger.info("EXTRACTION SUMMARY")
    logger.info("=" * 80)

    success = sum(1 for r in results if r["status"] == "success")
    failed = sum(1 for r in results if r["status"] == "failed")

    total_notes = sum(r["notes"] for r in results)
    total_abbr = sum(r["abbreviations"] for r in results)
    total_text = sum(r["text_length"] for r in results)

    logger.info("Sheets processed: %d", len(results))
    logger.info("  - Success: %d", success)
    logger.info("  - Failed: %d", failed)
    logger.info("")
    logger.info("Items extracted:")
    logger.info("  - Total text: %d characters", total_text)
    logger.info("  - Notes: %d", total_notes)
    logger.info("  - Abbreviations: %d", total_abbr)

    # List any errors
    errors = [e for r in results for e in r.get("errors", [])]
    if errors:
        logger.info("")
        logger.info("Errors encountered:")
        for error in errors:
            logger.info("  - %s", error)

    logger.info("=" * 80)

    # Verify data in database
    logger.info("")
    logger.info("Database verification:")
    with get_db(readonly=True) as conn:
        for sheet_id in sheet_ids:
            notes_count = conn.execute(
                "SELECT COUNT(*) as n FROM drawing_notes WHERE sheet_id = ?",
                (sheet_id,)
            ).fetchone()["n"]

            abbr_count = conn.execute(
                "SELECT COUNT(*) as n FROM drawing_abbreviations WHERE sheet_id = ?",
                (sheet_id,)
            ).fetchone()["n"]

            extracted = conn.execute(
                "SELECT extracted_at, quality_score FROM sheets WHERE id = ?",
                (sheet_id,)
            ).fetchone()

            logger.info("  Sheet %d: %d notes, %d abbreviations, extracted=%s",
                       sheet_id, notes_count, abbr_count,
                       "YES" if extracted["extracted_at"] else "NO")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
