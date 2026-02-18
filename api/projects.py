"""
Projects Blueprint — Flask routes for budget tracking UI.

Thin delivery layer: all business logic lives in projects.budget.
"""

import sqlite3

from flask import Blueprint, jsonify, request, render_template, send_file

from qms.core import get_db
from qms.projects import budget
from qms.projects.budget import VALID_STAGES
from qms.projects import timecard

bp = Blueprint("projects", __name__, url_prefix="/projects")


# ---------------------------------------------------------------------------
# Page routes (render templates)
# ---------------------------------------------------------------------------


@bp.route("/")
def dashboard():
    with get_db(readonly=True) as conn:
        stats = budget.get_dashboard_stats(conn)
    return render_template("projects/dashboard.html", stats=stats, stages=VALID_STAGES)


@bp.route("/manage")
def projects_page():
    return render_template("projects/projects.html", stages=VALID_STAGES)


@bp.route("/business-units")
def business_units_page():
    return render_template("projects/business_units.html")


@bp.route("/transactions")
def transactions_page():
    return render_template("projects/transactions.html")


@bp.route("/settings")
def settings_page():
    return render_template("projects/settings.html")


@bp.route("/projections")
def projections_page():
    return render_template("projects/projections.html")


# ---------------------------------------------------------------------------
# Projects API
# ---------------------------------------------------------------------------


@bp.route("/api/projects", methods=["GET"])
def api_list_projects():
    return jsonify(budget.list_projects_with_budgets())


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
    return jsonify(budget.list_projects_hierarchical())


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
    return jsonify(budget.list_business_units())


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
# Transactions API
# ---------------------------------------------------------------------------


@bp.route("/api/transactions", methods=["GET"])
def api_list_transactions():
    pid = request.args.get("project_id", type=int)
    ttype = request.args.get("type")
    return jsonify(budget.list_transactions(project_id=pid, transaction_type=ttype))


@bp.route("/api/transactions/<int:txn_id>", methods=["GET"])
def api_get_transaction(txn_id):
    with get_db(readonly=True) as conn:
        t = budget.get_transaction(conn, txn_id)
    if not t:
        return jsonify({"error": "Not found"}), 404
    return jsonify(t)


@bp.route("/api/transactions", methods=["POST"])
def api_create_transaction():
    data = request.json
    if not data.get("projectId"):
        return jsonify({"error": "Project is required"}), 400

    amount = data.get("amount", 0)
    hours = data.get("hours")
    rate = data.get("rate")
    if data.get("transactionType") == "Time" and hours and rate:
        amount = float(hours) * float(rate)

    with get_db() as conn:
        tid = budget.create_transaction(
            conn,
            project_id=data["projectId"],
            transaction_date=data["transactionDate"],
            transaction_type=data["transactionType"],
            description=data["description"],
            amount=float(amount),
            hours=float(hours) if hours else None,
            rate=float(rate) if rate else None,
            notes=data.get("notes"),
        )
    return jsonify({"id": tid, "message": "Transaction created"}), 201


@bp.route("/api/transactions/<int:txn_id>", methods=["PUT"])
def api_update_transaction(txn_id):
    data = request.json
    amount = data.get("amount", 0)
    hours = data.get("hours")
    rate = data.get("rate")
    if data.get("transactionType") == "Time" and hours and rate:
        amount = float(hours) * float(rate)

    with get_db() as conn:
        budget.update_transaction(
            conn, txn_id,
            project_id=data["projectId"],
            transaction_date=data["transactionDate"],
            transaction_type=data["transactionType"],
            description=data["description"],
            amount=float(amount),
            hours=float(hours) if hours else None,
            rate=float(rate) if rate else None,
            notes=data.get("notes"),
        )
    return jsonify({"message": "Transaction updated"})


@bp.route("/api/transactions/<int:txn_id>", methods=["DELETE"])
def api_delete_transaction(txn_id):
    with get_db() as conn:
        budget.delete_transaction(conn, txn_id)
    return jsonify({"message": "Transaction deleted"})


# ---------------------------------------------------------------------------
# Settings API
# ---------------------------------------------------------------------------


@bp.route("/api/settings", methods=["GET"])
def api_get_settings():
    return jsonify(budget.get_settings())


@bp.route("/api/settings", methods=["PUT"])
def api_update_settings():
    data = request.json
    with get_db() as conn:
        budget.update_settings(
            conn,
            company_name=data.get("companyName", "My Company"),
            default_hourly_rate=float(data.get("defaultHourlyRate", 150)),
            working_hours_per_month=int(data.get("workingHoursPerMonth", 176)),
            fiscal_year_start_month=int(data.get("fiscalYearStartMonth", 1)),
            gmp_weight_multiplier=float(data.get("gmpWeightMultiplier", 1.5)),
        )
    return jsonify({"message": "Settings updated"})


# ---------------------------------------------------------------------------
# Projection Periods API
# ---------------------------------------------------------------------------


@bp.route("/api/projection-periods", methods=["GET"])
def api_list_periods():
    return jsonify(budget.list_projection_periods())


@bp.route("/api/projection-periods", methods=["POST"])
def api_create_period():
    data = request.json
    year = int(data.get("year", 0))
    month = int(data.get("month", 0))
    if not (2020 <= year <= 2100) or not (1 <= month <= 12):
        return jsonify({"error": "Invalid year or month"}), 400

    with get_db() as conn:
        dup = conn.execute(
            "SELECT id FROM projection_periods WHERE year = ? AND month = ?",
            (year, month),
        ).fetchone()
        if dup:
            return jsonify({"error": f"Period {year}-{month:02d} already exists"}), 400
        result = budget.create_projection_period(conn, year=year, month=month)
    return jsonify({**result, "message": "Period created"}), 201


@bp.route("/api/projection-periods/<int:pid>", methods=["GET"])
def api_get_period(pid):
    with get_db(readonly=True) as conn:
        p = budget.get_projection_period(conn, pid)
    if not p:
        return jsonify({"error": "Period not found"}), 404
    return jsonify(p)


@bp.route("/api/projection-periods/<int:pid>/lock", methods=["PUT"])
def api_toggle_lock(pid):
    data = request.json
    with get_db() as conn:
        ok = budget.toggle_period_lock(conn, pid, locked=bool(data.get("locked")))
    if not ok:
        return jsonify({"error": "Period not found"}), 404
    return jsonify({"message": "Lock toggled"})


# ---------------------------------------------------------------------------
# Projections API
# ---------------------------------------------------------------------------


@bp.route("/api/projections/calculate", methods=["POST"])
def api_calculate_projection():
    data = request.json
    pid = data.get("periodId")
    if not pid:
        return jsonify({"error": "Period ID required"}), 400
    with get_db() as conn:
        result = budget.calculate_projection(conn, int(pid))
    if "error" in result:
        return jsonify(result), 400
    return jsonify(result)


@bp.route("/api/projections/<int:pid>", methods=["GET"])
def api_get_projection(pid):
    with get_db(readonly=True) as conn:
        result = budget.get_active_projection(conn, pid)
    if not result:
        return jsonify({"error": "No active snapshot"}), 404
    return jsonify(result)


# ---------------------------------------------------------------------------
# Per-Period Job Selection API
# ---------------------------------------------------------------------------


@bp.route("/api/projection-periods/<int:pid>/jobs", methods=["GET"])
def api_get_period_jobs(pid):
    with get_db() as conn:
        jobs = budget.load_period_jobs(conn, pid)
    return jsonify(jobs)


@bp.route("/api/projection-periods/<int:pid>/jobs/<int:aid>/toggle", methods=["PATCH"])
def api_toggle_period_job(pid, aid):
    data = request.json or {}
    included = bool(data.get("included", True))
    with get_db() as conn:
        budget.toggle_period_job(conn, pid, aid, included)
    return jsonify({"message": "Toggled"})


@bp.route("/api/projection-periods/<int:pid>/jobs/bulk-toggle", methods=["PATCH"])
def api_bulk_toggle_period_jobs(pid):
    data = request.json or {}
    ids = data.get("allocationIds", [])
    included = bool(data.get("included", True))
    if not ids:
        return jsonify({"error": "allocationIds required"}), 400
    with get_db() as conn:
        count = budget.bulk_toggle_period_jobs(conn, pid, ids, included)
    return jsonify({"updated": count})


# ---------------------------------------------------------------------------
# Snapshot Management API
# ---------------------------------------------------------------------------


@bp.route("/api/projections/period/<int:pid>/snapshots", methods=["GET"])
def api_list_snapshots(pid):
    with get_db(readonly=True) as conn:
        return jsonify(budget.list_snapshots(conn, pid))


@bp.route("/api/projections/snapshot/<int:sid>", methods=["GET"])
def api_get_snapshot(sid):
    with get_db(readonly=True) as conn:
        result = budget.get_snapshot_with_details(conn, sid)
    if not result:
        return jsonify({"error": "Snapshot not found"}), 404
    return jsonify(result)


@bp.route("/api/projections/snapshot/<int:sid>/activate", methods=["PUT"])
def api_activate_snapshot(sid):
    with get_db() as conn:
        ok = budget.activate_snapshot(conn, sid)
    if not ok:
        return jsonify({"error": "Cannot activate (not found or not Draft)"}), 400
    return jsonify({"message": "Snapshot activated"})


@bp.route("/api/projections/snapshot/<int:sid>/commit", methods=["PUT"])
def api_commit_snapshot(sid):
    with get_db() as conn:
        result = budget.commit_snapshot(conn, sid)
    if "error" in result:
        return jsonify(result), 400
    return jsonify(result)


@bp.route("/api/projections/snapshot/<int:sid>/uncommit", methods=["PUT"])
def api_uncommit_snapshot(sid):
    with get_db() as conn:
        result = budget.uncommit_snapshot(conn, sid)
    if "error" in result:
        return jsonify(result), 400
    return jsonify(result)


@bp.route("/api/projections/snapshot/<int:sid>/distribute", methods=["GET"])
def api_distribute_snapshot(sid):
    with get_db(readonly=True) as conn:
        result = budget.distribute_projection_hours(conn, sid)
    if "error" in result:
        return jsonify(result), 404
    return jsonify(result)


@bp.route("/api/projects/budget-summary", methods=["GET"])
def api_budget_summary():
    pid = request.args.get("project_id", type=int)
    with get_db(readonly=True) as conn:
        return jsonify(budget.get_budget_summary(conn, project_id=pid))


@bp.route("/api/projections/<int:pid>", methods=["POST"])
def api_create_snapshot(pid):
    data = request.json
    with get_db() as conn:
        period = conn.execute(
            "SELECT * FROM projection_periods WHERE id = ?", (pid,)
        ).fetchone()
        if not period:
            return jsonify({"error": "Period not found"}), 404
        if period["is_locked"]:
            return jsonify({"error": "Period is locked"}), 400

        # Aggregate per-job entries to per-project for snapshot storage
        raw_entries = data.get("entries", [])
        project_map = {}
        detail_entries = []
        for e in raw_entries:
            pid_key = e.get("project_id")
            if pid_key not in project_map:
                project_map[pid_key] = {
                    "project_id": pid_key,
                    "allocated_hours": 0,
                    "projected_cost": 0,
                    "weight_used": 0,
                    "remaining_budget": 0,
                }
            project_map[pid_key]["allocated_hours"] += e.get("allocated_hours", 0)
            project_map[pid_key]["projected_cost"] += e.get("projected_cost", 0)
            project_map[pid_key]["weight_used"] += e.get("weight_used", 0)
            project_map[pid_key]["remaining_budget"] += e.get("effective_budget", 0)

            # Build job-level detail entry
            if e.get("allocation_id"):
                detail_entries.append({
                    "project_id": pid_key,
                    "allocation_id": e["allocation_id"],
                    "job_code": e.get("job_code", ""),
                    "allocated_hours": e.get("allocated_hours", 0),
                    "projected_cost": e.get("projected_cost", 0),
                    "weight_used": e.get("weight_used"),
                    "is_manual_override": 1 if e.get("is_manual_override") else 0,
                })
        aggregated = list(project_map.values())

        result = budget.create_projection_snapshot(
            conn, pid,
            entries=aggregated,
            detail_entries=detail_entries if detail_entries else None,
            hourly_rate=data.get("hourlyRate", 150.0),
            total_hours=data.get("totalHours", period["total_hours"]),
            name=data.get("name"),
            description=data.get("description"),
        )
    return jsonify({**result, "message": "Snapshot created"}), 201


@bp.route("/api/projections/snapshot/<int:sid>/finalize", methods=["PUT"])
def api_finalize_snapshot(sid):
    with get_db() as conn:
        ok = budget.finalize_snapshot(conn, sid)
    if not ok:
        return jsonify({"error": "Snapshot not found"}), 404
    return jsonify({"message": "Snapshot finalized"})


# ---------------------------------------------------------------------------
# Timecard Export API
# ---------------------------------------------------------------------------


@bp.route("/api/timecard/<int:pid>", methods=["GET"])
def api_get_timecard(pid):
    """Export timecard entries for a single projection period."""
    from datetime import date as _date

    start = request.args.get("start_date")
    end = request.args.get("end_date")
    sd = _date.fromisoformat(start) if start else None
    ed = _date.fromisoformat(end) if end else None

    with get_db(readonly=True) as conn:
        result = timecard.generate_timecard_entries(conn, pid, start_date=sd, end_date=ed)

    if "error" in result:
        return jsonify(result), 400
    return jsonify(result)


@bp.route("/api/timecard", methods=["GET"])
def api_get_timecard_by_dates():
    """Export timecard entries for a date range (cross-month capable)."""
    from datetime import date as _date

    start = request.args.get("start_date")
    end = request.args.get("end_date")
    if not start or not end:
        return jsonify({"error": "start_date and end_date required"}), 400

    sd = _date.fromisoformat(start)
    ed = _date.fromisoformat(end)

    with get_db(readonly=True) as conn:
        result = timecard.generate_timecard_for_pay_period(conn, sd, ed)

    if "error" in result:
        return jsonify(result), 400
    return jsonify(result)


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
