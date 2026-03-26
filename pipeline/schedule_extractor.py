"""Schedule extractor — data management for schedule-first extraction.

Provides query and storage functions for schedule extraction. The actual
AI extraction happens through Claude Code agents (sis-extractor or
schedule-specific agents) using the user's subscription — NOT through
direct Anthropic API calls.

Workflow:
  1. get_pending_schedules(project_id) → sheets needing extraction
  2. Claude Code agent reads PDF, extracts structured data
  3. store_schedule_data(sheet_id, project_id, entries) → writes to staging table
  4. get_schedule_summary(project_id) → extraction progress

Part of v0.4 Equipment-Centric Platform (Phase 25).
"""

import json
from typing import Any, Dict, List, Optional

from qms.core import get_db, get_logger

logger = get_logger("qms.pipeline.schedule_extractor")


def get_pending_schedules(project_id: int) -> List[Dict]:
    """Get schedule sheets that haven't been extracted yet.

    Returns list of sheet dicts with id, drawing_number, discipline,
    file_name, file_path — ordered by discipline priority.
    """
    from qms.pipeline.extraction_order import get_schedule_sheets

    all_schedules = get_schedule_sheets(project_id)

    with get_db(readonly=True) as conn:
        # Find which sheets already have schedule_extractions data
        extracted_ids = set()
        for row in conn.execute(
            "SELECT DISTINCT sheet_id FROM schedule_extractions WHERE project_id = ?",
            (project_id,),
        ).fetchall():
            extracted_ids.add(row["sheet_id"])

    pending = [s for s in all_schedules if s["id"] not in extracted_ids]

    logger.info(
        "Schedule extraction status: %d total, %d extracted, %d pending",
        len(all_schedules), len(extracted_ids), len(pending),
    )
    return pending


def get_schedule_sheet_info(sheet_id: int) -> Optional[Dict]:
    """Get full info for a single schedule sheet including file path."""
    with get_db(readonly=True) as conn:
        row = conn.execute(
            """SELECT id, drawing_number, discipline, file_name, file_path,
                      drawing_type, drawing_category
               FROM sheets WHERE id = ?""",
            (sheet_id,),
        ).fetchone()
        return dict(row) if row else None


def store_schedule_data(
    sheet_id: int,
    project_id: int,
    entries: List[Dict],
    model_used: str = "claude-code",
) -> Dict[str, int]:
    """Store extracted schedule data in the staging table.

    Args:
        sheet_id: Source sheet ID
        project_id: Project ID
        entries: List of equipment dicts from Claude Code agent extraction.
            Each dict should have: tag (required), plus optional:
            description, equipment_type, hp, kva, voltage, amperage,
            phase_count, circuit, panel_source, manufacturer, model_number,
            weight_lbs, cfm
        model_used: Model identifier for tracking

    Returns:
        {"stored": N, "skipped": N, "errors": N}
    """
    stats = {"stored": 0, "skipped": 0, "errors": 0}

    if not entries:
        return stats

    with get_db() as conn:
        for entry in entries:
            tag = entry.get("tag")
            if not tag or not isinstance(tag, str) or not tag.strip():
                stats["skipped"] += 1
                continue

            # Collect overflow attributes
            known_cols = {
                "tag", "description", "equipment_type", "hp", "kva",
                "voltage", "amperage", "phase_count", "circuit",
                "panel_source", "manufacturer", "model_number",
                "weight_lbs", "cfm",
            }
            additional = {
                k: v for k, v in entry.items()
                if k not in known_cols and v is not None
            }

            try:
                conn.execute(
                    """INSERT OR REPLACE INTO schedule_extractions
                       (sheet_id, project_id, tag, description, equipment_type,
                        hp, kva, voltage, amperage, phase_count, circuit,
                        panel_source, manufacturer, model_number, weight_lbs,
                        cfm, additional_attributes, confidence, extraction_model)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        sheet_id, project_id,
                        tag.strip(),
                        entry.get("description"),
                        entry.get("equipment_type"),
                        entry.get("hp"),
                        entry.get("kva"),
                        entry.get("voltage"),
                        entry.get("amperage"),
                        entry.get("phase_count"),
                        entry.get("circuit"),
                        entry.get("panel_source"),
                        entry.get("manufacturer"),
                        entry.get("model_number"),
                        entry.get("weight_lbs"),
                        entry.get("cfm"),
                        json.dumps(additional) if additional else None,
                        0.9,
                        model_used,
                    ),
                )
                stats["stored"] += 1
            except Exception as e:
                logger.warning("Failed to store tag %s: %s", tag, e)
                stats["errors"] += 1

        conn.commit()

    logger.info(
        "Stored schedule data for sheet %d: %d stored, %d skipped, %d errors",
        sheet_id, stats["stored"], stats["skipped"], stats["errors"],
    )
    return stats


def clear_schedule_data(project_id: int, sheet_id: int = None) -> int:
    """Clear schedule extraction data. If sheet_id given, clear only that sheet."""
    with get_db() as conn:
        if sheet_id:
            cursor = conn.execute(
                "DELETE FROM schedule_extractions WHERE project_id = ? AND sheet_id = ?",
                (project_id, sheet_id),
            )
        else:
            cursor = conn.execute(
                "DELETE FROM schedule_extractions WHERE project_id = ?",
                (project_id,),
            )
        conn.commit()
        return cursor.rowcount


def get_schedule_summary(project_id: int) -> Dict[str, Any]:
    """Get schedule extraction progress summary."""
    from qms.pipeline.extraction_order import get_schedule_sheets

    all_schedules = get_schedule_sheets(project_id)

    with get_db(readonly=True) as conn:
        total_entries = conn.execute(
            "SELECT COUNT(*) FROM schedule_extractions WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0]

        extracted_sheets = conn.execute(
            "SELECT COUNT(DISTINCT sheet_id) FROM schedule_extractions WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0]

        by_discipline = conn.execute(
            """SELECT s.discipline, COUNT(DISTINCT se.sheet_id) as sheets,
                      COUNT(se.id) as entries
               FROM schedule_extractions se
               JOIN sheets s ON se.sheet_id = s.id
               WHERE se.project_id = ?
               GROUP BY s.discipline ORDER BY s.discipline""",
            (project_id,),
        ).fetchall()

    return {
        "total_schedule_sheets": len(all_schedules),
        "extracted_sheets": extracted_sheets,
        "pending_sheets": len(all_schedules) - extracted_sheets,
        "total_equipment_entries": total_entries,
        "by_discipline": [dict(r) for r in by_discipline],
    }


def get_extracted_equipment_list(project_id: int) -> List[Dict]:
    """Get all extracted schedule equipment for a project (for context building)."""
    with get_db(readonly=True) as conn:
        rows = conn.execute(
            """SELECT DISTINCT tag, description, equipment_type, hp, voltage,
                      amperage, panel_source, cfm, manufacturer,
                      s.discipline as source_discipline, s.drawing_number
               FROM schedule_extractions se
               JOIN sheets s ON se.sheet_id = s.id
               WHERE se.project_id = ?
               ORDER BY tag""",
            (project_id,),
        ).fetchall()
    return [dict(r) for r in rows]
