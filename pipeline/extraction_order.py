"""Extraction order engine — schedule-first processing strategy.

Classifies project sheets into extraction phases (schedules, legends, plans)
and determines the optimal processing order within each phase.

Part of v0.4 Equipment-Centric Platform (Phase 25).
"""

import re
from typing import Any, Dict, List

from qms.core import get_db, get_logger

logger = get_logger("qms.pipeline.extraction_order")

# Drawing number patterns for schedule detection
_SCHEDULE_NUMBER_RE = re.compile(r"^[A-Z]\d?6\d{2,3}", re.IGNORECASE)

# Drawing number patterns for legend/notes detection
_LEGEND_NUMBER_RE = re.compile(r"^[A-Z]\d?000[12]", re.IGNORECASE)

# Discipline extraction priority
# Refrigeration first, then utility/mechanical, electrical, plumbing last
DISCIPLINE_PRIORITY = {
    "Refrigeration": 1,
    "Refrigeration-Controls": 2,
    "Utility": 3,
    "Mechanical": 4,
    "Electrical": 5,
    "Plumbing": 6,
    "Architectural": 7,
    "Civil": 8,
    "Fire-Protection": 9,
    "General": 10,
    "Structural": 11,
}

# Model assignments per phase
PHASE_MODELS = {
    "schedules": "haiku",
    "legends": "haiku",
    "plans": "sonnet",
}


def _classify_sheet(sheet: Dict) -> str:
    """Classify a sheet into an extraction phase.

    Returns: 'schedules', 'legends', or 'plans'
    """
    category = (sheet.get("drawing_category") or "").lower()
    drawing_number = sheet.get("drawing_number") or ""

    # Schedule detection
    if category == "schedule":
        return "schedules"
    if _SCHEDULE_NUMBER_RE.match(drawing_number):
        return "schedules"

    # Legend/notes detection
    if category in ("cover", "legend"):
        return "legends"
    if _LEGEND_NUMBER_RE.match(drawing_number):
        return "legends"

    # Everything else
    return "plans"


def _discipline_sort_key(sheet: Dict) -> int:
    """Sort key for discipline priority ordering."""
    disc = sheet.get("discipline") or ""
    return DISCIPLINE_PRIORITY.get(disc, 99)


def get_extraction_order(project_id: int) -> List[Dict[str, Any]]:
    """Determine extraction processing order for a project.

    Returns list of phases, each with model assignment and ordered sheets:
    [
        {"phase": "schedules", "model": "haiku", "sheets": [...]},
        {"phase": "legends", "model": "haiku", "sheets": [...]},
        {"phase": "plans", "model": "sonnet", "sheets": [...]},
    ]

    Sheets within each phase are ordered by discipline priority.
    """
    with get_db(readonly=True) as conn:
        rows = conn.execute(
            """SELECT id, drawing_number, discipline, drawing_type,
                      drawing_category, file_name, file_path, is_current
               FROM sheets
               WHERE project_id = ? AND is_current = 1
               ORDER BY discipline, drawing_number""",
            (project_id,),
        ).fetchall()

    # Classify each sheet
    phases = {"schedules": [], "legends": [], "plans": []}
    for row in rows:
        sheet = dict(row)
        phase = _classify_sheet(sheet)
        phases[phase].append(sheet)

    # Sort each phase by discipline priority
    for phase_name in phases:
        phases[phase_name].sort(key=_discipline_sort_key)

    # Build ordered result
    result = []
    for phase_name in ("schedules", "legends", "plans"):
        sheets = phases[phase_name]
        result.append({
            "phase": phase_name,
            "model": PHASE_MODELS[phase_name],
            "sheets": sheets,
            "count": len(sheets),
        })

    logger.info(
        "Extraction order for project %d: %d schedules, %d legends, %d plans",
        project_id, len(phases["schedules"]), len(phases["legends"]),
        len(phases["plans"]),
    )
    return result


def get_phase_for_sheet(sheet: Dict) -> str:
    """Return which extraction phase a single sheet belongs to."""
    return _classify_sheet(sheet)


def get_schedule_sheets(project_id: int) -> List[Dict]:
    """Convenience: return just the schedule sheets for a project."""
    order = get_extraction_order(project_id)
    return order[0]["sheets"] if order else []


def get_legend_sheets(project_id: int) -> List[Dict]:
    """Convenience: return just the legend/notes sheets for a project."""
    order = get_extraction_order(project_id)
    return order[1]["sheets"] if len(order) > 1 else []
