"""
Licenses Blueprint — Flask routes for state license tracking.

Thin delivery layer: business logic lives in licenses.db.
"""

import csv
import io
import json
from datetime import datetime as _dt

from flask import (
    Blueprint, Response, current_app, jsonify, request,
    render_template, send_file, session,
)

from qms.core import get_db
from qms.auth.decorators import module_required
from qms.licenses.notifications import (
    acknowledge_notification,
    generate_all_notifications,
    get_notification_summary,
    list_active_notifications,
    resolve_notification,
)
from qms.licenses.db import (
    batch_get_license_scopes,
    calculate_compliance_score,
    create_ce_credit,
    create_ce_requirement,
    create_document,
    create_entity,
    create_event,
    create_license,
    create_note,
    create_registration,
    create_requirement,
    create_scope_category,
    delete_ce_credit,
    delete_ce_requirement,
    delete_document,
    delete_entity,
    delete_license,
    delete_note,
    delete_registration,
    delete_requirement,
    get_activity_feed,
    get_ce_compliance_report,
    get_ce_summary,
    get_certificate_path,
    get_compliance_dashboard_data,
    get_compliance_gap_analysis,
    get_compliance_summary_by_state,
    get_document,
    get_document_path,
    get_entity,
    get_entity_hierarchy,
    get_entity_summary,
    get_expiring_licenses,
    get_license,
    get_license_board,
    get_license_events,
    get_license_scopes,
    get_license_stats,
    get_registration,
    get_renewal_timeline,
    get_requirement,
    get_scope_coverage_gaps,
    get_state_license_summary,
    get_state_map_data,
    list_ce_credits,
    list_ce_requirements,
    list_documents,
    list_entities,
    list_licenses,
    list_licenses_for_state,
    list_notes,
    list_registrations,
    list_requirements,
    list_scope_categories,
    renew_license,
    save_certificate_file,
    save_document_file,
    set_license_scopes,
    update_ce_credit,
    update_ce_requirement,
    update_entity,
    update_license,
    update_registration,
    update_requirement,
    upsert_license_board,
    delete_portal_credential,
    get_portal_credential,
    upsert_portal_credential,
    VALID_ENTITY_TYPES,
    VALID_ENTITY_STATUSES,
    VALID_EVENT_TYPES,
    VALID_FEE_TYPES,
    VALID_FILING_FREQUENCIES,
    VALID_REGISTRATION_TYPES,
    VALID_REGISTRATION_STATUSES,
)

bp = Blueprint("licenses", __name__, url_prefix="/licenses")

_STATE_NAMES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia",
}

_VALID_HOLDER_TYPES = {"company", "employee"}
_VALID_STATUSES = {"active", "expired", "suspended", "pending"}
_DATE_FIELDS = {"expiration_date", "issued_date", "association_date", "disassociation_date"}


def _validate_date(value: str, field_name: str) -> str | None:
    """Return error string if value is not a valid YYYY-MM-DD date, else None."""
    try:
        _dt.strptime(value, "%Y-%m-%d")
        return None
    except (ValueError, TypeError):
        return f"Invalid date format for {field_name}: expected YYYY-MM-DD"


def _validate_license_fields(data: dict, require_all: bool = False) -> list[str]:
    """Validate license create/update fields. Returns list of error strings."""
    errors: list[str] = []

    if require_all:
        for f in ("business_entity", "state_code", "license_type", "license_number"):
            if not data.get(f):
                errors.append(f"Missing required field: {f}")

    if "state_code" in data and data["state_code"]:
        sc = str(data["state_code"]).strip().upper()
        data["state_code"] = sc
        if sc not in _STATE_NAMES:
            errors.append(f"Invalid state code: {sc}")

    if "holder_type" in data and data["holder_type"]:
        if data["holder_type"] not in _VALID_HOLDER_TYPES:
            errors.append(f"Invalid holder_type: must be one of {sorted(_VALID_HOLDER_TYPES)}")

    if "status" in data and data["status"]:
        if data["status"] not in _VALID_STATUSES:
            errors.append(f"Invalid status: must be one of {sorted(_VALID_STATUSES)}")

    for df in _DATE_FIELDS:
        if df in data and data[df]:
            err = _validate_date(data[df], df)
            if err:
                errors.append(err)

    if "license_number" in data and data.get("license_number"):
        data["license_number"] = str(data["license_number"]).strip()
        if len(data["license_number"]) > 100:
            errors.append("license_number exceeds 100 characters")

    if "license_type" in data and data.get("license_type"):
        data["license_type"] = str(data["license_type"]).strip()
        if len(data["license_type"]) > 100:
            errors.append("license_type exceeds 100 characters")

    return errors


def _validate_ce_credit_fields(data: dict) -> list[str]:
    """Validate CE credit create/update fields. Returns list of error strings."""
    errors: list[str] = []

    if "hours" in data and data.get("hours") is not None:
        try:
            h = float(data["hours"])
            if h < 0:
                errors.append("hours must be a positive number")
            elif h > 999:
                errors.append("hours exceeds maximum of 999")
        except (ValueError, TypeError):
            errors.append("hours must be a number")

    if "completion_date" in data and data.get("completion_date"):
        err = _validate_date(data["completion_date"], "completion_date")
        if err:
            errors.append(err)

    if "course_name" in data and data.get("course_name"):
        data["course_name"] = str(data["course_name"]).strip()
        if len(data["course_name"]) > 200:
            errors.append("course_name exceeds 200 characters")

    return errors


def _validate_ce_requirement_fields(data: dict) -> list[str]:
    """Validate CE requirement create/update fields. Returns list of error strings."""
    errors: list[str] = []

    if "state_code" in data and data.get("state_code"):
        sc = str(data["state_code"]).strip().upper()
        data["state_code"] = sc
        if sc not in _STATE_NAMES:
            errors.append(f"Invalid state code: {sc}")

    if "hours_required" in data and data.get("hours_required") is not None:
        try:
            h = float(data["hours_required"])
            if h <= 0:
                errors.append("hours_required must be a positive number")
        except (ValueError, TypeError):
            errors.append("hours_required must be a number")

    if "period_months" in data and data.get("period_months") is not None:
        try:
            p = int(data["period_months"])
            if p <= 0:
                errors.append("period_months must be a positive integer")
        except (ValueError, TypeError):
            errors.append("period_months must be a positive integer")

    return errors


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


@bp.route("/entities")
@module_required("licenses")
def entities_page():
    return render_template("licenses/entities.html")


@bp.route("/entities/<entity_id>")
@module_required("licenses")
def entity_detail_page(entity_id):
    with get_db(readonly=True) as conn:
        entity = get_entity(conn, entity_id)
        if not entity:
            return "Entity not found", 404
        # All entities for parent dropdown in edit modal
        all_entities = list_entities(conn, per_page=200)["items"]
    return render_template(
        "licenses/entity_detail.html",
        entity=entity,
        all_entities=[e for e in all_entities if e["id"] != entity_id],
    )


@bp.route("/state/<state_code>")
@module_required("licenses")
def state_detail_page(state_code):
    state_code = state_code.upper()
    state_name = _STATE_NAMES.get(state_code)
    if not state_name:
        return "State not found", 404
    with get_db(readonly=True) as conn:
        board = get_license_board(conn, state_code)
        stats = get_state_license_summary(conn, state_code)
        licenses_list = list_licenses_for_state(conn, state_code)
        ce_reqs = list_ce_requirements(conn, state_code=state_code)
        state_reqs_result = list_requirements(conn, state_code=state_code)
        state_reqs = state_reqs_result.get("items", state_reqs_result) if isinstance(state_reqs_result, dict) else state_reqs_result
        scopes = list_scope_categories(conn)
        # Batch-load scopes for all licenses (single query instead of N+1)
        license_ids = [lic["id"] for lic in licenses_list]
        scopes_map = batch_get_license_scopes(conn, license_ids)
        for lic in licenses_list:
            lic["scopes"] = scopes_map.get(lic["id"], [])
    return render_template(
        "licenses/state_detail.html",
        state_code=state_code,
        state_name=state_name,
        board=board,
        stats=stats,
        licenses=licenses_list,
        ce_reqs=ce_reqs,
        state_reqs=state_reqs,
        scopes=scopes,
    )


@bp.route("/<license_id>")
@module_required("licenses")
def license_detail_page(license_id):
    with get_db(readonly=True) as conn:
        lic = get_license(conn, license_id)
        if not lic:
            return "License not found", 404
        scopes = get_license_scopes(conn, license_id)
        all_scopes = list_scope_categories(conn)
        ce_summary = get_ce_summary(conn, license_id)
        credits = list_ce_credits(conn, license_id=license_id)
        # Get qualifying party name
        qp_name = None
        if lic.get("employee_id"):
            emp = conn.execute(
                "SELECT first_name || ' ' || last_name AS name FROM employees WHERE id = ?",
                (lic["employee_id"],),
            ).fetchone()
            if emp:
                qp_name = emp["name"]
        # Get current user's portal credentials
        user = session.get("user", {})
        user_id = user.get("id", user.get("email", ""))
        portal_cred = None
        if user_id:
            secret = current_app.config.get("SECRET_KEY", "")
            portal_cred = get_portal_credential(conn, license_id, user_id, secret)
        events = get_license_events(conn, license_id)
        compliance = calculate_compliance_score(conn, license_id)
    state_name = _STATE_NAMES.get(lic["state_code"], lic["state_code"])
    return render_template(
        "licenses/license_detail.html",
        license=lic,
        state_name=state_name,
        qualifying_party_name=qp_name,
        scopes=scopes,
        all_scopes=all_scopes,
        ce_summary=ce_summary,
        credits=credits,
        portal_cred=portal_cred,
        events=events,
        compliance=compliance,
    )


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@bp.route("/api/licenses", methods=["GET"])
@module_required("licenses")
def api_list_licenses():
    # Parse pagination params (0 = no limit, backward compat)
    try:
        page = int(request.args.get("page", 0))
        per_page = int(request.args.get("per_page", 0))
    except (ValueError, TypeError):
        page, per_page = 0, 0

    with get_db(readonly=True) as conn:
        result = list_licenses(
            conn,
            holder_type=request.args.get("holder_type"),
            state_code=request.args.get("state_code"),
            status=request.args.get("status"),
            search=request.args.get("search"),
            page=page,
            per_page=per_page,
        )
    return jsonify(result)


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
    errors = _validate_license_fields(data, require_all=True)
    if errors:
        return jsonify({"error": "; ".join(errors)}), 400

    # Auto-populate holder_name from business_entity for backward compat
    if not data.get("holder_name"):
        data["holder_name"] = data.get("business_entity", "")

    user = session.get("user", {})
    data["created_by"] = user.get("id", user.get("email", "unknown"))

    with get_db() as conn:
        result = create_license(conn, **data)
    return jsonify(result), 201


@bp.route("/api/licenses/<license_id>", methods=["PUT"])
@module_required("licenses", min_role="editor")
def api_update_license(license_id):
    data = request.get_json(force=True)
    errors = _validate_license_fields(data)
    if errors:
        return jsonify({"error": "; ".join(errors)}), 400
    user = session.get("user", {})
    data["changed_by"] = user.get("id", user.get("email", "unknown"))
    with get_db() as conn:
        result = update_license(conn, license_id, **data)
    if not result:
        return jsonify({"error": "License not found"}), 404
    return jsonify(result)


@bp.route("/api/licenses/<license_id>", methods=["DELETE"])
@module_required("licenses", min_role="admin")
def api_delete_license(license_id):
    user = session.get("user", {})
    changed_by = user.get("id", user.get("email", "unknown"))
    with get_db() as conn:
        deleted = delete_license(conn, license_id, changed_by=changed_by)
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
# Board API routes
# ---------------------------------------------------------------------------

@bp.route("/api/boards/<state_code>", methods=["GET"])
@module_required("licenses")
def api_get_board(state_code):
    with get_db(readonly=True) as conn:
        board = get_license_board(conn, state_code.upper())
    if not board:
        return jsonify({"error": "Board not found"}), 404
    return jsonify(board)


@bp.route("/api/boards/<state_code>", methods=["PUT"])
@module_required("licenses", min_role="admin")
def api_update_board(state_code):
    data = request.get_json(force=True)
    user = session.get("user", {})
    data["updated_by"] = user.get("id", user.get("email", "unknown"))
    with get_db() as conn:
        result = upsert_license_board(conn, state_code.upper(), **data)
    return jsonify(result)


# ---------------------------------------------------------------------------
# Scope Categories API routes
# ---------------------------------------------------------------------------

@bp.route("/api/scope-categories", methods=["GET"])
@module_required("licenses")
def api_list_scopes():
    with get_db(readonly=True) as conn:
        scopes = list_scope_categories(conn)
    return jsonify(scopes)


@bp.route("/api/scope-categories", methods=["POST"])
@module_required("licenses", min_role="admin")
def api_create_scope():
    data = request.get_json(force=True)
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "Name is required"}), 400
    with get_db() as conn:
        result = create_scope_category(conn, name)
    return jsonify(result), 201


# ---------------------------------------------------------------------------
# License Scopes API routes
# ---------------------------------------------------------------------------

@bp.route("/api/licenses/<license_id>/scopes", methods=["GET"])
@module_required("licenses")
def api_get_license_scopes(license_id):
    with get_db(readonly=True) as conn:
        scopes = get_license_scopes(conn, license_id)
    return jsonify(scopes)


@bp.route("/api/licenses/<license_id>/scopes", methods=["PUT"])
@module_required("licenses", min_role="editor")
def api_set_license_scopes(license_id):
    data = request.get_json(force=True)
    scope_ids = data.get("scope_ids", [])
    with get_db() as conn:
        result = set_license_scopes(conn, license_id, scope_ids)
    return jsonify(result)


# ---------------------------------------------------------------------------
# CE Requirements API routes
# ---------------------------------------------------------------------------

@bp.route("/api/ce-requirements", methods=["GET"])
@module_required("licenses")
def api_list_ce_requirements():
    with get_db(readonly=True) as conn:
        reqs = list_ce_requirements(conn, state_code=request.args.get("state_code"))
    return jsonify(reqs)


@bp.route("/api/ce-requirements", methods=["POST"])
@module_required("licenses", min_role="editor")
def api_create_ce_requirement():
    data = request.get_json(force=True)
    required = ["state_code", "license_type", "hours_required", "period_months"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"error": f"Missing: {', '.join(missing)}"}), 400
    errors = _validate_ce_requirement_fields(data)
    if errors:
        return jsonify({"error": "; ".join(errors)}), 400
    user = session.get("user", {})
    data["created_by"] = user.get("id", user.get("email", "unknown"))
    with get_db() as conn:
        result = create_ce_requirement(conn, **data)
    return jsonify(result), 201


@bp.route("/api/ce-requirements/<req_id>", methods=["PUT"])
@module_required("licenses", min_role="editor")
def api_update_ce_requirement(req_id):
    data = request.get_json(force=True)
    errors = _validate_ce_requirement_fields(data)
    if errors:
        return jsonify({"error": "; ".join(errors)}), 400
    user = session.get("user", {})
    data["changed_by"] = user.get("id", user.get("email", "unknown"))
    with get_db() as conn:
        result = update_ce_requirement(conn, req_id, **data)
    if not result:
        return jsonify({"error": "Not found"}), 404
    return jsonify(result)


@bp.route("/api/ce-requirements/<req_id>", methods=["DELETE"])
@module_required("licenses", min_role="admin")
def api_delete_ce_requirement(req_id):
    user = session.get("user", {})
    changed_by = user.get("id", user.get("email", "unknown"))
    with get_db() as conn:
        deleted = delete_ce_requirement(conn, req_id, changed_by=changed_by)
    if not deleted:
        return jsonify({"error": "Not found"}), 404
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# CE Credits API routes
# ---------------------------------------------------------------------------

@bp.route("/api/ce-credits", methods=["GET"])
@module_required("licenses")
def api_list_ce_credits():
    with get_db(readonly=True) as conn:
        credits = list_ce_credits(
            conn,
            license_id=request.args.get("license_id"),
            employee_id=request.args.get("employee_id"),
        )
    return jsonify(credits)


@bp.route("/api/ce-credits", methods=["POST"])
@module_required("licenses", min_role="editor")
def api_create_ce_credit():
    # Support both JSON and multipart (when certificate file attached)
    if request.content_type and "multipart" in request.content_type:
        data = dict(request.form)
        if "hours" in data:
            data["hours"] = float(data["hours"])
    else:
        data = request.get_json(force=True)

    required = ["employee_id", "license_id", "course_name", "hours", "completion_date"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"error": f"Missing: {', '.join(missing)}"}), 400
    errors = _validate_ce_credit_fields(data)
    if errors:
        return jsonify({"error": "; ".join(errors)}), 400

    # Handle certificate file upload
    if "certificate" in request.files:
        f = request.files["certificate"]
        if f.filename:
            rel_path = save_certificate_file(
                data["license_id"], f.filename, f.read()
            )
            data["certificate_file"] = rel_path

    user = session.get("user", {})
    data["created_by"] = user.get("id", user.get("email", "unknown"))
    with get_db() as conn:
        result = create_ce_credit(conn, **data)
    return jsonify(result), 201


@bp.route("/api/ce-credits/<credit_id>", methods=["PUT"])
@module_required("licenses", min_role="editor")
def api_update_ce_credit(credit_id):
    if request.content_type and "multipart" in request.content_type:
        data = dict(request.form)
        if "hours" in data:
            data["hours"] = float(data["hours"])
    else:
        data = request.get_json(force=True)

    errors = _validate_ce_credit_fields(data)
    if errors:
        return jsonify({"error": "; ".join(errors)}), 400

    # Handle certificate file upload
    if "certificate" in request.files:
        f = request.files["certificate"]
        if f.filename:
            # Need license_id to determine storage path
            with get_db(readonly=True) as conn:
                existing = conn.execute(
                    "SELECT license_id FROM ce_credits WHERE id = ?",
                    (credit_id,),
                ).fetchone()
            if existing:
                rel_path = save_certificate_file(
                    existing["license_id"], f.filename, f.read()
                )
                data["certificate_file"] = rel_path

    user = session.get("user", {})
    data["changed_by"] = user.get("id", user.get("email", "unknown"))
    with get_db() as conn:
        result = update_ce_credit(conn, credit_id, **data)
    if not result:
        return jsonify({"error": "Not found"}), 404
    return jsonify(result)


@bp.route("/api/ce-credits/<credit_id>", methods=["DELETE"])
@module_required("licenses", min_role="admin")
def api_delete_ce_credit(credit_id):
    user = session.get("user", {})
    changed_by = user.get("id", user.get("email", "unknown"))
    with get_db() as conn:
        deleted = delete_ce_credit(conn, credit_id, changed_by=changed_by)
    if not deleted:
        return jsonify({"error": "Not found"}), 404
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# CE Summary + Coverage Gaps API routes
# ---------------------------------------------------------------------------

@bp.route("/api/ce-summary/<license_id>", methods=["GET"])
@module_required("licenses")
def api_ce_summary(license_id):
    with get_db(readonly=True) as conn:
        summary = get_ce_summary(conn, license_id)
    return jsonify(summary)


@bp.route("/api/coverage-gaps", methods=["GET"])
@module_required("licenses")
def api_coverage_gaps():
    with get_db(readonly=True) as conn:
        gaps = get_scope_coverage_gaps(conn)
    return jsonify(gaps)


# ---------------------------------------------------------------------------
# Portal Credentials API routes
# ---------------------------------------------------------------------------

@bp.route("/api/licenses/<license_id>/credentials", methods=["GET"])
@module_required("licenses")
def api_get_credentials(license_id):
    user = session.get("user", {})
    user_id = user.get("id", user.get("email"))
    if not user_id:
        return jsonify({"error": "Not authenticated"}), 401
    secret = current_app.config.get("SECRET_KEY", "")
    with get_db(readonly=True) as conn:
        cred = get_portal_credential(conn, license_id, user_id, secret)
    if not cred:
        return jsonify(None)
    return jsonify(cred)


@bp.route("/api/licenses/<license_id>/credentials", methods=["PUT"])
@module_required("licenses")
def api_upsert_credentials(license_id):
    data = request.get_json(force=True)
    if not data.get("username") or not data.get("password"):
        return jsonify({"error": "Username and password are required"}), 400
    user = session.get("user", {})
    user_id = user.get("id", user.get("email"))
    if not user_id:
        return jsonify({"error": "Not authenticated"}), 401
    secret = current_app.config.get("SECRET_KEY", "")
    with get_db() as conn:
        result = upsert_portal_credential(
            conn, license_id, user_id, secret, **data
        )
    return jsonify(result)


@bp.route("/api/licenses/<license_id>/credentials", methods=["DELETE"])
@module_required("licenses")
def api_delete_credentials(license_id):
    user = session.get("user", {})
    user_id = user.get("id", user.get("email"))
    if not user_id:
        return jsonify({"error": "Not authenticated"}), 401
    with get_db() as conn:
        deleted = delete_portal_credential(conn, license_id, user_id)
    if not deleted:
        return jsonify({"error": "Not found"}), 404
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Certificate Download
# ---------------------------------------------------------------------------

@bp.route("/api/ce-credits/<credit_id>/certificate", methods=["GET"])
@module_required("licenses")
def api_download_certificate(credit_id):
    with get_db(readonly=True) as conn:
        full_path = get_certificate_path(conn, credit_id)
    if not full_path:
        return jsonify({"error": "Certificate not found"}), 404
    import os
    return send_file(
        full_path,
        as_attachment=True,
        download_name=os.path.basename(full_path),
    )


# ---------------------------------------------------------------------------
# CSV Exports
# ---------------------------------------------------------------------------

@bp.route("/export/licenses.csv", methods=["GET"])
@module_required("licenses")
def export_licenses_csv():
    """Export all licenses as CSV."""
    with get_db(readonly=True) as conn:
        rows = list_licenses(conn)["items"]  # Unpaginated (per_page=0)

        # Batch-load scopes (single query instead of N+1)
        license_ids = [r["id"] for r in rows]
        scopes_map = batch_get_license_scopes(conn, license_ids)
        for r in rows:
            r["scopes"] = ", ".join(
                s["name"] for s in scopes_map.get(r["id"], [])
            )

        # Batch-load employee names (single query instead of N+1)
        emp_ids = [r["employee_id"] for r in rows if r.get("employee_id")]
        emp_map: dict = {}
        if emp_ids:
            ph = ",".join("?" for _ in emp_ids)
            emp_rows = conn.execute(
                f"SELECT id, first_name || ' ' || last_name AS name "
                f"FROM employees WHERE id IN ({ph})",
                emp_ids,
            ).fetchall()
            emp_map = {e["id"]: e["name"] for e in emp_rows}
        for r in rows:
            r["qualifying_party"] = emp_map.get(r.get("employee_id", ""), "")

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "State", "License Type", "License #", "Business Entity",
        "Qualifying Party", "Scopes", "Status", "Expiration",
        "Issued", "Notes",
    ])
    for r in rows:
        writer.writerow([
            r["state_code"], r["license_type"], r["license_number"],
            r.get("business_entity") or r.get("holder_name", ""),
            r["qualifying_party"], r["scopes"], r["status"],
            r.get("expiration_date", ""), r.get("issued_date", ""),
            r.get("notes", ""),
        ])

    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=licenses.csv"},
    )


@bp.route("/export/ce-compliance.csv", methods=["GET"])
@module_required("licenses")
def export_ce_compliance_csv():
    """Export CE compliance report as CSV."""
    with get_db(readonly=True) as conn:
        report = get_ce_compliance_report(conn)

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "State", "License Type", "License #", "Qualifying Party",
        "Hours Required", "Hours Earned", "% Complete",
        "Period (months)", "Status", "Expiration",
    ])
    for r in report:
        writer.writerow([
            r["state_code"], r["license_type"], r["license_number"],
            r.get("qualifying_party", ""),
            r["hours_required"], r["hours_earned"], r["pct_complete"],
            r["period_months"], r["ce_status"],
            r.get("expiration_date", ""),
        ])

    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=ce-compliance.csv"},
    )


# ---------------------------------------------------------------------------
# Compliance Dashboard API
# ---------------------------------------------------------------------------

@bp.route("/api/compliance-dashboard", methods=["GET"])
@module_required("licenses")
def api_compliance_dashboard():
    with get_db(readonly=True) as conn:
        data = get_compliance_dashboard_data(conn)
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

        # Read back saved rows to get actual DB IDs for round-trip
        saved_rows = conn.execute(
            "SELECT id, row_index, action_type, record_data, existing_data, "
            "match_method, changes, reason FROM import_actions "
            "WHERE session_id = ? ORDER BY id",
            (session_id,),
        ).fetchall()

    categories = {}
    for row in saved_rows:
        atype = row["action_type"]
        if atype not in categories:
            categories[atype] = []
        categories[atype].append({
            "id": row["id"],
            "row_index": row["row_index"],
            "record": json.loads(row["record_data"]),
            "existing": json.loads(row["existing_data"]) if row["existing_data"] else None,
            "changes": json.loads(row["changes"]) if row["changes"] else None,
            "match_method": row["match_method"],
            "reason": row["reason"],
        })

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


# ---------------------------------------------------------------------------
# License Events API
# ---------------------------------------------------------------------------

def _validate_event_fields(data: dict) -> list[str]:
    """Validate event create fields. Returns list of error strings."""
    errors: list[str] = []

    if not data.get("event_type"):
        errors.append("Missing required field: event_type")
    elif data["event_type"] not in VALID_EVENT_TYPES:
        errors.append(f"Invalid event_type: must be one of {sorted(VALID_EVENT_TYPES)}")

    if not data.get("event_date"):
        errors.append("Missing required field: event_date")
    else:
        err = _validate_date(data["event_date"], "event_date")
        if err:
            errors.append(err)

    if data.get("fee_amount") is not None:
        try:
            fa = float(data["fee_amount"])
            if fa < 0:
                errors.append("fee_amount must be a positive number")
        except (ValueError, TypeError):
            errors.append("fee_amount must be a number")

    if data.get("fee_type") is not None and data["fee_type"] != "":
        if data["fee_type"] not in VALID_FEE_TYPES:
            errors.append(f"Invalid fee_type: must be one of {sorted(VALID_FEE_TYPES)}")

    if data.get("notes") and len(str(data["notes"])) > 500:
        errors.append("notes exceeds 500 characters")

    return errors


@bp.route("/api/licenses/<license_id>/events", methods=["GET"])
@module_required("licenses")
def api_get_events(license_id):
    """List events for a license, newest first."""
    with get_db(readonly=True) as conn:
        lic = get_license(conn, license_id)
        if not lic:
            return jsonify({"error": "License not found"}), 404
        events = get_license_events(conn, license_id)
    return jsonify(events)


@bp.route("/api/licenses/<license_id>/events", methods=["POST"])
@module_required("licenses", min_role="editor")
def api_create_event(license_id):
    """Create a new event for a license."""
    data = request.get_json(silent=True) or {}
    errors = _validate_event_fields(data)
    if errors:
        return jsonify({"errors": errors}), 400

    fee_amount = float(data["fee_amount"]) if data.get("fee_amount") is not None else None
    fee_type = data.get("fee_type") or None

    with get_db() as conn:
        event = create_event(
            conn, license_id,
            event_type=data["event_type"],
            event_date=data["event_date"],
            notes=data.get("notes"),
            fee_amount=fee_amount,
            fee_type=fee_type,
            created_by=_get_user_id(),
        )
    if not event:
        return jsonify({"error": "License not found"}), 404
    return jsonify(event), 201


@bp.route("/api/licenses/<license_id>/renew", methods=["POST"])
@module_required("licenses", min_role="editor")
def api_renew_license(license_id):
    """Renew a license: update expiration date and create renewal event."""
    data = request.get_json(silent=True) or {}

    errors: list[str] = []
    if not data.get("new_expiration_date"):
        errors.append("Missing required field: new_expiration_date")
    else:
        err = _validate_date(data["new_expiration_date"], "new_expiration_date")
        if err:
            errors.append(err)
        else:
            # Must be in the future
            try:
                exp = _dt.strptime(data["new_expiration_date"], "%Y-%m-%d")
                if exp.date() <= _dt.utcnow().date():
                    errors.append("new_expiration_date must be in the future")
            except ValueError:
                pass  # already caught by _validate_date

    if data.get("fee_amount") is not None:
        try:
            fa = float(data["fee_amount"])
            if fa < 0:
                errors.append("fee_amount must be a positive number")
        except (ValueError, TypeError):
            errors.append("fee_amount must be a number")

    if data.get("fee_type") and data["fee_type"] not in VALID_FEE_TYPES:
        errors.append(f"Invalid fee_type: must be one of {sorted(VALID_FEE_TYPES)}")

    if data.get("notes") and len(str(data["notes"])) > 500:
        errors.append("notes exceeds 500 characters")

    if errors:
        return jsonify({"errors": errors}), 400

    fee_amount = float(data["fee_amount"]) if data.get("fee_amount") is not None else None

    with get_db() as conn:
        result = renew_license(
            conn, license_id,
            new_expiration_date=data["new_expiration_date"],
            fee_amount=fee_amount,
            fee_type=data.get("fee_type") or None,
            notes=data.get("notes"),
            created_by=_get_user_id(),
        )
    if not result:
        return jsonify({"error": "License not found"}), 404
    return jsonify(result)


# ---------------------------------------------------------------------------
# Notification API routes
# ---------------------------------------------------------------------------


@bp.route("/api/notifications")
@module_required("licenses")
def api_notifications():
    """List active notifications with summary data."""
    ntype = request.args.get("type")
    priority = request.args.get("priority")
    limit = min(int(request.args.get("limit", 50)), 200)

    with get_db() as conn:
        notifications = list_active_notifications(conn, limit=limit)
        summary = get_notification_summary(conn)

    # Client-side filtering for optional query params
    if ntype:
        notifications = [n for n in notifications if n.get("notification_type") == ntype]
    if priority:
        notifications = [n for n in notifications if n.get("priority") == priority]

    return jsonify({"notifications": notifications, "summary": summary})


@bp.route("/api/notifications/summary")
@module_required("licenses")
def api_notification_summary():
    """Get notification summary counts only."""
    with get_db() as conn:
        summary = get_notification_summary(conn)
    return jsonify(summary)


@bp.route("/api/notifications/<int:notification_id>/acknowledge", methods=["POST"])
@module_required("licenses", min_role="editor")
def api_acknowledge_notification(notification_id):
    """Mark a notification as acknowledged."""
    user = _get_user_id()
    with get_db() as conn:
        ok = acknowledge_notification(conn, notification_id, acknowledged_by=user)
    if not ok:
        return jsonify({"error": "Notification not found or already acknowledged"}), 404
    return jsonify({"status": "acknowledged", "id": notification_id})


@bp.route("/api/notifications/<int:notification_id>/resolve", methods=["POST"])
@module_required("licenses", min_role="editor")
def api_resolve_notification(notification_id):
    """Mark a notification as resolved."""
    user = _get_user_id()
    with get_db() as conn:
        ok = resolve_notification(conn, notification_id, resolved_by=user)
    if not ok:
        return jsonify({"error": "Notification not found or already resolved"}), 404
    return jsonify({"status": "resolved", "id": notification_id})


@bp.route("/api/notifications/generate", methods=["POST"])
@module_required("licenses", min_role="admin")
def api_generate_notifications():
    """Generate notifications (admin only). Optionally send Teams webhook."""
    data = request.get_json(silent=True) or {}
    send_webhook = bool(data.get("send_webhook", False))

    with get_db() as conn:
        stats = generate_all_notifications(conn, send_webhook=send_webhook)
    return jsonify(stats)


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------

VALID_DOC_TYPES = {"certificate", "application", "correspondence",
                   "receipt", "bond", "insurance", "other"}


@bp.route("/api/licenses/<license_id>/documents", methods=["POST"])
@module_required("licenses", min_role="editor")
def api_upload_documents(license_id):
    """Upload one or more documents for a license (multipart)."""
    import mimetypes as _mt

    with get_db() as conn:
        lic = get_license(conn, license_id)
    if not lic:
        return jsonify({"error": "License not found"}), 404

    files = request.files.getlist("files")
    if not files or all(f.filename == "" for f in files):
        return jsonify({"error": "No files provided"}), 400

    doc_type = request.form.get("doc_type", "other")
    if doc_type not in VALID_DOC_TYPES:
        return jsonify({"error": f"Invalid doc_type. Must be one of: {sorted(VALID_DOC_TYPES)}"}), 400

    description = request.form.get("description", "").strip() or None
    user = _get_user_id()
    created = []

    with get_db() as conn:
        for f in files:
            if not f.filename:
                continue
            data = f.read()
            mime = f.content_type or _mt.guess_type(f.filename)[0] or "application/octet-stream"
            rel_path = save_document_file(license_id, f.filename, data)
            doc = create_document(
                conn, license_id, doc_type,
                filename=rel_path,
                original_filename=f.filename,
                file_size=len(data),
                mime_type=mime,
                description=description,
                uploaded_by=user,
            )
            created.append(doc)

    return jsonify(created), 201


@bp.route("/api/licenses/<license_id>/documents", methods=["GET"])
@module_required("licenses", min_role="viewer")
def api_list_documents(license_id):
    """List all documents for a license."""
    with get_db() as conn:
        docs = list_documents(conn, license_id)
    return jsonify(docs)


@bp.route("/api/documents/<doc_id>/download", methods=["GET"])
@module_required("licenses", min_role="viewer")
def api_download_document(doc_id):
    """Download a document file."""
    with get_db() as conn:
        doc = get_document(conn, doc_id)
        if not doc:
            return jsonify({"error": "Document not found"}), 404
        full_path = get_document_path(conn, doc_id)

    if not full_path:
        return jsonify({"error": "File not found on disk"}), 404

    return send_file(
        full_path,
        mimetype=doc.get("mime_type", "application/octet-stream"),
        as_attachment=True,
        download_name=doc["original_filename"],
    )


@bp.route("/api/documents/<doc_id>", methods=["DELETE"])
@module_required("licenses", min_role="admin")
def api_delete_document(doc_id):
    """Delete a document (admin only)."""
    user = _get_user_id()
    with get_db() as conn:
        ok = delete_document(conn, doc_id, deleted_by=user)
    if not ok:
        return jsonify({"error": "Document not found"}), 404
    return "", 204


# ---------------------------------------------------------------------------
# Notes
# ---------------------------------------------------------------------------

@bp.route("/api/licenses/<license_id>/notes", methods=["POST"])
@module_required("licenses", min_role="editor")
def api_create_note(license_id):
    """Create a note for a license."""
    with get_db() as conn:
        lic = get_license(conn, license_id)
    if not lic:
        return jsonify({"error": "License not found"}), 404

    data = request.get_json(force=True)
    note_text = (data.get("note_text") or "").strip()
    if not note_text:
        return jsonify({"error": "note_text is required"}), 400
    if len(note_text) > 2000:
        return jsonify({"error": "note_text must be 2000 characters or fewer"}), 400

    user = _get_user_id()
    with get_db() as conn:
        note = create_note(conn, license_id, note_text, created_by=user)
    return jsonify(note), 201


@bp.route("/api/licenses/<license_id>/notes", methods=["GET"])
@module_required("licenses", min_role="viewer")
def api_list_notes(license_id):
    """List all notes for a license."""
    with get_db() as conn:
        notes = list_notes(conn, license_id)
    return jsonify(notes)


@bp.route("/api/notes/<note_id>", methods=["DELETE"])
@module_required("licenses", min_role="admin")
def api_delete_note(note_id):
    """Delete a note (admin only)."""
    user = _get_user_id()
    with get_db() as conn:
        ok = delete_note(conn, note_id, deleted_by=user)
    if not ok:
        return jsonify({"error": "Note not found"}), 404
    return "", 204


# ---------------------------------------------------------------------------
# Activity Feed
# ---------------------------------------------------------------------------

@bp.route("/api/licenses/<license_id>/activity", methods=["GET"])
@module_required("licenses", min_role="viewer")
def api_activity_feed(license_id):
    """Unified activity feed: events + notes + documents."""
    limit = min(int(request.args.get("limit", 50)), 200)
    with get_db() as conn:
        feed = get_activity_feed(conn, license_id, limit=limit)
    return jsonify(feed)


# ---------------------------------------------------------------------------
# Business Entities
# ---------------------------------------------------------------------------

def _validate_entity_fields(data: dict, require_all: bool = False) -> list[str]:
    """Validate entity create/update fields."""
    errors: list[str] = []

    if require_all:
        if not data.get("name"):
            errors.append("Missing required field: name")

    if "name" in data and data.get("name"):
        data["name"] = str(data["name"]).strip()
        if len(data["name"]) > 200:
            errors.append("name exceeds 200 characters")

    if "entity_type" in data and data.get("entity_type"):
        if data["entity_type"] not in VALID_ENTITY_TYPES:
            errors.append(f"Invalid entity_type: must be one of {sorted(VALID_ENTITY_TYPES)}")

    if "status" in data and data.get("status"):
        if data["status"] not in VALID_ENTITY_STATUSES:
            errors.append(f"Invalid status: must be one of {sorted(VALID_ENTITY_STATUSES)}")

    if "state_code" in data and data.get("state_code"):
        sc = str(data["state_code"]).strip().upper()
        data["state_code"] = sc
        if sc not in _STATE_NAMES:
            errors.append(f"Invalid state_code: {sc}")

    if "state_of_incorporation" in data and data.get("state_of_incorporation"):
        sc = str(data["state_of_incorporation"]).strip().upper()
        data["state_of_incorporation"] = sc
        if sc not in _STATE_NAMES:
            errors.append(f"Invalid state_of_incorporation: {sc}")

    return errors


def _validate_registration_fields(data: dict, require_all: bool = False) -> list[str]:
    """Validate registration create/update fields."""
    errors: list[str] = []

    if require_all:
        for f in ("registration_type", "state_code"):
            if not data.get(f):
                errors.append(f"Missing required field: {f}")

    if "registration_type" in data and data.get("registration_type"):
        if data["registration_type"] not in VALID_REGISTRATION_TYPES:
            errors.append(f"Invalid registration_type: must be one of {sorted(VALID_REGISTRATION_TYPES)}")

    if "status" in data and data.get("status"):
        if data["status"] not in VALID_REGISTRATION_STATUSES:
            errors.append(f"Invalid status: must be one of {sorted(VALID_REGISTRATION_STATUSES)}")

    if "state_code" in data and data.get("state_code"):
        sc = str(data["state_code"]).strip().upper()
        data["state_code"] = sc
        if sc not in _STATE_NAMES:
            errors.append(f"Invalid state_code: {sc}")

    if "filing_frequency" in data and data.get("filing_frequency"):
        if data["filing_frequency"] not in VALID_FILING_FREQUENCIES:
            errors.append(f"Invalid filing_frequency: must be one of {sorted(VALID_FILING_FREQUENCIES)}")

    for df in ("issued_date", "expiration_date", "next_filing_date"):
        if df in data and data.get(df):
            err = _validate_date(data[df], df)
            if err:
                errors.append(err)

    if "fee_amount" in data and data.get("fee_amount") is not None:
        try:
            f = float(data["fee_amount"])
            if f < 0:
                errors.append("fee_amount must be non-negative")
        except (ValueError, TypeError):
            errors.append("fee_amount must be a number")

    return errors


@bp.route("/api/licenses/entities/summary", methods=["GET"])
@module_required("licenses", min_role="viewer")
def api_entity_summary():
    """Entity counts and registration stats."""
    with get_db() as conn:
        summary = get_entity_summary(conn)
    return jsonify(summary)


@bp.route("/api/licenses/entities", methods=["GET"])
@module_required("licenses", min_role="viewer")
def api_list_entities():
    """List business entities with pagination."""
    page = max(1, int(request.args.get("page", 1)))
    per_page = min(int(request.args.get("per_page", 25)), 100)
    search = request.args.get("search")
    entity_type = request.args.get("entity_type")
    status = request.args.get("status")
    parent_id = request.args.get("parent_id")

    with get_db() as conn:
        result = list_entities(
            conn, search=search, entity_type=entity_type,
            status=status, parent_id=parent_id,
            page=page, per_page=per_page,
        )
    return jsonify(result)


@bp.route("/api/licenses/entities", methods=["POST"])
@module_required("licenses", min_role="editor")
def api_create_entity():
    """Create a new business entity."""
    data = request.get_json(force=True, silent=True) or {}

    errors = _validate_entity_fields(data, require_all=True)
    if errors:
        return jsonify({"errors": errors}), 400

    user = _get_user_id()
    try:
        with get_db() as conn:
            entity = create_entity(
                conn,
                name=data["name"],
                entity_type=data.get("entity_type", "corporation"),
                parent_id=data.get("parent_id"),
                changed_by=user,
                **{k: v for k, v in data.items()
                   if k not in ("name", "entity_type", "parent_id")},
            )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify(entity), 201


@bp.route("/api/licenses/entities/<entity_id>", methods=["GET"])
@module_required("licenses", min_role="viewer")
def api_get_entity(entity_id):
    """Get a single entity with registrations and linked licenses."""
    with get_db() as conn:
        entity = get_entity(conn, entity_id)
    if not entity:
        return jsonify({"error": "Entity not found"}), 404
    return jsonify(entity)


@bp.route("/api/licenses/entities/<entity_id>", methods=["PUT"])
@module_required("licenses", min_role="editor")
def api_update_entity(entity_id):
    """Update a business entity."""
    data = request.get_json(force=True, silent=True) or {}

    errors = _validate_entity_fields(data)
    if errors:
        return jsonify({"errors": errors}), 400

    user = _get_user_id()
    with get_db() as conn:
        entity = update_entity(conn, entity_id, changed_by=user, **data)
    if not entity:
        return jsonify({"error": "Entity not found"}), 404
    return jsonify(entity)


@bp.route("/api/licenses/entities/<entity_id>", methods=["DELETE"])
@module_required("licenses", min_role="admin")
def api_delete_entity(entity_id):
    """Delete a business entity (admin only). Unlinks licenses, cascades registrations."""
    user = _get_user_id()
    with get_db() as conn:
        ok = delete_entity(conn, entity_id, changed_by=user)
    if not ok:
        return jsonify({"error": "Entity not found"}), 404
    return "", 204


@bp.route("/api/licenses/entities/hierarchy", methods=["GET"])
@module_required("licenses", min_role="viewer")
def api_entity_hierarchy():
    """Get entity hierarchy tree."""
    entity_id = request.args.get("entity_id")
    with get_db() as conn:
        tree = get_entity_hierarchy(conn, entity_id=entity_id)
    return jsonify(tree)


# ---------------------------------------------------------------------------
# Entity Registrations
# ---------------------------------------------------------------------------

@bp.route("/api/licenses/entities/<entity_id>/registrations", methods=["GET"])
@module_required("licenses", min_role="viewer")
def api_list_entity_registrations(entity_id):
    """List registrations for an entity."""
    with get_db() as conn:
        regs = list_registrations(conn, entity_id=entity_id)
    return jsonify(regs)


@bp.route("/api/licenses/entities/<entity_id>/registrations", methods=["POST"])
@module_required("licenses", min_role="editor")
def api_create_registration(entity_id):
    """Create a new registration for an entity."""
    data = request.get_json(force=True, silent=True) or {}

    errors = _validate_registration_fields(data, require_all=True)
    if errors:
        return jsonify({"errors": errors}), 400

    user = _get_user_id()
    try:
        with get_db() as conn:
            reg = create_registration(
                conn,
                entity_id=entity_id,
                registration_type=data["registration_type"],
                state_code=data["state_code"],
                changed_by=user,
                **{k: v for k, v in data.items()
                   if k not in ("registration_type", "state_code")},
            )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify(reg), 201


@bp.route("/api/licenses/entities/<entity_id>/registrations/<reg_id>", methods=["PUT"])
@module_required("licenses", min_role="editor")
def api_update_registration(entity_id, reg_id):
    """Update an entity registration."""
    data = request.get_json(force=True, silent=True) or {}

    errors = _validate_registration_fields(data)
    if errors:
        return jsonify({"errors": errors}), 400

    user = _get_user_id()
    with get_db() as conn:
        reg = update_registration(conn, reg_id, changed_by=user, **data)
    if not reg:
        return jsonify({"error": "Registration not found"}), 404
    return jsonify(reg)


@bp.route("/api/licenses/entities/<entity_id>/registrations/<reg_id>", methods=["DELETE"])
@module_required("licenses", min_role="admin")
def api_delete_registration(entity_id, reg_id):
    """Delete an entity registration (admin only)."""
    user = _get_user_id()
    with get_db() as conn:
        ok = delete_registration(conn, reg_id, changed_by=user)
    if not ok:
        return jsonify({"error": "Registration not found"}), 404
    return "", 204


# ---------------------------------------------------------------------------
# Phase 11 — State Requirements & Compliance
# ---------------------------------------------------------------------------

VALID_REQUIREMENT_TYPES = {
    "initial_application", "renewal", "ce_requirement",
    "bond", "insurance", "exam", "background_check", "fingerprinting",
}
VALID_FEE_FREQUENCIES = {
    "one_time", "annual", "biennial", "triennial", "per_renewal",
}


@bp.route("/api/requirements", methods=["GET"])
@module_required("licenses")
def api_list_requirements():
    """List state requirements with optional filters."""
    with get_db() as conn:
        result = list_requirements(
            conn,
            state_code=request.args.get("state_code"),
            license_type=request.args.get("license_type"),
            requirement_type=request.args.get("requirement_type"),
            page=int(request.args.get("page", 0)),
            per_page=int(request.args.get("per_page", 0)),
        )
    return jsonify(result)


@bp.route("/api/requirements/<req_id>", methods=["GET"])
@module_required("licenses")
def api_get_requirement(req_id):
    """Get a single state requirement."""
    with get_db() as conn:
        req = get_requirement(conn, req_id)
    if not req:
        return jsonify({"error": "Requirement not found"}), 404
    return jsonify(req)


@bp.route("/api/requirements", methods=["POST"])
@module_required("licenses", min_role="editor")
def api_create_requirement():
    """Create a state requirement."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    # Validate required fields
    missing = [f for f in ("state_code", "license_type", "requirement_type") if not data.get(f)]
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    if data["requirement_type"] not in VALID_REQUIREMENT_TYPES:
        return jsonify({"error": f"Invalid requirement_type. Must be one of: {', '.join(sorted(VALID_REQUIREMENT_TYPES))}"}), 400

    if data.get("fee_frequency") and data["fee_frequency"] not in VALID_FEE_FREQUENCIES:
        return jsonify({"error": f"Invalid fee_frequency. Must be one of: {', '.join(sorted(VALID_FEE_FREQUENCIES))}"}), 400

    if len(data.get("state_code", "")) != 2:
        return jsonify({"error": "state_code must be a 2-letter abbreviation"}), 400

    user = _get_user_id()
    with get_db() as conn:
        try:
            req = create_requirement(conn, data, created_by=user)
        except Exception as e:
            if "UNIQUE constraint" in str(e):
                return jsonify({"error": "Requirement already exists for this state/license_type/requirement_type"}), 409
            raise
    return jsonify(req), 201


@bp.route("/api/requirements/<req_id>", methods=["PUT"])
@module_required("licenses", min_role="editor")
def api_update_requirement(req_id):
    """Update a state requirement."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    if data.get("requirement_type") and data["requirement_type"] not in VALID_REQUIREMENT_TYPES:
        return jsonify({"error": f"Invalid requirement_type"}), 400

    if data.get("fee_frequency") and data["fee_frequency"] not in VALID_FEE_FREQUENCIES:
        return jsonify({"error": f"Invalid fee_frequency"}), 400

    user = _get_user_id()
    with get_db() as conn:
        req = update_requirement(conn, req_id, data, changed_by=user)
    if not req:
        return jsonify({"error": "Requirement not found"}), 404
    return jsonify(req)


@bp.route("/api/requirements/<req_id>", methods=["DELETE"])
@module_required("licenses", min_role="admin")
def api_delete_requirement(req_id):
    """Delete a state requirement (admin only)."""
    user = _get_user_id()
    with get_db() as conn:
        ok = delete_requirement(conn, req_id, deleted_by=user)
    if not ok:
        return jsonify({"error": "Requirement not found"}), 404
    return "", 204


@bp.route("/api/licenses/<license_id>/compliance", methods=["GET"])
@module_required("licenses")
def api_license_compliance(license_id):
    """Get compliance score for a single license."""
    with get_db() as conn:
        result = calculate_compliance_score(conn, license_id)
    if result.get("error"):
        return jsonify(result), 404
    return jsonify(result)


@bp.route("/api/compliance/gap-analysis", methods=["GET"])
@module_required("licenses")
def api_compliance_gap_analysis():
    """Full gap analysis across all active licenses."""
    with get_db() as conn:
        results = get_compliance_gap_analysis(conn)
    return jsonify({"items": results, "total": len(results)})


@bp.route("/api/compliance/summary", methods=["GET"])
@module_required("licenses")
def api_compliance_summary():
    """Compliance summary by state."""
    with get_db() as conn:
        summary = get_compliance_summary_by_state(conn)
    return jsonify(summary)
