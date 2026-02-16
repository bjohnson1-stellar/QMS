"""
Template manager and generation orchestration.

Handles template registration, auto-discovery, form data queries,
and dispatching to the appropriate renderer (Excel or PDF).
"""

import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from qms.core import get_config_value, get_db, get_logger, QMS_PATHS
from qms.welding.forms.base import BaseFormDefinition

logger = get_logger("qms.welding.generation.generator")


# ---------------------------------------------------------------------------
# Template registry
# ---------------------------------------------------------------------------

def register_template(form_type: str, format: str, file_path: str | Path,
                      variant: Optional[str] = None, description: Optional[str] = None,
                      is_default: bool = False,
                      conn: Optional[sqlite3.Connection] = None) -> int:
    """
    Register a template file in the weld_form_templates table.

    Args:
        form_type: 'wps', 'pqr', 'wpq', 'bps', 'bpq'.
        format: 'excel' or 'pdf'.
        file_path: Path to template file.
        variant: Optional variant identifier (e.g., WPS number for WPQ templates).
        description: Optional description.
        is_default: Whether this is the default template for the form type + format.
        conn: Optional database connection.

    Returns:
        Template record ID.
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"Template not found: {file_path}")

    own_conn = conn is None
    if own_conn:
        db_ctx = get_db()
        conn = db_ctx.__enter__()

    try:
        # If setting as default, clear other defaults
        if is_default:
            conn.execute(
                "UPDATE weld_form_templates SET is_default = 0 "
                "WHERE form_type = ? AND format = ?",
                (form_type, format),
            )

        cursor = conn.execute(
            """INSERT OR REPLACE INTO weld_form_templates
               (form_type, format, variant, file_path, description, is_default)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (form_type, format, variant, str(file_path), description,
             1 if is_default else 0),
        )
        conn.commit()
        logger.info("Registered template: %s %s %s -> %s",
                     form_type, format, variant or "(default)", file_path)
        return cursor.lastrowid

    finally:
        if own_conn:
            db_ctx.__exit__(None, None, None)


def find_template(form_type: str, format: str, variant: Optional[str] = None,
                  conn: Optional[sqlite3.Connection] = None) -> Optional[Path]:
    """
    Find the best matching template for a form type and format.

    Looks for exact variant match first, then falls back to default.
    """
    own_conn = conn is None
    if own_conn:
        db_ctx = get_db(readonly=True)
        conn = db_ctx.__enter__()

    try:
        # Try exact variant match
        if variant:
            row = conn.execute(
                "SELECT file_path FROM weld_form_templates "
                "WHERE form_type = ? AND format = ? AND variant = ?",
                (form_type, format, variant),
            ).fetchone()
            if row:
                return Path(row[0])

        # Fall back to default template
        row = conn.execute(
            "SELECT file_path FROM weld_form_templates "
            "WHERE form_type = ? AND format = ? AND is_default = 1",
            (form_type, format),
        ).fetchone()
        if row:
            return Path(row[0])

        # Fall back to any template for this form type + format
        row = conn.execute(
            "SELECT file_path FROM weld_form_templates "
            "WHERE form_type = ? AND format = ? ORDER BY id LIMIT 1",
            (form_type, format),
        ).fetchone()
        if row:
            return Path(row[0])

    finally:
        if own_conn:
            db_ctx.__exit__(None, None, None)

    return None


def auto_discover_templates(search_dirs: Optional[List[Path]] = None,
                            conn: Optional[sqlite3.Connection] = None) -> Dict[str, int]:
    """
    Scan directories for template files and auto-register them.

    Searches for Excel and PDF templates matching known naming patterns.

    Returns:
        Dict mapping form_type to count of templates discovered.
    """
    if search_dirs is None:
        raw_data = Path(r"D:\RAW_DATA")
        search_dirs = [
            raw_data / "Welding Information" / "WPQ Templates",
            raw_data / "Welding Information" / "AWS Specifications" / "Sample Forms",
            raw_data / "Welding Information" / "Brazing Procedures",
        ]

    counts: Dict[str, int] = {}

    for search_dir in search_dirs:
        if not search_dir.exists():
            logger.warning("Template search dir not found: %s", search_dir)
            continue

        for path in search_dir.rglob("*"):
            if path.suffix.lower() not in (".xls", ".xlsx", ".pdf"):
                continue
            if path.name.startswith("~"):
                continue

            name = path.stem.upper()
            fmt = "pdf" if path.suffix.lower() == ".pdf" else "excel"

            # Detect form type and variant from filename
            form_type = None
            variant = None

            if "WPQ" in name and "TEMPLATE" in name:
                form_type = "wpq"
                # Extract WPS variant: "WPQ Template CS-01-P1-SMAW 6 inch.xls"
                match = re.search(r"TEMPLATE\s+(.+?)(?:\s+\d+\s*(?:INCH|IN))?$",
                                  name, re.I)
                if match:
                    variant = match.group(1).strip()
            elif "PWPS" in name and "TEMPLATE" in name:
                form_type = "wps"
                variant = "PWPS"
            elif "BPS" in name and "TEMPLATE" in name:
                form_type = "bps"
            elif "WPS" in name:
                form_type = "wps"
            elif "PQR" in name:
                form_type = "pqr"
            elif "WPQ" in name or "TEST.RECORD" in name or "TEST-RECORD" in name:
                form_type = "wpq"
            elif "QB-482" in name or "BPS" in name:
                form_type = "bps"
            elif "QB-483" in name or "QB-484" in name:
                form_type = "bpq"

            if form_type:
                try:
                    register_template(form_type, fmt, path, variant=variant,
                                      description=f"Auto-discovered: {path.name}",
                                      conn=conn)
                    counts[form_type] = counts.get(form_type, 0) + 1
                except Exception as e:
                    logger.warning("Failed to register %s: %s", path, e)

    logger.info("Auto-discovered %d templates", sum(counts.values()))
    return counts


# ---------------------------------------------------------------------------
# Form data queries
# ---------------------------------------------------------------------------

def get_form_data(conn: sqlite3.Connection, form_def: BaseFormDefinition,
                  identifier: str) -> Optional[Dict[str, Any]]:
    """
    Query all parent + child table data for a form record.

    Args:
        conn: Database connection.
        form_def: Form definition.
        identifier: Document identifier.

    Returns:
        Dict with 'parent' and child section data, or None if not found.
    """
    from qms.welding.extraction.loader import find_existing_record

    parent = find_existing_record(conn, form_def, identifier)
    if not parent:
        return None

    parent_id = parent["id"]
    result: Dict[str, Any] = {"parent": parent}

    # Query each child table
    fk_col_map = {
        "wps": "wps_id",
        "pqr": "pqr_id",
        "wpq": "wpq_id",
        "bps": "bps_id",
        "bpq": "bpq_id",
    }
    fk_col = fk_col_map.get(form_def.form_type)

    for child_table in form_def.child_tables:
        try:
            rows = conn.execute(
                f"SELECT * FROM {child_table} WHERE {fk_col} = ?",
                (parent_id,),
            ).fetchall()
            # Use the suffix as section name (e.g., weld_wps_processes -> processes)
            section_name = child_table.replace(f"weld_{form_def.form_type}_", "")
            result[section_name] = [dict(r) for r in rows]
        except Exception as e:
            logger.warning("Could not query %s: %s", child_table, e)
            section_name = child_table.replace(f"weld_{form_def.form_type}_", "")
            result[section_name] = []

    return result


# ---------------------------------------------------------------------------
# Main generation entry point
# ---------------------------------------------------------------------------

def generate(form_type: str, identifier: str,
             output_format: str = "excel",
             output_dir: Optional[Path] = None) -> Optional[Path]:
    """
    Generate a filled-out form from database data.

    Args:
        form_type: 'wps', 'pqr', 'wpq', 'bps', 'bpq'.
        identifier: Document identifier (e.g., 'CS-01', 'WPQ-001').
        output_format: 'excel', 'pdf', or 'both'.
        output_dir: Output directory (defaults to config).

    Returns:
        Path to generated file, or None on failure.
    """
    from qms.welding.forms import get_form_definition
    from qms.welding.generation.excel_renderer import render_excel
    from qms.welding.generation.pdf_renderer import render_pdf

    form_def = get_form_definition(form_type)

    if output_dir is None:
        base_dir = get_config_value("welding", "forms", "generation", "output_dir",
                                    default="data/quality-documents/Welding")
        output_dir = QMS_PATHS._resolve(base_dir) / form_type.upper()
    else:
        output_dir = Path(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)

    # Get data from database
    with get_db(readonly=True) as conn:
        form_data = get_form_data(conn, form_def, identifier)

    if not form_data:
        logger.error("No data found for %s '%s'", form_type, identifier)
        return None

    outputs: List[Path] = []

    # Determine WPS variant for WPQ template selection
    variant = None
    if form_type == "wpq":
        variant = form_data.get("parent", {}).get("wps_number")

    if output_format in ("excel", "both"):
        with get_db(readonly=True) as conn:
            template = find_template(form_type, "excel", variant=variant, conn=conn)
        if template and template.exists():
            safe_id = re.sub(r'[<>:"/\\|?*]', '_', identifier)
            output_path = output_dir / f"{safe_id}.xlsx"
            result = render_excel(template, form_data, output_path, form_def)
            if result:
                outputs.append(result)
                logger.info("Generated Excel: %s", result)
        else:
            logger.warning("No Excel template found for %s (variant=%s)", form_type, variant)

    if output_format in ("pdf", "both"):
        with get_db(readonly=True) as conn:
            template = find_template(form_type, "pdf", variant=variant, conn=conn)
        if template and template.exists():
            safe_id = re.sub(r'[<>:"/\\|?*]', '_', identifier)
            output_path = output_dir / f"{safe_id}.pdf"
            result = render_pdf(template, form_data, output_path, form_def)
            if result:
                outputs.append(result)
                logger.info("Generated PDF: %s", result)
        else:
            logger.warning("No PDF template found for %s (variant=%s)", form_type, variant)

    return outputs[0] if outputs else None
