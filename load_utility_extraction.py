"""
Load extracted utility equipment data into the database.

Data extracted manually from the three utility plan drawings.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from qms.core import get_db, get_logger

logger = get_logger("load_utility_extraction")


# Extracted data from the three drawings
EXTRACTED_DATA = {
    689: {
        "drawing_number": "U1161",
        "title": "PARTIAL FIRST FLOOR UTILITIES PLAN - AREA 6",
        "revision": "1",
        "equipment": [
            # Equipment tags visible on drawing - limited detail due to resolution
            # This is a partial floor plan showing utility piping but minimal equipment schedules
            # Main equipment appears to be located elsewhere with just piping shown here
        ]
    },
    690: {
        "drawing_number": "U1301",
        "title": "UTILITY OVERALL INTERSTITIAL FLOOR PLAN",
        "revision": "2",
        "equipment": [
            # Equipment tags visible:
            {"equipment_mark": "HWH1", "equipment_type": "Hot Water Heater", "location": "Interstitial Space", "confidence": 0.75},
            {"equipment_mark": "HWH2", "equipment_type": "Hot Water Heater", "location": "Interstitial Space", "confidence": 0.75},
            {"equipment_mark": "HWH3", "equipment_type": "Hot Water Heater", "location": "Interstitial Space", "confidence": 0.75},
            {"equipment_mark": "HWH4", "equipment_type": "Hot Water Heater", "location": "Interstitial Space", "confidence": 0.75},
            {"equipment_mark": "HWH5", "equipment_type": "Hot Water Heater", "location": "Interstitial Space", "confidence": 0.75},
        ]
    },
    691: {
        "drawing_number": "U1401",
        "title": "UTILITY OVERALL ROOF PLAN",
        "revision": "2",
        "equipment": [
            # Equipment tags visible on roof:
            {"equipment_mark": "CZ01", "equipment_type": "Roof Equipment", "location": "Roof", "confidence": 0.70},
            {"equipment_mark": "CZ02", "equipment_type": "Roof Equipment", "location": "Roof", "confidence": 0.70},
        ]
    }
}


def load_equipment_to_db(sheet_id: int, equipment_list: list[dict]) -> int:
    """Load extracted equipment into utility_equipment table."""
    count = 0

    with get_db() as conn:
        # Clear existing equipment for this sheet
        conn.execute("DELETE FROM utility_equipment WHERE sheet_id = ?", (sheet_id,))

        for eq in equipment_list:
            # Build values dict
            values = {
                "sheet_id": sheet_id,
                "equipment_mark": eq.get("equipment_mark", ""),
                "equipment_type": eq.get("equipment_type"),
                "location": eq.get("location"),
                "manufacturer": eq.get("manufacturer"),
                "model": eq.get("model"),
                "capacity": eq.get("capacity"),
                "design_pressure": eq.get("design_pressure"),
                "dimensions": eq.get("dimensions"),
                "weight_lbs": eq.get("weight_lbs"),
                "operating_weight_lbs": eq.get("operating_weight_lbs"),
                "power_voltage": eq.get("power_voltage"),
                "power_hp": eq.get("power_hp"),
                "qty": eq.get("qty", 1),
                "gpm": eq.get("gpm"),
                "temperature_in": eq.get("temperature_in"),
                "temperature_out": eq.get("temperature_out"),
                "pressure_drop_psi": eq.get("pressure_drop_psi"),
                "steam_pressure_psi": eq.get("steam_pressure_psi"),
                "flow_rate_lbs_hr": eq.get("flow_rate_lbs_hr"),
                "inlet_size": eq.get("inlet_size"),
                "outlet_size": eq.get("outlet_size"),
                "specifications": eq.get("specifications"),
                "notes": eq.get("notes"),
                "contact_info": eq.get("contact_info"),
                "confidence": eq.get("confidence", 0.70),
            }

            # Build INSERT
            cols = ", ".join(values.keys())
            placeholders = ", ".join(["?" for _ in values])
            sql = f"INSERT INTO utility_equipment ({cols}) VALUES ({placeholders})"

            conn.execute(sql, list(values.values()))
            count += 1

        # Update sheet extraction status
        conn.execute(
            """UPDATE sheets
               SET extracted_at = CURRENT_TIMESTAMP,
                   extraction_model = 'manual-vision',
                   quality_score = 0.70,
                   drawing_type = 'plan'
               WHERE id = ?""",
            (sheet_id,)
        )

        conn.commit()

    return count


def main():
    """Load all extracted equipment data."""

    total_equipment = 0

    for sheet_id, data in EXTRACTED_DATA.items():
        logger.info(f"\n{'='*80}")
        logger.info(f"Loading Sheet {sheet_id}: {data['drawing_number']} Rev {data['revision']}")
        logger.info(f"Title: {data['title']}")
        logger.info(f"{'='*80}")

        equipment_list = data.get("equipment", [])

        if equipment_list:
            count = load_equipment_to_db(sheet_id, equipment_list)
            total_equipment += count
            logger.info(f"Loaded {count} equipment items")
        else:
            # Still mark as extracted even if no equipment found
            with get_db() as conn:
                conn.execute(
                    """UPDATE sheets
                       SET extracted_at = CURRENT_TIMESTAMP,
                           extraction_model = 'manual-vision',
                           quality_score = 0.60,
                           drawing_type = 'plan'
                       WHERE id = ?""",
                    (sheet_id,)
                )
                conn.commit()
            logger.info("No equipment found on this sheet (piping only)")

    logger.info(f"\n{'='*80}")
    logger.info("EXTRACTION COMPLETE")
    logger.info(f"{'='*80}")
    logger.info(f"Total Equipment Loaded: {total_equipment}")

    # Query summary
    with get_db(readonly=True) as conn:
        for sheet_id in EXTRACTED_DATA.keys():
            row = conn.execute(
                """SELECT s.drawing_number, s.title, s.extracted_at,
                          COUNT(u.id) as eq_count
                   FROM sheets s
                   LEFT JOIN utility_equipment u ON u.sheet_id = s.id
                   WHERE s.id = ?
                   GROUP BY s.id""",
                (sheet_id,)
            ).fetchone()

            if row:
                logger.info(f"  {row['drawing_number']}: {row['eq_count']} equipment items")

    logger.info(f"{'='*80}\n")


if __name__ == "__main__":
    main()
