"""
Workforce Blueprint — Flask routes for the employee sheet UI.

Thin delivery layer: business logic lives in workforce.employees.
Import wizard routes delegate to imports.engine + workforce.import_specs.
"""

import json

from flask import Blueprint, jsonify, request, render_template, session

from qms.core import get_db
from qms.auth.decorators import module_required
from qms.workforce.employees import (
    create_employee,
    get_employee_stats,
    list_employees,
    list_potential_managers,
    update_employee,
)

bp = Blueprint("workforce", __name__, url_prefix="/workforce")


# ---------------------------------------------------------------------------
# Page routes
# ---------------------------------------------------------------------------

@bp.route("/")
def employees_page():
    return render_template("workforce/employees.html")


@bp.route("/import")
@module_required("workforce", min_role="editor")
def import_page():
    return render_template("workforce/import.html")


# ---------------------------------------------------------------------------
# Import API routes
# ---------------------------------------------------------------------------

def _get_user_id():
    """Extract current user ID from session."""
    user = session.get("user", {})
    return user.get("id", user.get("email", "unknown"))


@bp.route("/api/import/upload", methods=["POST"])
@module_required("workforce", min_role="editor")
def api_import_upload():
    """Parse uploaded file, create session, return headers + auto-mapping."""
    from qms.imports.engine import (
        auto_map_columns, create_import_session, file_hash,
        parse_file, _cache_file,
    )
    from qms.workforce.import_specs import get_employee_import_spec

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

    spec = get_employee_import_spec()
    mapping = auto_map_columns(headers, spec)

    with get_db() as conn:
        session_id = create_import_session(
            conn,
            user_id=_get_user_id(),
            module="workforce",
            spec_name=spec.name,
            filename=f.filename,
            total_rows=len(rows),
            file_hash=file_hash(file_bytes),
        )

    _cache_file(session_id, headers, rows)

    # Build available fields for the mapping UI
    available_fields = [
        {"name": c.name, "label": c.label, "required": c.required}
        for c in spec.columns
    ]

    # Sample rows (first 5)
    sample = rows[:5]

    return jsonify({
        "session_id": session_id,
        "filename": f.filename,
        "total_rows": len(rows),
        "headers": headers,
        "mapping": mapping,
        "available_fields": available_fields,
        "sample_rows": sample,
    })


@bp.route("/api/import/<session_id>/plan", methods=["POST"])
@module_required("workforce", min_role="editor")
def api_import_plan(session_id):
    """Accept final column mapping, generate action plan."""
    from qms.imports.engine import (
        generate_action_plan, get_import_session, save_action_plan,
        transform_rows, update_session_status, validate_mapping,
        _get_cached,
    )
    from qms.workforce.import_specs import get_employee_import_spec

    data = request.get_json(force=True)
    mapping = data.get("mapping", {})
    detect_missing = data.get("detect_missing", False)

    spec = get_employee_import_spec()

    # Validate mapping
    errors = validate_mapping(mapping, spec)
    if errors:
        return jsonify({"error": "Invalid mapping", "details": errors}), 400

    # Get cached file data
    cached = _get_cached(session_id)
    if not cached:
        return jsonify({"error": "Session expired — please re-upload the file"}), 410

    headers, rows = cached

    with get_db() as conn:
        sess = get_import_session(conn, session_id)
        if not sess:
            return jsonify({"error": "Session not found"}), 404

        # Transform rows
        records, parse_errors = transform_rows(rows, mapping, spec, conn)

        # Generate plan
        plan = generate_action_plan(
            conn, records, spec, session_id,
            detect_missing=detect_missing,
        )
        plan.parse_errors = parse_errors

        # Save to DB
        save_action_plan(conn, plan)
        update_session_status(conn, session_id, "review", column_mapping=mapping)

    # Build response
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
@module_required("workforce", min_role="editor")
def api_import_execute(session_id):
    """Apply approved actions from the plan."""
    from qms.imports.engine import (
        execute_approved_actions, get_import_session,
        update_session_status, _clear_cache,
    )
    from qms.workforce.import_specs import get_employee_import_spec

    data = request.get_json(force=True)
    approve_categories = set(data.get("approve_categories", []))
    reject_categories = set(data.get("reject_categories", []))
    individual_approvals = data.get("approvals", {})

    spec = get_employee_import_spec()

    with get_db() as conn:
        sess = get_import_session(conn, session_id)
        if not sess:
            return jsonify({"error": "Session not found"}), 404

        # Reload actions from DB
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

            # Apply approval logic
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

    _clear_cache(session_id)

    return jsonify({
        "session_id": session_id,
        "status": "completed",
        **counts,
    })


@bp.route("/api/import/history", methods=["GET"])
@module_required("workforce", min_role="editor")
def api_import_history():
    """Return current user's recent import sessions."""
    from qms.imports.engine import get_user_import_history

    with get_db(readonly=True) as conn:
        history = get_user_import_history(conn, _get_user_id(), "workforce")
    return jsonify(history)


@bp.route("/api/import/<session_id>/cancel", methods=["POST"])
@module_required("workforce", min_role="editor")
def api_import_cancel(session_id):
    """Cancel an in-progress import session."""
    from qms.imports.engine import (
        get_import_session, update_session_status, _clear_cache,
    )

    with get_db() as conn:
        sess = get_import_session(conn, session_id)
        if not sess:
            return jsonify({"error": "Session not found"}), 404
        update_session_status(conn, session_id, "cancelled")

    _clear_cache(session_id)
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# API routes (JSON)
# ---------------------------------------------------------------------------

@bp.route("/api/employees", methods=["GET"])
def api_list_employees():
    status = request.args.get("status") or None
    role_id = request.args.get("role_id", type=int)
    department_id = request.args.get("department_id", type=int)
    job_id = request.args.get("job_id", type=int)
    search = request.args.get("search") or None
    include_inactive = request.args.get("include_inactive") == "1"

    with get_db(readonly=True) as conn:
        rows = list_employees(
            conn,
            status=status,
            role_id=role_id,
            department_id=department_id,
            job_id=job_id,
            search=search,
            include_inactive=include_inactive,
        )
    return jsonify(rows)


@bp.route("/api/employees/stats", methods=["GET"])
def api_employee_stats():
    with get_db(readonly=True) as conn:
        stats = get_employee_stats(conn)
    return jsonify(stats)


@bp.route("/api/employees/managers", methods=["GET"])
def api_list_managers():
    with get_db(readonly=True) as conn:
        managers = list_potential_managers(conn)
    return jsonify(managers)


@bp.route("/api/roles", methods=["GET"])
def api_list_roles():
    with get_db(readonly=True) as conn:
        rows = conn.execute(
            "SELECT id, role_name, role_code FROM roles "
            "WHERE status = 'active' ORDER BY role_name"
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@bp.route("/api/departments", methods=["GET"])
def api_list_departments():
    with get_db(readonly=True) as conn:
        rows = conn.execute(
            "SELECT id, department_number, name FROM departments "
            "WHERE status = 'active' ORDER BY name"
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@bp.route("/api/jobs", methods=["GET"])
def api_list_jobs():
    with get_db(readonly=True) as conn:
        rows = conn.execute(
            "SELECT j.id, j.job_number, p.name AS project_name "
            "FROM jobs j JOIN projects p ON p.id = j.project_id "
            "ORDER BY j.job_number"
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@bp.route("/api/employees", methods=["POST"])
def api_create_employee():
    data = request.get_json(force=True)
    if not data.get("last_name") or not data.get("first_name"):
        return jsonify({"error": "last_name and first_name are required"}), 400

    with get_db() as conn:
        emp_id = create_employee(
            conn,
            last_name=data["last_name"],
            first_name=data["first_name"],
            is_employee=data.get("is_employee", True),
            is_subcontractor=data.get("is_subcontractor", False),
            position=data.get("position"),
            department_id=data.get("department_id"),
            job_id=data.get("job_id"),
            role_id=data.get("role_id"),
            email=data.get("email"),
            phone=data.get("phone"),
            supervisor_id=data.get("supervisor_id"),
            status=data.get("status", "active"),
            notes=data.get("notes"),
        )
    return jsonify({"id": emp_id, "action": "created"}), 201


@bp.route("/api/employees/<employee_id>", methods=["PUT"])
def api_update_employee(employee_id):
    data = request.get_json(force=True)
    if not data:
        return jsonify({"error": "No data provided"}), 400

    with get_db() as conn:
        row = conn.execute(
            "SELECT id FROM employees WHERE id = ?", (employee_id,)
        ).fetchone()
        if not row:
            return jsonify({"error": "Employee not found"}), 404
        updated = update_employee(conn, employee_id, **data)
    return jsonify({"id": employee_id, "action": "updated", "changed": updated})


@bp.route("/api/employees/<employee_id>/supervisor", methods=["PATCH"])
def api_set_supervisor(employee_id):
    data = request.get_json(force=True)
    supervisor_id = data.get("supervisor_id")

    with get_db() as conn:
        row = conn.execute(
            "SELECT id FROM employees WHERE id = ?", (employee_id,)
        ).fetchone()
        if not row:
            return jsonify({"error": "Employee not found"}), 404

        if supervisor_id:
            sup = conn.execute(
                "SELECT id FROM employees WHERE id = ?", (supervisor_id,)
            ).fetchone()
            if not sup:
                return jsonify({"error": "Supervisor not found"}), 404

        conn.execute(
            "UPDATE employees SET supervisor_id = ? WHERE id = ?",
            (supervisor_id, employee_id),
        )
        conn.commit()
    return jsonify({"ok": True, "supervisor_id": supervisor_id})


@bp.route("/api/employees/<employee_id>/status", methods=["PATCH"])
def api_set_status(employee_id):
    data = request.get_json(force=True)
    new_status = data.get("status", "").lower()
    valid = ("active", "inactive", "on_leave", "terminated")
    if new_status not in valid:
        return jsonify({"error": f"Invalid status. Must be one of: {valid}"}), 400

    with get_db() as conn:
        row = conn.execute(
            "SELECT id FROM employees WHERE id = ?", (employee_id,)
        ).fetchone()
        if not row:
            return jsonify({"error": "Employee not found"}), 404

        updates = {"status": new_status}
        if new_status == "terminated":
            updates["is_active"] = 0
        elif new_status == "active":
            updates["is_active"] = 1

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        vals = list(updates.values()) + [employee_id]
        conn.execute(f"UPDATE employees SET {set_clause} WHERE id = ?", vals)
        conn.commit()
    return jsonify({"ok": True, "status": new_status})


@bp.route("/api/employees/<employee_id>/role", methods=["PATCH"])
def api_set_role(employee_id):
    data = request.get_json(force=True)
    role_id = data.get("role_id")

    with get_db() as conn:
        row = conn.execute(
            "SELECT id FROM employees WHERE id = ?", (employee_id,)
        ).fetchone()
        if not row:
            return jsonify({"error": "Employee not found"}), 404

        if role_id is not None:
            role = conn.execute(
                "SELECT id FROM roles WHERE id = ?", (role_id,)
            ).fetchone()
            if not role:
                return jsonify({"error": "Role not found"}), 404

        conn.execute(
            "UPDATE employees SET role_id = ? WHERE id = ?",
            (role_id, employee_id),
        )
        conn.commit()
    return jsonify({"ok": True, "role_id": role_id})


@bp.route("/api/employees/bulk", methods=["PATCH"])
def api_bulk_update():
    data = request.get_json(force=True)
    ids = data.get("ids", [])
    action = data.get("action")
    value = data.get("value")

    if not ids:
        return jsonify({"error": "No employee IDs provided"}), 400

    with get_db() as conn:
        updated = 0
        placeholders = ",".join(["?"] * len(ids))

        if action == "assign_manager":
            if value:
                sup = conn.execute(
                    "SELECT id FROM employees WHERE id = ?", (value,)
                ).fetchone()
                if not sup:
                    return jsonify({"error": "Supervisor not found"}), 404
            conn.execute(
                f"UPDATE employees SET supervisor_id = ? WHERE id IN ({placeholders})",
                [value] + ids,
            )
            updated = conn.execute("SELECT changes()").fetchone()[0]

        elif action == "set_role":
            if value is not None:
                role = conn.execute(
                    "SELECT id FROM roles WHERE id = ?", (value,)
                ).fetchone()
                if not role:
                    return jsonify({"error": "Role not found"}), 404
            conn.execute(
                f"UPDATE employees SET role_id = ? WHERE id IN ({placeholders})",
                [value] + ids,
            )
            updated = conn.execute("SELECT changes()").fetchone()[0]

        elif action == "set_status":
            valid = ("active", "inactive", "on_leave", "terminated")
            if value not in valid:
                return jsonify({"error": f"Invalid status"}), 400
            conn.execute(
                f"UPDATE employees SET status = ? WHERE id IN ({placeholders})",
                [value] + ids,
            )
            updated = conn.execute("SELECT changes()").fetchone()[0]

        else:
            return jsonify({"error": f"Unknown action: {action}"}), 400

        conn.commit()
    return jsonify({"ok": True, "updated": updated})
