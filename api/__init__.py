"""
QMS Web Application Factory

Centralized Flask app that registers module blueprints.
Mirrors how cli/main.py assembles module CLIs.
"""

import os
from datetime import timedelta

from flask import Flask, redirect, request, session, url_for


def create_app() -> Flask:
    """Create and configure the QMS Flask application."""
    app = Flask(
        __name__,
        template_folder="../frontend/templates",
        static_folder="../frontend/static",
    )

    # ── Secret key ───────────────────────────────────────────────────────
    from qms.core.config import get_config

    config = get_config()
    auth_cfg = config.get("auth", {})

    secret = os.environ.get("QMS_SECRET_KEY") or auth_cfg.get("secret_key")
    app.config["SECRET_KEY"] = secret or os.urandom(32).hex()

    session_minutes = auth_cfg.get("session_lifetime_minutes", 480)
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(minutes=session_minutes)

    # ── Branding context processor ───────────────────────────────────────
    from qms.core.config import get_branding

    @app.context_processor
    def inject_theme():
        return {"theme": get_branding()}

    # ── Current user context processor ───────────────────────────────────
    @app.context_processor
    def inject_current_user():
        user = session.get("user")
        # Build set of accessible module names for nav rendering
        if user and user.get("role") == "admin":
            accessible = {"projects", "welding", "pipeline", "automation", "settings"}
        elif user:
            accessible = set(user.get("modules", {}).keys())
        else:
            accessible = set()
        return {"current_user": user, "accessible_modules": accessible}

    # ── Auth gate (before_request) ───────────────────────────────────────

    # Map blueprint prefix → module name for access checks
    _BLUEPRINT_MODULE = {
        "projects": "projects",
        "welding": "welding",
        "pipeline": "pipeline",
        "automation": "automation",
    }

    @app.before_request
    def require_auth():
        # Allow static files, auth endpoints, and health checks
        if request.endpoint and (
            request.endpoint.startswith("auth.")
            or request.endpoint == "static"
        ):
            return None

        if "user" not in session:
            return redirect(url_for("auth.login_page"))

        # Make session permanent so it respects PERMANENT_SESSION_LIFETIME
        session.permanent = True

        user = session["user"]

        # Global admins bypass module checks
        if user.get("role") == "admin":
            return None

        # Determine which module this request belongs to
        bp_name = request.blueprints[0] if request.blueprints else None
        module = _BLUEPRINT_MODULE.get(bp_name)

        if module:
            modules = user.get("modules", {})
            if module not in modules:
                from flask import abort
                abort(403)

    # ── Register blueprints ──────────────────────────────────────────────
    from qms.api.auth import bp as auth_bp
    app.register_blueprint(auth_bp)

    from qms.api.projects import bp as projects_bp
    app.register_blueprint(projects_bp)

    from qms.api.pipeline import bp as pipeline_bp
    app.register_blueprint(pipeline_bp)

    from qms.api.automation import bp as automation_bp
    app.register_blueprint(automation_bp)

    from qms.api.welding import bp as welding_bp
    app.register_blueprint(welding_bp)

    from qms.api.settings import bp as settings_bp
    app.register_blueprint(settings_bp)

    # Root redirect — send user to their first accessible module
    _MODULE_DEFAULTS = {
        "projects": "projects.dashboard",
        "welding": "welding.dashboard",
        "pipeline": "pipeline.intake_dashboard",
        "automation": "automation.preview",
    }

    @app.route("/")
    def index():
        user = session.get("user")
        if user and user.get("role") == "admin":
            return redirect(url_for("projects.dashboard"))

        # Non-admin: redirect to first accessible module
        if user:
            modules = user.get("modules", {})
            for mod, endpoint in _MODULE_DEFAULTS.items():
                if mod in modules:
                    return redirect(url_for(endpoint))

        return redirect(url_for("projects.dashboard"))

    return app
