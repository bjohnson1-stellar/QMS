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
            return redirect(url_for("auth.login"))
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
                return redirect(url_for("auth.login"))
            user_role = session["user"].get("role", "viewer")
            if user_role not in roles:
                from flask import abort
                abort(403)
            return f(*args, **kwargs)
        return decorated
    return decorator
