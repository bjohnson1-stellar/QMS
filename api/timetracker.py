"""
Time Tracker Blueprint — Flask routes for projections, transactions, and timecard.

Admin-only module for budget projection and hour forecasting.
"""

from flask import Blueprint, jsonify, request, render_template, session

from qms.core import get_db
from qms.timetracker import transactions as tt_txn
from qms.timetracker import projections as tt_proj
from qms.timetracker import timecard as tt_tc

bp = Blueprint("timetracker", __name__, url_prefix="/timetracker")


def _user_bu_ids():
    """Extract the current user's BU filter list from the session."""
    user = session.get("user", {})
    if user.get("role") == "admin":
        return None
    return user.get("business_units")


# ---------------------------------------------------------------------------
# Page routes (render templates)
# ---------------------------------------------------------------------------


@bp.route("/transactions")
def transactions_page():
    return render_template("timetracker/transactions.html")


@bp.route("/projections")
def projections_page():
    return render_template("timetracker/projections.html")


# ---------------------------------------------------------------------------
# Transactions API
# ---------------------------------------------------------------------------


@bp.route("/api/transactions", methods=["GET"])
def api_list_transactions():
    pid = request.args.get("project_id", type=int)
    ttype = request.args.get("type")
    return jsonify(tt_txn.list_transactions(project_id=pid, transaction_type=ttype, bu_ids=_user_bu_ids()))


@bp.route("/api/transactions/<int:txn_id>", methods=["GET"])
def api_get_transaction(txn_id):
    with get_db(readonly=True) as conn:
        t = tt_txn.get_transaction(conn, txn_id)
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
        tid = tt_txn.create_transaction(
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
        tt_txn.update_transaction(
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
        tt_txn.delete_transaction(conn, txn_id)
    return jsonify({"message": "Transaction deleted"})


# ---------------------------------------------------------------------------
# Projection Periods API
# ---------------------------------------------------------------------------


@bp.route("/api/projection-periods", methods=["GET"])
def api_list_periods():
    return jsonify(tt_proj.list_projection_periods())


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
        result = tt_proj.create_projection_period(conn, year=year, month=month)
    return jsonify({**result, "message": "Period created"}), 201


@bp.route("/api/projection-periods/<int:pid>", methods=["GET"])
def api_get_period(pid):
    with get_db(readonly=True) as conn:
        p = tt_proj.get_projection_period(conn, pid)
    if not p:
        return jsonify({"error": "Period not found"}), 404
    return jsonify(p)


@bp.route("/api/projection-periods/<int:pid>/lock", methods=["PUT"])
def api_toggle_lock(pid):
    data = request.json
    with get_db() as conn:
        ok = tt_proj.toggle_period_lock(conn, pid, locked=bool(data.get("locked")))
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
        result = tt_proj.calculate_projection(conn, int(pid))
    if "error" in result:
        return jsonify(result), 400
    return jsonify(result)


@bp.route("/api/projections/<int:pid>", methods=["GET"])
def api_get_projection(pid):
    with get_db(readonly=True) as conn:
        result = tt_proj.get_active_projection(conn, pid)
    if not result:
        return jsonify({"error": "No active snapshot"}), 404
    return jsonify(result)


# ---------------------------------------------------------------------------
# Per-Period Job Selection API
# ---------------------------------------------------------------------------


@bp.route("/api/projection-periods/<int:pid>/jobs", methods=["GET"])
def api_get_period_jobs(pid):
    with get_db() as conn:
        jobs = tt_proj.load_period_jobs(conn, pid)
    return jsonify(jobs)


@bp.route("/api/projection-periods/<int:pid>/jobs/<int:aid>/toggle", methods=["PATCH"])
def api_toggle_period_job(pid, aid):
    data = request.json or {}
    included = bool(data.get("included", True))
    with get_db() as conn:
        tt_proj.toggle_period_job(conn, pid, aid, included)
    return jsonify({"message": "Toggled"})


@bp.route("/api/projection-periods/<int:pid>/jobs/bulk-toggle", methods=["PATCH"])
def api_bulk_toggle_period_jobs(pid):
    data = request.json or {}
    ids = data.get("allocationIds", [])
    included = bool(data.get("included", True))
    if not ids:
        return jsonify({"error": "allocationIds required"}), 400
    with get_db() as conn:
        count = tt_proj.bulk_toggle_period_jobs(conn, pid, ids, included)
    return jsonify({"updated": count})


# ---------------------------------------------------------------------------
# Snapshot Management API
# ---------------------------------------------------------------------------


@bp.route("/api/projections/period/<int:pid>/snapshots", methods=["GET"])
def api_list_snapshots(pid):
    with get_db(readonly=True) as conn:
        return jsonify(tt_proj.list_snapshots(conn, pid))


@bp.route("/api/projections/snapshot/<int:sid>", methods=["GET"])
def api_get_snapshot(sid):
    with get_db(readonly=True) as conn:
        result = tt_proj.get_snapshot_with_details(conn, sid)
    if not result:
        return jsonify({"error": "Snapshot not found"}), 404
    return jsonify(result)


@bp.route("/api/projections/snapshot/<int:sid>/activate", methods=["PUT"])
def api_activate_snapshot(sid):
    with get_db() as conn:
        ok = tt_proj.activate_snapshot(conn, sid)
    if not ok:
        return jsonify({"error": "Cannot activate (not found or not Draft)"}), 400
    return jsonify({"message": "Snapshot activated"})


@bp.route("/api/projections/snapshot/<int:sid>/commit", methods=["PUT"])
def api_commit_snapshot(sid):
    with get_db() as conn:
        result = tt_proj.commit_snapshot(conn, sid)
    if "error" in result:
        return jsonify(result), 400
    return jsonify(result)


@bp.route("/api/projections/snapshot/<int:sid>/uncommit", methods=["PUT"])
def api_uncommit_snapshot(sid):
    with get_db() as conn:
        result = tt_proj.uncommit_snapshot(conn, sid)
    if "error" in result:
        return jsonify(result), 400
    return jsonify(result)


@bp.route("/api/projections/snapshot/<int:sid>/distribute", methods=["GET"])
def api_distribute_snapshot(sid):
    with get_db(readonly=True) as conn:
        result = tt_proj.distribute_projection_hours(conn, sid)
    if "error" in result:
        return jsonify(result), 404
    return jsonify(result)


@bp.route("/api/projects/budget-summary", methods=["GET"])
def api_budget_summary():
    pid = request.args.get("project_id", type=int)
    with get_db(readonly=True) as conn:
        return jsonify(tt_proj.get_budget_summary(conn, project_id=pid))


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

        result = tt_proj.create_projection_snapshot(
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
        ok = tt_proj.finalize_snapshot(conn, sid)
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
        result = tt_tc.generate_timecard_entries(conn, pid, start_date=sd, end_date=ed)

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
        result = tt_tc.generate_timecard_for_pay_period(conn, sd, ed)

    if "error" in result:
        return jsonify(result), 400
    return jsonify(result)
