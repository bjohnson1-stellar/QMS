"""Context builder — creates per-sheet equipment checklists for informed extraction.

Builds focused context from schedule extraction results and the equipment
registry to inject into floor plan/P&ID extraction prompts. This transforms
extraction from open-ended discovery to targeted checklist verification.

Part of v0.4 Equipment-Centric Platform (Phase 25).
"""

from typing import Any, Dict, List, Optional

from qms.core import get_db, get_logger

logger = get_logger("qms.pipeline.context_builder")

# Max equipment to include in context (keep prompt focused)
_MAX_CONTEXT_ITEMS = 100


def build_sheet_context(project_id: int, sheet_id: int) -> Dict[str, Any]:
    """Build extraction context for a specific sheet.

    Queries schedule_extractions and equipment_instances to create
    a focused equipment checklist relevant to the sheet's discipline
    and drawing type.

    Returns:
        {
            "discipline": str,
            "drawing_number": str,
            "known_equipment": [{"tag", "type", "description", "hp", "voltage"}, ...],
            "known_abbreviations": [{"abbreviation", "full_text"}, ...],
            "equipment_count": int,
        }
    """
    context = {
        "discipline": "",
        "drawing_number": "",
        "known_equipment": [],
        "known_abbreviations": [],
        "equipment_count": 0,
    }

    with get_db(readonly=True) as conn:
        # Get sheet info
        sheet = conn.execute(
            "SELECT drawing_number, discipline, file_name FROM sheets WHERE id = ?",
            (sheet_id,),
        ).fetchone()
        if not sheet:
            return context

        context["discipline"] = sheet["discipline"]
        context["drawing_number"] = sheet["drawing_number"]
        discipline = sheet["discipline"]

        # Build equipment list from schedule_extractions (primary source)
        schedule_equip = conn.execute(
            """SELECT DISTINCT tag, description, equipment_type, hp, voltage,
                      amperage, panel_source, cfm, manufacturer
               FROM schedule_extractions
               WHERE project_id = ?
               ORDER BY tag""",
            (project_id,),
        ).fetchall()

        # Also pull from equipment_instances (for tags not in schedules)
        instance_equip = conn.execute(
            """SELECT DISTINCT ei.tag, et.name as equipment_type,
                      ei.hp, ei.voltage, ei.discipline_primary
               FROM equipment_instances ei
               LEFT JOIN equipment_types et ON ei.type_id = et.id
               WHERE ei.project_id = ? AND ei.parent_tag IS NULL""",
            (project_id,),
        ).fetchall()

        # Merge: schedule data takes priority, add instance-only tags
        seen_tags = set()
        equipment = []

        for row in schedule_equip:
            row = dict(row)
            tag = row["tag"]
            if tag in seen_tags:
                continue
            seen_tags.add(tag)
            equipment.append({
                "tag": tag,
                "type": row.get("equipment_type") or "",
                "description": row.get("description") or "",
                "hp": row.get("hp"),
                "voltage": row.get("voltage") or "",
                "amperage": row.get("amperage"),
                "panel_source": row.get("panel_source") or "",
                "cfm": row.get("cfm"),
                "source": "schedule",
            })

        for row in instance_equip:
            row = dict(row)
            tag = row["tag"]
            if tag in seen_tags:
                continue
            seen_tags.add(tag)
            equipment.append({
                "tag": tag,
                "type": row.get("equipment_type") or "",
                "description": "",
                "hp": row.get("hp"),
                "voltage": row.get("voltage") or "",
                "source": "registry",
            })

        # Filter by relevance to this sheet's discipline
        # Same discipline first, then cross-discipline equipment
        same_disc = []
        cross_disc = []
        for eq in equipment:
            # Check if this equipment's schedule came from same discipline
            disc_match = False
            if eq.get("source") == "schedule":
                # Check schedule sheet's discipline
                sched_disc = conn.execute(
                    """SELECT DISTINCT s.discipline
                       FROM schedule_extractions se
                       JOIN sheets s ON se.sheet_id = s.id
                       WHERE se.project_id = ? AND se.tag = ?""",
                    (project_id, eq["tag"]),
                ).fetchall()
                disc_match = any(
                    d["discipline"] == discipline for d in sched_disc
                )
            else:
                # Instance — check discipline_primary
                inst = conn.execute(
                    "SELECT discipline_primary FROM equipment_instances WHERE project_id = ? AND tag = ?",
                    (project_id, eq["tag"]),
                ).fetchone()
                disc_match = inst and inst["discipline_primary"] == discipline

            if disc_match:
                same_disc.append(eq)
            else:
                cross_disc.append(eq)

        # Prioritize same-discipline, then add cross-discipline up to limit
        filtered = same_disc[:_MAX_CONTEXT_ITEMS]
        remaining = _MAX_CONTEXT_ITEMS - len(filtered)
        if remaining > 0:
            filtered.extend(cross_disc[:remaining])

        context["known_equipment"] = filtered
        context["equipment_count"] = len(filtered)

        # Load abbreviations if available
        abbrevs = conn.execute(
            """SELECT abbreviation, full_text
               FROM drawing_abbreviations
               WHERE sheet_id IN (
                   SELECT id FROM sheets
                   WHERE project_id = ? AND discipline = ?
               )
               ORDER BY abbreviation""",
            (project_id, discipline),
        ).fetchall()
        context["known_abbreviations"] = [dict(a) for a in abbrevs]

    logger.info(
        "Built context for %s: %d equipment (%d same-discipline, %d cross), %d abbreviations",
        sheet["drawing_number"], len(filtered), len(same_disc),
        min(remaining, len(cross_disc)) if remaining > 0 else 0,
        len(context["known_abbreviations"]),
    )

    return context


def format_equipment_checklist(context: Dict[str, Any]) -> str:
    """Format context as a text checklist for injection into extraction prompts.

    Returns a formatted string suitable for appending to an extraction prompt.
    Returns empty string if no equipment context available.
    """
    equipment = context.get("known_equipment", [])
    if not equipment:
        return ""

    lines = []
    lines.append("=" * 60)
    lines.append("KNOWN EQUIPMENT FOR THIS PROJECT (from schedule extraction):")
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"{'Tag':<20s} {'Type':<25s} {'Description':<30s} {'HP':>6s} {'Voltage':>10s}")
    lines.append("-" * 95)

    for eq in equipment:
        hp_str = str(eq["hp"]) if eq.get("hp") else "-"
        lines.append(
            f"{eq['tag']:<20s} {eq.get('type',''):<25s} "
            f"{eq.get('description','')[:30]:<30s} {hp_str:>6s} "
            f"{eq.get('voltage',''):>10s}"
        )

    lines.append("")
    lines.append("INSTRUCTIONS:")
    lines.append("- For each tag from the list above that appears on this drawing,")
    lines.append("  report its location and any additional attributes visible.")
    lines.append("- If you find equipment NOT on this list, include it but mark")
    lines.append("  it with \"on_checklist\": false so it can be reviewed.")
    lines.append("- Set \"on_checklist\": true for equipment that matches the list above.")
    lines.append("- Do NOT fabricate equipment. Only report what is actually visible")
    lines.append("  on this drawing.")

    # Add abbreviations if available
    abbrevs = context.get("known_abbreviations", [])
    if abbrevs:
        lines.append("")
        lines.append("ABBREVIATIONS (from legend drawings):")
        for a in abbrevs[:50]:
            lines.append(f"  {a['abbreviation']}: {a['full_text']}")

    return "\n".join(lines)


def get_context_for_extraction(project_id: int, sheet_id: int) -> Optional[str]:
    """Convenience: build and format context in one call.

    Returns formatted checklist string, or None if no context available.
    """
    context = build_sheet_context(project_id, sheet_id)
    if not context["known_equipment"]:
        return None
    return format_equipment_checklist(context)
