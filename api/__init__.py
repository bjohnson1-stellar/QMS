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
        return {"current_user": session.get("user")}

    # ── Auth gate (before_request) ───────────────────────────────────────
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

    # Root redirect to projects dashboard
    @app.route("/")
    def index():
        return redirect(url_for("projects.dashboard"))

    return app
