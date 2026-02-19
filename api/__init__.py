"""
QMS Web Application Factory

Centralized Flask app that registers module blueprints.
Mirrors how cli/main.py assembles module CLIs.
"""

import hashlib
import hmac
import os
from datetime import timedelta
from pathlib import Path

from flask import Flask, abort, redirect, request, session, url_for


def _get_or_create_secret() -> str:
    """Resolve SECRET_KEY with priority: env var > config > file > generate.

    On first run with no key configured, generates a random key and persists
    it to data/.secret_key so sessions survive server restarts.
    """
    from qms.core.config import get_config, QMS_PATHS

    # 1. Environment variable
    env_key = os.environ.get("QMS_SECRET_KEY")
    if env_key:
        return env_key

    # 2. config.yaml auth.secret_key
    config = get_config()
    cfg_key = config.get("auth", {}).get("secret_key")
    if cfg_key:
        return cfg_key

    # 3. Persistent file in data directory
    key_file = Path(QMS_PATHS.database).parent / ".secret_key"
    if key_file.exists():
        stored = key_file.read_text().strip()
        if stored:
            return stored

    # 4. Generate, persist, and return
    new_key = os.urandom(32).hex()
    key_file.parent.mkdir(parents=True, exist_ok=True)
    key_file.write_text(new_key)
    return new_key


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

    app.config["SECRET_KEY"] = _get_or_create_secret()

    session_minutes = auth_cfg.get("session_lifetime_minutes", 480)
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(minutes=session_minutes)

    # ── Session cookie hardening ─────────────────────────────────────────
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_NAME"] = "qms_session"

    # ── Security headers ─────────────────────────────────────────────────
    @app.after_request
    def set_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        return response

    # ── Branding + module registry context processors ────────────────────
    from qms.core.config import get_branding, get_web_modules

    @app.context_processor
    def inject_theme():
        return {"theme": get_branding()}

    @app.context_processor
    def inject_current_user():
        user = session.get("user")
        modules_cfg = get_web_modules()
        # Build set of accessible module names for nav rendering
        if user and user.get("role") == "admin":
            accessible = set(modules_cfg.keys()) | {"settings"}
        elif user:
            accessible = set(user.get("modules", {}).keys())
        else:
            accessible = set()
        return {
            "current_user": user,
            "accessible_modules": accessible,
            "web_modules": modules_cfg,
        }

    # ── CSRF protection ──────────────────────────────────────────────────

    def _generate_csrf_token() -> str:
        """Generate a CSRF token tied to the session."""
        if "_csrf_nonce" not in session:
            session["_csrf_nonce"] = os.urandom(16).hex()
        return hmac.new(
            app.config["SECRET_KEY"].encode(),
            session["_csrf_nonce"].encode(),
            hashlib.sha256,
        ).hexdigest()

    @app.context_processor
    def inject_csrf():
        return {"csrf_token": _generate_csrf_token}

    @app.before_request
    def check_csrf():
        """Validate CSRF token on POST requests from HTML forms."""
        if request.method != "POST":
            return None
        # Skip CSRF for JSON API requests (protected by SameSite cookies)
        content_type = request.content_type or ""
        if "application/json" in content_type:
            return None
        # Auth login needs CSRF but may not have a session yet — skip if
        # there's no nonce (first visit). The token won't validate anyway
        # because there's nothing to compare against.
        if "_csrf_nonce" not in session:
            return None
        token = request.form.get("csrf_token", "")
        expected = _generate_csrf_token()
        if not hmac.compare_digest(token, expected):
            abort(400, "CSRF validation failed.")

    # ── Auth gate (before_request) ───────────────────────────────────────

    # Map blueprint prefix → module name for access checks (from config)
    _modules_cfg = get_web_modules()
    _BLUEPRINT_MODULE = {mod: mod for mod in _modules_cfg}

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

    from qms.api.workforce import bp as workforce_bp
    app.register_blueprint(workforce_bp)

    from qms.api.qualitydocs import bp as qualitydocs_bp
    app.register_blueprint(qualitydocs_bp)

    # Root redirect — send user to their first accessible module
    _MODULE_DEFAULTS = {
        mod: info["default_endpoint"] for mod, info in _modules_cfg.items()
    }

    # Determine the fallback endpoint (first module in config)
    _first_endpoint = next(iter(_MODULE_DEFAULTS.values()), "projects.dashboard")

    @app.route("/")
    def index():
        user = session.get("user")
        if user and user.get("role") == "admin":
            return redirect(url_for(_first_endpoint))

        # Non-admin: redirect to first accessible module
        if user:
            modules = user.get("modules", {})
            for mod, endpoint in _MODULE_DEFAULTS.items():
                if mod in modules:
                    return redirect(url_for(endpoint))

        return redirect(url_for(_first_endpoint))

    # ── Admin-only system map (unlisted, no nav link) ───────────────────
    @app.route("/admin/system-map")
    def system_map():
        from flask import render_template, abort, session
        from datetime import datetime

        user = session.get("user")
        if not user or user.get("role") != "admin":
            abort(404)  # hide from non-admins entirely

        from qms.core import get_db
        from qms.core.config import QMS_PATHS

        stats = {}
        try:
            with get_db() as conn:
                stats["projects"] = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
                stats["sheets"] = conn.execute("SELECT COUNT(*) FROM sheets").fetchone()[0]
                stats["extracted"] = conn.execute(
                    "SELECT COUNT(*) FROM sheets WHERE extracted_at IS NOT NULL"
                ).fetchone()[0]
                stats["employees"] = conn.execute("SELECT COUNT(*) FROM employees").fetchone()[0]
                stats["welders"] = conn.execute(
                    "SELECT COUNT(*) FROM weld_welder_registry WHERE status='active'"
                ).fetchone()[0]
                stats["wps_count"] = conn.execute("SELECT COUNT(*) FROM weld_wps").fetchone()[0]
                stats["wpq_count"] = conn.execute("SELECT COUNT(*) FROM weld_wpq").fetchone()[0]
                stats["tables"] = conn.execute(
                    "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
                ).fetchone()[0]
        except Exception:
            stats = {k: "?" for k in [
                "projects", "sheets", "extracted", "employees",
                "welders", "wps_count", "wpq_count", "tables",
            ]}

        # Count inbox files
        inbox = QMS_PATHS.inbox
        try:
            stats["inbox_files"] = sum(1 for f in inbox.iterdir() if f.is_file())
        except Exception:
            stats["inbox_files"] = "?"

        return render_template(
            "admin/system-map.html",
            stats=stats,
            current_user=user,
            updated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        )

    return app
