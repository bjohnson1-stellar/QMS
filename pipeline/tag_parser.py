"""Equipment tag parser — parent-child hierarchy and normalization.

Parses compound equipment tags to identify parent equipment, component
codes, and component types. Handles both forward (RAHU-2-CV2) and
reversed (CV2-SYS-RAHU-2) tag formats.

Part of v0.4 Equipment-Centric Platform (Phase 23).
"""

import re
from typing import Any, Dict, List, Optional, Set

from qms.core import get_db, get_logger

logger = get_logger("qms.pipeline.tag_parser")

# Component code prefix → human-readable type name
COMPONENT_TYPES = {
    "CV": "Control Valve",
    "PT": "Pressure Transmitter",
    "TT": "Temperature Transmitter",
    "STR": "Strainer",
    "SV": "Solenoid Valve",
    "FV": "Flow Valve",
    "PRV": "Pressure Relief Valve",
    "FM": "Flow Meter",
}

# Regex for known component suffixes (alpha prefix + optional digits)
_COMPONENT_RE = re.compile(
    r"^(" + "|".join(sorted(COMPONENT_TYPES, key=len, reverse=True)) + r")(\d*)$"
)

# Reversed tag patterns: CV2-SYS-RAHU-2 or CV5-RAHU-20-SYS
_REVERSED_SYS_PREFIX = re.compile(
    r"^([A-Z]+\d+)-SYS-(.+)$"
)
_REVERSED_SYS_SUFFIX = re.compile(
    r"^([A-Z]+\d+)-(.+)-SYS$"
)


def _extract_component(suffix: str) -> Optional[Dict[str, str]]:
    """Try to parse a suffix as a component code.

    Returns {"code": "CV2", "prefix": "CV", "type": "Control Valve"} or None.
    """
    m = _COMPONENT_RE.match(suffix)
    if m:
        prefix = m.group(1)
        return {
            "code": suffix,
            "prefix": prefix,
            "type": COMPONENT_TYPES[prefix],
        }
    return None


def normalize_reversed_tag(tag: str) -> Optional[str]:
    """Normalize a reversed tag to forward form.

    CV2-SYS-RAHU-2  → RAHU-2-CV2
    CV5-RAHU-20-SYS  → RAHU-20-CV5

    Returns normalized forward form, or None if not a reversed tag.
    """
    # Pattern 1: SUFFIX-SYS-PARENT (e.g., CV2-SYS-RAHU-2)
    m = _REVERSED_SYS_PREFIX.match(tag)
    if m:
        suffix, parent = m.group(1), m.group(2)
        if _extract_component(suffix):
            return f"{parent}-{suffix}"

    # Pattern 2: SUFFIX-PARENT-SYS (e.g., CV5-RAHU-20-SYS)
    m = _REVERSED_SYS_SUFFIX.match(tag)
    if m:
        suffix, parent = m.group(1), m.group(2)
        if _extract_component(suffix):
            return f"{parent}-{suffix}"

    return None


def parse_tag(tag: str, existing_tags: Set[str]) -> Dict[str, Any]:
    """Parse an equipment tag to identify parent-child relationship.

    Args:
        tag: The equipment tag to parse.
        existing_tags: Set of all tags in the project (for parent lookup).

    Returns dict with:
        original: Original tag
        parent_tag: Parent equipment tag (or None if primary)
        component_code: Component suffix like "CV2" (or None)
        component_type: Human-readable type like "Control Valve" (or None)
        is_reversed: True if tag was in reversed format
        normalized: Canonical forward form of the tag
    """
    result = {
        "original": tag,
        "parent_tag": None,
        "component_code": None,
        "component_type": None,
        "is_reversed": False,
        "normalized": tag,
    }

    # Check if this is a reversed tag
    forward = normalize_reversed_tag(tag)
    if forward:
        result["is_reversed"] = True
        result["normalized"] = forward
        # Parse the forward form for parent/component
        tag_to_parse = forward
    else:
        tag_to_parse = tag

    # Try to split into parent + component suffix
    # Find the LONGEST existing parent tag that this tag starts with
    # e.g., for RAHU-20-CV2, match RAHU-20 (not RAHU-2)
    best_parent = None
    for candidate in existing_tags:
        if candidate == tag_to_parse:
            continue  # Don't match self
        if tag_to_parse.startswith(candidate + "-"):
            remainder = tag_to_parse[len(candidate) + 1:]
            comp = _extract_component(remainder)
            if comp:
                if best_parent is None or len(candidate) > len(best_parent):
                    best_parent = candidate

    if best_parent:
        remainder = tag_to_parse[len(best_parent) + 1:]
        comp = _extract_component(remainder)
        if comp:
            result["parent_tag"] = best_parent
            result["component_code"] = comp["code"]
            result["component_type"] = comp["type"]

    return result


# ---------------------------------------------------------------------------
# Backfill functions
# ---------------------------------------------------------------------------


def _column_exists(conn, table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r["name"] == column for r in rows)


def run_migration(conn=None):
    """Add parent_tag and component_type columns to equipment_instances."""
    close = False
    if conn is None:
        conn = get_db().__enter__()
        close = True

    try:
        if not _column_exists(conn, "equipment_instances", "parent_tag"):
            conn.execute(
                "ALTER TABLE equipment_instances ADD COLUMN parent_tag TEXT"
            )
            logger.info("Added parent_tag column to equipment_instances")

        if not _column_exists(conn, "equipment_instances", "component_type"):
            conn.execute(
                "ALTER TABLE equipment_instances ADD COLUMN component_type TEXT"
            )
            logger.info("Added component_type column to equipment_instances")

        conn.execute(
            """CREATE INDEX IF NOT EXISTS idx_equipment_instances_parent
               ON equipment_instances(project_id, parent_tag)"""
        )

        # Phase 24: system_type_id on equipment_systems
        if not _column_exists(conn, "equipment_systems", "system_type_id"):
            conn.execute(
                "ALTER TABLE equipment_systems ADD COLUMN system_type_id "
                "INTEGER REFERENCES equipment_system_types(id)"
            )
            logger.info("Added system_type_id column to equipment_systems")

        conn.commit()
    finally:
        if close:
            conn.close()


def backfill_hierarchy(project_id: int) -> Dict[str, int]:
    """Backfill parent_tag and component_type, then deduplicate reversed tags.

    Returns summary dict with counts.
    """
    stats = {
        "total": 0,
        "parents_set": 0,
        "types_reclassified": 0,
        "duplicates_merged": 0,
        "final_count": 0,
    }

    with get_db() as conn:
        # Ensure columns exist
        run_migration(conn)

        # 1. Load all tags for this project
        rows = conn.execute(
            "SELECT id, tag FROM equipment_instances WHERE project_id = ?",
            (project_id,),
        ).fetchall()
        all_tags = {r["tag"] for r in rows}
        tag_to_id = {r["tag"]: r["id"] for r in rows}
        stats["total"] = len(rows)

        logger.info("Backfilling hierarchy for project %d: %d equipment",
                     project_id, stats["total"])

        # 2. Parse all tags and set parent_tag + component_type
        parsed = {}
        for tag in all_tags:
            parsed[tag] = parse_tag(tag, all_tags)

        for tag, info in parsed.items():
            if info["parent_tag"]:
                conn.execute(
                    """UPDATE equipment_instances
                       SET parent_tag = ?, component_type = ?
                       WHERE project_id = ? AND tag = ?""",
                    (info["parent_tag"], info["component_type"],
                     project_id, tag),
                )
                stats["parents_set"] += 1

        conn.commit()

        # 3. Reclassify sub-component types
        # Find equipment typed wrong (e.g., "Refrigeration AHU" for a CV2)
        for tag, info in parsed.items():
            if not info["component_type"]:
                continue
            instance_id = tag_to_id.get(tag)
            if not instance_id:
                continue

            # Ensure the correct equipment_type exists
            type_name = info["component_type"]
            type_row = conn.execute(
                "SELECT id FROM equipment_types WHERE name = ?",
                (type_name,),
            ).fetchone()

            if not type_row:
                cursor = conn.execute(
                    "INSERT INTO equipment_types (name) VALUES (?)",
                    (type_name,),
                )
                type_id = cursor.lastrowid
            else:
                type_id = type_row["id"]

            # Check if current type is wrong
            current = conn.execute(
                """SELECT et.name FROM equipment_instances ei
                   LEFT JOIN equipment_types et ON ei.type_id = et.id
                   WHERE ei.id = ?""",
                (instance_id,),
            ).fetchone()

            if current and current["name"] != type_name:
                conn.execute(
                    "UPDATE equipment_instances SET type_id = ? WHERE id = ?",
                    (type_id, instance_id),
                )
                stats["types_reclassified"] += 1

        conn.commit()

        # 4. Deduplicate reversed tags
        # For each reversed tag, check if its forward form also exists
        for tag, info in parsed.items():
            if not info["is_reversed"]:
                continue
            forward_tag = info["normalized"]
            if forward_tag not in tag_to_id:
                continue  # No forward form exists — keep this one
            if forward_tag == tag:
                continue

            reversed_id = tag_to_id[tag]
            forward_id = tag_to_id[forward_tag]

            # Merge appearances: move from reversed to forward
            conn.execute(
                """UPDATE OR IGNORE equipment_appearances
                   SET instance_id = ?
                   WHERE instance_id = ?""",
                (forward_id, reversed_id),
            )
            # Delete any that conflicted on UNIQUE
            conn.execute(
                "DELETE FROM equipment_appearances WHERE instance_id = ?",
                (reversed_id,),
            )

            # Merge relationships: update tag references
            conn.execute(
                """UPDATE equipment_relationships
                   SET source_tag = ?
                   WHERE project_id = ? AND source_tag = ?""",
                (forward_tag, project_id, tag),
            )
            conn.execute(
                """UPDATE equipment_relationships
                   SET target_tag = ?
                   WHERE project_id = ? AND target_tag = ?""",
                (forward_tag, project_id, tag),
            )

            # Merge conflicts: update tag references
            conn.execute(
                """UPDATE equipment_conflicts
                   SET equipment_tag = ?
                   WHERE project_id = ? AND equipment_tag = ?""",
                (forward_tag, project_id, tag),
            )

            # Delete the reversed instance
            conn.execute(
                "DELETE FROM equipment_instances WHERE id = ?",
                (reversed_id,),
            )
            stats["duplicates_merged"] += 1

        conn.commit()

        # Final count
        stats["final_count"] = conn.execute(
            "SELECT COUNT(*) FROM equipment_instances WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0]

    logger.info(
        "Backfill complete: %d parents set, %d types reclassified, "
        "%d duplicates merged. Count: %d -> %d",
        stats["parents_set"], stats["types_reclassified"],
        stats["duplicates_merged"], stats["total"], stats["final_count"],
    )

    return stats
