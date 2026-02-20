"""
Automation Preview — Live Adaptive Card preview with database data.

Renders card templates using the Adaptive Cards JS SDK with real
lookup data from quality.db. Supports simulating the two-step
card flow (Step 1 → Step 2) with filtering.

Routes:
    GET /automation/preview          — Preview page
    GET /automation/api/jobs         — Active projects with field personnel
    GET /automation/api/employees    — Employees (optionally filtered by project)
    GET /automation/api/wps          — WPS records with process/material details
    GET /automation/api/wps/<number> — Full WPS detail for a single record
    GET /automation/api/card/<name>  — Raw card template JSON
"""

from pathlib import Path

from flask import Blueprint, jsonify, render_template, request

from qms.core import get_db

bp = Blueprint(
    "automation",
    __name__,
    url_prefix="/automation",
)

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "automation" / "templates"


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

@bp.route("/preview")
def preview():
    """Render the Adaptive Card preview page."""
    # List available card templates
    cards = sorted(
        f.stem for f in TEMPLATES_DIR.glob("*.json")
        if not f.stem.endswith("-TEST")
    )
    return render_template("automation/preview.html", cards=cards)


# ---------------------------------------------------------------------------
# Data API — JSON endpoints for live card data
# ---------------------------------------------------------------------------

@bp.route("/api/jobs")
def api_jobs():
    """Projects with active field personnel, as Adaptive Card choices."""
    with get_db(readonly=True) as conn:
        rows = conn.execute(
            """SELECT p.number, p.name, COUNT(e.id) AS emp_count
               FROM projects p
               JOIN jobs j ON j.project_id = p.id
               JOIN employees e ON e.job_id = j.id AND e.is_active = 1
               GROUP BY p.number, p.name
               ORDER BY p.number"""
        ).fetchall()

    choices = [
        {"title": f"{r['number']} - {r['name']}", "value": r["number"]}
        for r in rows
    ]
    details = {
        r["number"]: {"name": r["name"], "emp_count": r["emp_count"]}
        for r in rows
    }
    return jsonify({"choices": choices, "details": details})


@bp.route("/api/employees")
def api_employees():
    """Active employees. ?job_number=X filters to that project."""
    job_number = request.args.get("job_number", "").strip()

    sql = """
        SELECT e.employee_number,
               COALESCE(e.preferred_name, e.first_name) || ' ' || e.last_name
                   AS display_name,
               e.first_name, e.last_name, e.preferred_name,
               e.phone, e.email, e.position,
               p.number AS project_number, p.name AS project_name
        FROM employees e
        LEFT JOIN jobs j ON e.job_id = j.id
        LEFT JOIN projects p ON j.project_id = p.id
        WHERE e.status = 'active' AND e.job_id IS NOT NULL
    """
    params = []
    if job_number:
        sql += " AND p.number = ?"
        params.append(job_number)
    sql += " ORDER BY e.last_name, e.first_name"

    with get_db(readonly=True) as conn:
        rows = conn.execute(sql, params).fetchall()

    # Skip employees without an employee_number (can't be referenced in cards)
    valid = [r for r in rows if r["employee_number"]]
    choices = [
        {"title": r["display_name"], "value": r["employee_number"]}
        for r in valid
    ]
    details = {
        r["employee_number"]: {
            "display_name": r["display_name"],
            "first_name": r["first_name"],
            "last_name": r["last_name"],
            "phone": r["phone"] or "",
            "email": r["email"] or "",
            "position": r["position"] or "",
            "project_number": r["project_number"] or "",
            "project_name": r["project_name"] or "",
        }
        for r in valid
    }
    return jsonify({"choices": choices, "details": details, "count": len(valid)})


@bp.route("/api/wps")
def api_wps():
    """WPS records with process and material summaries."""
    with get_db(readonly=True) as conn:
        wps_rows = conn.execute(
            """SELECT id, wps_number, title, status
               FROM weld_wps
               WHERE status IN ('active', 'draft')
               ORDER BY wps_number"""
        ).fetchall()

        result = []
        for w in wps_rows:
            wps_id = w["id"]
            label = w["title"] or w["wps_number"]

            # Processes
            procs = conn.execute(
                "SELECT process_type FROM weld_wps_processes WHERE wps_id = ? ORDER BY process_sequence",
                (wps_id,),
            ).fetchall()
            process_list = [p["process_type"] for p in procs]

            # Base metals
            metals = conn.execute(
                "SELECT material_spec, p_number, material_type FROM weld_wps_base_metals WHERE wps_id = ?",
                (wps_id,),
            ).fetchall()
            material_list = [m["material_spec"] or f"P{m['p_number']}" for m in metals]

            # Filler metals
            fillers = conn.execute(
                "SELECT aws_class, f_number FROM weld_wps_filler_metals WHERE wps_id = ?",
                (wps_id,),
            ).fetchall()
            filler_list = list({f["aws_class"] for f in fillers if f["aws_class"]})

            # Positions
            pos = conn.execute(
                "SELECT groove_positions, fillet_positions FROM weld_wps_positions WHERE wps_id = ?",
                (wps_id,),
            ).fetchone()

            result.append({
                "wps_number": w["wps_number"],
                "title": w["title"] or "",
                "status": w["status"],
                "processes": process_list,
                "materials": material_list,
                "fillers": filler_list,
                "groove_positions": (pos["groove_positions"] or "").split(",") if pos else [],
                "fillet_positions": (pos["fillet_positions"] or "").split(",") if pos else [],
                "summary": " / ".join(process_list) if process_list else w["wps_number"],
            })

    choices = [
        {
            "title": f"{r['wps_number']} - {r['summary']}" if r["summary"] != r["wps_number"]
                     else r["wps_number"],
            "value": r["wps_number"],
        }
        for r in result
    ]
    details = {r["wps_number"]: r for r in result}
    return jsonify({"choices": choices, "details": details})


@bp.route("/api/card/<name>")
def api_card(name: str):
    """Return raw card template JSON by name (without .json extension)."""
    safe_name = name.replace("/", "").replace("\\", "").replace("..", "")
    path = TEMPLATES_DIR / f"{safe_name}.json"
    if not path.is_file():
        return jsonify({"error": f"Card template '{name}' not found"}), 404

    import json
    with open(path, encoding="utf-8") as f:
        card = json.load(f)
    return jsonify(card)
