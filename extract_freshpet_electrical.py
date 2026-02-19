#!/usr/bin/env python3
"""
Extract electrical data from Freshpet electrical drawings.
Sheets: 517, 518, 519
"""

import sys
from pathlib import Path

# Add qms to path
sys.path.insert(0, str(Path(__file__).parent))

from pipeline.electrical_extractor import extract_batch

def main():
    sheet_ids = [517, 518, 519]

    print("=" * 80)
    print("Freshpet Electrical Drawing Extraction")
    print("=" * 80)
    print(f"Processing {len(sheet_ids)} sheets: {sheet_ids}")
    print()

    # Run extraction with Sonnet model
    results = extract_batch(sheet_ids, model="sonnet", dry_run=False)

    # Print summary
    print()
    print("=" * 80)
    print("EXTRACTION SUMMARY")
    print("=" * 80)

    for result in results:
        print(f"\nSheet ID: {result.sheet_id}")
        print(f"Drawing: {result.drawing_number}")
        print(f"Status: {result.status}")
        print(f"Confidence: {result.confidence:.2f}")
        print(f"Model: {result.extraction_model}")
        print(f"Processing Time: {result.processing_time_ms / 1000:.1f}s")
        print()
        print(f"  Panels: {len(result.panels)}")
        print(f"  Circuits: {len(result.circuits)}")
        print(f"  Equipment: {len(result.equipment)}")
        print(f"  Receptacles: {len(result.receptacles)}")
        print(f"  Lighting Fixtures: {len(result.lighting_fixtures)}")
        print(f"  Transformers: {len(result.transformers)}")
        print(f"  Switchgear: {len(result.switchgear)}")

        if result.notes:
            print(f"\n  Notes:")
            for note in result.notes:
                print(f"    - {note}")

        if result.errors:
            print(f"\n  Errors:")
            for error in result.errors:
                print(f"    - {error}")

        print("-" * 80)

    # Overall stats
    success_count = sum(1 for r in results if r.status == "success")
    partial_count = sum(1 for r in results if r.status == "partial")
    failed_count = sum(1 for r in results if r.status == "failed")

    total_panels = sum(len(r.panels) for r in results)
    total_circuits = sum(len(r.circuits) for r in results)
    total_equipment = sum(len(r.equipment) for r in results)
    total_receptacles = sum(len(r.receptacles) for r in results)
    total_fixtures = sum(len(r.lighting_fixtures) for r in results)
    total_time = sum(r.processing_time_ms for r in results) / 1000

    print()
    print("OVERALL STATISTICS")
    print("=" * 80)
    print(f"Total Sheets: {len(results)}")
    print(f"  Success: {success_count}")
    print(f"  Partial: {partial_count}")
    print(f"  Failed: {failed_count}")
    print()
    print(f"Total Items Extracted:")
    print(f"  Panels: {total_panels}")
    print(f"  Circuits: {total_circuits}")
    print(f"  Equipment: {total_equipment}")
    print(f"  Receptacles: {total_receptacles}")
    print(f"  Lighting Fixtures: {total_fixtures}")
    print()
    print(f"Total Processing Time: {total_time:.1f}s")
    print(f"Average Time per Sheet: {total_time / len(results):.1f}s")
    print()

    return 0 if failed_count == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
