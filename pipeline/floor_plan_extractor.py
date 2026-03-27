"""Floor plan extractor — data management and prompt building for floor plan extraction.

Provides storage, query, and prompt-building functions for floor plan/P&ID
extraction. The actual AI extraction happens through Claude Code agents
using vision — NOT through direct Anthropic API calls.

Workflow:
  1. get_pending_floor_plans(project_id) → non-schedule sheets needing extraction
  2. build_floor_plan_prompt(project_id, sheet_id, discipline) → context-aware prompt
  3. Claude Code agent reads PDF page, extracts structured data
  4. store_floor_plan_data(sheet_id, project_id, entries) → writes to staging table
  5. get_floor_plan_summary(project_id) → extraction progress

Part of v0.4 Equipment-Centric Platform (Phase 27).
"""

import json
from typing import Any, Dict, List, Optional

from qms.core import get_db, get_logger

logger = get_logger("qms.pipeline.floor_plan_extractor")


# ---------------------------------------------------------------------------
# Discipline-specific prompt supplements
# ---------------------------------------------------------------------------

_DISCIPLINE_NOTES = {
    "Refrigeration": (
        "This is a refrigeration drawing. Look for: RCU (condensing units), "
        "RAHU (refrigeration air handling units), valves (CV, SV, PRV), "
        "piping connections, instrument tags (TI, PI, FI, LI), compressors, "
        "evaporators, condensers, and refrigerant piping routing."
    ),
    "Electrical": (
        "This is an electrical drawing. Look for: panel tags (1HMSB, 1HH041, etc.), "
        "disconnect tags, motor connections, conduit routing, transformer tags, "
        "switchgear, MCC tags, and equipment fed-from labels."
    ),
    "Mechanical": (
        "This is a mechanical drawing. Look for: AHU (air handling units), "
        "VAV boxes, FPB (fan powered boxes), exhaust fans (EF), HVLS fans, "
        "RTU (rooftop units), ERV (energy recovery), ductwork routing, "
        "and equipment tags in title blocks or callouts."
    ),
    "Utility": (
        "This is a utility/piping drawing. Look for: boilers (B-), pumps (P-), "
        "storage tanks (HWT), water heaters (GWH, EWH), water softeners (WS-), "
        "air compressors (AC-), air dryers (AD), expansion tanks, piping routing, "
        "and equipment tags."
    ),
    "Plumbing": (
        "This is a plumbing drawing. Look for: fixture tags (WC water closet, "
        "LAV lavatory, FD floor drain, CO cleanout, UR urinal, FSD floor sink, "
        "MB mop basin, SH shower, EWC electric water cooler), backflow preventers, "
        "pipe routing, and fixture schedules."
    ),
}


# ---------------------------------------------------------------------------
# Storage Functions
# ---------------------------------------------------------------------------

def store_floor_plan_data(
    sheet_id: int,
    project_id: int,
    entries: List[Dict],
    model_used: str = "claude-code",
    confidence: float = None,
) -> Dict[str, int]:
    """Store extracted floor plan data in the staging table.

    Args:
        sheet_id: Source sheet ID
        project_id: Project ID
        entries: List of equipment dicts from Claude Code agent extraction.
            Each dict should have: tag (required), plus optional:
            location_area, location_room, grid_reference, appearance_type,
            description, equipment_type, page_number
        model_used: Extraction method
        confidence: Override confidence score. If None, defaults to 0.85.

    Returns:
        {"stored": N, "skipped": N, "errors": N}
    """
    stats = {"stored": 0, "skipped": 0, "errors": 0}
    if not entries:
        return stats

    conf = confidence if confidence is not None else 0.85

    with get_db() as conn:
        for entry in entries:
            tag = entry.get("tag")
            if tag is not None and not isinstance(tag, str):
                tag = str(tag)
            if not tag or not isinstance(tag, str) or not tag.strip():
                stats["skipped"] += 1
                continue

            # Collect overflow attributes
            known_cols = {
                "tag", "location_area", "location_room", "grid_reference",
                "appearance_type", "description", "equipment_type",
                "page_number", "confidence",
            }
            additional = {
                k: v for k, v in entry.items()
                if k not in known_cols and v is not None
            }

            app_type = entry.get("appearance_type", "physically_shown")
            if app_type not in ("physically_shown", "referenced", "legend"):
                app_type = "physically_shown"

            try:
                conn.execute(
                    """INSERT OR REPLACE INTO floor_plan_extractions
                       (sheet_id, project_id, tag, location_area, location_room,
                        grid_reference, appearance_type, description, equipment_type,
                        confidence, extraction_model, page_number, additional_attributes)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        sheet_id, project_id,
                        tag.strip(),
                        entry.get("location_area"),
                        entry.get("location_room"),
                        entry.get("grid_reference"),
                        app_type,
                        entry.get("description"),
                        entry.get("equipment_type"),
                        entry.get("confidence", conf),
                        model_used,
                        entry.get("page_number"),
                        json.dumps(additional) if additional else None,
                    ),
                )
                stats["stored"] += 1
            except Exception as e:
                logger.warning("Failed to store tag %s: %s", tag, e)
                stats["errors"] += 1

        conn.commit()

    logger.info(
        "Stored floor plan data for sheet %d: %d stored, %d skipped, %d errors",
        sheet_id, stats["stored"], stats["skipped"], stats["errors"],
    )
    return stats


def clear_floor_plan_data(project_id: int, sheet_id: int = None) -> int:
    """Clear floor plan extraction data. If sheet_id given, clear only that sheet."""
    with get_db() as conn:
        if sheet_id:
            cursor = conn.execute(
                "DELETE FROM floor_plan_extractions WHERE project_id = ? AND sheet_id = ?",
                (project_id, sheet_id),
            )
        else:
            cursor = conn.execute(
                "DELETE FROM floor_plan_extractions WHERE project_id = ?",
                (project_id,),
            )
        conn.commit()
        return cursor.rowcount


# ---------------------------------------------------------------------------
# Query Functions
# ---------------------------------------------------------------------------

def get_pending_floor_plans(project_id: int) -> List[Dict]:
    """Get non-schedule sheets that haven't been extracted yet.

    Returns list of sheet dicts ordered by discipline priority.
    """
    from qms.pipeline.extraction_order import get_plan_sheets

    all_plans = get_plan_sheets(project_id)

    with get_db(readonly=True) as conn:
        extracted_ids = set()
        for row in conn.execute(
            "SELECT DISTINCT sheet_id FROM floor_plan_extractions WHERE project_id = ?",
            (project_id,),
        ).fetchall():
            extracted_ids.add(row["sheet_id"])

    pending = [s for s in all_plans if s["id"] not in extracted_ids]

    logger.info(
        "Floor plan extraction status: %d total, %d extracted, %d pending",
        len(all_plans), len(extracted_ids), len(pending),
    )
    return pending


def get_floor_plan_summary(project_id: int) -> Dict[str, Any]:
    """Get floor plan extraction progress summary."""
    from qms.pipeline.extraction_order import get_plan_sheets

    all_plans = get_plan_sheets(project_id)

    with get_db(readonly=True) as conn:
        total_entries = conn.execute(
            "SELECT COUNT(*) FROM floor_plan_extractions WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0]

        extracted_sheets = conn.execute(
            "SELECT COUNT(DISTINCT sheet_id) FROM floor_plan_extractions WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0]

        by_discipline = conn.execute(
            """SELECT s.discipline, COUNT(DISTINCT fp.sheet_id) as sheets,
                      COUNT(fp.id) as entries
               FROM floor_plan_extractions fp
               JOIN sheets s ON fp.sheet_id = s.id
               WHERE fp.project_id = ?
               GROUP BY s.discipline ORDER BY s.discipline""",
            (project_id,),
        ).fetchall()

        by_appearance = conn.execute(
            """SELECT appearance_type, COUNT(*) as cnt
               FROM floor_plan_extractions WHERE project_id = ?
               GROUP BY appearance_type""",
            (project_id,),
        ).fetchall()

    return {
        "total_plan_sheets": len(all_plans),
        "extracted_sheets": extracted_sheets,
        "pending_sheets": len(all_plans) - extracted_sheets,
        "total_equipment_entries": total_entries,
        "by_discipline": [dict(r) for r in by_discipline],
        "by_appearance_type": {r["appearance_type"]: r["cnt"] for r in by_appearance},
    }


def get_extracted_floor_plan_list(project_id: int) -> List[Dict]:
    """Get all extracted floor plan equipment for a project."""
    with get_db(readonly=True) as conn:
        rows = conn.execute(
            """SELECT DISTINCT fp.tag, fp.location_area, fp.location_room,
                      fp.grid_reference, fp.appearance_type, fp.description,
                      fp.equipment_type, s.discipline, s.drawing_number
               FROM floor_plan_extractions fp
               JOIN sheets s ON fp.sheet_id = s.id
               WHERE fp.project_id = ?
               ORDER BY fp.tag""",
            (project_id,),
        ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Prompt Building
# ---------------------------------------------------------------------------

def build_floor_plan_prompt(
    project_id: int,
    sheet_id: int,
    discipline: str,
    drawing_number: str = None,
) -> str:
    """Build a context-aware vision prompt for floor plan extraction.

    Injects the schedule-built equipment checklist so the AI asks
    "which of these known tags appear here?" instead of "what do you see?"
    """
    from qms.pipeline.context_builder import get_context_for_extraction

    # Get formatted equipment checklist from context builder
    checklist = get_context_for_extraction(project_id, sheet_id)
    if not checklist:
        checklist = "No equipment checklist available."

    # Discipline-specific notes
    disc_notes = _DISCIPLINE_NOTES.get(discipline, "")

    drawing_label = drawing_number or f"sheet {sheet_id}"

    prompt = f"""You are analyzing a {discipline} drawing ({drawing_label}).

{disc_notes}

KNOWN EQUIPMENT FOR THIS PROJECT (from schedules):
{checklist}

TASK: Examine this drawing and identify which of the known equipment tags
are PHYSICALLY SHOWN on this drawing (not just referenced in notes/legends).

For each equipment tag found, return a JSON object with:
- "tag": exact tag as shown on the drawing
- "location_area": area/zone name if visible (e.g., "Dock Area", "Office", "Mechanical Room")
- "location_room": room number/name if visible (e.g., "Room 101", "MER-1")
- "grid_reference": column/row grid reference if visible (e.g., "C-4", "J.2-12")
- "appearance_type": one of:
  - "physically_shown" — equipment is drawn/depicted on this sheet
  - "referenced" — only mentioned in a note, callout, or table (not drawn)
  - "legend" — appears only in legend/key
- "description": brief description of what's shown (e.g., "condensing unit on roof", "panel in MER")
- "equipment_type": type if identifiable (e.g., "Condensing Unit", "Panel", "Floor Drain")
- "confidence": 0.0-1.0 how confident you are

CRITICAL RULES:
1. Only report equipment you can actually see depicted or labeled on this drawing.
2. Do NOT fabricate entries from the checklist. If a tag from the checklist is
   NOT visible on this drawing, do NOT include it.
3. It is MUCH better to miss equipment than to report equipment that isn't shown.
4. Also report any equipment tags you see that are NOT on the checklist — these
   may be unlisted equipment needing review. Mark them with confidence 0.7.

Return ONLY a JSON array of objects. No markdown, no explanation."""

    return prompt


def format_vision_result(
    raw_entries: List[Dict],
    project_id: int,
) -> List[Dict]:
    """Validate and normalize extraction results from Claude vision.

    - Normalizes tags (strip whitespace)
    - Cross-references against schedule data to flag unlisted equipment
    - Returns list of dicts ready for store_floor_plan_data()
    """
    if not raw_entries:
        return []

    # Get known tags from schedules
    with get_db(readonly=True) as conn:
        known_tags = set()
        for row in conn.execute(
            "SELECT DISTINCT tag FROM schedule_extractions WHERE project_id = ?",
            (project_id,),
        ).fetchall():
            known_tags.add(row["tag"].upper())

        # Also check equipment_instances
        for row in conn.execute(
            "SELECT DISTINCT tag FROM equipment_instances WHERE project_id = ?",
            (project_id,),
        ).fetchall():
            known_tags.add(row["tag"].upper())

    validated = []
    for entry in raw_entries:
        tag = entry.get("tag")
        if not tag:
            continue
        if not isinstance(tag, str):
            tag = str(tag)
        tag = tag.strip()
        if not tag:
            continue

        result = {
            "tag": tag,
            "location_area": entry.get("location_area"),
            "location_room": entry.get("location_room"),
            "grid_reference": entry.get("grid_reference"),
            "appearance_type": entry.get("appearance_type", "physically_shown"),
            "description": entry.get("description"),
            "equipment_type": entry.get("equipment_type"),
            "confidence": entry.get("confidence", 0.85),
            "page_number": entry.get("page_number"),
        }

        # Flag unlisted equipment
        if tag.upper() not in known_tags:
            result["unlisted"] = True
            if result["confidence"] > 0.7:
                result["confidence"] = 0.7  # Cap confidence for unlisted

        validated.append(result)

    return validated
