"""Equipment registry CRUD and query functions.

Part of v0.4 Equipment-Centric Platform.
"""

import json
from typing import Any, Dict, List, Optional

from qms.core import get_db, get_logger

logger = get_logger("qms.pipeline.equipment")

# Valid lifecycle stages in order
LIFECYCLE_STAGES = [
    "design", "submitted", "approved", "procured", "received",
    "installed", "connected", "startup", "tested", "punch",
    "commissioned", "turned_over",
]


# ---------------------------------------------------------------------------
# Equipment Instances
# ---------------------------------------------------------------------------

def get_equipment_instance(project_id: int, tag: str) -> Optional[Dict]:
    """Get a single equipment instance by project and tag."""
    with get_db(readonly=True) as conn:
        row = conn.execute(
            "SELECT * FROM equipment_instances WHERE project_id = ? AND tag = ?",
            (project_id, tag),
        ).fetchone()
        return dict(row) if row else None


def list_equipment(project_id: int, **filters) -> List[Dict]:
    """List equipment instances with optional filters.

    Filters: discipline_primary, system_id, lifecycle_stage, type_id
    """
    sql = "SELECT * FROM equipment_instances WHERE project_id = ?"
    params: list = [project_id]

    for col in ("discipline_primary", "system_id", "lifecycle_stage", "type_id"):
        val = filters.get(col)
        if val is not None:
            sql += f" AND {col} = ?"
            params.append(val)

    sql += " ORDER BY tag"
    with get_db(readonly=True) as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def create_equipment_instance(
    project_id: int,
    tag: str,
    type_id: Optional[int] = None,
    **attrs,
) -> int:
    """Create or update an equipment instance. Returns instance ID."""
    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM equipment_instances WHERE project_id = ? AND tag = ?",
            (project_id, tag),
        ).fetchone()

        columns = {
            "type_id": type_id,
            "variant_id": attrs.get("variant_id"),
            "serial_number": attrs.get("serial_number"),
            "system_id": attrs.get("system_id"),
            "discipline_primary": attrs.get("discipline_primary"),
            "location_area": attrs.get("location_area"),
            "location_room": attrs.get("location_room"),
            "hp": attrs.get("hp"),
            "voltage": attrs.get("voltage"),
            "amperage": attrs.get("amperage"),
            "weight_lbs": attrs.get("weight_lbs"),
            "pipe_size": attrs.get("pipe_size"),
            "attributes": json.dumps(attrs.get("attributes")) if attrs.get("attributes") else None,
            "lifecycle_stage": attrs.get("lifecycle_stage", "design"),
        }

        if existing:
            set_clause = ", ".join(f"{k} = ?" for k, v in columns.items() if v is not None)
            values = [v for v in columns.values() if v is not None]
            if set_clause:
                values.append(existing["id"])
                conn.execute(
                    f"UPDATE equipment_instances SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    values,
                )
            conn.commit()
            return existing["id"]
        else:
            columns["project_id"] = project_id
            columns["tag"] = tag
            cols = [k for k, v in columns.items() if v is not None]
            vals = [v for v in columns.values() if v is not None]
            placeholders = ", ".join("?" * len(cols))
            col_names = ", ".join(cols)
            cursor = conn.execute(
                f"INSERT INTO equipment_instances ({col_names}) VALUES ({placeholders})",
                vals,
            )
            conn.commit()
            return cursor.lastrowid


def update_equipment_instance(instance_id: int, **attrs) -> bool:
    """Update attributes on an equipment instance."""
    allowed = {
        "type_id", "variant_id", "serial_number", "system_id",
        "discipline_primary", "location_area", "location_room",
        "hp", "voltage", "amperage", "weight_lbs", "pipe_size",
        "attributes", "lifecycle_stage",
    }
    updates = {k: v for k, v in attrs.items() if k in allowed and v is not None}
    if not updates:
        return False

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [instance_id]

    with get_db() as conn:
        conn.execute(
            f"UPDATE equipment_instances SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            values,
        )
        conn.commit()
    return True


# ---------------------------------------------------------------------------
# Appearances
# ---------------------------------------------------------------------------

def get_equipment_appearances(instance_id: int) -> List[Dict]:
    """Get all cross-discipline appearances for an equipment instance."""
    with get_db(readonly=True) as conn:
        rows = conn.execute(
            "SELECT * FROM equipment_appearances WHERE instance_id = ? ORDER BY discipline",
            (instance_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def add_appearance(
    instance_id: int, discipline: str, sheet_id: int,
    drawing_number: str, attributes_on_sheet: Optional[Dict] = None,
    source_table: Optional[str] = None, source_id: Optional[int] = None,
) -> int:
    """Add a discipline appearance for an equipment instance."""
    with get_db() as conn:
        cursor = conn.execute(
            """INSERT OR IGNORE INTO equipment_appearances
               (instance_id, discipline, sheet_id, drawing_number,
                attributes_on_sheet, source_table, source_id, extracted_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (
                instance_id, discipline, sheet_id, drawing_number,
                json.dumps(attributes_on_sheet) if attributes_on_sheet else None,
                source_table, source_id,
            ),
        )
        conn.commit()
        return cursor.lastrowid


# ---------------------------------------------------------------------------
# Relationships
# ---------------------------------------------------------------------------

def get_equipment_relationships(project_id: int, tag: str) -> List[Dict]:
    """Get all relationships where tag is source or target."""
    with get_db(readonly=True) as conn:
        rows = conn.execute(
            """SELECT * FROM equipment_relationships
               WHERE project_id = ? AND (source_tag = ? OR target_tag = ?)
               ORDER BY relationship_type""",
            (project_id, tag, tag),
        ).fetchall()
        return [dict(r) for r in rows]


def add_relationship(
    project_id: int, source_tag: str, target_tag: str,
    relationship_type: str, discipline: str = None,
    drawing_number: str = None, attributes: Dict = None,
) -> int:
    """Add an equipment relationship."""
    with get_db() as conn:
        cursor = conn.execute(
            """INSERT OR IGNORE INTO equipment_relationships
               (project_id, source_tag, target_tag, relationship_type,
                discipline, drawing_number, attributes)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                project_id, source_tag, target_tag, relationship_type,
                discipline, drawing_number,
                json.dumps(attributes) if attributes else None,
            ),
        )
        conn.commit()
        return cursor.lastrowid


# ---------------------------------------------------------------------------
# Systems
# ---------------------------------------------------------------------------

def create_system(
    project_id: int, system_tag: str, system_name: str,
    category: str, discipline: str, description: str = None,
    cx_required: bool = False, parent_system_id: int = None,
) -> int:
    """Create or get an equipment system grouping."""
    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM equipment_systems WHERE project_id = ? AND system_tag = ?",
            (project_id, system_tag),
        ).fetchone()
        if existing:
            return existing["id"]

        cursor = conn.execute(
            """INSERT INTO equipment_systems
               (project_id, system_tag, system_name, system_category,
                discipline, description, cx_required, parent_system_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (project_id, system_tag, system_name, category,
             discipline, description, int(cx_required), parent_system_id),
        )
        conn.commit()
        return cursor.lastrowid


def assign_to_system(instance_id: int, system_id: int) -> bool:
    """Assign an equipment instance to a system."""
    with get_db() as conn:
        conn.execute(
            "UPDATE equipment_instances SET system_id = ? WHERE id = ?",
            (system_id, instance_id),
        )
        conn.commit()
    return True


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

def advance_lifecycle(
    instance_id: int, new_stage: str,
    changed_by: int = None, evidence_document_id: int = None,
    notes: str = None,
) -> bool:
    """Advance equipment to a new lifecycle stage with audit trail."""
    if new_stage not in LIFECYCLE_STAGES:
        raise ValueError(f"Invalid stage: {new_stage}. Valid: {LIFECYCLE_STAGES}")

    with get_db() as conn:
        row = conn.execute(
            "SELECT lifecycle_stage FROM equipment_instances WHERE id = ?",
            (instance_id,),
        ).fetchone()
        if not row:
            return False

        old_stage = row["lifecycle_stage"]

        conn.execute(
            """UPDATE equipment_instances
               SET lifecycle_stage = ?, stage_updated_at = CURRENT_TIMESTAMP,
                   updated_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (new_stage, instance_id),
        )
        conn.execute(
            """INSERT INTO equipment_stage_history
               (instance_id, from_stage, to_stage, changed_by,
                evidence_document_id, notes)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (instance_id, old_stage, new_stage, changed_by,
             evidence_document_id, notes),
        )
        conn.commit()
    return True


# ---------------------------------------------------------------------------
# Summary / Stats
# ---------------------------------------------------------------------------

def get_equipment_stats(project_id: int) -> Dict[str, Any]:
    """Get equipment registry statistics for a project."""
    with get_db(readonly=True) as conn:
        instances = conn.execute(
            "SELECT COUNT(*) as cnt FROM equipment_instances WHERE project_id = ?",
            (project_id,),
        ).fetchone()["cnt"]

        appearances = conn.execute(
            """SELECT COUNT(*) as cnt FROM equipment_appearances ea
               JOIN equipment_instances ei ON ea.instance_id = ei.id
               WHERE ei.project_id = ?""",
            (project_id,),
        ).fetchone()["cnt"]

        systems = conn.execute(
            "SELECT COUNT(*) as cnt FROM equipment_systems WHERE project_id = ?",
            (project_id,),
        ).fetchone()["cnt"]

        relationships = conn.execute(
            "SELECT COUNT(*) as cnt FROM equipment_relationships WHERE project_id = ?",
            (project_id,),
        ).fetchone()["cnt"]

        types = conn.execute(
            """SELECT COUNT(DISTINCT type_id) as cnt FROM equipment_instances
               WHERE project_id = ? AND type_id IS NOT NULL""",
            (project_id,),
        ).fetchone()["cnt"]

        by_stage = conn.execute(
            """SELECT lifecycle_stage, COUNT(*) as cnt FROM equipment_instances
               WHERE project_id = ? GROUP BY lifecycle_stage ORDER BY cnt DESC""",
            (project_id,),
        ).fetchall()

        by_discipline = conn.execute(
            """SELECT discipline_primary, COUNT(*) as cnt FROM equipment_instances
               WHERE project_id = ? GROUP BY discipline_primary ORDER BY cnt DESC""",
            (project_id,),
        ).fetchall()

        return {
            "instances": instances,
            "appearances": appearances,
            "systems": systems,
            "relationships": relationships,
            "types": types,
            "by_stage": {r["lifecycle_stage"]: r["cnt"] for r in by_stage},
            "by_discipline": {r["discipline_primary"]: r["cnt"] for r in by_discipline if r["discipline_primary"]},
        }
