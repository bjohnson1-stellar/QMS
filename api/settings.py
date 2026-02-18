"""
Settings Blueprint — Centralized admin panel for QMS configuration.

Two storage backends:
  - Database (budget_settings table) — budget/project settings
  - config.yaml — everything else (branding, intake, processing, etc.)
"""

from flask import Blueprint, jsonify, request, render_template

from qms.core import get_db
from qms.core.config import get_config, update_config_section
from qms.projects import budget

bp = Blueprint("settings", __name__, url_prefix="/settings")

# Sections of config.yaml that are safe to edit through the UI.
# Keys are the section paths (dot notation), used in the URL.
EDITABLE_SECTIONS = {
    "branding",
    "intake",
    "processing",
    "onedrive_sync",
    "welding.cert_requests",
    "extraction.thresholds",
    "conflicts.checks",
    "embeddings",
}


# ---------------------------------------------------------------------------
# Page route
# ---------------------------------------------------------------------------


@bp.route("/")
def settings_page():
    return render_template("settings/index.html")


# ---------------------------------------------------------------------------
# Budget settings API (DB-backed)
# ---------------------------------------------------------------------------


@bp.route("/api/budget", methods=["GET"])
def api_get_budget():
    return jsonify(budget.get_settings())


@bp.route("/api/budget", methods=["PUT"])
def api_update_budget():
    data = request.json
    with get_db() as conn:
        budget.update_settings(
            conn,
            company_name=data.get("companyName", "My Company"),
            default_hourly_rate=float(data.get("defaultHourlyRate", 150)),
            working_hours_per_month=int(data.get("workingHoursPerMonth", 176)),
            fiscal_year_start_month=int(data.get("fiscalYearStartMonth", 1)),
            gmp_weight_multiplier=float(data.get("gmpWeightMultiplier", 1.5)),
            max_hours_per_week=float(data.get("maxHoursPerWeek", 40.0)),
        )
    return jsonify({"message": "Budget settings updated"})


# ---------------------------------------------------------------------------
# Config.yaml section API
# ---------------------------------------------------------------------------


@bp.route("/api/config/<path:section>", methods=["GET"])
def api_get_config_section(section):
    section = section.replace("/", ".")
    if section not in EDITABLE_SECTIONS:
        return jsonify({"error": f"Section '{section}' is not editable"}), 403

    config = get_config(reload=True)
    keys = section.split(".")
    target = config
    for key in keys:
        if isinstance(target, dict) and key in target:
            target = target[key]
        else:
            return jsonify({"error": f"Section '{section}' not found"}), 404

    return jsonify(target)


@bp.route("/api/config/<path:section>", methods=["PUT"])
def api_update_config_section(section):
    section = section.replace("/", ".")
    if section not in EDITABLE_SECTIONS:
        return jsonify({"error": f"Section '{section}' is not editable"}), 403

    data = request.json
    if not isinstance(data, dict):
        return jsonify({"error": "Request body must be a JSON object"}), 400

    try:
        update_config_section(section, data)
    except KeyError as e:
        return jsonify({"error": str(e)}), 404

    return jsonify({"message": f"Section '{section}' updated"})
