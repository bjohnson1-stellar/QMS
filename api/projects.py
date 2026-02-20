"""
Projects Blueprint — Flask routes for budget tracking UI.

Thin delivery layer: all business logic lives in projects.budget.
"""

import sqlite3

from flask import Blueprint, abort, jsonify, request, render_template, send_file, session

from qms.core import get_db
from qms.projects import budget
from qms.projects.budget import VALID_STAGES

bp = Blueprint("projects", __name__, url_prefix="/projects")


def _user_bu_ids():
    """Extract the current user's BU filter list from the session.

    Returns None (unrestricted) for admins or users with no BU assignments.
    Returns a list of BU IDs when the user is restricted to specific BUs.
    """
    user = session.get("user", {})
    if user.get("role") == "admin":
        return None
    return user.get("business_units")  # None = unrestricted, list = restricted


# ---------------------------------------------------------------------------
# Page routes (render templates)
# ---------------------------------------------------------------------------


@bp.route("/")
def dashboard():
    with get_db(readonly=True) as conn:
        stats = budget.get_dashboard_stats(conn, bu_ids=_user_bu_ids())
    return render_template("projects/dashboard.html", stats=stats, stages=VALID_STAGES)


@bp.route("/manage")
def projects_page():
    return render_template("projects/projects.html", stages=VALID_STAGES)


@bp.route("/<project_number>")
def project_detail(project_number: str):
    """Project hub — single-page view aggregating all project data."""
    with get_db(readonly=True) as conn:
        data = budget.get_project_hub_data(conn, project_number)
    if not data:
        abort(404)
    return render_template("projects/detail.html", project=data)


# ---------------------------------------------------------------------------
# Projects API
# ---------------------------------------------------------------------------


@bp.route("/api/projects", methods=["GET"])
def api_list_projects():
    return jsonify(budget.list_projects_with_budgets(bu_ids=_user_bu_ids()))


@bp.route("/api/projects", methods=["POST"])
def api_create_project():
    data = request.json
    code = data.get("code", "")
    ok, err = budget.validate_project_number(code)
    if not ok:
        return jsonify({"error": err}), 400

    # Extract base number for duplicate check
    parsed = budget.parse_job_code(code)
    base_number = parsed[0] if parsed else code

    with get_db() as conn:
        dup = conn.execute(
            "SELECT id FROM projects WHERE number = ?", (base_number,)
        ).fetchone()
        if dup:
            return jsonify({"error": "Project number already exists"}), 400

        pid = budget.create_project_with_budget(
            conn,
            name=data["name"],
            code=code,
            stage=data.get("stage", "Proposal"),
            total_budget=float(data.get("totalBudget", 0)),
            weight_adjustment=float(data.get("weightAdjustment", 1.0)),
            start_date=data.get("startDate"),
            end_date=data.get("endDate"),
            notes=data.get("notes"),
            client=data.get("ownerName"),
            street=data.get("ownerAddress"),
            city=data.get("ownerCity"),
            state=data.get("ownerState"),
            zip_code=data.get("ownerZip"),
            description=data.get("description"),
            allocations=data.get("allocations"),
        )
    return jsonify({"id": pid, "message": "Project created successfully"}), 201


@bp.route("/api/projects/<int:project_id>", methods=["PUT"])
def api_update_project(project_id):
    data = request.json
    code = data.get("code", "")
    ok, err = budget.validate_project_number(code)
    if not ok:
        return jsonify({"error": err}), 400

    parsed = budget.parse_job_code(code)
    base_number = parsed[0] if parsed else code

    with get_db() as conn:
        dup = conn.execute(
            "SELECT id FROM projects WHERE number = ? AND id != ?",
            (base_number, project_id),
        ).fetchone()
        if dup:
            return jsonify({"error": "Project number already exists"}), 400

        budget.update_project_with_budget(
            conn,
            project_id,
            name=data["name"],
            code=code,
            stage=data.get("stage", "Proposal"),
            total_budget=float(data.get("totalBudget", 0)),
            weight_adjustment=float(data.get("weightAdjustment", 1.0)),
            start_date=data.get("startDate"),
            end_date=data.get("endDate"),
            notes=data.get("notes"),
            client=data.get("ownerName"),
            street=data.get("ownerAddress"),
            city=data.get("ownerCity"),
            state=data.get("ownerState"),
            zip_code=data.get("ownerZip"),
            description=data.get("description"),
            allocations=data.get("allocations"),
        )
    return jsonify({"message": "Project updated successfully"})


@bp.route("/api/projects/<int:project_id>", methods=["DELETE"])
def api_delete_project(project_id):
    with get_db() as conn:
        try:
            budget.delete_project(conn, project_id)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
    return jsonify({"message": "Project deleted successfully"})


# ---------------------------------------------------------------------------
# Project Allocations API
# ---------------------------------------------------------------------------


@bp.route("/api/projects/<int:pid>/allocations", methods=["GET"])
def api_get_allocations(pid):
    with get_db(readonly=True) as conn:
        return jsonify(budget.get_project_allocations(conn, pid))


@bp.route("/api/projects/<int:pid>/allocations", methods=["POST"])
def api_upsert_allocation(pid):
    data = request.json
    bu_code = data.get("buCode", "").strip()
    if not bu_code:
        return jsonify({"error": "Business unit code is required"}), 400

    with get_db() as conn:
        try:
            budget.upsert_allocation(
                conn, pid,
                bu_code=bu_code,
                subjob=data.get("subjob", "00"),
                allocated_budget=float(data.get("budget", 0)),
                weight_adjustment=float(data.get("weight", 1.0)),
                notes=data.get("notes"),
            )
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        allocs = budget.get_project_allocations(conn, pid)
    return jsonify(allocs), 201


@bp.route("/api/projects/<int:pid>/allocations/<int:aid>", methods=["DELETE"])
def api_delete_allocation(pid, aid):
    try:
        with get_db() as conn:
            budget.delete_allocation(conn, aid)
            allocs = budget.get_project_allocations(conn, pid)
        return jsonify(allocs)
    except sqlite3.IntegrityError as e:
        return jsonify({"error": f"Cannot delete: referenced by other records ({e})"}), 409


# ---------------------------------------------------------------------------
# Hierarchical Projects API
# ---------------------------------------------------------------------------


@bp.route("/api/projects/hierarchical", methods=["GET"])
def api_list_projects_hierarchical():
    return jsonify(budget.list_projects_hierarchical(bu_ids=_user_bu_ids()))


@bp.route("/api/allocations/<int:aid>/weight", methods=["PATCH"])
def api_update_allocation_weight(aid):
    data = request.json
    weight = data.get("weight")
    if weight is None:
        return jsonify({"error": "weight is required"}), 400
    weight = float(weight)
    if not (0 <= weight <= 2):
        return jsonify({"error": "weight must be between 0 and 2"}), 400
    with get_db() as conn:
        ok = budget.update_allocation_field(conn, aid, "weight_adjustment", weight)
    if not ok:
        return jsonify({"error": "Allocation not found"}), 404
    return jsonify({"message": "Weight updated"})


@bp.route("/api/allocations/<int:aid>/projection", methods=["PATCH"])
def api_update_allocation_projection(aid):
    data = request.json
    enabled = 1 if data.get("enabled") else 0
    with get_db() as conn:
        ok = budget.update_allocation_field(conn, aid, "projection_enabled", enabled)
    if not ok:
        return jsonify({"error": "Allocation not found"}), 404
    return jsonify({"message": "Projection flag updated"})


@bp.route("/api/allocations/<int:aid>/gmp", methods=["PATCH"])
def api_update_allocation_gmp(aid):
    data = request.json
    flag = 1 if data.get("isGmp") else 0
    with get_db() as conn:
        ok = budget.update_allocation_field(conn, aid, "is_gmp", flag)
    if not ok:
        return jsonify({"error": "Allocation not found"}), 404
    return jsonify({"message": "GMP flag updated"})


@bp.route("/api/allocations/<int:aid>/budget", methods=["PATCH"])
def api_update_allocation_budget(aid):
    data = request.json
    amount = data.get("budget")
    if amount is None:
        return jsonify({"error": "budget is required"}), 400
    with get_db() as conn:
        ok = budget.update_allocation_budget(conn, aid, float(amount))
    if not ok:
        return jsonify({"error": "Allocation not found"}), 404
    return jsonify({"message": "Budget updated"})


@bp.route("/api/allocations/<int:aid>/stage", methods=["PATCH"])
def api_update_allocation_stage(aid):
    data = request.json
    stage = data.get("stage", "")
    if stage not in VALID_STAGES:
        return jsonify({"error": f"Invalid stage: {stage}"}), 400
    with get_db() as conn:
        ok = budget.update_allocation_field(conn, aid, "stage", stage)
    if not ok:
        return jsonify({"error": "Allocation not found"}), 404
    return jsonify({"message": "Stage updated"})


@bp.route("/api/allocations/bulk", methods=["PATCH"])
def api_bulk_update_allocations():
    data = request.json or {}
    ids = data.get("ids", [])
    action = data.get("action", "")
    value = data.get("value")
    if not ids or not isinstance(ids, list):
        return jsonify({"error": "ids must be a non-empty list"}), 400
    if action not in ("set_stage", "set_projection", "set_gmp", "set_weight", "delete"):
        return jsonify({"error": f"Invalid action: {action}"}), 400
    try:
        with get_db() as conn:
            result = budget.bulk_update_allocations(conn, ids, action, value)
        return jsonify(result)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


# ---------------------------------------------------------------------------
# Business Units API
# ---------------------------------------------------------------------------


@bp.route("/api/business-units", methods=["GET"])
def api_list_bus():
    return jsonify(budget.list_business_units(bu_ids=_user_bu_ids()))


@bp.route("/api/business-units", methods=["POST"])
def api_create_bu():
    data = request.json
    import re

    code = data.get("code", "").strip()
    if not re.match(r"^\d{3}$", code):
        return jsonify({"error": "Code must be exactly 3 digits"}), 400

    with get_db() as conn:
        dup = conn.execute(
            "SELECT id FROM business_units WHERE code = ?", (code,)
        ).fetchone()
        if dup:
            return jsonify({"error": "Code already exists"}), 400
        bu_id = budget.create_business_unit(
            conn, code=code, name=data["name"], description=data.get("description", "")
        )
    return jsonify({"id": bu_id, "message": "Business Unit created"}), 201


@bp.route("/api/business-units/<int:bu_id>", methods=["PUT"])
def api_update_bu(bu_id):
    data = request.json
    import re

    code = data.get("code", "").strip()
    if not re.match(r"^\d{3}$", code):
        return jsonify({"error": "Code must be exactly 3 digits"}), 400

    with get_db() as conn:
        dup = conn.execute(
            "SELECT id FROM business_units WHERE code = ? AND id != ?", (code, bu_id)
        ).fetchone()
        if dup:
            return jsonify({"error": "Code already exists"}), 400
        budget.update_business_unit(
            conn, bu_id, code=code, name=data["name"],
            description=data.get("description", ""),
        )
    return jsonify({"message": "Business Unit updated"})


@bp.route("/api/business-units/<int:bu_id>", methods=["DELETE"])
def api_delete_bu(bu_id):
    with get_db() as conn:
        ok = budget.delete_business_unit(conn, bu_id)
    if not ok:
        return jsonify({"error": "Cannot delete: in use by jobs"}), 400
    return jsonify({"message": "Business Unit deleted"})


# ---------------------------------------------------------------------------
# Excel Import/Export
# ---------------------------------------------------------------------------


@bp.route("/api/projects/template", methods=["GET"])
def api_download_template():
    from qms.projects.excel_io import generate_template

    output = generate_template()
    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name="project_import_template.xlsx",
    )


@bp.route("/api/projects/import", methods=["POST"])
def api_import_projects():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    file = request.files["file"]
    if not file.filename.endswith(".xlsx"):
        return jsonify({"error": "File must be .xlsx"}), 400

    from qms.projects.excel_io import import_projects_from_excel

    with get_db() as conn:
        result = import_projects_from_excel(conn, file)
    return jsonify(result)


@bp.route("/api/projects/import-procore", methods=["POST"])
def api_import_procore():
    """Import projects from a Procore Company Home CSV export."""
    import tempfile

    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    file = request.files["file"]
    if not file.filename.endswith(".csv"):
        return jsonify({"error": "File must be .csv"}), 400

    from qms.projects.procore_io import import_from_procore

    # Save uploaded file to a temp path for the importer
    with tempfile.NamedTemporaryFile(
        suffix=".csv", delete=False, mode="wb"
    ) as tmp:
        file.save(tmp)
        tmp_path = tmp.name

    try:
        with get_db() as conn:
            result = import_from_procore(conn, tmp_path)
        return jsonify(result)
    finally:
        import os
        os.unlink(tmp_path)
