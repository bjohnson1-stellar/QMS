"""
QMS Web Application Factory

Centralized Flask app that registers module blueprints.
Mirrors how cli/main.py assembles module CLIs.
"""

from flask import Flask


def create_app() -> Flask:
    """Create and configure the QMS Flask application."""
    app = Flask(
        __name__,
        template_folder="../frontend/templates",
        static_folder="../frontend/static",
    )
    app.config["SECRET_KEY"] = "qms-dev-key"

    from qms.core.config import get_branding

    @app.context_processor
    def inject_theme():
        return {"theme": get_branding()}

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
        from flask import redirect, url_for
        return redirect(url_for("projects.dashboard"))

    return app
