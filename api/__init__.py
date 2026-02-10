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

    from qms.api.projects import bp as projects_bp
    app.register_blueprint(projects_bp)

    # Root redirect to projects dashboard
    @app.route("/")
    def index():
        from flask import redirect, url_for
        return redirect(url_for("projects.dashboard"))

    return app
