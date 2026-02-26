"""
Unified QR code generation for QMS documents.

Generates branded QR codes encoding self-contained metadata text.
Used by welding forms (WPS, PQR, WPQ, BPS, BPQ, BPQR) and quality
manual exports. Designed for future URL mode via a ``mode`` parameter.

Usage:
    from qms.core.qrcode import build_metadata, generate_qr

    payload = build_metadata("pqr", {"PQR": "A53-NPS6", "Rev": "0"})
    data_uri = generate_qr(payload)
    # -> "data:image/png;base64,..."
"""

import base64
import io
from typing import Any, Dict, Optional

import qrcode as _qrcode
from qrcode.constants import (
    ERROR_CORRECT_H,
    ERROR_CORRECT_L,
    ERROR_CORRECT_M,
    ERROR_CORRECT_Q,
)

from qms.core.config import get_branding

# ---------------------------------------------------------------------------
# Field ordering templates per document type
# ---------------------------------------------------------------------------

_FIELD_ORDER: Dict[str, list] = {
    "wps": ["WPS", "Rev", "Code", "Process", "Base Metal"],
    "pqr": ["PQR", "Rev", "WPS", "Code", "Process", "Base Metal", "Status"],
    "wpq": ["WPQ", "Welder", "ID", "Process", "WPS", "Qualified Range"],
    "bps": ["BPS", "Rev", "Code", "Process", "Base Metal"],
    "bpq": ["BPQ", "Rev", "Code", "Process"],
    "bpqr": ["BPQR", "Rev", "BPS", "Code", "Process", "Status"],
    "quality_manual": ["Module", "Title", "Version", "Effective"],
}

_ERROR_LEVELS = {
    "L": ERROR_CORRECT_L,
    "M": ERROR_CORRECT_M,
    "Q": ERROR_CORRECT_Q,
    "H": ERROR_CORRECT_H,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_metadata(doc_type: str, fields: Dict[str, Any]) -> str:
    """
    Build a standardized multi-line text payload for a QR code.

    Known fields are emitted first in canonical order for the document type;
    any extra fields are appended alphabetically after them.

    Args:
        doc_type: Document type key (``wps``, ``pqr``, ``wpq``, ``bps``,
            ``bpq``, ``bpqr``, ``quality_manual``).
        fields: Key-value pairs to encode.

    Returns:
        Multi-line ``"Key: Value\\n"`` string.
    """
    ordered_keys = _FIELD_ORDER.get(doc_type, [])

    lines: list[str] = []
    seen: set[str] = set()

    # Emit known fields in canonical order
    for key in ordered_keys:
        if key in fields:
            lines.append(f"{key}: {fields[key]}")
            seen.add(key)

    # Append remaining fields alphabetically
    for key in sorted(fields.keys()):
        if key not in seen:
            lines.append(f"{key}: {fields[key]}")

    return "\n".join(lines)


def generate_qr(
    data: str,
    *,
    fill_color: Optional[str] = None,
    back_color: str = "white",
    box_size: int = 6,
    border: int = 1,
    error_correction: str = "M",
) -> str:
    """
    Generate a QR code and return it as a base64 data URI for HTML ``<img>``.

    Args:
        data: Text payload to encode.
        fill_color: Foreground color (default: branding nav_bg, ``#0C2340``).
        back_color: Background color (default: white).
        box_size: Pixel size per QR module.
        border: Quiet zone width in modules.
        error_correction: Error correction level — ``L``, ``M``, ``Q``, or ``H``.

    Returns:
        ``"data:image/png;base64,..."`` string.
    """
    png_bytes = generate_qr_bytes(
        data,
        fill_color=fill_color,
        back_color=back_color,
        box_size=box_size,
        border=border,
        error_correction=error_correction,
    )
    b64 = base64.b64encode(png_bytes).decode("ascii")
    return f"data:image/png;base64,{b64}"


def generate_qr_bytes(
    data: str,
    *,
    fill_color: Optional[str] = None,
    back_color: str = "white",
    box_size: int = 6,
    border: int = 1,
    error_correction: str = "M",
) -> bytes:
    """
    Generate a QR code and return raw PNG bytes (for PDF embedding).

    Args:
        data: Text payload to encode.
        fill_color: Foreground color (default: branding nav_bg).
        back_color: Background color (default: white).
        box_size: Pixel size per QR module.
        border: Quiet zone width in modules.
        error_correction: Error correction level — ``L``, ``M``, ``Q``, or ``H``.

    Returns:
        PNG image bytes.
    """
    if fill_color is None:
        branding = get_branding()
        fill_color = branding.get("colors", {}).get("nav_bg", "#0C2340")

    level = _ERROR_LEVELS.get(error_correction.upper(), ERROR_CORRECT_M)

    qr = _qrcode.QRCode(
        version=None,  # auto-size
        error_correction=level,
        box_size=box_size,
        border=border,
    )
    qr.add_data(data)
    qr.make(fit=True)

    img = qr.make_image(fill_color=fill_color, back_color=back_color)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
