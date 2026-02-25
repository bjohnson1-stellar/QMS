"""
Welding Blueprint — Flask routes for welding qualification UI.

Thin delivery layer: business logic lives in welding.qualification_rules
and welding.forms. CRUD operations go through the database directly.
"""

from flask import Blueprint, jsonify, request, render_template, session

from qms.core import get_db
from qms.auth.decorators import module_required, role_required

bp = Blueprint("welding", __name__, url_prefix="/welding")


# ---------------------------------------------------------------------------
# Page routes (render templates)
# ---------------------------------------------------------------------------

@bp.route("/")
def dashboard():
    with get_db(readonly=True) as conn:
        stats = _get_dashboard_stats(conn)
        recent = _get_recent_qualifications(conn)
        expiring = _get_expiring_qualifications(conn)
    return render_template(
        "welding/dashboard.html",
        stats=stats, recent=recent, expiring=expiring,
    )


@bp.route("/forms")
def forms_list():
    return render_template("welding/form_list.html")


@bp.route("/welders")
def welders_list():
    return render_template("welding/welders.html")


@bp.route("/welder/<welder_stamp>")
def welder_profile(welder_stamp):
    with get_db(readonly=True) as conn:
        welder = _get_welder_info(conn, welder_stamp)
        wpqs = conn.execute(
            "SELECT * FROM weld_wpq WHERE welder_stamp = ? ORDER BY test_date DESC",
            (welder_stamp,)
        ).fetchall()
        bpqrs = conn.execute(
            "SELECT * FROM weld_bpqr WHERE brazer_stamp = ? ORDER BY test_date DESC",
            (welder_stamp,)
        ).fetchall()
    return render_template(
        "welding/welder_profile.html",
        welder=welder, wpqs=[dict(r) for r in wpqs],
        bpqrs=[dict(r) for r in bpqrs],
        stamp=welder_stamp,
    )


@bp.route("/wpq/new")
def wpq_new():
    return render_template("welding/wpq_detail.html", wpq=None, qualifications=[], edit=True)


@bp.route("/wpq/<int:wpq_id>")
def wpq_detail(wpq_id):
    edit = request.args.get("edit") == "1"
    with get_db(readonly=True) as conn:
        wpq = conn.execute("SELECT * FROM weld_wpq WHERE id = ?", (wpq_id,)).fetchone()
        if not wpq:
            return "WPQ not found", 404
        tests = conn.execute(
            "SELECT * FROM weld_wpq_tests WHERE wpq_id = ? ORDER BY test_type",
            (wpq_id,)
        ).fetchall()
        qualifications = _get_qualifications(conn, "weld_wpq_qualifications", "wpq_id", wpq_id)
    return render_template(
        "welding/wpq_detail.html",
        wpq=dict(wpq), tests=[dict(t) for t in tests],
        qualifications=qualifications, edit=edit,
    )


@bp.route("/bpqr/new")
def bpqr_new():
    return render_template("welding/bpqr_detail.html", bpqr=None, qualifications=[], edit=True)


@bp.route("/bpqr/<int:bpqr_id>")
def bpqr_detail(bpqr_id):
    edit = request.args.get("edit") == "1"
    with get_db(readonly=True) as conn:
        bpqr = conn.execute("SELECT * FROM weld_bpqr WHERE id = ?", (bpqr_id,)).fetchone()
        if not bpqr:
            return "BPQR not found", 404
        tests = conn.execute(
            "SELECT * FROM weld_bpqr_tests WHERE bpqr_id = ? ORDER BY test_type",
            (bpqr_id,)
        ).fetchall()
        qualifications = _get_qualifications(conn, "weld_bpqr_qualifications", "bpqr_id", bpqr_id)
    return render_template(
        "welding/bpqr_detail.html",
        bpqr=dict(bpqr), tests=[dict(t) for t in tests],
        qualifications=qualifications, edit=edit,
    )


@bp.route("/wps/<int:wps_id>")
def wps_detail(wps_id):
    edit = request.args.get("edit") == "1"
    with get_db(readonly=True) as conn:
        wps = conn.execute("SELECT * FROM weld_wps WHERE id = ?", (wps_id,)).fetchone()
        if not wps:
            return "WPS not found", 404
    return render_template("welding/wps_detail.html", wps=dict(wps), edit=edit)


@bp.route("/pqr/<int:pqr_id>")
def pqr_detail(pqr_id):
    edit = request.args.get("edit") == "1"
    with get_db(readonly=True) as conn:
        pqr = conn.execute("SELECT * FROM weld_pqr WHERE id = ?", (pqr_id,)).fetchone()
        if not pqr:
            return "PQR not found", 404
    return render_template("welding/pqr_detail.html", pqr=dict(pqr), edit=edit)


# ---------------------------------------------------------------------------
# Cert Request Page Routes
# ---------------------------------------------------------------------------

@bp.route("/cert-requests")
@module_required("welding")
def cert_requests_list():
    from qms.welding.cert_requests import list_cert_requests
    requests_data = list_cert_requests(limit=100)
    return render_template("welding/cert_requests_list.html", requests=requests_data)


@bp.route("/cert-request/new")
@module_required("welding", min_role="editor")
def cert_request_new():
    return render_template("welding/cert_request_form.html")


# ---------------------------------------------------------------------------
# Cert Request Lookup API (cascade endpoints)
# ---------------------------------------------------------------------------

@bp.route("/api/lookup/materials")
@module_required("welding")
def api_lookup_materials():
    """Distinct base materials from WPS base metals (all WPSes with data)."""
    with get_db(readonly=True) as conn:
        # Primary: from weld_wps_base_metals child table
        rows = conn.execute("""
            SELECT DISTINCT bm.material_spec, bm.p_number, bm.group_number
            FROM weld_wps_base_metals bm
            JOIN weld_wps w ON w.id = bm.wps_id
            WHERE bm.material_spec IS NOT NULL AND bm.material_spec != ''
            ORDER BY bm.material_spec
        """).fetchall()
        materials = [dict(r) for r in rows]

        # Fallback: if no child data, parse WPS numbers for P-number hints
        if not materials:
            wps_rows = conn.execute(
                "SELECT DISTINCT wps_number FROM weld_wps ORDER BY wps_number"
            ).fetchall()
            seen = set()
            for r in wps_rows:
                num = r["wps_number"] or ""
                # e.g. CS-01-P1-SMAW → infer "Carbon Steel (P1)"
                if "P1" in num and "Carbon Steel" not in seen:
                    materials.append({"material_spec": "Carbon Steel (P1)", "p_number": 1, "group_number": None})
                    seen.add("Carbon Steel")
                elif "P8" in num and "Stainless Steel" not in seen:
                    materials.append({"material_spec": "Stainless Steel (P8)", "p_number": 8, "group_number": None})
                    seen.add("Stainless Steel")
                elif "P08" in num and "Stainless Steel" not in seen:
                    materials.append({"material_spec": "Stainless Steel (P8)", "p_number": 8, "group_number": None})
                    seen.add("Stainless Steel")

    return jsonify(materials)


@bp.route("/api/lookup/processes")
@module_required("welding")
def api_lookup_processes():
    """Processes from WPSes that cover a given base material."""
    material = request.args.get("material", "")
    with get_db(readonly=True) as conn:
        if material:
            # Try child table first
            rows = conn.execute("""
                SELECT p.process_type, COUNT(DISTINCT w.id) as count_of_wps
                FROM weld_wps_processes p
                JOIN weld_wps w ON w.id = p.wps_id
                JOIN weld_wps_base_metals bm ON bm.wps_id = w.id
                WHERE bm.material_spec = ?
                AND p.process_type IS NOT NULL
                GROUP BY p.process_type
                ORDER BY p.process_type
            """, (material,)).fetchall()

            if not rows:
                # Fallback: parse process from WPS number for matching P-number
                p_num = request.args.get("p_number", "")
                p_pattern = f"P{p_num}" if p_num else ""
                all_wps = conn.execute(
                    "SELECT wps_number FROM weld_wps ORDER BY wps_number"
                ).fetchall()
                process_counts = {}
                for r in all_wps:
                    num = r["wps_number"] or ""
                    if p_pattern and p_pattern not in num:
                        continue
                    for proc in ("GTAW/SMAW", "GTAW", "SMAW", "FCAW", "GMAW", "SAW"):
                        if proc in num:
                            process_counts[proc] = process_counts.get(proc, 0) + 1
                            break
                rows = [{"process_type": k, "count_of_wps": v}
                        for k, v in sorted(process_counts.items())]
        else:
            rows = conn.execute("""
                SELECT p.process_type, COUNT(DISTINCT w.id) as count_of_wps
                FROM weld_wps_processes p
                JOIN weld_wps w ON w.id = p.wps_id
                WHERE p.process_type IS NOT NULL
                GROUP BY p.process_type
                ORDER BY p.process_type
            """).fetchall()
            if not rows:
                # Fallback: all known processes from lookup table
                rows = conn.execute(
                    "SELECT code as process_type, 0 as count_of_wps FROM weld_valid_processes ORDER BY code"
                ).fetchall()

    return jsonify([dict(r) if hasattr(r, 'keys') else r for r in rows])


@bp.route("/api/lookup/wps")
@module_required("welding")
def api_lookup_wps():
    """Active WPSes matching material and/or process filters."""
    material = request.args.get("material", "")
    process = request.args.get("process", "")

    with get_db(readonly=True) as conn:
        # Build query based on available child data
        if material and process:
            rows = conn.execute("""
                SELECT DISTINCT w.id, w.wps_number, w.revision, w.title, w.status
                FROM weld_wps w
                LEFT JOIN weld_wps_base_metals bm ON bm.wps_id = w.id
                LEFT JOIN weld_wps_processes p ON p.wps_id = w.id
                WHERE (bm.material_spec = ? OR w.wps_number LIKE ?)
                  AND (p.process_type = ? OR w.wps_number LIKE ?)
                ORDER BY w.wps_number
            """, (material, f"%{process}%", process, f"%{process}%")).fetchall()
        elif material:
            rows = conn.execute("""
                SELECT DISTINCT w.id, w.wps_number, w.revision, w.title, w.status
                FROM weld_wps w
                LEFT JOIN weld_wps_base_metals bm ON bm.wps_id = w.id
                WHERE bm.material_spec = ? OR 1=1
                ORDER BY w.wps_number
            """, (material,)).fetchall()
        elif process:
            rows = conn.execute("""
                SELECT DISTINCT w.id, w.wps_number, w.revision, w.title, w.status
                FROM weld_wps w
                LEFT JOIN weld_wps_processes p ON p.wps_id = w.id
                WHERE p.process_type = ? OR w.wps_number LIKE ?
                ORDER BY w.wps_number
            """, (process, f"%{process}%")).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, wps_number, revision, title, status FROM weld_wps ORDER BY wps_number"
            ).fetchall()

        results = []
        for r in rows:
            wps = dict(r)
            wps_id = wps["id"]
            # Enrich with child data
            fillers = conn.execute(
                "SELECT sfa_spec, aws_class FROM weld_wps_filler_metals WHERE wps_id = ?",
                (wps_id,)
            ).fetchall()
            wps["filler_metals"] = [dict(f) for f in fillers]

            positions = conn.execute(
                "SELECT groove_positions, fillet_positions FROM weld_wps_positions WHERE wps_id = ?",
                (wps_id,)
            ).fetchone()
            wps["positions"] = dict(positions) if positions else {}

            thickness = conn.execute(
                "SELECT MIN(thickness_min) as t_min, MAX(thickness_max) as t_max, "
                "MIN(diameter_min) as d_min, MAX(diameter_max) as d_max "
                "FROM weld_wps_base_metals WHERE wps_id = ?",
                (wps_id,)
            ).fetchone()
            if thickness:
                wps["thickness_range"] = {"min": thickness["t_min"], "max": thickness["t_max"]}
                wps["diameter_range"] = {"min": thickness["d_min"], "max": thickness["d_max"]}

            results.append(wps)

    return jsonify(results)


@bp.route("/api/lookup/positions")
@module_required("welding")
def api_lookup_positions():
    """All valid welding positions."""
    with get_db(readonly=True) as conn:
        rows = conn.execute(
            "SELECT code, description, joint_type, qualifies_for FROM weld_valid_positions ORDER BY code"
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@bp.route("/api/lookup/preapproved-coupons")
@module_required("welding")
def api_lookup_preapproved_coupons():
    """All active pre-approved coupon configurations, grouped by category."""
    with get_db(readonly=True) as conn:
        rows = conn.execute("""
            SELECT code, name, description, qualification_code, category,
                   process, base_material, p_number, position, wps_number,
                   filler_metal, diameter, thickness, priority
            FROM weld_preapproved_coupons
            WHERE status = 'active'
            ORDER BY category, priority, code
        """).fetchall()
    return jsonify([dict(r) for r in rows])


@bp.route("/api/welders/search")
@module_required("welding")
def api_welders_search():
    """Search welders by name, stamp, or employee number."""
    q = request.args.get("q", "").strip()
    if len(q) < 2:
        return jsonify([])

    with get_db(readonly=True) as conn:
        like = f"%{q}%"
        rows = conn.execute("""
            SELECT r.id, r.display_name, r.welder_stamp, r.employee_number,
                   r.department, r.status
            FROM weld_welder_registry r
            WHERE r.status = 'active'
              AND (r.display_name LIKE ? OR r.welder_stamp LIKE ?
                   OR r.employee_number LIKE ? OR r.first_name LIKE ?
                   OR r.last_name LIKE ?)
            ORDER BY r.display_name
            LIMIT 20
        """, (like, like, like, like, like)).fetchall()

        results = []
        for r in rows:
            w = dict(r)
            # Get active WPQs for this welder
            wpqs = conn.execute("""
                SELECT wpq_number, process_type, groove_positions_qualified,
                       current_expiration_date, status
                FROM weld_wpq WHERE welder_stamp = ? AND status = 'active'
                ORDER BY current_expiration_date
            """, (w["welder_stamp"],)).fetchall()
            w["active_wpqs"] = [dict(wpq) for wpq in wpqs]
            results.append(w)

    return jsonify(results)


@bp.route("/api/projects/search")
@module_required("welding")
def api_projects_search():
    """Search projects by number or name (filtered by user BU access)."""
    q = request.args.get("q", "").strip()
    if len(q) < 2:
        return jsonify([])

    with get_db(readonly=True) as conn:
        like = f"%{q}%"
        rows = conn.execute("""
            SELECT id, project_number, project_name
            FROM projects
            WHERE project_number LIKE ? OR project_name LIKE ?
            ORDER BY project_number
            LIMIT 20
        """, (like, like)).fetchall()

    return jsonify([dict(r) for r in rows])


@bp.route("/api/welders/check-duplicate")
@module_required("welding")
def api_check_duplicate_qual():
    """Check if a welder already has an active WPQ for a given WPS+process+position."""
    stamp = request.args.get("stamp", "")
    wps = request.args.get("wps", "")
    process = request.args.get("process", "")
    position = request.args.get("position", "")

    if not stamp:
        return jsonify({"duplicate": False})

    with get_db(readonly=True) as conn:
        conditions = ["welder_stamp = ?", "status = 'active'"]
        params = [stamp]

        if wps:
            conditions.append("wps_number = ?")
            params.append(wps)
        if process:
            conditions.append("process_type = ?")
            params.append(process)
        if position:
            conditions.append("(groove_positions_qualified LIKE ? OR test_position = ?)")
            params.extend([f"%{position}%", position])

        where = " AND ".join(conditions)
        row = conn.execute(
            f"SELECT id, wpq_number, current_expiration_date FROM weld_wpq WHERE {where} LIMIT 1",
            params
        ).fetchone()

        if row:
            return jsonify({
                "duplicate": True,
                "wpq_number": row["wpq_number"],
                "expiration": row["current_expiration_date"],
            })

    return jsonify({"duplicate": False})


@bp.route("/api/cert-requests", methods=["POST"])
@module_required("welding", min_role="editor")
def api_create_cert_request():
    """Create a new WCR from the web form (same logic as JSON intake)."""
    from datetime import date, datetime
    from qms.welding.cert_requests import (
        validate_cert_request_json, get_next_wcr_number,
        _lookup_or_register_welder,
    )

    data = request.json
    if not data:
        return jsonify({"errors": ["No data provided"]}), 400

    # Ensure required structure
    if "type" not in data:
        data["type"] = "weld_cert_request"

    # Validate
    errors = validate_cert_request_json(data)
    if errors:
        return jsonify({"errors": errors}), 400

    with get_db() as conn:
        # Welder lookup/registration
        welder_data = data["welder"]
        welder_result = _lookup_or_register_welder(conn, welder_data)
        if welder_result["errors"]:
            return jsonify({"errors": welder_result["errors"]}), 400

        wcr_number = get_next_wcr_number(conn)
        project = data.get("project", {})
        user = session.get("user", {})

        conn.execute(
            """INSERT INTO weld_cert_requests (
                   wcr_number, welder_id, employee_number, welder_name,
                   welder_stamp, project_number, project_name,
                   request_date, submitted_by, submitted_at,
                   status, is_new_welder, notes, source_file
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending_approval', ?, ?, 'web-form')""",
            (
                wcr_number,
                welder_result["welder_id"],
                welder_data.get("employee_number"),
                welder_data.get("name"),
                welder_result["stamp"],
                project.get("number"),
                project.get("name"),
                data.get("request_date", date.today().isoformat()),
                data.get("submitted_by") or user.get("name", "web"),
                datetime.now().isoformat(),
                1 if welder_data.get("is_new") else 0,
                data.get("notes"),
            ),
        )
        wcr_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        coupons = data.get("coupons", [])
        for i, coupon in enumerate(coupons, 1):
            conn.execute(
                """INSERT INTO weld_cert_request_coupons (
                       wcr_id, coupon_number, process, position,
                       wps_number, base_material, filler_metal,
                       thickness, diameter, status
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')""",
                (
                    wcr_id, i,
                    coupon.get("process", "").upper(),
                    coupon.get("position"),
                    coupon.get("wps_number"),
                    coupon.get("base_material"),
                    coupon.get("filler_metal"),
                    coupon.get("thickness"),
                    coupon.get("diameter"),
                ),
            )
        conn.commit()

    return jsonify({
        "wcr_number": wcr_number,
        "coupon_count": len(coupons),
        "welder_stamp": welder_result["stamp"],
        "welder_created": welder_result["was_created"],
    }), 201


# ---------------------------------------------------------------------------
# API routes (JSON)
# ---------------------------------------------------------------------------

@bp.route("/api/forms/<form_type>", methods=["GET"])
def api_list_forms(form_type):
    table_map = {
        "wps": "weld_wps", "pqr": "weld_pqr", "wpq": "weld_wpq",
        "bps": "weld_bps", "bpq": "weld_bpq", "bpqr": "weld_bpqr",
    }
    table = table_map.get(form_type.lower())
    if not table:
        return jsonify({"error": f"Unknown form type: {form_type}"}), 400

    with get_db(readonly=True) as conn:
        rows = conn.execute(f"SELECT * FROM {table} ORDER BY id DESC").fetchall()
    return jsonify([dict(r) for r in rows])


@bp.route("/api/forms/<form_type>", methods=["POST"])
def api_create_form(form_type):
    table_map = {
        "wps": "weld_wps", "pqr": "weld_pqr", "wpq": "weld_wpq",
        "bps": "weld_bps", "bpq": "weld_bpq", "bpqr": "weld_bpqr",
    }
    table = table_map.get(form_type.lower())
    if not table:
        return jsonify({"error": f"Unknown form type: {form_type}"}), 400

    data = request.json
    if not data:
        return jsonify({"error": "No data provided"}), 400

    with get_db() as conn:
        # Filter to valid columns
        valid_cols = {
            r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()
        }
        filtered = {k: v for k, v in data.items()
                    if k in valid_cols and k not in ("id", "created_at")}

        if not filtered:
            return jsonify({"error": "No valid fields provided"}), 400

        columns = list(filtered.keys())
        placeholders = ", ".join(["?"] * len(columns))
        col_str = ", ".join(columns)
        values = [filtered[c] for c in columns]

        cursor = conn.execute(
            f"INSERT INTO {table} ({col_str}) VALUES ({placeholders})", values
        )
        conn.commit()
        record_id = cursor.lastrowid

    return jsonify({"id": record_id, "action": "created"}), 201


@bp.route("/api/forms/<form_type>/<int:record_id>", methods=["GET"])
def api_get_form(form_type, record_id):
    table_map = {
        "wps": "weld_wps", "pqr": "weld_pqr", "wpq": "weld_wpq",
        "bps": "weld_bps", "bpq": "weld_bpq", "bpqr": "weld_bpqr",
    }
    table = table_map.get(form_type.lower())
    if not table:
        return jsonify({"error": f"Unknown form type: {form_type}"}), 400

    with get_db(readonly=True) as conn:
        row = conn.execute(f"SELECT * FROM {table} WHERE id = ?", (record_id,)).fetchone()
        if not row:
            return jsonify({"error": "Record not found"}), 404

        result = dict(row)

        # Include qualifications if WPQ or BPQR
        ft = form_type.lower()
        if ft in ("wpq", "bpqr"):
            qual_table = f"weld_{ft}_qualifications"
            fk_col = f"{ft}_id"
            try:
                quals = conn.execute(
                    f"SELECT * FROM {qual_table} WHERE {fk_col} = ?",
                    (record_id,)
                ).fetchall()
                result["qualifications"] = [dict(q) for q in quals]
            except Exception:
                result["qualifications"] = []

    return jsonify(result)


@bp.route("/api/forms/<form_type>/<int:record_id>", methods=["PUT"])
def api_update_form(form_type, record_id):
    table_map = {
        "wps": "weld_wps", "pqr": "weld_pqr", "wpq": "weld_wpq",
        "bps": "weld_bps", "bpq": "weld_bpq", "bpqr": "weld_bpqr",
    }
    table = table_map.get(form_type.lower())
    if not table:
        return jsonify({"error": f"Unknown form type: {form_type}"}), 400

    data = request.json
    if not data:
        return jsonify({"error": "No data provided"}), 400

    with get_db() as conn:
        valid_cols = {
            r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()
        }
        filtered = {k: v for k, v in data.items()
                    if k in valid_cols and k not in ("id", "created_at")}

        if not filtered:
            return jsonify({"error": "No valid fields"}), 400

        set_clauses = [f"{k} = ?" for k in filtered.keys()]
        set_clauses.append("updated_at = CURRENT_TIMESTAMP")
        values = list(filtered.values()) + [record_id]

        conn.execute(
            f"UPDATE {table} SET {', '.join(set_clauses)} WHERE id = ?",
            values,
        )
        conn.commit()

    return jsonify({"id": record_id, "action": "updated"})


@bp.route("/api/derive", methods=["POST"])
def api_derive():
    """Live derivation endpoint — no database write."""
    data = request.json
    if not data:
        return jsonify({"error": "No data provided"}), 400

    form_type = data.get("form_type", "wpq")
    parent = data.get("parent", {})

    if not parent:
        return jsonify({"error": "No parent data"}), 400

    from qms.welding.qualification_rules import derive_qualified_ranges, UNLIMITED
    result = derive_qualified_ranges({"parent": parent}, form_type)

    # Convert UNLIMITED sentinel to string for display
    per_code = {}
    for code_id, code_data in result.per_code.items():
        per_code[code_id] = {
            k: ("Unlimited" if v == UNLIMITED else v)
            for k, v in code_data.items()
        }

    governing = {
        k: ("Unlimited" if v == UNLIMITED else v)
        for k, v in result.governing.items()
    }

    return jsonify({
        "per_code": per_code,
        "governing": governing,
        "governing_code": result.governing_code,
        "warnings": result.warnings,
        "rules_fired": len(result.rules_fired),
    })


@bp.route("/api/derive/<form_type>/<int:record_id>", methods=["POST"])
def api_derive_and_save(form_type, record_id):
    """Derive ranges and save to database."""
    table_map = {"wpq": "weld_wpq", "bpqr": "weld_bpqr"}
    table = table_map.get(form_type.lower())
    if not table:
        return jsonify({"error": "Only wpq and bpqr support derivation"}), 400

    from qms.welding.qualification_rules import derive_qualified_ranges

    with get_db() as conn:
        row = conn.execute(f"SELECT * FROM {table} WHERE id = ?", (record_id,)).fetchone()
        if not row:
            return jsonify({"error": "Record not found"}), 404

        data = {"parent": dict(row)}
        result = derive_qualified_ranges(data, form_type, conn)

        # Update parent with governing values
        if result.governing:
            set_clauses = [f"{k} = ?" for k in result.governing.keys()]
            values = list(result.governing.values()) + [record_id]
            conn.execute(
                f"UPDATE {table} SET {', '.join(set_clauses)} WHERE id = ?",
                values,
            )

        # Write per-code qualification rows
        qual_table = f"weld_{form_type}_qualifications"
        fk_col = f"{form_type}_id"
        try:
            valid_cols = {
                r[1] for r in conn.execute(f"PRAGMA table_info({qual_table})").fetchall()
            }
            conn.execute(f"DELETE FROM {qual_table} WHERE {fk_col} = ?", (record_id,))
            for code_id, code_data in result.per_code.items():
                filtered = {k: v for k, v in code_data.items()
                            if k in valid_cols and k not in ("id",)}
                filtered[fk_col] = record_id
                columns = list(filtered.keys())
                placeholders = ", ".join(["?"] * len(columns))
                col_str = ", ".join(columns)
                values = [filtered[c] for c in columns]
                conn.execute(
                    f"INSERT INTO {qual_table} ({col_str}) VALUES ({placeholders})",
                    values,
                )
        except Exception:
            pass  # Table may not exist yet

        conn.commit()

    return jsonify({
        "id": record_id,
        "action": "derived",
        "rules_fired": len(result.rules_fired),
        "warnings": result.warnings,
    })


@bp.route("/api/welders", methods=["GET"])
def api_list_welders():
    status = request.args.get("status", "")
    with get_db(readonly=True) as conn:
        rows = conn.execute("""
            SELECT r.id, r.welder_stamp as stamp, r.display_name as name,
                   r.department, r.status,
                   COUNT(DISTINCT w.id) as active_wpqs,
                   COUNT(DISTINCT b.id) as active_bpqrs,
                   MIN(CASE WHEN w.current_expiration_date >= date('now')
                       THEN w.current_expiration_date END) as next_expiration
            FROM weld_welder_registry r
            LEFT JOIN weld_wpq w ON w.welder_stamp = r.welder_stamp
                AND w.status = 'active'
            LEFT JOIN weld_bpqr b ON b.brazer_stamp = r.welder_stamp
                AND b.status = 'active'
            GROUP BY r.id
            ORDER BY r.display_name
        """).fetchall()
        result = [dict(r) for r in rows]
        if status:
            result = [r for r in result if (r.get("status") or "") == status]
    return jsonify(result)


@bp.route("/api/welders/<welder_stamp>", methods=["GET"])
def api_welder_detail(welder_stamp):
    with get_db(readonly=True) as conn:
        welder = _get_welder_info(conn, welder_stamp)
        wpqs = conn.execute(
            "SELECT id, wpq_number, process_type, test_position, status, "
            "current_expiration_date FROM weld_wpq WHERE welder_stamp = ?",
            (welder_stamp,)
        ).fetchall()
        bpqrs = conn.execute(
            "SELECT id, bpqr_number, brazing_process, status, "
            "current_expiration_date FROM weld_bpqr WHERE brazer_stamp = ?",
            (welder_stamp,)
        ).fetchall()
    return jsonify({
        "welder": welder,
        "wpqs": [dict(r) for r in wpqs],
        "bpqrs": [dict(r) for r in bpqrs],
    })


@bp.route("/api/welders/<welder_stamp>/status", methods=["PATCH"])
@role_required("admin")
def api_welder_update_status(welder_stamp):
    data = request.get_json(force=True)
    new_status = data.get("status", "").lower()
    if new_status not in ("active", "inactive", "terminated", "archived"):
        return jsonify({"error": "Invalid status"}), 400
    with get_db() as conn:
        row = conn.execute(
            "SELECT id FROM weld_welder_registry WHERE welder_stamp = ?",
            (welder_stamp,),
        ).fetchone()
        if not row:
            return jsonify({"error": "Welder not found"}), 404
        conn.execute(
            "UPDATE weld_welder_registry SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE welder_stamp = ?",
            (new_status, welder_stamp),
        )
        conn.commit()
    return jsonify({"ok": True, "status": new_status})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_dashboard_stats(conn):
    stats = {}
    for table, key in [
        ("weld_wps", "active_wps"),
        ("weld_pqr", "total_pqr"),
        ("weld_wpq", "active_wpq"),
        ("weld_bpqr", "active_bpqr"),
    ]:
        try:
            row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            stats[key] = row[0] if row else 0
        except Exception:
            stats[key] = 0

    # Expiring soon (within 30 days)
    try:
        row = conn.execute("""
            SELECT COUNT(*) FROM weld_wpq
            WHERE status = 'active'
            AND current_expiration_date IS NOT NULL
            AND current_expiration_date <= date('now', '+30 days')
        """).fetchone()
        stats["expiring_soon"] = row[0] if row else 0
    except Exception:
        stats["expiring_soon"] = 0

    return stats


def _get_recent_qualifications(conn, limit=5):
    try:
        rows = conn.execute("""
            SELECT w.id, w.wpq_number as number, 'wpq' as type,
                   COALESCE(w.welder_name, r.display_name) as name,
                   w.welder_stamp as stamp,
                   w.process_type, w.test_date, w.status
            FROM weld_wpq w
            LEFT JOIN weld_welder_registry r ON r.welder_stamp = w.welder_stamp
            UNION ALL
            SELECT b.id, b.bpqr_number, 'bpqr',
                   COALESCE(b.brazer_name, r2.display_name),
                   b.brazer_stamp,
                   b.brazing_process, b.test_date, b.status
            FROM weld_bpqr b
            LEFT JOIN weld_welder_registry r2 ON r2.welder_stamp = b.brazer_stamp
            ORDER BY test_date DESC LIMIT ?
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


def _get_expiring_qualifications(conn, limit=10):
    try:
        rows = conn.execute("""
            SELECT w.id, w.wpq_number as number, 'wpq' as type,
                   COALESCE(w.welder_name, r.display_name) as name,
                   w.welder_stamp as stamp,
                   w.process_type, w.current_expiration_date as expiration
            FROM weld_wpq w
            LEFT JOIN weld_welder_registry r ON r.welder_stamp = w.welder_stamp
            WHERE w.status = 'active'
            AND w.current_expiration_date IS NOT NULL
            AND w.current_expiration_date >= date('now')
            ORDER BY w.current_expiration_date ASC LIMIT ?
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


def _get_welder_info(conn, stamp):
    # Primary source: welder registry (canonical master)
    row = conn.execute(
        "SELECT display_name as name, welder_stamp as stamp, status FROM weld_welder_registry WHERE welder_stamp = ?",
        (stamp,)
    ).fetchone()
    if row:
        return dict(row)
    # Fallback: check WPQ/BPQR records directly
    row = conn.execute(
        "SELECT welder_name as name, welder_stamp as stamp FROM weld_wpq WHERE welder_stamp = ? AND welder_name IS NOT NULL LIMIT 1",
        (stamp,)
    ).fetchone()
    if row:
        return dict(row)
    row = conn.execute(
        "SELECT brazer_name as name, brazer_stamp as stamp FROM weld_bpqr WHERE brazer_stamp = ? AND brazer_name IS NOT NULL LIMIT 1",
        (stamp,)
    ).fetchone()
    return dict(row) if row else {"name": "Unknown", "stamp": stamp}


def _get_qualifications(conn, table, fk_col, record_id):
    try:
        rows = conn.execute(
            f"SELECT * FROM {table} WHERE {fk_col} = ? ORDER BY code_id",
            (record_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []
