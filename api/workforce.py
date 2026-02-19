"""
Workforce Blueprint — Flask routes for the employee sheet UI.

Thin delivery layer: business logic lives in workforce.employees.
"""

from flask import Blueprint, jsonify, request, render_template

from qms.core import get_db
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
