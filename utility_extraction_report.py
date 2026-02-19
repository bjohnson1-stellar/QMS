"""
Generate extraction report and add notes about extraction quality issues.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from qms.core import get_db, get_logger

logger = get_logger("utility_extraction_report")


def add_extraction_notes():
    """Add extraction notes explaining limitations and issues."""

    notes_data = [
        # Sheet 689 - Limited visibility
        (689, "limited_detail", "Drawing resolution limits detailed schedule reading. Primarily shows piping layout with minimal equipment. More detailed schedules may exist on legend/schedule sheets.", 0.60),

        # Sheet 690 - Partial extraction
        (690, "partial_extraction", "Five hot water heaters (HWH1-HWH5) identified from plan view. Equipment schedules not clearly visible at current resolution. Detailed specifications may require higher resolution scan.", 0.75),

        # Sheet 691 - Equipment tags unclear
        (691, "unclear_tags", "Roof equipment tags partially visible (CZ01, CZ02). Equipment type uncertain - may be chillers, cooling towers, or other rooftop units. Equipment schedules not readable at current resolution.", 0.70),
    ]

    with get_db() as conn:
        # Clear existing notes for these sheets
        conn.execute(
            "DELETE FROM extraction_notes WHERE sheet_id IN (689, 690, 691)"
        )

        # Insert new notes
        for sheet_id, note_type, description, confidence in notes_data:
            conn.execute(
                """INSERT INTO extraction_notes
                   (sheet_id, note_type, description, confidence)
                   VALUES (?, ?, ?, ?)""",
                (sheet_id, note_type, description, confidence)
            )

        conn.commit()

    logger.info("Added extraction notes for all three sheets")


def generate_report():
    """Generate comprehensive extraction report."""

    print("\n" + "="*80)
    print("UTILITY DRAWING EXTRACTION REPORT")
    print("Project: 07609-Freshpet")
    print("Discipline: Utility")
    print("="*80 + "\n")

    with get_db(readonly=True) as conn:
        # Sheet summary
        sheets = conn.execute(
            """SELECT s.id, s.drawing_number, s.title, s.revision,
                      s.extracted_at, s.extraction_model, s.quality_score,
                      COUNT(u.id) as equipment_count
               FROM sheets s
               LEFT JOIN utility_equipment u ON u.sheet_id = s.id
               WHERE s.id IN (689, 690, 691)
               GROUP BY s.id
               ORDER BY s.id"""
        ).fetchall()

        print("SHEET SUMMARY")
        print("-" * 80)
        for sheet in sheets:
            print(f"\nSheet ID: {sheet['id']}")
            print(f"  Drawing: {sheet['drawing_number']} Rev {sheet['revision']}")
            print(f"  Title: {sheet['title']}")
            print(f"  Extracted: {sheet['extracted_at']}")
            print(f"  Model: {sheet['extraction_model']}")
            print(f"  Quality Score: {sheet['quality_score']}")
            print(f"  Equipment Count: {sheet['equipment_count']}")

        # Equipment details
        print("\n" + "-" * 80)
        print("EXTRACTED EQUIPMENT")
        print("-" * 80)

        equipment = conn.execute(
            """SELECT sheet_id, equipment_mark, equipment_type, location,
                      manufacturer, model, capacity, confidence
               FROM utility_equipment
               WHERE sheet_id IN (689, 690, 691)
               ORDER BY sheet_id, equipment_mark"""
        ).fetchall()

        if equipment:
            for eq in equipment:
                print(f"\n[Sheet {eq['sheet_id']}] {eq['equipment_mark']}")
                print(f"  Type: {eq['equipment_type']}")
                print(f"  Location: {eq['location']}")
                if eq['manufacturer']:
                    print(f"  Manufacturer: {eq['manufacturer']}")
                if eq['model']:
                    print(f"  Model: {eq['model']}")
                if eq['capacity']:
                    print(f"  Capacity: {eq['capacity']}")
                print(f"  Confidence: {eq['confidence']}")
        else:
            print("\n(No equipment extracted)")

        # Extraction notes
        print("\n" + "-" * 80)
        print("EXTRACTION NOTES & ISSUES")
        print("-" * 80)

        notes = conn.execute(
            """SELECT sheet_id, note_type, description, confidence
               FROM extraction_notes
               WHERE sheet_id IN (689, 690, 691)
               ORDER BY sheet_id"""
        ).fetchall()

        for note in notes:
            print(f"\n[Sheet {note['sheet_id']}] {note['note_type'].upper()}")
            print(f"  {note['description']}")
            print(f"  Confidence: {note['confidence']}")

        # Statistics
        print("\n" + "="*80)
        print("STATISTICS")
        print("="*80)

        stats = conn.execute(
            """SELECT
                   COUNT(DISTINCT s.id) as total_sheets,
                   COUNT(u.id) as total_equipment,
                   AVG(s.quality_score) as avg_quality,
                   MIN(s.quality_score) as min_quality,
                   MAX(s.quality_score) as max_quality
               FROM sheets s
               LEFT JOIN utility_equipment u ON u.sheet_id = s.id
               WHERE s.id IN (689, 690, 691)"""
        ).fetchone()

        print(f"\nSheets Processed: {stats['total_sheets']}")
        print(f"Equipment Extracted: {stats['total_equipment']}")
        print(f"Average Quality Score: {stats['avg_quality']:.2f}")
        print(f"Quality Range: {stats['min_quality']:.2f} - {stats['max_quality']:.2f}")

        print("\n" + "="*80)
        print("ISSUES ENCOUNTERED")
        print("="*80)
        print("""
1. RESOLUTION LIMITATIONS
   - PDF to PNG conversion at 150 DPI provides good overview but limits
     ability to read detailed equipment schedules and small text
   - Equipment tags on plans are visible but detailed specifications are not
   - Recommendation: Use higher DPI (300+) for schedule-heavy drawings

2. DRAWING TYPE CHARACTERISTICS
   - Sheet 689 (U1161): Partial plan showing primarily piping, minimal equipment
   - Sheet 690 (U1301): Overall plan with equipment locations but schedules unclear
   - Sheet 691 (U1401): Roof plan with equipment outlines but tags partially visible
   - These are plan views, not equipment schedules - need to process legend/
     schedule sheets (U0001) for complete equipment specifications

3. EXTRACTION METHOD
   - Manual vision extraction used due to API authentication limitations
   - Claude Code's vision capabilities can identify equipment locations and tags
   - Full automated extraction would require:
     a) Anthropic API key configuration
     b) Higher resolution images or direct PDF text extraction
     c) Processing of companion schedule sheets with detailed specs

4. CONFIDENCE SCORES
   - Ranged from 0.60 to 0.75
   - Lower confidence reflects uncertainty in equipment details
   - Equipment exists and locations are accurate, but specifications incomplete
        """)

        print("\n" + "="*80)
        print("RECOMMENDATIONS")
        print("="*80)
        print("""
1. Process equipment schedule sheets (U0001 series) to get complete specs
2. For critical equipment, cross-reference with:
   - Mechanical schedules
   - Submittal data
   - Equipment cut sheets
3. Consider re-scanning at higher DPI if original PDFs are low quality
4. Validate equipment tags against mechanical drawings for consistency
5. Future extractions: Use automated pipeline with Anthropic API for:
   - Batch processing
   - Dual-agent cross-checking
   - Automated confidence scoring
        """)

        print("="*80 + "\n")


def main():
    """Generate report and add notes."""

    # Add extraction notes
    add_extraction_notes()

    # Generate report
    generate_report()


if __name__ == "__main__":
    main()
