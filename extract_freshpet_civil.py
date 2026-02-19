#!/usr/bin/env python3
"""
Extract data from Freshpet civil drawings.

Processes the three civil drawing sheets:
- Sheet 494: CU2001 - Storm and Sewer Pipe Profiles
- Sheet 495: CU5011 - Utility and Geometry Details
- Sheet 496: CX1011 - Existing Conditions Plan
"""

import sys
from pathlib import Path

# Add qms to path
sys.path.insert(0, str(Path(__file__).parent))

from qms.pipeline.civil_extractor import extract_civil_drawing
from qms.core import get_db, get_logger

logger = get_logger("extract_freshpet_civil")


def main():
    """Extract data from the three Freshpet civil drawings."""
    sheets = [
        {
            "id": 494,
            "path": r"D:\qms\data\projects\07609-Freshpet\Civil\CU2001-CIVIL-STORM-AND-SEWER-PIPE-PROFILES-Rev.1.pdf",
            "name": "CU2001 - Storm and Sewer Pipe Profiles"
        },
        {
            "id": 495,
            "path": r"D:\qms\data\projects\07609-Freshpet\Civil\CU5011-CIVIL-UTILITY-AND-GEOMETRY-DETAILS-Rev.1.pdf",
            "name": "CU5011 - Utility and Geometry Details"
        },
        {
            "id": 496,
            "path": r"D:\qms\data\projects\07609-Freshpet\Civil\CX1011-CIVIL-EXISTING-CONDITIONS-PLAN-Rev.1.pdf",
            "name": "CX1011 - Existing Conditions Plan"
        },
    ]

    results = []

    print("=" * 80)
    print("FRESHPET CIVIL DRAWING EXTRACTION")
    print("=" * 80)
    print()

    for i, sheet in enumerate(sheets, 1):
        print(f"[{i}/3] Processing: {sheet['name']}")
        print(f"        Sheet ID: {sheet['id']}")
        print(f"        File: {sheet['path']}")
        print()

        try:
            result = extract_civil_drawing(
                sheet_id=sheet["id"],
                file_path=sheet["path"],
                dry_run=False  # Actually write to database
            )
            results.append(result)

            if result["status"] == "success":
                print(f"✓ SUCCESS - Extracted {result['total_items']} items")
                print(f"  Drawing Type: {result['drawing_type']}")
                print(f"  Processing Time: {result['processing_time_ms']}ms")
                print(f"  Breakdown:")
                for key, count in result["counts"].items():
                    if count > 0:
                        print(f"    - {key}: {count}")
            else:
                print(f"✗ FAILED - {result.get('error', 'Unknown error')}")

        except Exception as e:
            print(f"✗ ERROR - {e}")
            logger.error("Failed to extract sheet %d: %s", sheet["id"], e, exc_info=True)
            results.append({
                "status": "error",
                "sheet_id": sheet["id"],
                "error": str(e)
            })

        print()

    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)

    success_count = sum(1 for r in results if r.get("status") == "success")
    failed_count = len(results) - success_count

    print(f"Total Sheets: {len(sheets)}")
    print(f"Success: {success_count}")
    print(f"Failed: {failed_count}")
    print()

    if success_count > 0:
        total_items = sum(r.get("total_items", 0) for r in results if r.get("status") == "success")
        avg_time = sum(r.get("processing_time_ms", 0) for r in results if r.get("status") == "success") / success_count
        print(f"Total Items Extracted: {total_items}")
        print(f"Average Processing Time: {avg_time:.0f}ms")
        print()

        # Combined counts
        combined_counts = {}
        for result in results:
            if result.get("status") == "success":
                for key, count in result.get("counts", {}).items():
                    combined_counts[key] = combined_counts.get(key, 0) + count

        print("Combined Extraction Counts:")
        for key, count in sorted(combined_counts.items()):
            if count > 0:
                print(f"  - {key}: {count}")

    print()
    print("Extraction complete!")


if __name__ == "__main__":
    main()
