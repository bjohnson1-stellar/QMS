#!/usr/bin/env python3
"""
Extract architectural data from Freshpet wall section drawings.

Processes sheets 454, 455, 456 (A3111, A3112, A3113).
"""

import sys
from pathlib import Path

# Add qms to path
sys.path.insert(0, str(Path(__file__).parent))

from qms.core import get_db, get_logger
from qms.pipeline.architectural_extractor import extract_architectural_drawing

logger = get_logger("extract_freshpet_arch")


def main():
    """Extract data from three Freshpet architectural sheets."""

    # Sheet IDs to process
    sheet_ids = [454, 455, 456]

    logger.info("Starting extraction for %d architectural sheets", len(sheet_ids))

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
            result = extract_architectural_drawing(sheet_id, file_path, conn)
            results.append(result)

            # Print result
            if result["status"] == "success":
                logger.info("✓ SUCCESS")
                logger.info("  - Notes: %d", result["notes"])
                logger.info("  - Details: %d", result["details"])
                logger.info("  - Abbreviations: %d", result["abbreviations"])
                logger.info("  - Confidence: %.2f", result["confidence"])
                logger.info("  - Processing time: %d ms", result["processing_time_ms"])
            else:
                logger.error("✗ FAILED: %s", result["errors"])

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
    total_details = sum(r["details"] for r in results)
    total_abbr = sum(r["abbreviations"] for r in results)
    avg_confidence = sum(r["confidence"] for r in results) / len(results) if results else 0.0

    logger.info("Sheets processed: %d", len(results))
    logger.info("  - Success: %d", success)
    logger.info("  - Failed: %d", failed)
    logger.info("")
    logger.info("Items extracted:")
    logger.info("  - Notes: %d", total_notes)
    logger.info("  - Details: %d", total_details)
    logger.info("  - Abbreviations: %d", total_abbr)
    logger.info("  - Average confidence: %.2f", avg_confidence)

    # List any errors
    errors = [e for r in results for e in r.get("errors", [])]
    if errors:
        logger.info("")
        logger.info("Errors encountered:")
        for error in errors:
            logger.info("  - %s", error)

    logger.info("=" * 80)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
