"""
Direct form-field extraction for fillable ASME QW-484 WPQ PDFs.

Reads PDF form widgets (fillable fields) and maps them to ``weld_wpq``
database columns.  No AI calls needed — this is a deterministic mapping
of the 76 standard QW-484 form fields.

Usage::

    data = extract_wpq_form_fields(pdf_path)
    # data = {"parent": {...}, "tests": [...]}

Returns data in the same dict structure as the AI pipeline so it can
be fed directly to ``loader.load_to_database()``.
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from qms.core import get_logger

logger = get_logger("qms.welding.extraction.form_fields")


# ---------------------------------------------------------------------------
# Numeric parsing helpers
# ---------------------------------------------------------------------------

_NUM_RE = re.compile(r"[+-]?\d*\.?\d+")


def _parse_float(text: str) -> Optional[float]:
    """Extract a numeric value from text like '.218"', '..218', '0.436" Max.'."""
    if not text:
        return None
    m = _NUM_RE.search(text)
    if m:
        try:
            return float(m.group())
        except ValueError:
            return None
    return None


def _parse_thickness_range(text: str) -> Tuple[Optional[float], Optional[float]]:
    """
    Parse a thickness range like '.0625" to .436"'.

    Returns (min, max) or (None, None) if unparseable.
    """
    if not text:
        return None, None
    nums = _NUM_RE.findall(text)
    if len(nums) >= 2:
        try:
            return float(nums[0]), float(nums[1])
        except ValueError:
            return None, None
    if len(nums) == 1:
        val = float(nums[0])
        low = text.lower()
        if "max" in low:
            return None, val
        if "min" in low:
            return val, None
        return None, val
    return None, None


def _parse_diameter_range(text: str) -> Tuple[Optional[float], Optional[float]]:
    """
    Parse a diameter range like 'Over 1" Diameter' or '2.875" to Unlimited'.

    Returns (min, max).  ``None`` means unlimited.
    """
    if not text:
        return None, None
    low = text.lower()
    nums = _NUM_RE.findall(text)

    if "unlimited" in low or "over" in low:
        if nums:
            return float(nums[0]), None
        return None, None

    if len(nums) >= 2:
        return float(nums[0]), float(nums[1])

    if len(nums) == 1:
        return float(nums[0]), None

    return None, None


def _clean(text: str) -> str:
    """Strip whitespace and normalize internal spacing."""
    if not text:
        return ""
    return " ".join(text.split())


# ---------------------------------------------------------------------------
# QW-484 form field name → DB column mapping
# ---------------------------------------------------------------------------

def _map_parent_fields(fields: Dict[str, str]) -> Dict[str, Any]:
    """
    Map QW-484 form fields to ``weld_wpq`` column values.

    The ``fields`` dict uses form field names as keys and stripped
    field values as values.
    """
    parent: Dict[str, Any] = {}

    # --- Header ---
    parent["welder_name"] = _clean(fields.get("Test Description", ""))
    parent["welder_stamp"] = _clean(fields.get("Identification No", ""))

    # WPS — field '1'; sometimes has extra text like "(ER70S-2 / E7018)"
    raw_wps = _clean(fields.get("1", ""))
    # Strip parenthetical filler info that appears in combo-process WPS entries
    wps_cleaned = re.sub(r"\s*\(.*?\)\s*", " ", raw_wps).strip()
    # Collapse spaces around slashes and hyphens
    wps_cleaned = re.sub(r"\s*/\s*", "/", wps_cleaned)
    wps_cleaned = re.sub(r"\s*-\s*", "-", wps_cleaned)
    # Remove trailing whitespace artifacts
    wps_cleaned = wps_cleaned.strip(" -")
    parent["wps_number"] = wps_cleaned

    parent["coupon_base_metal"] = _clean(fields.get("2", ""))
    parent["process_type"] = _clean(fields.get("Welding Processes", ""))
    parent["process_variation"] = _clean(fields.get("Type", ""))

    # Coupon thickness — header value
    t = _parse_float(fields.get("Thickness", ""))
    parent["coupon_thickness"] = t

    # Coupon diameter — actual values row 2
    parent["coupon_diameter"] = _clean(fields.get("Actual Values 2", ""))

    # --- Actual Values (15 rows) ---
    parent["backing_actual"] = _clean(fields.get("Actual Values 1", ""))
    # Actual Values 2 = coupon_diameter (mapped above)
    parent["p_number_actual"] = _clean(fields.get("Actual Values 3", ""))
    # Actual Values 4 = base metal thickness actual (same as coupon_thickness)
    parent["filler_sfa_spec"] = _clean(fields.get("Actual Values 5", ""))
    parent["filler_aws_class"] = _clean(fields.get("Actual Values 6", ""))
    parent["f_number_actual"] = _clean(fields.get("Actual Values 7", ""))
    parent["consumable_insert"] = _clean(fields.get("Actual Values 8", ""))
    parent["filler_type"] = _clean(fields.get("Actual Values 9", ""))
    parent["deposit_thickness_actual"] = _parse_float(
        fields.get("Actual Values 10", ""))
    parent["test_position"] = _clean(fields.get("Actual Values 11", ""))
    parent["progression"] = _clean(fields.get("Actual Values 12", ""))
    parent["backing_gas"] = _clean(fields.get("Actual Values 13", ""))
    parent["transfer_mode"] = _clean(fields.get("Actual Values 14", ""))
    parent["current_type"] = _clean(fields.get("Actual Values 15", ""))

    # --- Range Qualified ---
    parent["backing_type"] = _clean(fields.get("Range Qualified 1", ""))

    # Diameter range — Range Qualified 2
    d_min, d_max = _parse_diameter_range(fields.get("Range Qualified 2", ""))
    parent["diameter_qualified_min"] = d_min
    parent["diameter_qualified_max"] = d_max

    parent["p_number_qualified"] = _clean(fields.get("Range Qualified 3", ""))

    # Thickness range — Range Qualified 4
    t_min, t_max = _parse_thickness_range(fields.get("Range Qualified 4", ""))
    parent["thickness_qualified_min"] = t_min
    parent["thickness_qualified_max"] = t_max

    # Range Qualified rows 5-9 use generic field names '1_2' through '9'
    parent["f_number_qualified"] = _clean(fields.get("1_2", ""))
    # '2_2' = consumable insert qualified (no dedicated column, skip)
    parent["filler_type_qualified"] = _clean(fields.get("3", ""))
    parent["deposit_thickness_max"] = _parse_float(fields.get("4", ""))
    parent["groove_positions_qualified"] = _clean(fields.get("5", ""))
    # Field '6' = progression qualified (use if actual progression is empty)
    prog_qual = _clean(fields.get("6", ""))
    if not parent["progression"] and prog_qual:
        parent["progression"] = prog_qual

    # --- Personnel ---
    parent["evaluator_name"] = _clean(fields.get("1_3", ""))
    parent["evaluator_company"] = _clean(fields.get("Company", ""))
    parent["lab_name"] = _clean(fields.get("2_3", ""))
    parent["lab_test_number"] = _clean(fields.get("Laboratory Test No", ""))
    parent["witness_name"] = _clean(
        fields.get("Welding Supervised Witnessed By", ""))
    parent["witness_company"] = _clean(fields.get("Company_2", ""))
    parent["organization"] = _clean(fields.get("Organization", ""))

    # Date — may be test date and/or certification date
    raw_date = _clean(fields.get("Date", ""))
    parent["test_date"] = _normalize_date(raw_date)
    parent["certified_date"] = parent["test_date"]

    parent["certified_by"] = _clean(fields.get("By", ""))

    parent["status"] = "active"

    # --- Generate WPQ number ---
    stamp = parent.get("welder_stamp", "")
    wps = parent.get("wps_number", "")
    if stamp and wps:
        parent["wpq_number"] = f"{stamp}-{wps}"
    elif stamp and parent.get("process_type"):
        parent["wpq_number"] = f"{stamp}-{parent['process_type']}"
    else:
        parent["wpq_number"] = stamp or "UNKNOWN"

    # Strip empty string values to None for cleaner DB storage
    for k, v in parent.items():
        if isinstance(v, str) and not v:
            parent[k] = None

    return parent


def _normalize_date(raw: str) -> Optional[str]:
    """
    Normalize dates like '6/2/2022' or '03/03/2025' to ISO 'YYYY-MM-DD'.

    Returns None if unparseable.
    """
    if not raw:
        return None
    # Try M/D/YYYY or MM/DD/YYYY
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", raw)
    if m:
        month, day, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return f"{year:04d}-{month:02d}-{day:02d}"
    # Try YYYY-MM-DD already
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", raw)
    if m:
        return raw
    return raw  # Return as-is if no pattern matches


# ---------------------------------------------------------------------------
# Test result extraction
# ---------------------------------------------------------------------------

def _extract_tests(fields: Dict[str, str]) -> List[Dict[str, Any]]:
    """
    Extract test result child records from QW-484 form fields.

    Returns list of dicts suitable for ``weld_wpq_tests`` table.
    """
    tests: List[Dict[str, Any]] = []

    # Visual/RT result — field 'undefined' (Adobe's default for unnamed field)
    visual_result = _clean(fields.get("undefined", ""))
    if visual_result:
        tests.append({
            "test_type": "visual",
            "result": visual_result,
        })

    # Guided bend test rows — 6 type/result pairs in 2 rows × 3 columns
    bend_pairs = [
        ("TypeRow1", "ResultRow1"),
        ("TypeRow1_2", "ResultRow1_2"),
        ("TypeRow1_3", "ResultRow1_3"),
        ("TypeRow2", "ResultRow2"),
        ("TypeRow2_2", "ResultRow2_2"),
        ("TypeRow2_3", "ResultRow2_3"),
    ]
    for type_field, result_field in bend_pairs:
        bend_type = _clean(fields.get(type_field, ""))
        bend_result = _clean(fields.get(result_field, ""))
        if bend_type or bend_result:
            tests.append({
                "test_type": "guided_bend",
                "bend_type": bend_type.lower() if bend_type else None,
                "result": bend_result or None,
            })

    # Fillet weld / fracture test
    fillet_result = _clean(fields.get("Fillet Weld  Fracture Test", ""))
    defects = _clean(fields.get("Length and Percent of Defects", ""))
    if fillet_result or defects:
        tests.append({
            "test_type": "fillet_fracture",
            "result": fillet_result or None,
            "defect_description": defects or None,
        })

    # Macro exam
    macro_result = _clean(fields.get("Macro Exam", ""))
    fillet_size = _parse_float(fields.get("Fillet Sizein", ""))
    concavity = _parse_float(fields.get("Concavity  Convexity in", ""))
    if macro_result or fillet_size is not None:
        tests.append({
            "test_type": "macro",
            "result": macro_result or None,
            "fillet_size": fillet_size,
            "concavity_convexity": concavity,
        })

    # Other tests
    other = _clean(fields.get("Other Tests", ""))
    if other:
        tests.append({
            "test_type": "other",
            "results": other,
        })

    return tests


# ---------------------------------------------------------------------------
# Main extraction function
# ---------------------------------------------------------------------------

def extract_wpq_form_fields(pdf_path: str | Path) -> Optional[Dict[str, Any]]:
    """
    Extract WPQ data from a fillable ASME QW-484 PDF using form widgets.

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        Dict with 'parent' and 'tests' keys (matching AI pipeline format),
        or ``None`` if the PDF has no form fields.
    """
    try:
        import fitz
    except ImportError:
        raise ImportError(
            "PyMuPDF (fitz) is required for form field extraction. "
            "Install with: pip install pymupdf"
        )

    pdf_path = Path(pdf_path)
    doc = fitz.open(str(pdf_path))

    try:
        # Collect all form widgets across all pages
        all_widgets = []
        for page in doc:
            all_widgets.extend(list(page.widgets()))

        if not all_widgets:
            return None  # Not a fillable form

        # Build field name → value dict
        fields: Dict[str, str] = {}
        for w in all_widgets:
            name = w.field_name
            value = (w.field_value or "").strip()
            # For checkboxes, keep 'On' or empty
            if w.field_type_string == "CheckBox":
                fields[name] = value
            else:
                fields[name] = value

        logger.info("Extracted %d form fields from %s", len(fields), pdf_path.name)

        # Map to database structure
        parent = _map_parent_fields(fields)
        parent["file_path"] = str(pdf_path)

        tests = _extract_tests(fields)

        return {
            "parent": parent,
            "tests": tests,
        }

    finally:
        doc.close()


def has_form_fields(pdf_path: str | Path) -> bool:
    """Quick check whether a PDF has fillable form fields."""
    try:
        import fitz
    except ImportError:
        return False

    doc = fitz.open(str(pdf_path))
    try:
        for page in doc:
            if list(page.widgets()):
                return True
        return False
    finally:
        doc.close()
