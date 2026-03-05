"""
Licenses Blueprint — Flask routes for state license tracking.

Thin delivery layer: business logic lives in licenses.db.
"""

import json

from flask import Blueprint, jsonify, request, render_template, session

from qms.core import get_db
from qms.auth.decorators import module_required
from qms.licenses.db import (
    create_license,
    delete_license,
    get_expiring_licenses,
    get_license,
    get_license_stats,
    get_renewal_timeline,
    get_state_map_data,
    list_licenses,
    update_license,
)

bp = Blueprint("licenses", __name__, url_prefix="/licenses")


# ---------------------------------------------------------------------------
# Page routes
# ---------------------------------------------------------------------------

@bp.route("/")
@module_required("licenses")
def licenses_page():
    return render_template("licenses/licenses.html")


@bp.route("/import")
@module_required("licenses", min_role="editor")
def import_page():
    return render_template("licenses/import.html")


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@bp.route("/api/licenses", methods=["GET"])
@module_required("licenses")
def api_list_licenses():
    with get_db(readonly=True) as conn:
        rows = list_licenses(
            conn,
            holder_type=request.args.get("holder_type"),
            state_code=request.args.get("state_code"),
            status=request.args.get("status"),
            search=request.args.get("search"),
        )
    return jsonify(rows)


@bp.route("/api/licenses/stats", methods=["GET"])
@module_required("licenses")
def api_license_stats():
    with get_db(readonly=True) as conn:
        stats = get_license_stats(conn)
    return jsonify(stats)


@bp.route("/api/licenses", methods=["POST"])
@module_required("licenses", min_role="editor")
def api_create_license():
    data = request.get_json(force=True)
    required = ["holder_type", "state_code", "license_type", "license_number", "holder_name"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    user = session.get("user", {})
    data["created_by"] = user.get("id", user.get("email", "unknown"))

    with get_db() as conn:
        result = create_license(conn, **data)
    return jsonify(result), 201


@bp.route("/api/licenses/<license_id>", methods=["PUT"])
@module_required("licenses", min_role="editor")
def api_update_license(license_id):
    data = request.get_json(force=True)
    with get_db() as conn:
        result = update_license(conn, license_id, **data)
    if not result:
        return jsonify({"error": "License not found"}), 404
    return jsonify(result)


@bp.route("/api/licenses/<license_id>", methods=["DELETE"])
@module_required("licenses", min_role="admin")
def api_delete_license(license_id):
    with get_db() as conn:
        deleted = delete_license(conn, license_id)
    if not deleted:
        return jsonify({"error": "License not found"}), 404
    return jsonify({"ok": True})


@bp.route("/api/employees/lookup", methods=["GET"])
@module_required("licenses")
def api_employee_lookup():
    """Employee picker data for license form."""
    with get_db(readonly=True) as conn:
        rows = conn.execute(
            """SELECT id, first_name, last_name, employee_number, position
               FROM employees
               WHERE status = 'active'
               ORDER BY last_name, first_name"""
        ).fetchall()
    return jsonify([dict(r) for r in rows])


# ---------------------------------------------------------------------------
# Dashboard API routes
# ---------------------------------------------------------------------------

@bp.route("/api/map-data", methods=["GET"])
@module_required("licenses")
def api_map_data():
    """Per-state aggregation for the SVG map."""
    with get_db(readonly=True) as conn:
        data = get_state_map_data(conn)
    return jsonify(data)


@bp.route("/api/expiring", methods=["GET"])
@module_required("licenses")
def api_expiring():
    """Licenses in 30/60/90 day expiration bands."""
    with get_db(readonly=True) as conn:
        bands = get_expiring_licenses(conn)
    return jsonify(bands)


@bp.route("/api/renewal-timeline", methods=["GET"])
@module_required("licenses")
def api_renewal_timeline():
    """Monthly renewal counts for next 12 months."""
    with get_db(readonly=True) as conn:
        data = get_renewal_timeline(conn)
    return jsonify(data)


# ---------------------------------------------------------------------------
# Import API routes
# ---------------------------------------------------------------------------

def _get_user_id():
    """Extract current user ID from session."""
    user = session.get("user", {})
    return user.get("id", user.get("email", "unknown"))


@bp.route("/api/import/upload", methods=["POST"])
@module_required("licenses", min_role="editor")
def api_import_upload():
    """Parse uploaded file, create session, return headers + auto-mapping."""
    from qms.imports.engine import (
        auto_map_columns, create_import_session, file_hash,
        parse_file, cache_file,
    )
    from qms.licenses.import_specs import get_license_import_spec

    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "No file selected"}), 400

    file_bytes = f.read()
    if not file_bytes:
        return jsonify({"error": "File is empty"}), 400

    try:
        headers, rows = parse_file(file_bytes, f.filename)
    except (ValueError, ImportError) as exc:
        return jsonify({"error": str(exc)}), 400

    spec = get_license_import_spec()
    mapping = auto_map_columns(headers, spec)

    with get_db() as conn:
        session_id = create_import_session(
            conn,
            user_id=_get_user_id(),
            module="licenses",
            spec_name=spec.name,
            filename=f.filename,
            total_rows=len(rows),
            file_hash=file_hash(file_bytes),
        )

    cache_file(session_id, headers, rows)

    available_fields = [
        {"name": c.name, "label": c.label, "required": c.required}
        for c in spec.columns
    ]

    return jsonify({
        "session_id": session_id,
        "filename": f.filename,
        "total_rows": len(rows),
        "headers": headers,
        "mapping": mapping,
        "available_fields": available_fields,
        "sample_rows": rows[:5],
    })


@bp.route("/api/import/<session_id>/plan", methods=["POST"])
@module_required("licenses", min_role="editor")
def api_import_plan(session_id):
    """Accept final column mapping, generate action plan."""
    from qms.imports.engine import (
        generate_action_plan, get_import_session, save_action_plan,
        transform_rows, update_session_status, validate_mapping,
        get_cached,
    )
    from qms.licenses.import_specs import get_license_import_spec

    data = request.get_json(force=True)
    mapping = data.get("mapping", {})

    spec = get_license_import_spec()

    errors = validate_mapping(mapping, spec)
    if errors:
        return jsonify({"error": "Invalid mapping", "details": errors}), 400

    cached = get_cached(session_id)
    if not cached:
        return jsonify({"error": "Session expired — please re-upload the file"}), 410

    headers, rows = cached

    with get_db() as conn:
        sess = get_import_session(conn, session_id)
        if not sess:
            return jsonify({"error": "Session not found"}), 404

        records, parse_errors = transform_rows(rows, mapping, spec, conn)

        plan = generate_action_plan(
            conn, records, spec, session_id,
            detect_missing=False,
        )
        plan.parse_errors = parse_errors

        save_action_plan(conn, plan)
        update_session_status(conn, session_id, "review", column_mapping=mapping)

    categories = {}
    for action_type, items in plan.by_category.items():
        categories[action_type] = [
            {
                "id": i,
                "row_index": item.row_index,
                "record": item.record_data,
                "existing": item.existing_data,
                "changes": item.changes,
                "match_method": item.match_method,
                "reason": item.reason,
            }
            for i, item in enumerate(items)
        ]

    return jsonify({
        "session_id": session_id,
        "summary": plan.summary,
        "categories": categories,
        "parse_errors": parse_errors[:20],
    })


@bp.route("/api/import/<session_id>/execute", methods=["POST"])
@module_required("licenses", min_role="editor")
def api_import_execute(session_id):
    """Apply approved actions from the plan."""
    from qms.imports.engine import (
        execute_approved_actions, get_import_session,
        update_session_status, clear_cache,
    )
    from qms.licenses.import_specs import get_license_import_spec

    data = request.get_json(force=True)
    approve_categories = set(data.get("approve_categories", []))
    reject_categories = set(data.get("reject_categories", []))
    individual_approvals = data.get("approvals", {})

    spec = get_license_import_spec()

    with get_db() as conn:
        sess = get_import_session(conn, session_id)
        if not sess:
            return jsonify({"error": "Session not found"}), 404

        action_rows = conn.execute(
            "SELECT * FROM import_actions WHERE session_id = ? ORDER BY id",
            (session_id,),
        ).fetchall()

        from qms.imports.specs import ActionItem, ActionPlan
        plan = ActionPlan(session_id=session_id)

        for row in action_rows:
            item = ActionItem(
                row_index=row["row_index"],
                action_type=row["action_type"],
                record_data=json.loads(row["record_data"]),
                existing_data=json.loads(row["existing_data"]) if row["existing_data"] else None,
                match_method=row["match_method"],
                changes=json.loads(row["changes"]) if row["changes"] else None,
                reason=row["reason"],
            )

            db_id = str(row["id"])

            if db_id in individual_approvals:
                item.approved = individual_approvals[db_id]
            elif item.action_type in approve_categories:
                item.approved = True
            elif item.action_type in reject_categories:
                item.approved = False
            else:
                item.approved = False

            plan.items.append(item)

        update_session_status(conn, session_id, "executing")

        try:
            counts = execute_approved_actions(
                conn, plan, spec, executed_by=_get_user_id()
            )
            update_session_status(
                conn, session_id, "completed",
                result_summary=counts,
            )
        except Exception as exc:
            update_session_status(
                conn, session_id, "error",
                error_message=str(exc),
            )
            return jsonify({"error": str(exc)}), 500

    clear_cache(session_id)

    return jsonify({
        "session_id": session_id,
        "status": "completed",
        **counts,
    })


@bp.route("/api/import/history", methods=["GET"])
@module_required("licenses", min_role="editor")
def api_import_history():
    """Return current user's recent import sessions."""
    from qms.imports.engine import get_user_import_history

    with get_db(readonly=True) as conn:
        history = get_user_import_history(conn, _get_user_id(), "licenses")
    return jsonify(history)


@bp.route("/api/import/<session_id>/cancel", methods=["POST"])
@module_required("licenses", min_role="editor")
def api_import_cancel(session_id):
    """Cancel an in-progress import session."""
    from qms.imports.engine import (
        get_import_session, update_session_status, clear_cache,
    )

    with get_db() as conn:
        sess = get_import_session(conn, session_id)
        if not sess:
            return jsonify({"error": "Session not found"}), 404
        update_session_status(conn, session_id, "cancelled")

    clear_cache(session_id)
    return jsonify({"ok": True})
