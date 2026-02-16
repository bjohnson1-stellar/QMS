"""
PDF text extraction and AI prompt building for welding forms.

Uses PyMuPDF (fitz) for text extraction from PDF files, then builds
form-type-specific prompts using the form definition registry.
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from qms.core import get_logger

logger = get_logger("qms.welding.extraction.extractor")


def extract_pdf_text(pdf_path: Path) -> str:
    """
    Extract text content from a PDF file using PyMuPDF.

    Args:
        pdf_path: Path to PDF file.

    Returns:
        Extracted text as a single string.

    Raises:
        ImportError: If PyMuPDF is not installed.
        FileNotFoundError: If PDF file doesn't exist.
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        raise ImportError(
            "PyMuPDF is required for PDF extraction. "
            "Install with: pip install PyMuPDF>=1.23.0"
        )

    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    pages: List[str] = []
    with fitz.open(str(pdf_path)) as doc:
        for page_num, page in enumerate(doc):
            text = page.get_text("text")
            if text.strip():
                pages.append(f"--- PAGE {page_num + 1} ---\n{text}")

    full_text = "\n\n".join(pages)
    logger.info("Extracted %d pages, %d chars from %s", len(pages), len(full_text), pdf_path.name)
    return full_text


def extract_pdf_form_fields(pdf_path: Path) -> Dict[str, str]:
    """
    Extract fillable form field values from a PDF (AcroForm fields).

    Args:
        pdf_path: Path to fillable PDF.

    Returns:
        Dict mapping field name to field value.
    """
    try:
        import fitz
    except ImportError:
        raise ImportError("PyMuPDF is required. Install with: pip install PyMuPDF>=1.23.0")

    fields: Dict[str, str] = {}
    with fitz.open(str(pdf_path)) as doc:
        for page in doc:
            widgets = page.widgets()
            if widgets:
                for widget in widgets:
                    name = widget.field_name
                    value = widget.field_value
                    if name and value:
                        fields[name] = str(value)

    logger.info("Extracted %d form fields from %s", len(fields), pdf_path.name)
    return fields


def build_extraction_prompt(raw_text: str, form_type: str,
                            valid_values: Optional[Dict[str, List[str]]] = None) -> str:
    """
    Build an extraction prompt using the form definition registry.

    Args:
        raw_text: Text extracted from PDF.
        form_type: Form type identifier ('wps', 'pqr', etc.).
        valid_values: Valid lookup values for constrained fields.

    Returns:
        Complete prompt string for AI extraction.
    """
    from qms.welding.forms import get_form_definition

    form_def = get_form_definition(form_type)
    values = valid_values or {}

    return form_def.get_extraction_prompt(raw_text, values)


def parse_extraction_response(response_text: str) -> Dict[str, Any]:
    """
    Parse AI model JSON response, handling common formatting issues.

    Args:
        response_text: Raw text response from AI model.

    Returns:
        Parsed JSON data dict.

    Raises:
        ValueError: If response cannot be parsed as valid JSON.
    """
    text = response_text.strip()

    # Strip markdown code fence if present
    if text.startswith("```"):
        # Remove opening fence (with optional language tag)
        text = re.sub(r"^```\w*\n?", "", text)
        # Remove closing fence
        text = re.sub(r"\n?```$", "", text)
        text = text.strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        # Try to find JSON object within the response
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                data = json.loads(match.group())
            except json.JSONDecodeError:
                raise ValueError(f"Could not parse JSON from response: {e}")
        else:
            raise ValueError(f"No JSON object found in response: {e}")

    # Normalize structure: ensure 'parent' key exists
    if "parent" not in data:
        # If the top-level looks like parent data, wrap it
        child_keys = {"processes", "joints", "base_metals", "filler_metals",
                      "positions", "preheat", "pwht", "gas", "electrical",
                      "technique", "pqr_links", "tensile_tests", "bend_tests",
                      "toughness_tests", "other_tests", "personnel", "tests",
                      "flux_atmosphere"}
        parent_data = {k: v for k, v in data.items() if k not in child_keys}
        child_data = {k: v for k, v in data.items() if k in child_keys}
        if parent_data:
            data = {"parent": parent_data, **child_data}

    return data


def detect_form_type(pdf_path: Path, text: Optional[str] = None) -> Optional[str]:
    """
    Auto-detect the form type from filename and/or PDF content.

    Args:
        pdf_path: Path to PDF file.
        text: Optional pre-extracted text (avoids re-extraction).

    Returns:
        Detected form type or None.
    """
    name = pdf_path.stem.upper()

    # Filename-based detection
    if re.match(r"^(WPS|SWPS|PWPS)[-_]", name) or re.search(r"QW[-_]?482", name):
        return "wps"
    if re.match(r"^PQR[-_]", name) or re.search(r"QW[-_]?483", name):
        return "pqr"
    if re.match(r"^(WPQ|WQ|WELDER[-_]QUAL)[-_]", name) or re.search(r"QW[-_]?484", name):
        return "wpq"
    if re.match(r"^BPS[-_]", name) or re.search(r"QB[-_]?482", name):
        return "bps"
    if re.match(r"^(BPQ|BPQR)[-_]", name) or re.search(r"QB[-_]?48[34]", name):
        return "bpq"

    # Content-based detection
    if text:
        text_upper = text[:2000].upper()  # Check first 2000 chars
        if "QW-482" in text_upper or "WELDING PROCEDURE SPECIFICATION" in text_upper:
            return "wps"
        if "QW-483" in text_upper or "PROCEDURE QUALIFICATION RECORD" in text_upper:
            return "pqr"
        if "QW-484" in text_upper or "WELDER PERFORMANCE QUALIFICATION" in text_upper:
            return "wpq"
        if "QB-482" in text_upper or "BRAZING PROCEDURE SPECIFICATION" in text_upper:
            return "bps"
        if "QB-483" in text_upper or "QB-484" in text_upper or "BRAZING PERFORMANCE" in text_upper:
            return "bpq"

    return None
