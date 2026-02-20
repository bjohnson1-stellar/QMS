"""
Quality Manual PDF Export

Renders quality manual modules as professional PDF documents using
WeasyPrint. The HTML+CSS template controls all visual output — this
module only gathers data and passes it to the template.

Usage (Python):
    from qms.qualitydocs.export import export_module_pdf
    path = export_module_pdf(1)

Usage (CLI):
    qms docs export 1
    qms docs export 1 --format html
"""

import os
from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader

from qms.core import get_logger
from qms.core.config import QMS_PATHS, get_branding
from qms.qualitydocs.loader import get_module_detail, get_section_content

logger = get_logger("qms.qualitydocs.export")

# Template directory
_TEMPLATE_DIR = QMS_PATHS.root / "frontend" / "templates" / "qualitydocs"

# Auto-detect MSYS2 GTK DLLs on Windows so users don't have to set env vars
_MSYS2_BIN = Path(r"C:\msys64\mingw64\bin")
if _MSYS2_BIN.is_dir() and "WEASYPRINT_DLL_DIRECTORIES" not in os.environ:
    os.environ["WEASYPRINT_DLL_DIRECTORIES"] = str(_MSYS2_BIN)


def _get_jinja_env() -> Environment:
    """Create a Jinja2 environment for PDF templates (standalone, not Flask)."""
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=True,
    )


def render_module_html(module_number: int) -> str:
    """
    Render a quality manual module as a complete HTML document.

    Queries the database for module metadata, all sections, subsections,
    content blocks, and responsibilities. Combines with branding config
    and renders the pdf_module.html Jinja2 template.

    Args:
        module_number: The module number to render (e.g. 1, 2).

    Returns:
        Complete HTML string ready for WeasyPrint or browser preview.

    Raises:
        ValueError: If the module is not found in the database.
    """
    # 1. Get module-level info (sections list, cross-refs, code-refs)
    module = get_module_detail(module_number)
    if module is None:
        raise ValueError(f"Module {module_number} not found in database")

    # 2. For each section, fetch full content (subsections + blocks)
    sections = []
    for sec in module.get("sections", []):
        content = get_section_content(sec["section_number"])
        if content:
            sections.append(content)

    # 3. Get branding config
    branding = get_branding()

    # 4. Render template
    env = _get_jinja_env()
    template = env.get_template("pdf_module.html")
    html = template.render(
        module=module,
        sections=sections,
        branding=branding,
    )

    logger.info(
        "Rendered HTML for Module %d: %d sections, %d chars",
        module_number,
        len(sections),
        len(html),
    )
    return html


def _default_output_dir() -> Path:
    """Return (and create) the default export output directory."""
    out = QMS_PATHS.quality_documents / "exports"
    out.mkdir(parents=True, exist_ok=True)
    return out


def export_module_pdf(module_number: int, output_path: Optional[str] = None) -> Path:
    """
    Export a quality manual module as a formatted PDF.

    Args:
        module_number: Module number to export.
        output_path: Optional output file path. If None, writes to
            data/quality-documents/exports/Module_{n}_v{ver}.pdf

    Returns:
        Path to the generated PDF file.

    Raises:
        ImportError: If WeasyPrint is not installed.
        ValueError: If the module is not found.
    """
    try:
        from weasyprint import HTML
    except ImportError:
        raise ImportError(
            "WeasyPrint is required for PDF export. "
            'Install it with: pip install -e ".[export]"'
        )

    html_str = render_module_html(module_number)

    # Determine output path
    if output_path:
        out = Path(output_path)
    else:
        module = get_module_detail(module_number)
        version = module["version"] if module else "0"
        out = _default_output_dir() / f"Module_{module_number}_v{version}.pdf"

    # Convert HTML to PDF
    # base_url lets WeasyPrint resolve relative font URLs if any
    HTML(string=html_str, base_url=str(_TEMPLATE_DIR)).write_pdf(str(out))

    logger.info("Exported PDF: %s (%.1f KB)", out, out.stat().st_size / 1024)
    return out


def export_module_pdf_bytes(module_number: int) -> bytes:
    """
    Export a quality manual module as PDF bytes (for web download).

    Args:
        module_number: Module number to export.

    Returns:
        PDF file contents as bytes.

    Raises:
        ImportError: If WeasyPrint is not installed.
        ValueError: If the module is not found.
    """
    try:
        from weasyprint import HTML
    except ImportError:
        raise ImportError(
            "WeasyPrint is required for PDF export. "
            'Install it with: pip install -e ".[export]"'
        )

    html_str = render_module_html(module_number)
    return HTML(string=html_str, base_url=str(_TEMPLATE_DIR)).write_pdf()


def export_module_html(module_number: int, output_path: Optional[str] = None) -> Path:
    """
    Export a quality manual module as an HTML file (for template debugging).

    Args:
        module_number: Module number to export.
        output_path: Optional output file path. If None, writes to
            data/quality-documents/exports/Module_{n}_v{ver}.html

    Returns:
        Path to the generated HTML file.
    """
    html_str = render_module_html(module_number)

    if output_path:
        out = Path(output_path)
    else:
        module = get_module_detail(module_number)
        version = module["version"] if module else "0"
        out = _default_output_dir() / f"Module_{module_number}_v{version}.html"

    out.write_text(html_str, encoding="utf-8")

    logger.info("Exported HTML: %s (%.1f KB)", out, out.stat().st_size / 1024)
    return out
