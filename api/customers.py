"""
Customers Blueprint — Customer profile management.

Thin delivery layer: all business logic lives in customers.db.
"""

from flask import Blueprint, abort, jsonify, render_template, request, session

from qms.core import get_db

bp = Blueprint("customers", __name__, url_prefix="/customers")


def _require_editor():
    """Require at least editor-level access for write operations."""
    user = session.get("user", {})
    if user.get("role") == "admin":
        return user
    mod_role = user.get("modules", {}).get("customers")
    if mod_role in ("admin", "editor"):
        return user
    abort(403)


# ---------------------------------------------------------------------------
# Page routes (render templates)
# ---------------------------------------------------------------------------


@bp.route("/")
def dashboard():
    """Customer directory with stats overview."""
    from qms.customers.db import list_customers

    with get_db(readonly=True) as conn:
        customers = list_customers(conn)
        tier_counts = {}
        for c in customers:
            t = c["tier"] or "standard"
            tier_counts[t] = tier_counts.get(t, 0) + 1

    return render_template(
        "customers/dashboard.html",
        customers=customers,
        tier_counts=tier_counts,
    )


@bp.route("/<int:customer_id>")
def customer_detail(customer_id: int):
    """Customer profile — tabbed detail view."""
    from qms.customers.db import get_customer_summary

    with get_db(readonly=True) as conn:
        summary = get_customer_summary(conn, customer_id)
    if not summary:
        abort(404)
    return render_template("customers/detail.html", **summary)


# ---------------------------------------------------------------------------
# Customers API
# ---------------------------------------------------------------------------


@bp.route("/api/customers", methods=["GET"])
def api_list_customers():
    from qms.customers.db import list_customers

    status = request.args.get("status", "active")
    tier = request.args.get("tier")
    with get_db(readonly=True) as conn:
        rows = list_customers(conn, status=status, tier=tier)
    return jsonify([dict(r) for r in rows])


@bp.route("/api/customers", methods=["POST"])
def api_create_customer():
    _require_editor()
    from qms.customers.db import create_customer, get_customer

    data = request.get_json(force=True)
    if not (data.get("name") or "").strip():
        return jsonify({"error": "Customer name is required"}), 400

    with get_db() as conn:
        cid = create_customer(conn, **data)
        customer = get_customer(conn, cid)
    return jsonify(dict(customer)), 201


@bp.route("/api/customers/<int:customer_id>", methods=["PUT"])
def api_update_customer(customer_id: int):
    _require_editor()
    from qms.customers.db import get_customer, update_customer

    data = request.get_json(force=True)
    with get_db() as conn:
        if not get_customer(conn, customer_id):
            abort(404)
        update_customer(conn, customer_id, **data)
        customer = get_customer(conn, customer_id)
    return jsonify(dict(customer))


# ---------------------------------------------------------------------------
# Requirements API
# ---------------------------------------------------------------------------


@bp.route("/api/customers/<int:customer_id>/requirements", methods=["GET"])
def api_list_requirements(customer_id: int):
    from qms.customers.db import list_requirements

    category = request.args.get("category")
    with get_db(readonly=True) as conn:
        rows = list_requirements(conn, customer_id, category=category)
    return jsonify([dict(r) for r in rows])


@bp.route("/api/customers/<int:customer_id>/requirements", methods=["POST"])
def api_create_requirement(customer_id: int):
    _require_editor()
    from qms.customers.db import create_requirement

    data = request.get_json(force=True)
    with get_db() as conn:
        req_id = create_requirement(conn, customer_id, **data)
    return jsonify({"id": req_id}), 201


@bp.route("/api/requirements/<int:req_id>", methods=["PUT"])
def api_update_requirement(req_id: int):
    _require_editor()
    from qms.customers.db import update_requirement

    data = request.get_json(force=True)
    with get_db() as conn:
        if not update_requirement(conn, req_id, **data):
            abort(404)
    return jsonify({"ok": True})


@bp.route("/api/requirements/<int:req_id>", methods=["DELETE"])
def api_delete_requirement(req_id: int):
    _require_editor()
    from qms.customers.db import delete_requirement

    with get_db() as conn:
        if not delete_requirement(conn, req_id):
            abort(404)
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Specifications API
# ---------------------------------------------------------------------------


@bp.route("/api/customers/<int:customer_id>/specifications", methods=["GET"])
def api_list_specifications(customer_id: int):
    from qms.customers.db import list_specifications

    spec_type = request.args.get("spec_type")
    with get_db(readonly=True) as conn:
        rows = list_specifications(conn, customer_id, spec_type=spec_type)
    return jsonify([dict(r) for r in rows])


@bp.route("/api/customers/<int:customer_id>/specifications", methods=["POST"])
def api_create_specification(customer_id: int):
    _require_editor()
    from qms.customers.db import create_specification

    data = request.get_json(force=True)
    with get_db() as conn:
        spec_id = create_specification(conn, customer_id, **data)
    return jsonify({"id": spec_id}), 201


@bp.route("/api/specifications/<int:spec_id>", methods=["PUT"])
def api_update_specification(spec_id: int):
    _require_editor()
    from qms.customers.db import update_specification

    data = request.get_json(force=True)
    with get_db() as conn:
        if not update_specification(conn, spec_id, **data):
            abort(404)
    return jsonify({"ok": True})


@bp.route("/api/specifications/<int:spec_id>", methods=["DELETE"])
def api_delete_specification(spec_id: int):
    _require_editor()
    from qms.customers.db import delete_specification

    with get_db() as conn:
        if not delete_specification(conn, spec_id):
            abort(404)
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Quality Preferences API
# ---------------------------------------------------------------------------


@bp.route("/api/customers/<int:customer_id>/preferences", methods=["GET"])
def api_list_preferences(customer_id: int):
    from qms.customers.db import list_preferences

    ptype = request.args.get("preference_type")
    with get_db(readonly=True) as conn:
        rows = list_preferences(conn, customer_id, preference_type=ptype)
    return jsonify([dict(r) for r in rows])


@bp.route("/api/customers/<int:customer_id>/preferences", methods=["POST"])
def api_set_preference(customer_id: int):
    _require_editor()
    from qms.customers.db import set_preference

    data = request.get_json(force=True)
    for field in ("preference_type", "preference_key", "preference_value"):
        if not data.get(field):
            return jsonify({"error": f"{field} is required"}), 400

    with get_db() as conn:
        pref_id = set_preference(
            conn, customer_id,
            preference_type=data["preference_type"],
            preference_key=data["preference_key"],
            preference_value=data["preference_value"],
            notes=data.get("notes"),
        )
    return jsonify({"id": pref_id}), 201


@bp.route("/api/preferences/<int:pref_id>", methods=["DELETE"])
def api_delete_preference(pref_id: int):
    _require_editor()
    from qms.customers.db import delete_preference

    with get_db() as conn:
        if not delete_preference(conn, pref_id):
            abort(404)
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# History API
# ---------------------------------------------------------------------------


@bp.route("/api/customers/<int:customer_id>/history", methods=["GET"])
def api_list_history(customer_id: int):
    from qms.customers.db import list_history

    entry_type = request.args.get("entry_type")
    with get_db(readonly=True) as conn:
        rows = list_history(conn, customer_id, entry_type=entry_type)
    return jsonify([dict(r) for r in rows])


@bp.route("/api/customers/<int:customer_id>/history", methods=["POST"])
def api_add_history(customer_id: int):
    _require_editor()
    from qms.customers.db import add_history_entry

    data = request.get_json(force=True)
    if not data.get("entry_type") or not data.get("title"):
        return jsonify({"error": "entry_type and title are required"}), 400

    user = session.get("user", {})
    with get_db() as conn:
        entry_id = add_history_entry(
            conn, customer_id,
            entry_type=data["entry_type"],
            title=data["title"],
            description=data.get("description"),
            project_id=data.get("project_id"),
            recorded_by=user.get("id"),
        )
    return jsonify({"id": entry_id}), 201
