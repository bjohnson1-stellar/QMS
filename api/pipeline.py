"""
Pipeline Blueprint — Flask routes for document intake UI.

Thin delivery layer: all business logic lives in pipeline.classifier.
"""

from flask import Blueprint, jsonify, request, render_template
from pathlib import Path

bp = Blueprint("pipeline", __name__, url_prefix="/pipeline")


# ---------------------------------------------------------------------------
# Page routes
# ---------------------------------------------------------------------------


@bp.route("/")
def intake_dashboard():
    return render_template("pipeline/intake.html")


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------


@bp.route("/api/inbox")
def api_inbox():
    """Return classified inbox contents as JSON."""
    from qms.pipeline.classifier import scan_inbox

    results = scan_inbox()
    return jsonify([
        {
            "filename": r.filename,
            "doc_type": r.doc_type,
            "handler": r.handler,
            "destination": r.destination,
            "destination_template": r.destination_template,
            "matched_pattern": r.matched_pattern,
            "status": r.status,
            "unresolved_vars": r.unresolved_vars,
            "notes": r.notes,
            "file_size": r.file_size,
            "file_modified": r.file_modified,
        }
        for r in results
    ])


@bp.route("/api/intake", methods=["POST"])
def api_intake():
    """Process inbox files (move to destinations)."""
    from qms.pipeline.classifier import (
        classify_file,
        compile_patterns,
        process_files,
        scan_inbox,
    )
    from qms.core.config import QMS_PATHS

    data = request.get_json(silent=True) or {}
    filenames = data.get("filenames", [])
    dry_run = data.get("dry_run", False)

    if not filenames:
        # Process all inbox files
        results = scan_inbox()
    else:
        compiled = compile_patterns()
        inbox = QMS_PATHS.inbox
        results = []
        for fn in filenames:
            src = inbox / fn
            if src.exists():
                results.append(classify_file(fn, src, compiled))

    if not results:
        return jsonify({"actions": [], "summary": "No files to process"})

    actions = process_files(results, dry_run=dry_run)

    summary = {
        "routed": sum(1 for a in actions if a.action in ("routed", "would_route")),
        "needs_review": sum(
            1 for a in actions if a.action in ("needs_review", "would_need_review")
        ),
        "duplicate": sum(1 for a in actions if a.action == "duplicate"),
        "dry_run": dry_run,
    }

    return jsonify({
        "actions": [
            {
                "filename": a.filename,
                "action": a.action,
                "destination": a.destination,
                "doc_type": a.doc_type,
                "handler": a.handler,
                "notes": a.notes,
            }
            for a in actions
        ],
        "summary": summary,
    })


@bp.route("/api/classify", methods=["POST"])
def api_classify():
    """Classify a single uploaded file (preview only, no move)."""
    from qms.pipeline.classifier import classify_file, compile_patterns

    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    uploaded = request.files["file"]
    if not uploaded.filename:
        return jsonify({"error": "Empty filename"}), 400

    compiled = compile_patterns()
    # Classify by filename only (don't save the upload)
    result = classify_file(
        uploaded.filename,
        Path(uploaded.filename),  # placeholder path
        compiled,
    )

    return jsonify({
        "filename": result.filename,
        "doc_type": result.doc_type,
        "handler": result.handler,
        "destination_template": result.destination_template,
        "status": result.status,
        "matched_pattern": result.matched_pattern,
        "notes": result.notes,
    })


@bp.route("/api/intake-log")
def api_intake_log():
    """Return recent intake log entries."""
    from qms.pipeline.classifier import get_intake_log

    limit = request.args.get("limit", 50, type=int)
    entries = get_intake_log(limit=limit)
    return jsonify(entries)
