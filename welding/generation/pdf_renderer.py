"""
PDF form filler for welding forms.

Fills fillable PDF form fields (AcroForm) with data from the database.
Uses PyMuPDF (fitz) which is already a dependency for extraction.
"""

from pathlib import Path
from typing import Any, Dict, Optional

from qms.core import get_logger
from qms.welding.forms.base import BaseFormDefinition

logger = get_logger("qms.welding.generation.pdf_renderer")


def _get_pdf_field_names(pdf_path: Path) -> list[str]:
    """List all fillable field names in a PDF."""
    try:
        import fitz
    except ImportError:
        raise ImportError("PyMuPDF is required. Install with: pip install PyMuPDF>=1.23.0")

    fields = []
    with fitz.open(str(pdf_path)) as doc:
        for page in doc:
            widgets = page.widgets()
            if widgets:
                for widget in widgets:
                    if widget.field_name:
                        fields.append(widget.field_name)
    return fields


def render_pdf(template_path: Path, form_data: Dict[str, Any],
               output_path: Path,
               form_def: Optional[BaseFormDefinition] = None) -> Optional[Path]:
    """
    Fill a fillable PDF template with form data and save to output path.

    Args:
        template_path: Path to fillable PDF template.
        form_data: Dict with 'parent' and child sections.
        output_path: Where to save the filled PDF.
        form_def: Form definition (used for field name resolution).

    Returns:
        Path to output file, or None on failure.
    """
    try:
        import fitz
    except ImportError:
        logger.error("PyMuPDF is required for PDF generation. "
                     "Install with: pip install PyMuPDF>=1.23.0")
        return None

    template_path = Path(template_path)
    output_path = Path(output_path)

    if not template_path.exists():
        logger.error("PDF template not found: %s", template_path)
        return None

    try:
        doc = fitz.open(str(template_path))

        # Build a flat dict of all form data for field matching
        flat_data = _flatten_form_data(form_data, form_def)

        # Get all PDF form fields
        fields_filled = 0
        fields_total = 0

        for page in doc:
            widgets = page.widgets()
            if not widgets:
                continue

            for widget in widgets:
                field_name = widget.field_name
                if not field_name:
                    continue

                fields_total += 1

                # Try exact match, then normalized match
                value = flat_data.get(field_name)
                if value is None:
                    # Try case-insensitive match
                    normalized = field_name.lower().replace(" ", "_").replace("-", "_")
                    value = flat_data.get(normalized)

                if value is None:
                    # Try partial match (field name contains DB column name)
                    for data_key, data_val in flat_data.items():
                        if data_key in field_name.lower() or field_name.lower() in data_key:
                            value = data_val
                            break

                if value is not None:
                    widget.field_value = str(value)
                    widget.update()
                    fields_filled += 1

        # Save
        output_path.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(output_path))
        doc.close()

        logger.info("PDF generated: %s (%d/%d fields filled)",
                     output_path, fields_filled, fields_total)
        return output_path

    except Exception as e:
        logger.error("PDF generation failed for %s: %s", template_path.name, e)
        return None


def _flatten_form_data(form_data: Dict[str, Any],
                       form_def: Optional[BaseFormDefinition] = None) -> Dict[str, str]:
    """
    Flatten hierarchical form data into a single dict for PDF field matching.

    Creates multiple key variations for each value to maximize field matches:
    - table.column format (e.g., "weld_wps.wps_number")
    - column name only (e.g., "wps_number")
    - lowercase versions of both
    """
    flat: Dict[str, str] = {}

    parent = form_data.get("parent", {})
    for key, value in parent.items():
        if value is None or key in ("id", "created_at", "updated_at"):
            continue
        str_val = str(value)
        flat[key] = str_val
        flat[key.lower()] = str_val
        if form_def:
            flat[f"{form_def.parent_table}.{key}"] = str_val

    # Child data — use first row of each section
    for section_name, section_data in form_data.items():
        if section_name == "parent" or not isinstance(section_data, list):
            continue
        if not section_data:
            continue

        first_row = section_data[0]
        for key, value in first_row.items():
            if value is None or key in ("id",):
                continue
            str_val = str(value)
            # Prefix with section name for disambiguation
            flat[f"{section_name}.{key}"] = str_val
            flat[f"{section_name}_{key}"] = str_val
            # Also store without prefix if not already present
            if key not in flat:
                flat[key] = str_val
                flat[key.lower()] = str_val

    return flat


def inspect_pdf_fields(pdf_path: Path) -> list[Dict[str, Any]]:
    """
    Inspect a PDF and return all fillable fields with their properties.
    Useful for creating field mappings for new templates.

    Returns:
        List of dicts with field_name, field_type, field_value, page.
    """
    try:
        import fitz
    except ImportError:
        raise ImportError("PyMuPDF required")

    fields = []
    with fitz.open(str(pdf_path)) as doc:
        for page_num, page in enumerate(doc):
            widgets = page.widgets()
            if not widgets:
                continue

            for widget in widgets:
                fields.append({
                    "field_name": widget.field_name,
                    "field_type": widget.field_type_string,
                    "field_value": widget.field_value,
                    "page": page_num + 1,
                    "rect": list(widget.rect),
                })

    return fields
