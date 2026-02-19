"""
Extract data from Freshpet architectural section drawings.

Processes sheets 451-453 (A3001, A3002, A3003 BUILDING SECTIONS).
"""

import sys
from pathlib import Path

# Add qms to path
sys.path.insert(0, str(Path(__file__).parent))

from qms.pipeline.extractor import extract_batch
from qms.core import get_logger

logger = get_logger("extract_freshpet")

def main():
    """Extract data from the three Freshpet section drawings."""
    sheet_ids = [451, 452, 453]

    logger.info("Starting extraction for sheets: %s", sheet_ids)
    logger.info("Files:")
    logger.info("  451: A3001-BUILDING-SECTIONS-Rev.2.pdf")
    logger.info("  452: A3002-BUILDING-SECTIONS-Rev.1.pdf")
    logger.info("  453: A3003-BUILDING-SECTIONS-Rev.1.pdf")

    # Run extraction
    results = extract_batch(sheet_ids, dry_run=False)

    # Print summary
    print("\n" + "=" * 80)
    print("EXTRACTION SUMMARY")
    print("=" * 80)

    for result in results:
        print(f"\nSheet {result.sheet_id}: {result.drawing_number}")
        print(f"  Type: {result.drawing_type}")
        print(f"  Model: {result.model_used}")
        print(f"  Status: {result.status}")
        print(f"  Confidence: {result.confidence:.2f}")
        print(f"  Extracted:")
        print(f"    - Lines: {result.lines_extracted}")
        print(f"    - Equipment: {result.equipment_extracted}")
        print(f"    - Instruments: {result.instruments_extracted}")
        print(f"    - Welds: {result.welds_extracted}")

        if result.flagged_items:
            print(f"  Flagged for Review ({len(result.flagged_items)}):")
            for item in result.flagged_items[:5]:  # Show first 5
                print(f"    - {item['item']}: {item['reason']} (conf={item['confidence']:.2f})")

        if result.errors:
            print(f"  Errors:")
            for error in result.errors:
                print(f"    - {error}")

        print(f"  Processing Time: {result.processing_time_ms}ms")

    # Overall stats
    total_lines = sum(r.lines_extracted for r in results)
    total_equipment = sum(r.equipment_extracted for r in results)
    total_instruments = sum(r.instruments_extracted for r in results)
    total_welds = sum(r.welds_extracted for r in results)
    avg_confidence = sum(r.confidence for r in results) / len(results) if results else 0.0

    print("\n" + "=" * 80)
    print("TOTALS")
    print("=" * 80)
    print(f"Lines: {total_lines}")
    print(f"Equipment: {total_equipment}")
    print(f"Instruments: {total_instruments}")
    print(f"Welds: {total_welds}")
    print(f"Average Confidence: {avg_confidence:.2f}")

    success_count = sum(1 for r in results if r.status == "success")
    partial_count = sum(1 for r in results if r.status == "partial")
    failed_count = sum(1 for r in results if r.status == "failed")

    print(f"\nStatus: {success_count} success, {partial_count} partial, {failed_count} failed")
    print("=" * 80)

if __name__ == "__main__":
    main()
