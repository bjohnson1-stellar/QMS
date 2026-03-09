"""
External API Blueprint — token-authenticated read-only endpoints for system integration.

Mounted at /api/v1/. Uses X-API-Key header for authentication (separate from session auth).
"""

from functools import wraps

from flask import Blueprint, jsonify, request

from qms.auth.db import validate_api_token
from qms.core import get_db


bp = Blueprint("external_api", __name__, url_prefix="/api/v1")


def require_api_token(f):
    """Decorator: validates X-API-Key header against api_tokens table."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("X-API-Key", "").strip()
        if not token:
            return jsonify({"error": "Missing X-API-Key header"}), 401
        with get_db(readonly=True) as conn:
            record = validate_api_token(conn, token)
        if not record:
            return jsonify({"error": "Invalid or expired API token"}), 401
        request._api_token = record
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# Health (no auth required)
# ---------------------------------------------------------------------------

@bp.route("/health", methods=["GET"])
def health():
    """Health check endpoint — no authentication required."""
    return jsonify({"status": "ok", "version": "0.2.0"})


# ---------------------------------------------------------------------------
# Licenses
# ---------------------------------------------------------------------------

@bp.route("/licenses", methods=["GET"])
@require_api_token
def list_licenses():
    """Paginated license list."""
    from qms.licenses.db import list_licenses as _list_licenses

    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 25, type=int), 100)
    state_code = request.args.get("state_code")
    status = request.args.get("status")

    with get_db(readonly=True) as conn:
        result = _list_licenses(
            conn,
            state_code=state_code,
            status=status,
            page=page,
            per_page=per_page,
        )
    return jsonify(result)


@bp.route("/licenses/<license_id>", methods=["GET"])
@require_api_token
def get_license(license_id):
    """Full license detail including events and scopes."""
    from qms.licenses.db import (
        get_license as _get_license,
        get_license_events,
        get_license_scopes,
        get_ce_summary,
    )

    with get_db(readonly=True) as conn:
        lic = _get_license(conn, license_id)
        if not lic:
            return jsonify({"error": "License not found"}), 404
        lic["events"] = get_license_events(conn, license_id)
        lic["scopes"] = get_license_scopes(conn, license_id)
        lic["ce_summary"] = get_ce_summary(conn, license_id)
    return jsonify(lic)


# ---------------------------------------------------------------------------
# Compliance
# ---------------------------------------------------------------------------

@bp.route("/compliance/summary", methods=["GET"])
@require_api_token
def compliance_summary():
    """Compliance overview: total, active, expiring, expired counts."""
    with get_db(readonly=True) as conn:
        row = conn.execute("""
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) AS active,
                SUM(CASE WHEN status = 'expired' THEN 1 ELSE 0 END) AS expired,
                SUM(CASE WHEN status = 'active'
                         AND expiration_date IS NOT NULL
                         AND julianday(expiration_date) - julianday('now') <= 30
                         AND julianday(expiration_date) - julianday('now') > 0
                    THEN 1 ELSE 0 END) AS expiring_30,
                SUM(CASE WHEN status = 'active'
                         AND expiration_date IS NOT NULL
                         AND julianday(expiration_date) - julianday('now') <= 60
                         AND julianday(expiration_date) - julianday('now') > 0
                    THEN 1 ELSE 0 END) AS expiring_60
            FROM state_licenses
        """).fetchone()
        data = dict(row)
        total = data["total"] or 0
        active = data["active"] or 0
        data["compliance_rate"] = round(active / total * 100, 1) if total > 0 else 0.0
    return jsonify(data)


# ---------------------------------------------------------------------------
# Employees
# ---------------------------------------------------------------------------

@bp.route("/employees", methods=["GET"])
@require_api_token
def list_employees():
    """List employees with license counts."""
    from qms.licenses.db import list_employees_with_licenses

    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 25, type=int), 100)

    with get_db(readonly=True) as conn:
        result = list_employees_with_licenses(conn, page=page, per_page=per_page)
    return jsonify(result)
