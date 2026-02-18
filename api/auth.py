"""
Auth Blueprint — login/callback/logout + user management API.

Routes:
    GET  /auth/login     → Redirect to Entra ID (or dev bypass)
    GET  /auth/callback  → Handle Entra ID redirect
    GET  /auth/logout    → Clear session, redirect to Entra logout
    GET  /auth/me        → JSON: current user info
    GET  /auth/users     → JSON: all users (admin only)
    POST /auth/users/<id>/role  → Update user role (admin only)
    POST /auth/users/<id>/active → Toggle user active status (admin only)
"""

from flask import (
    Blueprint,
    abort,
    jsonify,
    redirect,
    request,
    session,
    url_for,
)

from qms.auth.decorators import login_required, role_required

bp = Blueprint("auth", __name__, url_prefix="/auth")


def _get_auth_config():
    """Load auth config from config.yaml."""
    from qms.core.config import get_config
    return get_config().get("auth", {})


def _is_dev_bypass():
    return _get_auth_config().get("dev_bypass", False)


# ── Login Page ───────────────────────────────────────────────────────────────

@bp.route("/login")
def login_page():
    """Show login page, or auto-login in dev bypass mode."""
    auth_cfg = _get_auth_config()

    if auth_cfg.get("dev_bypass"):
        # Auto-create a dev admin session
        session["user"] = {
            "id": 0,
            "entra_oid": "dev-bypass",
            "email": "dev@localhost",
            "display_name": "Dev User",
            "role": "admin",
            "is_active": True,
        }
        return redirect(url_for("index"))

    from flask import render_template
    return render_template("auth/login.html", error=request.args.get("error"))


# ── Login Start ──────────────────────────────────────────────────────────────

@bp.route("/login/start")
def login():
    """Initiate the real Entra ID OAuth2 flow."""
    auth_cfg = _get_auth_config()

    if auth_cfg.get("dev_bypass"):
        return redirect(url_for("auth.login_page"))

    from qms.auth.entra import build_auth_url

    entra_cfg = auth_cfg.get("entra", {})
    redirect_uri = url_for("auth.callback", _external=True)
    flow = build_auth_url(entra_cfg, redirect_uri)

    # Cache the flow in session for the callback
    session["auth_flow"] = flow

    return redirect(flow["auth_uri"])


# ── Callback ─────────────────────────────────────────────────────────────────

@bp.route("/callback")
def callback():
    """Handle Entra ID redirect after user authenticates."""
    auth_cfg = _get_auth_config()
    entra_cfg = auth_cfg.get("entra", {})

    auth_flow = session.pop("auth_flow", None)
    if not auth_flow:
        return redirect(url_for("auth.login_page"))

    from qms.auth.entra import complete_auth_flow, extract_claims

    result = complete_auth_flow(entra_cfg, auth_flow, request.args)
    if not result:
        abort(401, "Authentication failed")

    claims = extract_claims(result)
    if not claims["oid"]:
        abort(401, "Missing user identifier from Entra ID")

    # Upsert user in local DB
    from qms.core.db import get_db
    from qms.auth.db import upsert_user

    default_role = auth_cfg.get("default_role", "user")
    with get_db() as conn:
        user = upsert_user(
            conn,
            entra_oid=claims["oid"],
            email=claims["email"],
            display_name=claims["display_name"],
            default_role=default_role,
        )

    if not user["is_active"]:
        abort(403, "Account deactivated. Contact an administrator.")

    # Store minimal user info in session
    session["user"] = {
        "id": user["id"],
        "entra_oid": user["entra_oid"],
        "email": user["email"],
        "display_name": user["display_name"],
        "role": user["role"],
        "is_active": user["is_active"],
    }

    return redirect(url_for("index"))


# ── Logout ───────────────────────────────────────────────────────────────────

@bp.route("/logout")
def logout():
    """Clear session and redirect to Entra logout (or home if dev bypass)."""
    auth_cfg = _get_auth_config()
    session.clear()

    if auth_cfg.get("dev_bypass"):
        return redirect(url_for("auth.login_page"))

    from qms.auth.entra import build_logout_url

    entra_cfg = auth_cfg.get("entra", {})
    post_logout_uri = url_for("auth.login_page", _external=True)
    logout_url = build_logout_url(entra_cfg["tenant_id"], post_logout_uri)
    return redirect(logout_url)


# ── Current User Info ────────────────────────────────────────────────────────

@bp.route("/me")
@login_required
def me():
    """Return current user info as JSON."""
    return jsonify(session["user"])


# ── User Management (admin only) ────────────────────────────────────────────

@bp.route("/users")
@role_required("admin")
def users_list():
    """List all users."""
    from qms.core.db import get_db
    from qms.auth.db import list_users

    with get_db(readonly=True) as conn:
        users = list_users(conn)
    return jsonify(users)


@bp.route("/users/<int:user_id>/role", methods=["POST"])
@role_required("admin")
def update_user_role(user_id: int):
    """Update a user's role."""
    data = request.get_json(silent=True) or {}
    role = data.get("role")
    if role not in ("admin", "user", "viewer"):
        abort(400, "Invalid role")

    from qms.core.db import get_db
    from qms.auth.db import update_role

    with get_db() as conn:
        if not update_role(conn, user_id, role):
            abort(404, "User not found")

    return jsonify({"ok": True, "role": role})


@bp.route("/users/<int:user_id>/active", methods=["POST"])
@role_required("admin")
def toggle_user_active(user_id: int):
    """Toggle a user's active status."""
    data = request.get_json(silent=True) or {}
    is_active = data.get("is_active", True)

    from qms.core.db import get_db
    from qms.auth.db import set_active

    with get_db() as conn:
        if not set_active(conn, user_id, bool(is_active)):
            abort(404, "User not found")

    return jsonify({"ok": True, "is_active": is_active})
