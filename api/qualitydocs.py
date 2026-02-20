"""
Quality Manual Web Module — Browse and search quality manual content.

Routes:
    GET /qualitydocs/                      — Document viewer page
    GET /qualitydocs/api/summary           — Module list + aggregate stats
    GET /qualitydocs/api/module/<int:n>    — Sections + xrefs for a module
    GET /qualitydocs/api/section/<number>  — Content blocks for a section
    GET /qualitydocs/api/search?q=...      — FTS5 full-text search
"""

from flask import Blueprint, Response, jsonify, render_template, request

from qms.qualitydocs.loader import (
    get_manual_summary,
    get_module_detail,
    get_section_content,
    search_content,
)

bp = Blueprint(
    "qualitydocs",
    __name__,
    url_prefix="/qualitydocs",
)


@bp.route("/")
def manual():
    """Render the quality manual document viewer."""
    return render_template("qualitydocs/index.html")


@bp.route("/api/summary")
def api_summary():
    """Module list with aggregate stats."""
    return jsonify(get_manual_summary())


@bp.route("/api/module/<int:module_number>")
def api_module(module_number: int):
    """Sections, cross-references, and code references for a module."""
    detail = get_module_detail(module_number)
    if detail is None:
        return jsonify({"error": f"Module {module_number} not found"}), 404
    return jsonify(detail)


@bp.route("/api/section/<path:section_number>")
def api_section(section_number: str):
    """Content blocks and responsibilities for a section."""
    content = get_section_content(section_number)
    if content is None:
        return jsonify({"error": f"Section {section_number} not found"}), 404
    return jsonify(content)


@bp.route("/api/export/<int:module_number>")
def api_export(module_number: int):
    """Download a module as a formatted PDF."""
    from qms.qualitydocs.export import export_module_pdf_bytes

    detail = get_module_detail(module_number)
    if detail is None:
        return jsonify({"error": f"Module {module_number} not found"}), 404

    try:
        pdf_bytes = export_module_pdf_bytes(module_number)
    except ImportError:
        return jsonify({"error": "WeasyPrint not installed"}), 501

    version = detail.get("version", "0")
    filename = f"Module_{module_number}_v{version}.pdf"
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@bp.route("/api/search")
def api_search():
    """Full-text search across quality manual content."""
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"results": [], "query": ""})
    limit = min(int(request.args.get("limit", 50)), 100)
    results = search_content(q, limit=limit)
    return jsonify({"results": results, "query": q})
