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
    get_license,
    get_license_stats,
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
