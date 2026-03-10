"""
Quality Manual Web Module — Browse and search quality manual content.

Routes:
    GET /qualitydocs/                      — Document viewer page
    GET /qualitydocs/api/summary           — Module list + aggregate stats
    GET /qualitydocs/api/module/<int:n>    — Sections + xrefs for a module
    GET /qualitydocs/api/section/<number>  — Content blocks for a section
    GET /qualitydocs/api/search?q=...      — FTS5 full-text search

    M3 Programs:
    GET /qualitydocs/api/programs           — List all programs
    GET /qualitydocs/api/programs/<id>      — Program detail + linked SOPs

    M4 Categories:
    GET /qualitydocs/api/categories         — List categories with SOP counts
    GET /qualitydocs/api/categories/<code>  — Category detail

    M4 SOPs:
    GET  /qualitydocs/api/sops              — Paginated SOP list
    GET  /qualitydocs/api/sops/search?q=    — Search SOPs
    GET  /qualitydocs/api/sops/<doc_id>     — SOP detail
    POST /qualitydocs/api/sops              — Create SOP (draft)
    POST /qualitydocs/api/sops/<id>/approve — Approve SOP
    POST /qualitydocs/api/sops/<id>/publish — Publish SOP
    POST /qualitydocs/api/sops/<id>/link-program — Link SOP to program
    GET  /qualitydocs/api/sops/<id>/history — SOP revision history
"""

from flask import Blueprint, Response, jsonify, render_template, request

from qms.qualitydocs.loader import (
    get_manual_summary,
    get_module_detail,
    get_section_content,
    search_content,
)
from qms.qualitydocs.db import (
    list_programs,
    get_program,
    get_program_sops,
    list_categories,
    get_category,
    list_sops,
    get_sop,
    create_sop,
    approve_sop,
    publish_sop,
    link_sop_to_program,
    search_sops,
    get_sop_history,
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


# ---------------------------------------------------------------------------
# M3 Programs
# ---------------------------------------------------------------------------

@bp.route("/api/programs")
def api_programs():
    """List all quality programs."""
    status = request.args.get("status")
    return jsonify(list_programs(status=status))


@bp.route("/api/programs/<program_id>")
def api_program_detail(program_id: str):
    """Program detail with linked SOPs."""
    prog = get_program(program_id)
    if prog is None:
        return jsonify({"error": f"Program {program_id} not found"}), 404
    prog["sops"] = get_program_sops(program_id)
    return jsonify(prog)


# ---------------------------------------------------------------------------
# M4 Categories
# ---------------------------------------------------------------------------

@bp.route("/api/categories")
def api_categories():
    """List categories with SOP counts."""
    module = request.args.get("module", 4, type=int)
    return jsonify(list_categories(module_number=module))


@bp.route("/api/categories/<code>")
def api_category_detail(code: str):
    """Category detail by category_code."""
    cat = get_category(code)
    if cat is None:
        return jsonify({"error": f"Category {code} not found"}), 404
    return jsonify(cat)


# ---------------------------------------------------------------------------
# M4 SOPs
# ---------------------------------------------------------------------------

@bp.route("/api/sops")
def api_sops():
    """Paginated SOP list with optional filters."""
    category_id = request.args.get("category_id", type=int)
    status = request.args.get("status")
    scope = request.args.get("scope")
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)
    return jsonify(list_sops(
        category_id=category_id, scope=scope, status=status,
        page=page, per_page=per_page,
    ))


@bp.route("/api/sops/search")
def api_sops_search():
    """Search SOPs by title and content."""
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"results": [], "query": ""})
    limit = min(int(request.args.get("limit", 50)), 100)
    results = search_sops(q, limit=limit)
    return jsonify({"results": results, "query": q})


@bp.route("/api/sops/<document_id>")
def api_sop_detail(document_id: str):
    """Full SOP detail with category, programs, and parsed scope_tags."""
    sop = get_sop(document_id)
    if sop is None:
        return jsonify({"error": f"SOP {document_id} not found"}), 404
    return jsonify(sop)


@bp.route("/api/sops", methods=["POST"])
def api_sop_create():
    """Create a new SOP in draft status."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON body required"}), 400
    document_id = data.get("document_id")
    title = data.get("title")
    category_id = data.get("category_id")
    if not all([document_id, title, category_id]):
        return jsonify({"error": "document_id, title, and category_id are required"}), 400
    try:
        sop_id = create_sop(
            document_id=document_id,
            title=title,
            category_id=category_id,
            scope_tags=data.get("scope_tags"),
            file_path=data.get("file_path"),
            file_hash=data.get("file_hash"),
            content_text=data.get("content_text"),
            summary=data.get("summary"),
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"id": sop_id, "status": "draft"}), 201


@bp.route("/api/sops/<int:id>/approve", methods=["POST"])
def api_sop_approve(id: int):
    """Approve a SOP (sets status, approved_by, approved_at)."""
    data = request.get_json(silent=True) or {}
    approved_by = data.get("approved_by")
    if not approved_by:
        return jsonify({"error": "approved_by is required"}), 400
    if approve_sop(id, approved_by):
        return jsonify({"id": id, "status": "approved"})
    return jsonify({"error": f"SOP {id} not found or could not be approved"}), 404


@bp.route("/api/sops/<int:id>/publish", methods=["POST"])
def api_sop_publish(id: int):
    """Publish a SOP (sets status to published)."""
    if publish_sop(id):
        return jsonify({"id": id, "status": "published"})
    return jsonify({"error": f"SOP {id} not found or could not be published"}), 404


@bp.route("/api/sops/<int:id>/link-program", methods=["POST"])
def api_sop_link_program(id: int):
    """Link a SOP to a program."""
    data = request.get_json(silent=True) or {}
    program_id = data.get("program_id")
    if program_id is None:
        return jsonify({"error": "program_id is required"}), 400
    if link_sop_to_program(id, program_id):
        return jsonify({"sop_id": id, "program_id": program_id, "linked": True})
    return jsonify({"error": "Failed to link SOP to program"}), 400


@bp.route("/api/sops/<int:id>/history")
def api_sop_history(id: int):
    """SOP revision/approval history."""
    history = get_sop_history(id)
    return jsonify(history)
