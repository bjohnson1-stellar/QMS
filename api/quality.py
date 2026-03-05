"""
Quality Blueprint — Flask routes for quality intelligence dashboard.

Thin delivery layer: all schema lives in quality/schema.sql,
normalization in quality/db.py, import logic in quality/import_engine.py.
"""

import json

from flask import Blueprint, jsonify, render_template, request, session

from qms.core import get_db

bp = Blueprint("quality", __name__, url_prefix="/quality")


def _user_bu_ids():
    """Extract the current user's BU filter list from the session.

    Returns None (unrestricted) for admins or users with no BU assignments.
    Returns a list of BU IDs when the user is restricted to specific BUs.
    """
    user = session.get("user", {})
    if user.get("role") == "admin":
        return None
    return user.get("business_units")


def _bu_filter(bu_ids, table_alias="qi"):
    """Build a WHERE clause fragment and params for BU filtering.

    Returns (sql_fragment, params) where sql_fragment starts with 'AND'
    if filtering is needed, or is empty string with empty list otherwise.
    """
    if bu_ids is None:
        return "", []
    placeholders = ",".join("?" * len(bu_ids))
    return f"AND {table_alias}.business_unit_id IN ({placeholders})", list(bu_ids)


def _get_dashboard_stats(conn, bu_ids=None):
    """Aggregate quality issue counts for the dashboard stats cards."""
    frag, params = _bu_filter(bu_ids)
    base = "SELECT COUNT(*) FROM quality_issues qi WHERE 1=1 "

    total = conn.execute(base + frag, params).fetchone()[0]
    open_count = conn.execute(
        base + "AND qi.status = 'open' " + frag, params
    ).fetchone()[0]
    in_progress = conn.execute(
        base + "AND qi.status IN ('in_progress', 'in_review') " + frag, params
    ).fetchone()[0]
    critical = conn.execute(
        base + "AND qi.severity = 'critical' AND qi.status != 'closed' " + frag, params
    ).fetchone()[0]

    return {
        "total_issues": total,
        "open_issues": open_count,
        "in_progress": in_progress,
        "critical_issues": critical,
    }


def _get_recent_issues(conn, limit=10, bu_ids=None):
    """Return the N most recent quality issues with project info."""
    frag, params = _bu_filter(bu_ids)
    rows = conn.execute(
        f"""
        SELECT qi.id, qi.title, qi.type, qi.status, qi.severity,
               qi.trade, qi.due_date, qi.created_at,
               p.number AS project_number, p.name AS project_name
        FROM quality_issues qi
        LEFT JOIN projects p ON p.id = qi.project_id
        WHERE 1=1 {frag}
        ORDER BY qi.created_at DESC
        LIMIT ?
        """,
        params + [limit],
    ).fetchall()
    return [dict(r) for r in rows]


def _get_issues_by_project(conn, bu_ids=None):
    """Aggregate issue counts per project for the breakdown table."""
    frag, params = _bu_filter(bu_ids)
    rows = conn.execute(
        f"""
        SELECT p.number AS project_number, p.name AS project_name,
               COUNT(*) AS total,
               COUNT(CASE WHEN qi.status = 'open' THEN 1 END) AS open_count,
               COUNT(CASE WHEN qi.severity = 'critical'
                          AND qi.status != 'closed' THEN 1 END) AS critical_count
        FROM quality_issues qi
        JOIN projects p ON p.id = qi.project_id
        WHERE 1=1 {frag}
        GROUP BY qi.project_id
        ORDER BY total DESC
        """,
        params,
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Page routes
# ---------------------------------------------------------------------------


@bp.route("/")
def dashboard():
    with get_db(readonly=True) as conn:
        stats = _get_dashboard_stats(conn, bu_ids=_user_bu_ids())
        recent = _get_recent_issues(conn, limit=10, bu_ids=_user_bu_ids())
        by_project = _get_issues_by_project(conn, bu_ids=_user_bu_ids())
    return render_template(
        "quality/dashboard.html",
        stats=stats,
        recent=recent,
        by_project=by_project,
    )


@bp.route("/browse")
def browse():
    return render_template("quality/browse.html")


@bp.route("/captures")
def captures():
    return render_template("quality/captures.html")


# ---------------------------------------------------------------------------
# JSON API — aggregations for charts
# ---------------------------------------------------------------------------


@bp.route("/api/by-type")
def api_by_type():
    frag, params = _bu_filter(_user_bu_ids())
    with get_db(readonly=True) as conn:
        rows = conn.execute(
            f"SELECT type, COUNT(*) AS count FROM quality_issues qi "
            f"WHERE 1=1 {frag} GROUP BY type ORDER BY count DESC",
            params,
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@bp.route("/api/by-status")
def api_by_status():
    frag, params = _bu_filter(_user_bu_ids())
    with get_db(readonly=True) as conn:
        rows = conn.execute(
            f"SELECT status, COUNT(*) AS count FROM quality_issues qi "
            f"WHERE 1=1 {frag} GROUP BY status ORDER BY count DESC",
            params,
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@bp.route("/api/by-trade")
def api_by_trade():
    frag, params = _bu_filter(_user_bu_ids())
    with get_db(readonly=True) as conn:
        rows = conn.execute(
            f"SELECT trade, COUNT(*) AS count FROM quality_issues qi "
            f"WHERE trade IS NOT NULL AND trade != '' AND 1=1 {frag} "
            f"GROUP BY trade ORDER BY count DESC",
            params,
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@bp.route("/api/search")
def api_search():
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify([])

    bu_ids = _user_bu_ids()
    frag, bu_params = _bu_filter(bu_ids)

    # Try vector search first
    try:
        from qms.vectordb.search import search_collection

        results = search_collection("quality_issues", query, n_results=30)
        if results:
            issue_ids = [r["metadata"]["db_id"] for r in results if "metadata" in r]
            if issue_ids:
                placeholders = ",".join("?" * len(issue_ids))
                with get_db(readonly=True) as conn:
                    rows = conn.execute(
                        f"""
                        SELECT qi.id, qi.title, qi.type, qi.status, qi.severity,
                               qi.trade, qi.location, qi.due_date, qi.created_at,
                               p.number AS project_number, p.name AS project_name
                        FROM quality_issues qi
                        LEFT JOIN projects p ON p.id = qi.project_id
                        WHERE qi.id IN ({placeholders}) {frag}
                        """,
                        issue_ids + bu_params,
                    ).fetchall()
                # Preserve vector similarity order
                row_map = {r["id"]: dict(r) for r in rows}
                ordered = [row_map[iid] for iid in issue_ids if iid in row_map]
                return jsonify(ordered)
    except Exception:
        pass  # Fallback to SQL LIKE

    # SQL LIKE fallback
    with get_db(readonly=True) as conn:
        like_param = f"%{query}%"
        rows = conn.execute(
            f"""
            SELECT qi.id, qi.title, qi.type, qi.status, qi.severity,
                   qi.trade, qi.location, qi.due_date, qi.created_at,
                   p.number AS project_number, p.name AS project_name
            FROM quality_issues qi
            LEFT JOIN projects p ON p.id = qi.project_id
            WHERE (qi.title LIKE ? OR qi.description LIKE ?) {frag}
            ORDER BY qi.created_at DESC LIMIT 50
            """,
            [like_param, like_param] + bu_params,
        ).fetchall()
    return jsonify([dict(r) for r in rows])


# ---------------------------------------------------------------------------
# JSON API — core endpoints (from Plan 01)
# ---------------------------------------------------------------------------


@bp.route("/api/stats")
def api_stats():
    with get_db(readonly=True) as conn:
        stats = _get_dashboard_stats(conn, bu_ids=_user_bu_ids())
    return jsonify(stats)


@bp.route("/api/issues")
def api_issues():
    bu_ids = _user_bu_ids()
    frag, params = _bu_filter(bu_ids)

    # Optional filters from query string
    filters = ""
    for col in ("type", "status", "severity"):
        val = request.args.get(col)
        if val:
            filters += f" AND qi.{col} = ?"
            params.append(val)

    project_id = request.args.get("project_id")
    if project_id:
        filters += " AND qi.project_id = ?"
        params.append(project_id)

    with get_db(readonly=True) as conn:
        rows = conn.execute(
        f"""
        SELECT qi.id, qi.title, qi.type, qi.status, qi.severity,
               qi.trade, qi.location, qi.due_date, qi.created_at,
               qi.source, qi.source_id,
               p.number AS project_number, p.name AS project_name,
               rc.name AS root_cause
        FROM quality_issues qi
        LEFT JOIN projects p ON p.id = qi.project_id
        LEFT JOIN root_causes rc ON rc.id = qi.root_cause_id
        WHERE 1=1 {frag} {filters}
        ORDER BY qi.created_at DESC
        LIMIT 200
        """,
            params,
        ).fetchall()
    return jsonify([dict(r) for r in rows])


# ---------------------------------------------------------------------------
# JSON API — mobile captures
# ---------------------------------------------------------------------------


@bp.route("/api/captures")
def api_captures():
    """Return mobile-captured issues with capture_log and attachment info."""
    bu_ids = _user_bu_ids()
    frag, params = _bu_filter(bu_ids)

    days = request.args.get("days", 30, type=int)

    with get_db(readonly=True) as conn:
        rows = conn.execute(
            f"""
            SELECT qi.id, qi.title, qi.type, qi.status, qi.severity,
                   qi.trade, qi.location, qi.description, qi.created_at,
                   qi.metadata,
                   cl.filename AS source_file, cl.processed_at,
                   a.filepath AS attachment_path, a.file_type,
                   p.number AS project_number, p.name AS project_name
            FROM quality_issues qi
            JOIN capture_log cl ON cl.issue_id = qi.id
            LEFT JOIN quality_issue_attachments a ON a.issue_id = qi.id
            LEFT JOIN projects p ON p.id = qi.project_id
            WHERE qi.source = 'mobile'
              AND qi.created_at >= datetime('now', '-' || ? || ' days')
              {frag}
            ORDER BY qi.created_at DESC
            """,
            [days] + params,
        ).fetchall()

    results = []
    for r in rows:
        item = dict(r)
        # Parse metadata to extract transcript and recommended_action
        if item.get("metadata"):
            try:
                meta = json.loads(item["metadata"])
                item["transcript"] = meta.get("transcript", "")
                item["recommended_action"] = meta.get("recommended_action", "")
            except (json.JSONDecodeError, TypeError):
                item["transcript"] = ""
                item["recommended_action"] = ""
        else:
            item["transcript"] = ""
            item["recommended_action"] = ""
        del item["metadata"]
        results.append(item)

    return jsonify(results)


@bp.route("/api/captures/<int:issue_id>", methods=["PUT"])
def api_captures_update(issue_id):
    """Update a mobile-captured issue (inline edit from review page)."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "No JSON body"}), 400

    allowed = {"title", "trade", "severity", "description", "location"}
    updates = {k: v for k, v in data.items() if k in allowed}
    if not updates:
        return jsonify({"error": "No valid fields to update"}), 400

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values())

    with get_db() as conn:
        # Verify issue exists and is mobile-sourced
        row = conn.execute(
            "SELECT id FROM quality_issues WHERE id = ? AND source = 'mobile'",
            (issue_id,),
        ).fetchone()
        if not row:
            return jsonify({"error": "Issue not found or not a mobile capture"}), 404

        conn.execute(
            f"UPDATE quality_issues SET {set_clause} WHERE id = ?",
            values + [issue_id],
        )

        # Log changes to history
        user = session.get("user", {})
        for field, new_val in updates.items():
            conn.execute(
                """INSERT INTO quality_issue_history
                   (issue_id, field_name, new_value, changed_by)
                   VALUES (?, ?, ?, ?)""",
                (issue_id, field, str(new_val), user.get("email", "system")),
            )

        # Return updated issue
        updated = conn.execute(
            """SELECT id, title, type, status, severity, trade, location, description
               FROM quality_issues WHERE id = ?""",
            (issue_id,),
        ).fetchone()

    return jsonify(dict(updated))
