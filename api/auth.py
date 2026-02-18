"""
Auth Blueprint — local email + password authentication + user management.

Routes:
    GET  /auth/login            → Show login form (or dev bypass)
    POST /auth/login            → Validate email + password, create session
    GET  /auth/logout           → Clear session, redirect to login
    GET  /auth/me               → JSON: current user info
    GET+POST /auth/change-password → Change own password
    GET  /auth/users            → JSON: all users (admin only)
    POST /auth/users/create     → Create user account (admin only)
    POST /auth/users/<id>/role  → Update user role (admin only)
    POST /auth/users/<id>/active → Toggle user active status (admin only)
    POST /auth/users/<id>/reset-password → Reset user password (admin only)
"""

from flask import (
    Blueprint,
    abort,
    jsonify,
    redirect,
    render_template,
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


def _current_email() -> str:
    """Return current session user's email, or 'anonymous'."""
    user = session.get("user")
    return user["email"] if user else "anonymous"


# ── Login ────────────────────────────────────────────────────────────────────

@bp.route("/login", methods=["GET", "POST"])
def login_page():
    """GET: show login form. POST: validate credentials."""
    auth_cfg = _get_auth_config()

    # Dev bypass — auto-create admin session
    if auth_cfg.get("dev_bypass"):
        session["user"] = {
            "id": 0,
            "email": "dev@localhost",
            "display_name": "Dev User",
            "role": "admin",
            "is_active": True,
            "must_change_password": False,
            "business_units": None,  # admin = unrestricted
        }
        return redirect(url_for("index"))

    if request.method == "GET":
        return render_template("auth/login.html", error=None)

    # POST — validate email + password
    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""

    if not email or not password:
        return render_template("auth/login.html", error="Email and password are required.")

    # Rate limiting — check before hitting the database
    from qms.auth.rate_limit import limiter

    client_ip = request.remote_addr or "unknown"
    wait = limiter.check(client_ip, email)
    if wait:
        return render_template(
            "auth/login.html",
            error=f"Too many failed attempts. Try again in {wait} seconds.",
        )

    from qms.core.db import get_db
    from qms.auth.db import authenticate, get_user_modules, get_user_business_units, log_auth_event

    with get_db() as conn:
        user = authenticate(conn, email, password)
        if not user:
            limiter.record_failure(client_ip, email)
            log_auth_event(conn, "login_failure", email, "anonymous", {"ip": client_ip})
            return render_template("auth/login.html", error="Invalid email or password.")
        modules = get_user_modules(conn, user["id"])
        bu_ids = get_user_business_units(conn, user["id"])
        log_auth_event(conn, "login_success", user["id"], user["email"], {"ip": client_ip})

    limiter.reset(client_ip, email)

    # Store session (include module access map + BU restrictions)
    session["user"] = {
        "id": user["id"],
        "email": user["email"],
        "display_name": user["display_name"],
        "role": user["role"],
        "is_active": bool(user["is_active"]),
        "must_change_password": bool(user.get("must_change_password", False)),
        "modules": modules,
        "business_units": bu_ids or None,  # None = unrestricted, list = restricted
    }

    # Force password change if required
    if user.get("must_change_password"):
        return redirect(url_for("auth.change_password"))

    return redirect(url_for("index"))


# ── Logout ───────────────────────────────────────────────────────────────────

@bp.route("/logout")
def logout():
    """Clear session and redirect to login."""
    session.clear()
    return redirect(url_for("auth.login_page"))


# ── Current User Info ────────────────────────────────────────────────────────

@bp.route("/me")
@login_required
def me():
    """Return current user info as JSON."""
    return jsonify(session["user"])


# ── Change Password ──────────────────────────────────────────────────────────

@bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    """Change the current user's password."""
    if request.method == "GET":
        return render_template("auth/change_password.html", error=None, success=None)

    current_password = request.form.get("current_password") or ""
    new_password = request.form.get("new_password") or ""
    confirm_password = request.form.get("confirm_password") or ""

    if not current_password or not new_password:
        return render_template(
            "auth/change_password.html",
            error="All fields are required.",
            success=None,
        )

    if len(new_password) < 8:
        return render_template(
            "auth/change_password.html",
            error="New password must be at least 8 characters.",
            success=None,
        )

    if new_password != confirm_password:
        return render_template(
            "auth/change_password.html",
            error="New passwords do not match.",
            success=None,
        )

    from qms.core.db import get_db
    from qms.auth.db import change_password as do_change, log_auth_event

    user_id = session["user"]["id"]
    with get_db() as conn:
        ok, msg = do_change(conn, user_id, current_password, new_password)
        if ok:
            log_auth_event(conn, "password_change", user_id, _current_email())

    if not ok:
        return render_template("auth/change_password.html", error=msg, success=None)

    # Clear the must_change flag in session
    session["user"]["must_change_password"] = False
    return render_template(
        "auth/change_password.html",
        error=None,
        success="Password changed successfully.",
    )


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


@bp.route("/users/create", methods=["POST"])
@role_required("admin")
def create_user():
    """Create a new user account."""
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    display_name = (data.get("display_name") or "").strip()
    password = data.get("password") or ""
    role = data.get("role", "user")

    if not email or not display_name or not password:
        abort(400, "email, display_name, and password are required")
    if role not in ("admin", "user", "viewer"):
        abort(400, "Invalid role")
    if len(password) < 8:
        abort(400, "Password must be at least 8 characters")

    from qms.core.db import get_db
    from qms.auth.db import create_user as do_create
    import sqlite3

    from qms.auth.db import log_auth_event

    try:
        with get_db() as conn:
            user = do_create(conn, email, display_name, password, role)
            log_auth_event(
                conn, "user_create", user["id"], _current_email(),
                {"email": email, "role": role},
            )
    except sqlite3.IntegrityError:
        abort(409, "A user with that email already exists")

    return jsonify(user), 201


@bp.route("/users/<int:user_id>/role", methods=["POST"])
@role_required("admin")
def update_user_role(user_id: int):
    """Update a user's role."""
    data = request.get_json(silent=True) or {}
    role = data.get("role")
    if role not in ("admin", "user", "viewer"):
        abort(400, "Invalid role")

    from qms.core.db import get_db
    from qms.auth.db import update_role, log_auth_event

    with get_db() as conn:
        if not update_role(conn, user_id, role):
            abort(404, "User not found")
        log_auth_event(conn, "role_change", user_id, _current_email(), {"role": role})

    return jsonify({"ok": True, "role": role})


@bp.route("/users/<int:user_id>/active", methods=["POST"])
@role_required("admin")
def toggle_user_active(user_id: int):
    """Toggle a user's active status."""
    data = request.get_json(silent=True) or {}
    is_active = data.get("is_active", True)

    from qms.core.db import get_db
    from qms.auth.db import set_active, log_auth_event

    with get_db() as conn:
        if not set_active(conn, user_id, bool(is_active)):
            abort(404, "User not found")
        log_auth_event(
            conn, "active_toggle", user_id, _current_email(),
            {"is_active": bool(is_active)},
        )

    return jsonify({"ok": True, "is_active": is_active})


@bp.route("/users/<int:user_id>/reset-password", methods=["POST"])
@role_required("admin")
def reset_user_password(user_id: int):
    """Reset a user's password (admin action)."""
    data = request.get_json(silent=True) or {}
    new_password = data.get("password") or ""

    if not new_password or len(new_password) < 8:
        abort(400, "Password must be at least 8 characters")

    from qms.core.db import get_db
    from qms.auth.db import set_password, log_auth_event

    with get_db() as conn:
        if not set_password(conn, user_id, new_password, must_change=True):
            abort(404, "User not found")
        log_auth_event(conn, "password_reset", user_id, _current_email())

    return jsonify({"ok": True, "must_change_password": True})


# ── Module Access (admin only) ──────────────────────────────────────────────

@bp.route("/users/<int:user_id>/modules")
@role_required("admin")
def get_user_module_access(user_id: int):
    """Get a user's module access map."""
    from qms.core.db import get_db
    from qms.auth.db import get_user_modules

    with get_db(readonly=True) as conn:
        modules = get_user_modules(conn, user_id)
    return jsonify(modules)


@bp.route("/users/<int:user_id>/modules", methods=["POST"])
@role_required("admin")
def set_user_module_access(user_id: int):
    """Grant or update a user's access to a module."""
    data = request.get_json(silent=True) or {}
    module = data.get("module", "")
    role = data.get("role", "viewer")

    from qms.auth.db import _valid_modules, VALID_MODULE_ROLES
    valid = _valid_modules()
    if module not in valid:
        abort(400, f"Invalid module. Must be one of: {', '.join(valid)}")
    if role not in VALID_MODULE_ROLES:
        abort(400, f"Invalid role. Must be one of: {', '.join(VALID_MODULE_ROLES)}")

    from qms.core.db import get_db
    from qms.auth.db import grant_module_access, log_auth_event

    with get_db() as conn:
        grant_module_access(conn, user_id, module, role)
        log_auth_event(
            conn, "module_grant", user_id, _current_email(),
            {"module": module, "role": role},
        )

    return jsonify({"ok": True, "module": module, "role": role})


@bp.route("/users/<int:user_id>/modules/<module>", methods=["DELETE"])
@role_required("admin")
def delete_user_module_access(user_id: int, module: str):
    """Revoke a user's access to a module."""
    from qms.core.db import get_db
    from qms.auth.db import revoke_module_access, log_auth_event

    with get_db() as conn:
        if not revoke_module_access(conn, user_id, module):
            abort(404, "Module access not found")
        log_auth_event(
            conn, "module_revoke", user_id, _current_email(),
            {"module": module},
        )

    return jsonify({"ok": True})


# ── Business Unit Access (admin only) ────────────────────────────────────────

@bp.route("/users/<int:user_id>/business-units")
@role_required("admin")
def get_user_bu_access(user_id: int):
    """Get a user's business unit access list."""
    from qms.core.db import get_db
    from qms.auth.db import get_user_business_units

    with get_db(readonly=True) as conn:
        bu_ids = get_user_business_units(conn, user_id)
    return jsonify(bu_ids)


@bp.route("/users/<int:user_id>/business-units", methods=["POST"])
@role_required("admin")
def set_user_bu_access(user_id: int):
    """Set a user's business unit access (replace all)."""
    data = request.get_json(silent=True) or {}
    bu_ids = data.get("business_unit_ids", [])

    if not isinstance(bu_ids, list):
        abort(400, "business_unit_ids must be a list")

    from qms.core.db import get_db
    from qms.auth.db import set_user_business_units_bulk, log_auth_event

    with get_db() as conn:
        set_user_business_units_bulk(conn, user_id, bu_ids)
        log_auth_event(
            conn, "bu_access_update", user_id, _current_email(),
            {"business_unit_ids": bu_ids},
        )

    return jsonify({"ok": True, "business_unit_ids": bu_ids})
