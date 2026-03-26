"""Equipment Blueprint — Flask routes for equipment registry web UI.

Thin delivery layer: all business logic lives in pipeline.equipment,
pipeline.conflict_detector, pipeline.spec_checker, pipeline.impact_analyzer.
"""

import json

from flask import Blueprint, abort, jsonify, render_template, request

bp = Blueprint("equipment", __name__, url_prefix="/equipment")


# ---------------------------------------------------------------------------
# Page routes
# ---------------------------------------------------------------------------


@bp.route("/")
def dashboard():
    from qms.core import get_db

    with get_db(readonly=True) as conn:
        projects = [
            dict(r)
            for r in conn.execute(
                """SELECT DISTINCT p.id, p.number, p.name
                   FROM projects p
                   JOIN equipment_instances ei ON ei.project_id = p.id
                   ORDER BY p.name"""
            ).fetchall()
        ]

    selected = request.args.get("project", type=int)
    return render_template(
        "equipment/dashboard.html",
        projects=projects,
        selected_project=selected,
    )


@bp.route("/<int:project_id>/<path:tag>")
def detail(project_id, tag):
    from qms.core import get_db

    with get_db(readonly=True) as conn:
        project = conn.execute(
            "SELECT id, number, name FROM projects WHERE id = ?",
            (project_id,),
        ).fetchone()
        if not project:
            abort(404)

    return render_template(
        "equipment/detail.html",
        project=dict(project),
        tag=tag,
    )


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------


@bp.route("/api/stats/<int:project_id>")
def api_stats(project_id):
    from qms.pipeline.equipment import get_equipment_stats

    stats = get_equipment_stats(project_id)
    return jsonify(stats)


@bp.route("/api/list/<int:project_id>")
def api_list(project_id):
    from qms.core import get_db

    discipline = request.args.get("discipline")
    system_id = request.args.get("system_id", type=int)
    search = request.args.get("search", "").strip()
    lifecycle_stage = request.args.get("lifecycle_stage")

    sql = """SELECT ei.id, ei.tag, et.name as type_name,
                    ei.discipline_primary, es.system_tag,
                    ei.lifecycle_stage, ei.hp, ei.voltage,
                    ei.parent_tag, ei.component_type
             FROM equipment_instances ei
             LEFT JOIN equipment_types et ON ei.type_id = et.id
             LEFT JOIN equipment_systems es ON ei.system_id = es.id
             WHERE ei.project_id = ?"""
    params = [project_id]

    if discipline:
        sql += " AND ei.discipline_primary = ?"
        params.append(discipline)
    if system_id:
        sql += " AND ei.system_id = ?"
        params.append(system_id)
    if lifecycle_stage:
        sql += " AND ei.lifecycle_stage = ?"
        params.append(lifecycle_stage)
    if search:
        sql += " AND ei.tag LIKE ?"
        params.append(f"%{search}%")

    sql += " ORDER BY ei.tag"

    with get_db(readonly=True) as conn:
        rows = conn.execute(sql, params).fetchall()

    return jsonify([dict(r) for r in rows])


@bp.route("/api/systems/<int:project_id>")
def api_systems(project_id):
    from qms.core import get_db

    with get_db(readonly=True) as conn:
        # Get all systems with type info and equipment counts
        systems = conn.execute(
            """SELECT es.id, es.system_tag, es.system_name,
                      es.system_category, es.discipline,
                      es.parent_system_id,
                      est.code as type_code, est.name as type_name,
                      (SELECT COUNT(*) FROM equipment_instances ei
                       WHERE ei.system_id = es.id AND ei.project_id = es.project_id
                      ) as equipment_count
               FROM equipment_systems es
               LEFT JOIN equipment_system_types est ON es.system_type_id = est.id
               WHERE es.project_id = ?
               ORDER BY es.system_category, es.system_tag""",
            (project_id,),
        ).fetchall()

    # Build hierarchy: nest children under parents
    by_id = {s["id"]: dict(s) for s in systems}
    roots = []
    for s in systems:
        s = dict(s)
        s["child_systems"] = []
        by_id[s["id"]] = s

    for s in by_id.values():
        pid = s.get("parent_system_id")
        if pid and pid in by_id:
            by_id[pid]["child_systems"].append(s)
        else:
            roots.append(s)

    return jsonify(roots)


@bp.route("/api/conflicts/<int:project_id>")
def api_conflicts(project_id):
    from qms.pipeline.conflict_detector import get_conflict_summary

    summary = get_conflict_summary(project_id)
    return jsonify(summary)


@bp.route("/api/instance/<int:project_id>/<path:tag>")
def api_instance(project_id, tag):
    from qms.core import get_db
    from qms.pipeline.equipment import get_equipment_instance
    from qms.pipeline.impact_analyzer import get_forward_impact, get_reverse_trace

    instance = get_equipment_instance(project_id, tag)
    if not instance:
        return jsonify({"error": "Not found"}), 404

    with get_db(readonly=True) as conn:
        # Type name
        type_name = ""
        if instance.get("type_id"):
            type_row = conn.execute(
                "SELECT name FROM equipment_types WHERE id = ?",
                (instance["type_id"],),
            ).fetchone()
            if type_row:
                type_name = type_row["name"]

        # Appearances
        appearances = []
        for app in conn.execute(
            """SELECT ea.discipline, ea.drawing_number, ea.attributes_on_sheet
               FROM equipment_appearances ea
               WHERE ea.instance_id = ?
               ORDER BY ea.discipline""",
            (instance["id"],),
        ).fetchall():
            app = dict(app)
            try:
                app["attributes_on_sheet"] = (
                    json.loads(app["attributes_on_sheet"])
                    if app["attributes_on_sheet"]
                    else {}
                )
            except (json.JSONDecodeError, TypeError):
                app["attributes_on_sheet"] = {}
            appearances.append(app)

        # Conflicts for this tag
        conflicts = [
            dict(r)
            for r in conn.execute(
                """SELECT * FROM equipment_conflicts
                   WHERE project_id = ? AND equipment_tag = ?
                   ORDER BY severity DESC""",
                (project_id, tag),
            ).fetchall()
        ]

        # System info
        system = None
        if instance.get("system_id"):
            sys_row = conn.execute(
                "SELECT system_tag, system_name FROM equipment_systems WHERE id = ?",
                (instance["system_id"],),
            ).fetchone()
            if sys_row:
                system = dict(sys_row)

    # Impact chains
    forward = get_forward_impact(project_id, tag, max_depth=5)
    reverse = get_reverse_trace(project_id, tag, max_depth=5)

    # Parse overflow attributes
    overflow = {}
    if instance.get("attributes"):
        try:
            overflow = json.loads(instance["attributes"])
        except (json.JSONDecodeError, TypeError):
            pass

    return jsonify({
        "instance": instance,
        "type_name": type_name,
        "system": system,
        "appearances": appearances,
        "conflicts": conflicts,
        "forward_impact": forward,
        "reverse_trace": reverse,
        "overflow_attributes": overflow,
    })
