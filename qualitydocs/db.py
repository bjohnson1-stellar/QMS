"""
QMS Quality Documents DB — M3 Programs & M4 SOPs

CRUD functions for quality programs, SOP categories, SOPs,
intake pipeline, and revision history.
"""

import json
import math
from datetime import datetime

from qms.core import get_db


# ---------------------------------------------------------------------------
# M3 Programs
# ---------------------------------------------------------------------------

def list_programs(status=None):
    """List all quality programs, optionally filtered by status."""
    with get_db(readonly=True) as conn:
        sql = "SELECT * FROM qm_programs"
        params = []
        if status:
            sql += " WHERE status = ?"
            params.append(status)
        sql += " ORDER BY program_id"
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_program(program_id: str):
    """Get a program by its program_id (e.g. 'SIS-3.01')."""
    with get_db(readonly=True) as conn:
        row = conn.execute(
            "SELECT * FROM qm_programs WHERE program_id = ?", (program_id,)
        ).fetchone()
        return dict(row) if row else None


def get_program_by_id(id: int):
    """Get a program by its integer primary key."""
    with get_db(readonly=True) as conn:
        row = conn.execute(
            "SELECT * FROM qm_programs WHERE id = ?", (id,)
        ).fetchone()
        return dict(row) if row else None


def create_program(program_id, title, description=None, primary_codes=None,
                   qualification_requirements=None, status="draft"):
    """Create a new quality program. Returns the new id."""
    codes_json = json.dumps(primary_codes) if primary_codes else None
    with get_db() as conn:
        cur = conn.execute(
            """INSERT INTO qm_programs
               (program_id, title, description, primary_codes,
                qualification_requirements, status)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (program_id, title, description, codes_json,
             qualification_requirements, status),
        )
        conn.commit()
        return cur.lastrowid


def update_program(id, **kwargs):
    """Update program fields. Returns True if a row was updated."""
    if not kwargs:
        return False
    if "primary_codes" in kwargs and isinstance(kwargs["primary_codes"], list):
        kwargs["primary_codes"] = json.dumps(kwargs["primary_codes"])
    kwargs["updated_at"] = datetime.utcnow().isoformat()
    sets = ", ".join(f"{k} = ?" for k in kwargs)
    vals = list(kwargs.values()) + [id]
    with get_db() as conn:
        cur = conn.execute(f"UPDATE qm_programs SET {sets} WHERE id = ?", vals)
        conn.commit()
        return cur.rowcount > 0


def get_program_sops(program_id: str):
    """Get all SOPs linked to a program (by program_id string)."""
    with get_db(readonly=True) as conn:
        rows = conn.execute(
            """SELECT s.* FROM qm_sops s
               JOIN qm_program_sops ps ON ps.sop_id = s.id
               JOIN qm_programs p ON p.id = ps.program_id
               WHERE p.program_id = ?
               ORDER BY s.document_id""",
            (program_id,),
        ).fetchall()
        return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# M4 Categories
# ---------------------------------------------------------------------------

def list_categories(module_number=4):
    """List categories with SOP counts."""
    with get_db(readonly=True) as conn:
        rows = conn.execute(
            """SELECT c.*,
                      (SELECT COUNT(*) FROM qm_sops WHERE category_id = c.id) AS sop_count
               FROM qm_categories c
               WHERE c.module_number = ?
               ORDER BY c.display_order, c.category_code""",
            (module_number,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_category(category_code: str):
    """Get a category by its code (e.g. '4.01')."""
    with get_db(readonly=True) as conn:
        row = conn.execute(
            """SELECT c.*,
                      (SELECT COUNT(*) FROM qm_sops WHERE category_id = c.id) AS sop_count
               FROM qm_categories c
               WHERE c.category_code = ?""",
            (category_code,),
        ).fetchone()
        return dict(row) if row else None


def create_category(category_code, name, description=None,
                    parent_program_id=None, display_order=None,
                    module_number=4):
    """Create a new SOP category. Returns the new id."""
    with get_db() as conn:
        cur = conn.execute(
            """INSERT INTO qm_categories
               (category_code, module_number, name, description,
                parent_program_id, display_order)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (category_code, module_number, name, description,
             parent_program_id, display_order),
        )
        conn.commit()
        return cur.lastrowid


# ---------------------------------------------------------------------------
# M3 Program Seed Data
# ---------------------------------------------------------------------------

_M3_PROGRAMS = [
    (
        "SIS-3.01",
        "Hot Work & Welding",
        "Quality program governing hot work permits, welding procedures, welder qualifications, and weld inspection per ASME and AWS codes.",
        ["ASME IX", "AWS D1.1", "ASME B31.1", "ASME B31.5"],
        "Welders must hold current qualification per ASME IX or AWS D1.1. Hot work permits required for all open-flame operations.",
    ),
    (
        "SIS-3.02",
        "Mechanical & Piping",
        "Quality program for mechanical piping, HVAC ductwork, and plumbing installation including refrigeration systems and glycol loops.",
        ["ASME B31.1", "ASME B31.5", "SMACNA", "IMC", "UPC"],
        "Journeyman-level mechanical installer certification. Brazing qualifications for refrigerant piping per ASME IX.",
    ),
    (
        "SIS-3.03",
        "Rigging & Equipment",
        "Quality program for equipment rigging, setting, alignment, grouting, and foundation work for heavy mechanical equipment.",
        ["ASME BTH-1", "OSHA 1926"],
        "Certified rigger or signal person credentials. Equipment-specific training for cranes and hoisting devices.",
    ),
    (
        "SIS-3.04",
        "Testing & Commissioning",
        "Quality program for system testing, startup, commissioning, and performance verification of mechanical and refrigeration systems.",
        ["ASHRAE", "NETA", "ASME PCC-1"],
        "Commissioning authority certification or equivalent experience. System-specific startup training required.",
    ),
    (
        "SIS-3.05",
        "Electrical & Controls",
        "Quality program for electrical installation, controls wiring, instrumentation calibration, and PLC programming.",
        ["NEC", "NFPA 70E", "UL 508A"],
        "Licensed electrician or apprentice under licensed supervision. Arc flash training per NFPA 70E.",
    ),
]


def seed_programs():
    """Seed the 5 M3 discipline programs if not already present.

    Also fixes category parent_program_id linkage after programs exist.
    """
    with get_db() as conn:
        for prog_id, title, desc, codes, qual_req in _M3_PROGRAMS:
            existing = conn.execute(
                "SELECT id FROM qm_programs WHERE program_id = ?", (prog_id,)
            ).fetchone()
            if existing:
                continue
            conn.execute(
                """INSERT INTO qm_programs
                   (program_id, title, description, primary_codes,
                    qualification_requirements, status)
                   VALUES (?, ?, ?, ?, ?, 'published')""",
                (prog_id, title, desc, json.dumps(codes), qual_req),
            )
        # Fix category linkage — update parent_program_id for categories
        # that reference M3 programs by program_id string
        for code, _name, _desc, parent_prog, _order in _M4_CATEGORIES:
            if not parent_prog:
                continue
            prog = conn.execute(
                "SELECT id FROM qm_programs WHERE program_id = ?",
                (parent_prog,),
            ).fetchone()
            if prog:
                conn.execute(
                    "UPDATE qm_categories SET parent_program_id = ? WHERE category_code = ?",
                    (prog["id"], code),
                )
        conn.commit()


_M4_CATEGORIES = [
    ("4.01", "Project Management & Meetings", "Kickoff meetings, coordination, scheduling, daily reports, extra work documentation.", None, 1),
    ("4.02", "Material Handling, Receiving & Storage", "Receiving inspection, pipe/valve handling, equipment storage, winter protection.", None, 2),
    ("4.03", "Rigging & Equipment Setting", "Equipment rigging by type — evaporators, compressors, chillers, boilers, pumps, AHUs.", "SIS-3.03", 3),
    ("4.04", "Piping & Refrigeration Installation", "Refrigerant piping, glycol systems, valves, control groups, system evacuation.", "SIS-3.02", 4),
    ("4.05", "Ductwork & HVAC", "Ductwork rigging, air diffuser handling, sanitary ductwork fabrication/installation.", "SIS-3.02", 5),
    ("4.06", "Grouting & Foundations", "Equipment grouting methods — pourable, dry pack, with/without moving parts.", "SIS-3.03", 6),
    ("4.07", "Roof & Site Protection", "Roof protection, winter protection, roof curb installation.", None, 7),
    ("4.08", "Hot Work & Tie-Ins", "Working around pressure vessels, tie-in planning.", "SIS-3.01", 8),
    ("4.09", "Welding & Qualification", "Welder qualification testing, weld inspection, WPS procedures, dissimilar metals.", "SIS-3.01", 9),
    ("4.10", "Testing & Inspection", "System testing, charging, flushing, Victaulic testing.", "SIS-3.04", 10),
    ("4.11", "Electrical", "Panel points, structural framing, compressor motor power connections.", "SIS-3.05", 11),
    ("4.12", "Administrative & Expenses", "Administrative procedures, expense documentation, travel.", None, 12),
    ("4.13", "Commissioning & Startup", "Commissioning procedures, system startup, performance verification.", "SIS-3.04", 13),
    ("4.14", "Controls & Instrumentation", "Controls installation, instrumentation calibration, PLC programming.", "SIS-3.05", 14),
    ("4.15", "Plumbing", "Plumbing installation, domestic water, sanitary, storm drainage.", "SIS-3.02", 15),
]


def seed_categories():
    """Seed the 15 M4 categories if not already present.

    Links parent_program_id to existing programs if they exist.
    """
    with get_db() as conn:
        for code, name, desc, parent_prog, order in _M4_CATEGORIES:
            existing = conn.execute(
                "SELECT id FROM qm_categories WHERE category_code = ?", (code,)
            ).fetchone()
            if existing:
                continue
            parent_id = None
            if parent_prog:
                prog = conn.execute(
                    "SELECT id FROM qm_programs WHERE program_id = ?",
                    (parent_prog,),
                ).fetchone()
                if prog:
                    parent_id = prog["id"]
            conn.execute(
                """INSERT INTO qm_categories
                   (category_code, module_number, name, description,
                    parent_program_id, display_order)
                   VALUES (?, 4, ?, ?, ?, ?)""",
                (code, name, desc, parent_id, order),
            )
        conn.commit()


# ---------------------------------------------------------------------------
# M4 SOPs
# ---------------------------------------------------------------------------

def list_sops(category_id=None, scope=None, status=None,
              page=1, per_page=50):
    """List SOPs with optional filters and pagination.

    Returns {items, total, page, per_page, pages}.
    """
    where, params = [], []
    if category_id is not None:
        where.append("s.category_id = ?")
        params.append(category_id)
    if status:
        where.append("s.status = ?")
        params.append(status)
    if scope:
        where.append("s.scope_tags LIKE ?")
        params.append(f'%"{scope}"%')

    where_sql = (" WHERE " + " AND ".join(where)) if where else ""

    with get_db(readonly=True) as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM qm_sops s{where_sql}", params
        ).fetchone()[0]

        per_page = min(per_page, 200) if per_page > 0 else 50
        pages = max(1, math.ceil(total / per_page)) if total else 1
        offset = (page - 1) * per_page

        rows = conn.execute(
            f"""SELECT s.*, c.category_code, c.name AS category_name
                FROM qm_sops s
                JOIN qm_categories c ON c.id = s.category_id
                {where_sql}
                ORDER BY s.document_id
                LIMIT ? OFFSET ?""",
            params + [per_page, offset],
        ).fetchall()

        return {
            "items": [dict(r) for r in rows],
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": pages,
        }


def get_sop(document_id: str):
    """Get a full SOP by document_id, including category and program links."""
    with get_db(readonly=True) as conn:
        row = conn.execute(
            """SELECT s.*, c.category_code, c.name AS category_name
               FROM qm_sops s
               JOIN qm_categories c ON c.id = s.category_id
               WHERE s.document_id = ?""",
            (document_id,),
        ).fetchone()
        if not row:
            return None
        sop = dict(row)
        # Parse scope_tags JSON
        try:
            sop["scope_tags"] = json.loads(sop["scope_tags"] or "[]")
        except (json.JSONDecodeError, TypeError):
            sop["scope_tags"] = []
        # Attach linked programs
        programs = conn.execute(
            """SELECT p.program_id, p.title
               FROM qm_programs p
               JOIN qm_program_sops ps ON ps.program_id = p.id
               WHERE ps.sop_id = ?""",
            (sop["id"],),
        ).fetchall()
        sop["programs"] = [dict(p) for p in programs]
        return sop


def get_sop_by_id(id: int):
    """Get a SOP by its integer primary key."""
    with get_db(readonly=True) as conn:
        row = conn.execute(
            "SELECT * FROM qm_sops WHERE id = ?", (id,)
        ).fetchone()
        return dict(row) if row else None


def create_sop(document_id, title, category_id, scope_tags=None,
               file_path=None, file_hash=None, content_text=None,
               summary=None):
    """Create a new SOP in draft status. Returns the new id."""
    tags_json = json.dumps(scope_tags or [])
    with get_db() as conn:
        cur = conn.execute(
            """INSERT INTO qm_sops
               (document_id, title, category_id, status, scope_tags,
                file_path, file_hash, content_text, summary)
               VALUES (?, ?, ?, 'draft', ?, ?, ?, ?, ?)""",
            (document_id, title, category_id, tags_json,
             file_path, file_hash, content_text, summary),
        )
        conn.commit()
        sop_id = cur.lastrowid
    # Record creation history (separate transaction)
    _add_sop_history_internal(sop_id, "created", notes="SOP created in draft status")
    return sop_id


def update_sop(id, **kwargs):
    """Update SOP fields. Returns True if a row was updated."""
    if not kwargs:
        return False
    if "scope_tags" in kwargs and isinstance(kwargs["scope_tags"], list):
        kwargs["scope_tags"] = json.dumps(kwargs["scope_tags"])
    kwargs["updated_at"] = datetime.utcnow().isoformat()
    sets = ", ".join(f"{k} = ?" for k in kwargs)
    vals = list(kwargs.values()) + [id]
    with get_db() as conn:
        cur = conn.execute(f"UPDATE qm_sops SET {sets} WHERE id = ?", vals)
        conn.commit()
        return cur.rowcount > 0


def approve_sop(id, approved_by):
    """Approve a SOP — sets status, approved_by, approved_at."""
    sop = get_sop_by_id(id)
    if not sop:
        return False
    prev_status = sop["status"]
    now = datetime.utcnow().isoformat()
    with get_db() as conn:
        cur = conn.execute(
            """UPDATE qm_sops
               SET status = 'approved', approved_by = ?, approved_at = ?,
                   updated_at = ?
               WHERE id = ?""",
            (approved_by, now, now, id),
        )
        conn.commit()
        if cur.rowcount > 0:
            _add_sop_history_internal(
                id, "approved", actor=approved_by,
                previous_status=prev_status, new_status="approved",
            )
            return True
    return False


def publish_sop(id):
    """Publish a SOP — sets status to 'published'."""
    sop = get_sop_by_id(id)
    if not sop:
        return False
    prev_status = sop["status"]
    now = datetime.utcnow().isoformat()
    with get_db() as conn:
        cur = conn.execute(
            "UPDATE qm_sops SET status = 'published', updated_at = ? WHERE id = ?",
            (now, id),
        )
        conn.commit()
        if cur.rowcount > 0:
            _add_sop_history_internal(
                id, "published",
                previous_status=prev_status, new_status="published",
            )
            return True
    return False


def link_sop_to_program(sop_id, program_id):
    """Link a SOP to a program (by integer IDs). Returns True on success."""
    with get_db() as conn:
        try:
            conn.execute(
                "INSERT OR IGNORE INTO qm_program_sops (program_id, sop_id) VALUES (?, ?)",
                (program_id, sop_id),
            )
            conn.commit()
            return True
        except Exception:
            return False


def search_sops(query, limit=50):
    """Search SOPs by title and content_text using LIKE."""
    pattern = f"%{query}%"
    with get_db(readonly=True) as conn:
        rows = conn.execute(
            """SELECT s.*, c.category_code, c.name AS category_name
               FROM qm_sops s
               JOIN qm_categories c ON c.id = s.category_id
               WHERE s.title LIKE ? OR s.content_text LIKE ?
               ORDER BY s.document_id
               LIMIT ?""",
            (pattern, pattern, limit),
        ).fetchall()
        return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# SOP History
# ---------------------------------------------------------------------------

def _add_sop_history_internal(sop_id, action, actor=None, notes=None,
                              previous_status=None, new_status=None):
    """Internal helper — adds history in its own transaction."""
    with get_db() as conn:
        cur = conn.execute(
            """INSERT INTO qm_sop_history
               (sop_id, action, actor, notes, previous_status, new_status)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (sop_id, action, actor, notes, previous_status, new_status),
        )
        conn.commit()
        return cur.lastrowid


def add_sop_history(sop_id, action, actor=None, notes=None,
                    previous_status=None, new_status=None):
    """Add a history entry for a SOP. Returns the new id."""
    return _add_sop_history_internal(
        sop_id, action, actor, notes, previous_status, new_status
    )


def get_sop_history(sop_id):
    """Get revision/approval history for a SOP, newest first."""
    with get_db(readonly=True) as conn:
        rows = conn.execute(
            "SELECT * FROM qm_sop_history WHERE sop_id = ? ORDER BY created_at DESC",
            (sop_id,),
        ).fetchall()
        return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# SOP Intake
# ---------------------------------------------------------------------------

def create_intake(file_name, file_path=None, file_hash=None):
    """Create a new intake record in pending status. Returns the new id."""
    with get_db() as conn:
        cur = conn.execute(
            """INSERT INTO qm_sop_intake (file_name, file_path, file_hash)
               VALUES (?, ?, ?)""",
            (file_name, file_path, file_hash),
        )
        conn.commit()
        return cur.lastrowid


def get_intake_by_hash(file_hash):
    """Check for existing intake with the same file hash (dedup)."""
    if not file_hash:
        return None
    with get_db(readonly=True) as conn:
        row = conn.execute(
            "SELECT * FROM qm_sop_intake WHERE file_hash = ?", (file_hash,)
        ).fetchone()
        return dict(row) if row else None


def update_intake(id, **kwargs):
    """Update intake fields. Returns True if a row was updated."""
    if not kwargs:
        return False
    if "suggested_scope_tags" in kwargs and isinstance(kwargs["suggested_scope_tags"], list):
        kwargs["suggested_scope_tags"] = json.dumps(kwargs["suggested_scope_tags"])
    if "suggested_program_ids" in kwargs and isinstance(kwargs["suggested_program_ids"], list):
        kwargs["suggested_program_ids"] = json.dumps(kwargs["suggested_program_ids"])
    if "ai_classification" in kwargs and isinstance(kwargs["ai_classification"], dict):
        kwargs["ai_classification"] = json.dumps(kwargs["ai_classification"])
    if "user_overrides" in kwargs and isinstance(kwargs["user_overrides"], dict):
        kwargs["user_overrides"] = json.dumps(kwargs["user_overrides"])
    sets = ", ".join(f"{k} = ?" for k in kwargs)
    vals = list(kwargs.values()) + [id]
    with get_db() as conn:
        cur = conn.execute(f"UPDATE qm_sop_intake SET {sets} WHERE id = ?", vals)
        conn.commit()
        return cur.rowcount > 0


def get_intake(id):
    """Get an intake record by ID."""
    with get_db(readonly=True) as conn:
        row = conn.execute(
            "SELECT * FROM qm_sop_intake WHERE id = ?", (id,)
        ).fetchone()
        return dict(row) if row else None


def list_intakes(status=None):
    """List intake records, optionally filtered by status."""
    with get_db(readonly=True) as conn:
        sql = "SELECT * FROM qm_sop_intake"
        params = []
        if status:
            sql += " WHERE status = ?"
            params.append(status)
        sql += " ORDER BY created_at DESC"
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def list_intakes_paginated(status=None, page=1, per_page=25):
    """List intake records with pagination. Returns {items, total, page, per_page, pages}."""
    where, params = [], []
    if status:
        where.append("i.status = ?")
        params.append(status)
    where_sql = (" WHERE " + " AND ".join(where)) if where else ""

    with get_db(readonly=True) as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM qm_sop_intake i{where_sql}", params
        ).fetchone()[0]

        per_page = min(per_page, 200) if per_page > 0 else 25
        pages = max(1, math.ceil(total / per_page)) if total else 1
        offset = (page - 1) * per_page

        rows = conn.execute(
            f"""SELECT i.*, c.category_code, c.name AS suggested_category_name
                FROM qm_sop_intake i
                LEFT JOIN qm_categories c ON c.id = i.suggested_category_id
                {where_sql}
                ORDER BY i.created_at DESC
                LIMIT ? OFFSET ?""",
            params + [per_page, offset],
        ).fetchall()

        return {
            "items": [dict(r) for r in rows],
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": pages,
        }


def get_intake_detail(id):
    """Get an intake record with parsed JSON fields and joined names."""
    with get_db(readonly=True) as conn:
        row = conn.execute(
            """SELECT i.*, c.category_code, c.name AS suggested_category_name
               FROM qm_sop_intake i
               LEFT JOIN qm_categories c ON c.id = i.suggested_category_id
               WHERE i.id = ?""",
            (id,),
        ).fetchone()
        if not row:
            return None
        intake = dict(row)
        # Parse JSON fields
        for field in ("ai_classification", "user_overrides"):
            try:
                intake[field] = json.loads(intake[field]) if intake[field] else None
            except (json.JSONDecodeError, TypeError):
                pass
        for field in ("suggested_scope_tags", "suggested_program_ids"):
            try:
                intake[field] = json.loads(intake[field]) if intake[field] else []
            except (json.JSONDecodeError, TypeError):
                intake[field] = []
        # Resolve program names
        if intake.get("suggested_program_ids"):
            placeholders = ",".join("?" * len(intake["suggested_program_ids"]))
            progs = conn.execute(
                f"SELECT id, program_id, title FROM qm_programs WHERE id IN ({placeholders})",
                intake["suggested_program_ids"],
            ).fetchall()
            intake["suggested_programs"] = [dict(p) for p in progs]
        else:
            intake["suggested_programs"] = []
        return intake


def next_document_id(category_code):
    """Generate the next SOP document_id for a category (e.g., SOP-004-001)."""
    # Convert category code like "4.03" to zero-padded "004"
    parts = category_code.split(".")
    cat_num = parts[1] if len(parts) > 1 else parts[0]
    cat_prefix = f"SOP-{cat_num.zfill(3)}"

    with get_db(readonly=True) as conn:
        row = conn.execute(
            "SELECT document_id FROM qm_sops WHERE document_id LIKE ? ORDER BY document_id DESC LIMIT 1",
            (f"{cat_prefix}-%",),
        ).fetchone()
        if row:
            # Extract the sequence number and increment
            last_seq = int(row["document_id"].split("-")[-1])
            return f"{cat_prefix}-{str(last_seq + 1).zfill(3)}"
        return f"{cat_prefix}-001"


def create_code_references(sop_id, references):
    """Bulk insert code references for a SOP."""
    if not references:
        return
    with get_db() as conn:
        for ref in references:
            conn.execute(
                """INSERT INTO qm_sop_code_references
                   (sop_id, code, organization, code_section, original_text, detection_method)
                   VALUES (?, ?, ?, ?, ?, 'ai_detected')""",
                (sop_id, ref.get("code", ""), ref.get("organization"),
                 ref.get("section"), ref.get("original_text")),
            )
        conn.commit()


def approve_intake(id, overrides=None):
    """Approve an intake record — creates a draft SOP from AI suggestions + user overrides.

    Returns the new SOP id, or None on failure.
    """
    intake = get_intake(id)
    if not intake or intake["status"] != "classified":
        return None

    overrides = overrides or {}

    # Parse AI classification
    ai_class = {}
    try:
        ai_class = json.loads(intake["ai_classification"]) if intake["ai_classification"] else {}
    except (json.JSONDecodeError, TypeError):
        pass

    # Merge: user overrides win over AI suggestions
    category_id = overrides.get("category_id") or intake.get("suggested_category_id")
    scope_tags = overrides.get("scope_tags") or (
        json.loads(intake["suggested_scope_tags"]) if intake.get("suggested_scope_tags") else []
    )
    program_ids = overrides.get("program_ids") or (
        json.loads(intake["suggested_program_ids"]) if intake.get("suggested_program_ids") else []
    )
    document_id = overrides.get("document_id") or intake.get("suggested_document_id")
    title = overrides.get("title") or ai_class.get("title") or intake["file_name"].replace(".pdf", "").replace("_", " ").title()
    summary = overrides.get("summary") or ai_class.get("summary", "")
    content_text = ai_class.get("content_text", "")

    if not category_id or not document_id:
        return None

    # Create SOP
    sop_id = create_sop(
        document_id=document_id,
        title=title,
        category_id=category_id,
        scope_tags=scope_tags if isinstance(scope_tags, list) else [],
        file_path=intake.get("file_path"),
        file_hash=intake.get("file_hash"),
        content_text=content_text,
        summary=summary,
    )

    # Create code references from AI classification
    code_refs = ai_class.get("code_references", [])
    if code_refs:
        create_code_references(sop_id, code_refs)

    # Link to programs
    for prog_id in (program_ids if isinstance(program_ids, list) else []):
        link_sop_to_program(sop_id, prog_id)

    # Update intake record
    update_intake(
        id,
        status="approved",
        final_sop_id=sop_id,
        user_overrides=overrides if overrides else None,
    )

    return sop_id
