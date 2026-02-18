"""
Authentication and authorization decorators for Flask routes.

These are the only Flask-coupled parts of the auth module.
"""

from functools import wraps

from flask import redirect, session, url_for


def login_required(f):
    """Require an authenticated user session. Redirects to login if missing."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("auth.login_page"))
        return f(*args, **kwargs)
    return decorated


def role_required(*roles):
    """
    Require the current user to have one of the specified roles.

    Usage:
        @role_required("admin")
        @role_required("admin", "user")
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if "user" not in session:
                return redirect(url_for("auth.login_page"))
            user_role = session["user"].get("role", "viewer")
            if user_role not in roles:
                from flask import abort
                abort(403)
            return f(*args, **kwargs)
        return decorated
    return decorator


def module_required(module: str, min_role: str = "viewer"):
    """
    Require the current user to have access to a specific module.

    Global admins bypass this check entirely. For non-admin users,
    checks the user_module_access table for at least min_role.

    Role hierarchy: admin > editor > viewer

    Usage:
        @module_required("welding")
        @module_required("welding", min_role="editor")
        @module_required("welding", min_role="admin")
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if "user" not in session:
                return redirect(url_for("auth.login_page"))

            user = session["user"]

            # Global admins bypass module checks
            if user.get("role") == "admin":
                return f(*args, **kwargs)

            # Check module access from session cache
            modules = user.get("modules", {})
            role_rank = {"admin": 3, "editor": 2, "viewer": 1}
            user_module_role = modules.get(module)

            if not user_module_role:
                from flask import abort
                abort(403)

            if role_rank.get(user_module_role, 0) < role_rank.get(min_role, 1):
                from flask import abort
                abort(403)

            return f(*args, **kwargs)
        return decorated
    return decorator
