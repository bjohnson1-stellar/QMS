"""
Welding Blueprint — Flask routes for welding qualification UI.

Thin delivery layer: business logic lives in welding.qualification_rules
and welding.forms. CRUD operations go through the database directly.
"""

from flask import Blueprint, jsonify, request, render_template

from qms.core import get_db

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
        "SELECT display_name as name, welder_stamp as stamp FROM weld_welder_registry WHERE welder_stamp = ?",
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
