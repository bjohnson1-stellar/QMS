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
        }
        return redirect(url_for("index"))

    if request.method == "GET":
        return render_template("auth/login.html", error=None)

    # POST — validate email + password
    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""

    if not email or not password:
        return render_template("auth/login.html", error="Email and password are required.")

    from qms.core.db import get_db
    from qms.auth.db import authenticate, get_user_modules

    with get_db() as conn:
        user = authenticate(conn, email, password)
        if not user:
            return render_template("auth/login.html", error="Invalid email or password.")
        modules = get_user_modules(conn, user["id"])

    # Store session (include module access map)
    session["user"] = {
        "id": user["id"],
        "email": user["email"],
        "display_name": user["display_name"],
        "role": user["role"],
        "is_active": bool(user["is_active"]),
        "must_change_password": bool(user.get("must_change_password", False)),
        "modules": modules,
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
    from qms.auth.db import change_password as do_change

    user_id = session["user"]["id"]
    with get_db() as conn:
        ok, msg = do_change(conn, user_id, current_password, new_password)

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

    try:
        with get_db() as conn:
            user = do_create(conn, email, display_name, password, role)
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


@bp.route("/users/<int:user_id>/reset-password", methods=["POST"])
@role_required("admin")
def reset_user_password(user_id: int):
    """Reset a user's password (admin action)."""
    data = request.get_json(silent=True) or {}
    new_password = data.get("password") or ""

    if not new_password or len(new_password) < 8:
        abort(400, "Password must be at least 8 characters")

    from qms.core.db import get_db
    from qms.auth.db import set_password

    with get_db() as conn:
        if not set_password(conn, user_id, new_password, must_change=True):
            abort(404, "User not found")

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
    from qms.auth.db import grant_module_access

    with get_db() as conn:
        grant_module_access(conn, user_id, module, role)

    return jsonify({"ok": True, "module": module, "role": role})


@bp.route("/users/<int:user_id>/modules/<module>", methods=["DELETE"])
@role_required("admin")
def delete_user_module_access(user_id: int, module: str):
    """Revoke a user's access to a module."""
    from qms.core.db import get_db
    from qms.auth.db import revoke_module_access

    with get_db() as conn:
        if not revoke_module_access(conn, user_id, module):
            abort(404, "Module access not found")

    return jsonify({"ok": True})
