"""
Civil drawing extraction for storm/sewer profiles, utility plans, and site drawings.

Extracts structured data from civil engineering drawings:
- Utility lines (storm, sewer, water, gas, electric, etc.)
- Manholes and drainage structures
- Spot elevations and contours
- Dimensions and control points
- Grid lines and reference points
"""

import json
import re
from typing import Any, Dict, List

from qms.core import get_db, get_logger
from qms.pipeline.extractor import (
    extract_pdf_text,
    call_model,
    parse_extraction_response,
)

logger = get_logger("qms.pipeline.civil_extractor")


def build_civil_prompt(text: str, drawing_type: str) -> str:
    """
    Build extraction prompt for civil drawings.

    Args:
        text: Extracted text from drawing.
        drawing_type: Specific civil drawing type.

    Returns:
        Extraction prompt for AI model.
    """
    if "PROFILE" in drawing_type.upper() or "STORM" in drawing_type.upper() or "SEWER" in drawing_type.upper():
        return _build_storm_sewer_prompt(text)
    elif "UTILITY" in drawing_type.upper() or "GEOMETRY" in drawing_type.upper():
        return _build_utility_geometry_prompt(text)
    elif "EXISTING" in drawing_type.upper() or "CONDITIONS" in drawing_type.upper():
        return _build_existing_conditions_prompt(text)
    else:
        return _build_generic_civil_prompt(text)


def _build_storm_sewer_prompt(text: str) -> str:
    """Build extraction prompt for storm and sewer pipe profiles."""
    return f"""Extract all storm and sewer utility data from this civil drawing profile.

DRAWING TEXT:
{text}

For each UTILITY LINE (storm/sewer pipe), provide:
- Line type (e.g., "Storm", "Sanitary Sewer", "Water", "Gas")
- Size (pipe diameter, e.g., "12\"", "18\"", "24\"")
- Material (e.g., "PVC", "HDPE", "Ductile Iron", "RCP")
- From location (station/manhole ID)
- To location (station/manhole ID)
- Length (in feet, if shown)
- Slope (percent grade, e.g., "0.50%", "1.2%")
- Depth or invert elevation (if shown)

For each MANHOLE or DRAINAGE STRUCTURE, provide:
- Manhole ID (e.g., "MH-1", "MH-2", "CB-1", "INLET-1")
- Type (e.g., "Manhole", "Catch Basin", "Inlet", "Junction Box")
- Rim elevation (top of structure, in feet)
- Invert IN elevation (incoming pipe invert, in feet)
- Invert OUT elevation (outgoing pipe invert, in feet)
- Depth (in feet, if calculable from rim and invert)
- Diameter or size (if shown)
- Grid reference or station number

For each SPOT ELEVATION shown:
- Location description (e.g., "Top of Curb", "Finish Grade", "Existing Grade")
- Elevation value (in feet)
- Grid reference or station

Return as JSON in this format:
{{
  "utility_lines": [
    {{
      "line_type": "Storm",
      "size": "18\\"",
      "material": "RCP",
      "from_location": "MH-1",
      "to_location": "MH-2",
      "length_ft": 125.5,
      "slope_percent": 0.5,
      "depth_ft": 8.5,
      "confidence": 0.92
    }}
  ],
  "manholes": [
    {{
      "manhole_id": "MH-1",
      "manhole_type": "Manhole",
      "rim_elevation": 425.8,
      "invert_in_elevation": 417.3,
      "invert_out_elevation": 417.0,
      "depth_ft": 8.5,
      "diameter": "48\\"",
      "grid_reference": "STA 1+00",
      "confidence": 0.90
    }}
  ],
  "spot_elevations": [
    {{
      "location_description": "Top of Curb",
      "elevation": 428.5,
      "grid_reference": "STA 2+50",
      "confidence": 0.95
    }}
  ],
  "drainage_features": [
    {{
      "feature_id": "CB-1",
      "feature_type": "Catch Basin",
      "rim_elevation": 426.2,
      "invert_elevation": 418.5,
      "size": "24\\"x24\\"",
      "grid_reference": "STA 3+00",
      "confidence": 0.88
    }}
  ]
}}

IMPORTANT:
- If you cannot read a value clearly, reduce confidence and include what you can read
- Look for profile views showing pipe slopes and elevations
- Station numbers are critical for locating features (e.g., "STA 1+25.5")
- Invert elevations are the bottom inside of the pipe
- Rim elevations are the top of ground/pavement
"""


def _build_utility_geometry_prompt(text: str) -> str:
    """Build extraction prompt for utility and geometry detail sheets."""
    return f"""Extract utility connection details and geometric dimensions from this civil detail sheet.

DRAWING TEXT:
{text}

For each UTILITY CONNECTION or detail, provide:
- Connection ID (if labeled)
- Connection type (e.g., "Water Service", "Gas Service", "Electric Service")
- Size (pipe/conduit size)
- Utility type (Water, Gas, Electric, Telecom, etc.)
- Material specification
- Notes about installation or requirements

For each DIMENSION or CONTROL MEASUREMENT, provide:
- Dimension type (e.g., "Offset", "Depth", "Width", "Radius")
- Value (in feet or inches)
- From point (reference location)
- To point (target location)
- Description

For each DETAIL DRAWING, provide:
- Detail number (e.g., "1", "2", "A")
- Detail title
- Description of what is shown
- Any material specifications
- Any critical dimensions

Return as JSON in this format:
{{
  "utility_connections": [
    {{
      "connection_id": "WS-1",
      "connection_type": "Water Service",
      "size": "2\\"",
      "utility_type": "Water",
      "material": "Ductile Iron",
      "notes": "Connect to existing main",
      "confidence": 0.90
    }}
  ],
  "dimensions": [
    {{
      "dimension_type": "Offset",
      "value": 5.0,
      "unit": "ft",
      "from_point": "Building Face",
      "to_point": "Water Line",
      "description": "Minimum clearance",
      "confidence": 0.95
    }}
  ],
  "details": [
    {{
      "detail_number": "1",
      "detail_title": "Trench Detail",
      "description": "Typical utility trench cross-section",
      "materials": "Bedding: 6\\" crushed stone",
      "confidence": 0.88
    }}
  ]
}}
"""


def _build_existing_conditions_prompt(text: str) -> str:
    """Build extraction prompt for existing conditions plans."""
    return f"""Extract existing site features and conditions from this civil drawing.

DRAWING TEXT:
{text}

For each EXISTING UTILITY shown, provide:
- Utility type (e.g., "Storm", "Sanitary", "Water", "Gas", "Electric", "Telecom")
- Description (e.g., "8\\" Storm Line", "6\\" Water Main")
- Owner (e.g., "City", "County", "Private", utility company name)
- Location description
- Size if shown

For each SITE FEATURE or condition, provide:
- Feature type (e.g., "Building", "Pavement", "Tree", "Fence", "Curb")
- Description
- Location or grid reference
- Elevation if shown

For each PROPERTY BOUNDARY or EASEMENT, provide:
- Type (e.g., "Property Line", "Easement", "Right-of-Way")
- Description
- Dimensions or area
- Recording reference if shown

For each BENCHMARK or CONTROL POINT, provide:
- Point ID
- Elevation
- Datum (e.g., "NAVD88", "NGVD29")
- Description

Return as JSON in this format:
{{
  "utilities": [
    {{
      "utility_type": "Storm",
      "description": "12\\" Storm Sewer",
      "owner": "City",
      "location_description": "Along Main Street",
      "size": "12\\"",
      "confidence": 0.85
    }}
  ],
  "site_features": [
    {{
      "feature_type": "Building",
      "description": "Existing warehouse building",
      "location": "Grid A-1 to C-5",
      "elevation": 425.0,
      "confidence": 0.90
    }}
  ],
  "boundaries": [
    {{
      "type": "Property Line",
      "description": "North property boundary",
      "area_acres": 5.25,
      "recording_reference": "Book 1234, Page 567",
      "confidence": 0.92
    }}
  ],
  "benchmarks": [
    {{
      "benchmark_id": "BM-1",
      "elevation": 432.15,
      "datum": "NAVD88",
      "description": "Nail in power pole",
      "confidence": 0.95
    }}
  ]
}}
"""


def _build_generic_civil_prompt(text: str) -> str:
    """Build generic civil extraction prompt."""
    return f"""Extract civil engineering data from this drawing.

DRAWING TEXT:
{text}

Extract any identifiable:
- Utility lines (type, size, material, locations)
- Manholes, catch basins, or drainage structures
- Spot elevations and benchmarks
- Dimensions and measurements
- Grid lines and control points

Return as structured JSON with appropriate arrays.
"""


def classify_civil_drawing(text: str, file_name: str) -> str:
    """
    Classify civil drawing type.

    Args:
        text: Extracted text from drawing.
        file_name: File name for hints.

    Returns:
        Drawing type string.
    """
    text_upper = text.upper()
    fname_upper = file_name.upper()

    if "PROFILE" in fname_upper or ("STORM" in fname_upper and "SEWER" in fname_upper):
        return "Civil - Storm/Sewer Profile"
    elif "UTILITY" in fname_upper and "GEOMETRY" in fname_upper:
        return "Civil - Utility/Geometry Details"
    elif "EXISTING" in fname_upper and "CONDITIONS" in fname_upper:
        return "Civil - Existing Conditions"
    elif "GRADING" in fname_upper or "GRADING" in text_upper:
        return "Civil - Grading Plan"
    elif "SITE" in fname_upper and "PLAN" in fname_upper:
        return "Civil - Site Plan"
    else:
        return "Civil - General"


def store_civil_extraction(conn, sheet_id: int, data: Dict[str, Any]) -> Dict[str, int]:
    """
    Store extracted civil data in database.

    Args:
        conn: Database connection.
        sheet_id: Sheet ID from sheets table.
        data: Extracted data dictionary.

    Returns:
        Counts of items stored by type.
    """
    counts = {
        "utility_lines": 0,
        "manholes": 0,
        "drainage_features": 0,
        "spot_elevations": 0,
        "dimensions": 0,
        "connections": 0,
        "details": 0,
        "utilities": 0,
        "site_features": 0,
        "boundaries": 0,
        "benchmarks": 0,
    }

    # Store utility lines
    for line in data.get("utility_lines", []):
        try:
            conn.execute("""
                INSERT INTO civil_utility_lines (
                    sheet_id, line_type, size, material, from_location,
                    to_location, length_ft, slope_percent, depth_ft,
                    confidence
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                sheet_id,
                line.get("line_type"),
                line.get("size"),
                line.get("material"),
                line.get("from_location"),
                line.get("to_location"),
                line.get("length_ft"),
                line.get("slope_percent"),
                line.get("depth_ft"),
                line.get("confidence", 1.0),
            ))
            counts["utility_lines"] += 1
        except Exception as e:
            logger.error("Failed to insert utility line: %s", e)

    # Store manholes
    for mh in data.get("manholes", []):
        try:
            conn.execute("""
                INSERT INTO civil_manholes (
                    sheet_id, manhole_id, manhole_type, rim_elevation,
                    invert_in_elevation, invert_out_elevation, depth_ft,
                    diameter, grid_reference, confidence
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                sheet_id,
                mh.get("manhole_id"),
                mh.get("manhole_type"),
                mh.get("rim_elevation"),
                mh.get("invert_in_elevation"),
                mh.get("invert_out_elevation"),
                mh.get("depth_ft"),
                mh.get("diameter"),
                mh.get("grid_reference"),
                mh.get("confidence", 1.0),
            ))
            counts["manholes"] += 1
        except Exception as e:
            logger.error("Failed to insert manhole %s: %s", mh.get("manhole_id"), e)

    # Store drainage features
    for feat in data.get("drainage_features", []):
        try:
            conn.execute("""
                INSERT INTO civil_drainage_features (
                    sheet_id, feature_id, feature_type, rim_elevation,
                    invert_elevation, size, grid_reference, confidence
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                sheet_id,
                feat.get("feature_id"),
                feat.get("feature_type"),
                feat.get("rim_elevation"),
                feat.get("invert_elevation"),
                feat.get("size"),
                feat.get("grid_reference"),
                feat.get("confidence", 1.0),
            ))
            counts["drainage_features"] += 1
        except Exception as e:
            logger.error("Failed to insert drainage feature %s: %s", feat.get("feature_id"), e)

    # Store spot elevations
    for elev in data.get("spot_elevations", []):
        try:
            conn.execute("""
                INSERT INTO civil_spot_elevations (
                    sheet_id, location_description, elevation,
                    grid_reference, confidence
                ) VALUES (?, ?, ?, ?, ?)
            """, (
                sheet_id,
                elev.get("location_description"),
                elev.get("elevation"),
                elev.get("grid_reference"),
                elev.get("confidence", 1.0),
            ))
            counts["spot_elevations"] += 1
        except Exception as e:
            logger.error("Failed to insert spot elevation: %s", e)

    # Store dimensions
    for dim in data.get("dimensions", []):
        try:
            conn.execute("""
                INSERT INTO civil_dimension_control (
                    sheet_id, dimension_type, dimension_value, dimension_units,
                    from_point, to_point, description, confidence
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                sheet_id,
                dim.get("dimension_type"),
                dim.get("value"),
                dim.get("unit", "feet"),
                dim.get("from_point"),
                dim.get("to_point"),
                dim.get("description"),
                dim.get("confidence", 1.0),
            ))
            counts["dimensions"] += 1
        except Exception as e:
            logger.error("Failed to insert dimension: %s", e)

    # Store utility connections
    for conn_item in data.get("utility_connections", []):
        try:
            conn.execute("""
                INSERT INTO civil_utility_connections (
                    sheet_id, connection_id, connection_type, size,
                    utility_type, notes, confidence
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                sheet_id,
                conn_item.get("connection_id"),
                conn_item.get("connection_type"),
                conn_item.get("size"),
                conn_item.get("utility_type"),
                conn_item.get("notes"),
                conn_item.get("confidence", 1.0),
            ))
            counts["connections"] += 1
        except Exception as e:
            logger.error("Failed to insert utility connection: %s", e)

    # Store detail drawings
    for detail in data.get("details", []):
        try:
            conn.execute("""
                INSERT INTO drawing_details (
                    sheet_id, detail_id, detail_title, description,
                    materials, dimensions, confidence
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                sheet_id,
                detail.get("detail_number"),
                detail.get("detail_title"),
                detail.get("description"),
                detail.get("materials"),
                detail.get("critical_dimensions"),
                detail.get("confidence", 1.0),
            ))
            counts["details"] += 1
        except Exception as e:
            logger.error("Failed to insert detail: %s", e)

    # Store existing utilities (from existing conditions plans)
    for util in data.get("utilities", []):
        try:
            conn.execute("""
                INSERT INTO survey_utilities (
                    sheet_id, utility_type, description, owner,
                    location_description, confidence
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                sheet_id,
                util.get("utility_type"),
                util.get("description"),
                util.get("owner"),
                util.get("location_description"),
                util.get("confidence", 1.0),
            ))
            counts["utilities"] += 1
        except Exception as e:
            logger.error("Failed to insert existing utility: %s", e)

    # Store site features
    for feat in data.get("site_features", []):
        try:
            conn.execute("""
                INSERT INTO survey_site_features (
                    sheet_id, feature_type, description, elevation,
                    location_description, confidence
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                sheet_id,
                feat.get("feature_type"),
                feat.get("description"),
                feat.get("elevation"),
                feat.get("location"),
                feat.get("confidence", 1.0),
            ))
            counts["site_features"] += 1
        except Exception as e:
            logger.error("Failed to insert site feature: %s", e)

    # Store property boundaries
    for boundary in data.get("boundaries", []):
        try:
            if boundary.get("type") == "Property Line":
                conn.execute("""
                    INSERT INTO survey_property_boundaries (
                        sheet_id, area_acres, description,
                        recording_reference, confidence
                    ) VALUES (?, ?, ?, ?, ?)
                """, (
                    sheet_id,
                    boundary.get("area_acres"),
                    boundary.get("description"),
                    boundary.get("recording_reference"),
                    boundary.get("confidence", 1.0),
                ))
            else:  # Easement
                conn.execute("""
                    INSERT INTO survey_easements (
                        sheet_id, easement_type, description,
                        recording_reference, confidence
                    ) VALUES (?, ?, ?, ?, ?)
                """, (
                    sheet_id,
                    boundary.get("type"),
                    boundary.get("description"),
                    boundary.get("recording_reference"),
                    boundary.get("confidence", 1.0),
                ))
            counts["boundaries"] += 1
        except Exception as e:
            logger.error("Failed to insert boundary: %s", e)

    # Store benchmarks
    for bm in data.get("benchmarks", []):
        try:
            conn.execute("""
                INSERT INTO survey_benchmarks (
                    sheet_id, benchmark_id, elevation, datum,
                    description, confidence
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                sheet_id,
                bm.get("benchmark_id"),
                bm.get("elevation"),
                bm.get("datum"),
                bm.get("description"),
                bm.get("confidence", 1.0),
            ))
            counts["benchmarks"] += 1
        except Exception as e:
            logger.error("Failed to insert benchmark: %s", e)

    return counts


def extract_civil_drawing(sheet_id: int, file_path: str, dry_run: bool = False) -> Dict[str, Any]:
    """
    Extract data from a civil drawing.

    Args:
        sheet_id: Sheet ID from database.
        file_path: Path to PDF file.
        dry_run: If True, don't write to database.

    Returns:
        Dictionary with extraction results.
    """
    import time
    from pathlib import Path

    start_time = time.time()

    # Get sheet info
    with get_db(readonly=True) as conn:
        row = conn.execute(
            "SELECT drawing_number, file_name FROM sheets WHERE id = ?",
            (sheet_id,)
        ).fetchone()
        if not row:
            raise ValueError(f"Sheet ID {sheet_id} not found")

        drawing_number = row["drawing_number"]
        file_name = row["file_name"]

    logger.info("Extracting civil drawing: %s (sheet %d)", drawing_number, sheet_id)

    # Extract text from PDF
    pdf_path = Path(file_path)
    if not pdf_path.exists():
        return {
            "status": "failed",
            "error": f"File not found: {file_path}",
        }

    text = extract_pdf_text(pdf_path)
    if not text.strip():
        return {
            "status": "failed",
            "error": "No text extracted from PDF",
        }

    # Classify drawing type
    drawing_type = classify_civil_drawing(text, file_name)
    logger.info("Classified as: %s", drawing_type)

    # Build prompt and extract
    prompt = build_civil_prompt(text, drawing_type)
    response = call_model(prompt, "sonnet")
    data = parse_extraction_response(response)

    # Calculate totals
    total_items = sum([
        len(data.get("utility_lines", [])),
        len(data.get("manholes", [])),
        len(data.get("drainage_features", [])),
        len(data.get("spot_elevations", [])),
        len(data.get("dimensions", [])),
        len(data.get("utility_connections", [])),
        len(data.get("details", [])),
        len(data.get("utilities", [])),
        len(data.get("site_features", [])),
        len(data.get("boundaries", [])),
        len(data.get("benchmarks", [])),
    ])

    logger.info("Extracted %d total items", total_items)

    # Store in database
    if not dry_run:
        with get_db() as conn:
            counts = store_civil_extraction(conn, sheet_id, data)

            # Update sheet record
            conn.execute("""
                UPDATE sheets
                SET extracted_at = CURRENT_TIMESTAMP,
                    drawing_type = ?,
                    extraction_model = 'sonnet',
                    quality_score = 0.85
                WHERE id = ?
            """, (drawing_type, sheet_id))

            conn.commit()

            logger.info("Stored: %s", counts)
    else:
        counts = {
            k: len(data.get(k, []))
            for k in ["utility_lines", "manholes", "drainage_features",
                     "spot_elevations", "dimensions"]
        }
        logger.info("[DRY RUN] Would store: %s", counts)

    processing_time_ms = int((time.time() - start_time) * 1000)

    return {
        "status": "success",
        "sheet_id": sheet_id,
        "drawing_number": drawing_number,
        "drawing_type": drawing_type,
        "total_items": total_items,
        "counts": counts,
        "processing_time_ms": processing_time_ms,
    }
