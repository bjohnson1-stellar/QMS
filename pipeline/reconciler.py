"""Equipment reconciliation engine.

Scans extraction data across all disciplines for a project and populates
the unified equipment registry (equipment_instances, equipment_appearances,
equipment_systems, equipment_relationships).

Part of v0.4 Equipment-Centric Platform.
"""

import json
import re
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from qms.core import get_db, get_logger
from qms.pipeline.equipment import (
    add_appearance,
    add_relationship,
    create_equipment_instance,
    create_system,
    assign_to_system,
)

logger = get_logger("qms.pipeline.reconciler")


# Expected disciplines per equipment category (for negative space detection)
EXPECTED_DISCIPLINES = {
    "Condensing Unit": ["Refrigeration", "Electrical", "Structural"],
    "Refrigeration AHU": ["Refrigeration", "Electrical", "Controls"],
    "Air Handling Unit": ["Mechanical", "Electrical", "Structural", "Controls"],
    "Pump": ["Mechanical", "Electrical"],
    "VFD/Pump": ["Mechanical", "Electrical"],
    "Boiler": ["Mechanical", "Electrical", "Plumbing", "Structural"],
    "Chiller": ["Mechanical", "Electrical", "Structural"],
    "Exhaust Fan": ["Mechanical", "Electrical"],
    "HVLS Fan": ["Mechanical", "Electrical"],
    "Rooftop Unit": ["Mechanical", "Electrical", "Structural"],
    "Transformer": ["Electrical"],
    "Switchboard": ["Electrical"],
    "Distribution Panel": ["Electrical"],
    "Power Panel": ["Electrical"],
    "Motor Control Center": ["Electrical"],
    "Lighting Panel": ["Electrical"],
    "Panelboard": ["Electrical"],
    "Automatic Transfer Switch": ["Electrical"],
    "Generator": ["Electrical", "Mechanical", "Structural"],
    "Water Heater": ["Plumbing", "Electrical"],
    "Water Cooler": ["Plumbing", "Electrical"],
    "Floor Drain": ["Plumbing"],
    "Hub Drain": ["Plumbing"],
    "Floor Cleanout": ["Plumbing"],
    "Sink": ["Plumbing"],
    "Water Closet": ["Plumbing"],
    "Urinal": ["Plumbing"],
    "Mop Basin": ["Plumbing"],
    "Shower": ["Plumbing"],
    "Floor Sink": ["Plumbing"],
    "Air Compressor": ["Mechanical", "Electrical"],
    "Air Dryer": ["Mechanical", "Electrical"],
    "Unit Heater": ["Mechanical", "Electrical"],
    "Trench Heater": ["Mechanical", "Electrical"],
    "Air Curtain": ["Mechanical", "Electrical"],
    "Energy Recovery": ["Mechanical", "Electrical"],
    "Computer Room AC": ["Mechanical", "Electrical"],
    "VAV Box": ["Mechanical", "Electrical"],
    "Fan Powered Box": ["Mechanical", "Electrical"],
    "Backflow Preventer": ["Plumbing"],
    "Storage Tank": ["Mechanical", "Plumbing", "Structural"],
}


@dataclass
class ReconcileResult:
    """Result of a project reconciliation run."""
    instances: int = 0
    appearances: int = 0
    systems: int = 0
    relationships: int = 0
    types: int = 0
    duration_ms: int = 0
    errors: List[str] = field(default_factory=list)


def _extract_all_equipment_tags(conn, project_id: int) -> Dict[str, List[Dict]]:
    """Scan all extraction tables and collect equipment by tag.

    Returns: {tag: [{discipline, sheet_id, drawing_number, description,
                     equipment_type, source_table, source_id, attrs}]}
    """
    tag_map: Dict[str, List[Dict]] = {}

    # 1. Main equipment table (from extractor.py store_extraction)
    rows = conn.execute(
        """SELECT e.id, e.sheet_id, e.tag, e.description, e.equipment_type, e.confidence,
                  s.discipline, s.drawing_number
           FROM equipment e
           JOIN sheets s ON e.sheet_id = s.id
           WHERE s.project_id = ?""",
        (project_id,),
    ).fetchall()

    for row in rows:
        r = dict(row)
        tag = r.get("tag")
        if not tag:
            continue
        tag_map.setdefault(tag, []).append({
            "discipline": r.get("discipline", "Unknown"),
            "sheet_id": r.get("sheet_id"),
            "drawing_number": r.get("drawing_number", ""),
            "description": r.get("description", ""),
            "equipment_type": r.get("equipment_type", ""),
            "source_table": "equipment",
            "source_id": r.get("id"),
            "confidence": r.get("confidence", 1.0),
            "attrs": {},
        })

    # 2. Electrical panels (if table exists)
    _scan_table(conn, project_id, tag_map, "electrical_panels",
                discipline_override="Electrical")

    # 3. Electrical transformers
    _scan_table(conn, project_id, tag_map, "electrical_transformers",
                discipline_override="Electrical")

    # 4. Electrical switchgear
    _scan_table(conn, project_id, tag_map, "electrical_switchgear",
                discipline_override="Electrical")

    # 5. Electrical motors
    _scan_table(conn, project_id, tag_map, "electrical_motors",
                discipline_override="Electrical")

    # 6. Electrical disconnects
    _scan_table(conn, project_id, tag_map, "electrical_disconnects",
                discipline_override="Electrical")

    # 7. Mechanical equipment
    _scan_table(conn, project_id, tag_map, "mechanical_equipment",
                discipline_override="Mechanical")

    # 8. Utility equipment
    _scan_table(conn, project_id, tag_map, "utility_equipment",
                discipline_override="Utility")

    # 9. Refrigeration equipment
    _scan_table(conn, project_id, tag_map, "refrigeration_equipment",
                discipline_override="Refrigeration")

    # 10. Fire protection equipment
    _scan_table(conn, project_id, tag_map, "fire_protection_equipment",
                discipline_override="Fire Protection")

    # 11. Instruments (as equipment appearances)
    rows = conn.execute(
        """SELECT i.id, i.sheet_id, i.tag, i.instrument_type, i.service,
                  i.loop_number, i.confidence, s.discipline, s.drawing_number
           FROM instruments i
           JOIN sheets s ON i.sheet_id = s.id
           WHERE s.project_id = ?""",
        (project_id,),
    ).fetchall()

    for row in rows:
        r = dict(row)
        tag = r.get("tag")
        if not tag:
            continue
        tag_map.setdefault(tag, []).append({
            "discipline": r.get("discipline", "Unknown"),
            "sheet_id": r.get("sheet_id"),
            "drawing_number": r.get("drawing_number", ""),
            "description": r.get("instrument_type") or "",
            "equipment_type": "Instrument",
            "source_table": "instruments",
            "source_id": r.get("id"),
            "confidence": r.get("confidence", 1.0),
            "attrs": {"service": r.get("service"), "loop_number": r.get("loop_number")},
        })

    return tag_map


def _scan_table(
    conn, project_id: int, tag_map: Dict, table_name: str,
    discipline_override: str = None,
):
    """Scan a discipline-specific extraction table for equipment tags."""
    # Check if table exists
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone()
    if not exists:
        return

    # Get column names to find tag-like columns
    cols = [c[1] for c in conn.execute(f"PRAGMA table_info({table_name})").fetchall()]

    tag_col = "tag" if "tag" in cols else "name" if "name" in cols else None
    if not tag_col:
        return

    desc_col = "description" if "description" in cols else None
    type_col = "equipment_type" if "equipment_type" in cols else "type" if "type" in cols else None

    has_sheet = "sheet_id" in cols

    if has_sheet:
        desc_expr = f"t.{desc_col} as description" if desc_col else "'' as description"
        type_expr = f"t.{type_col} as equipment_type" if type_col else "'' as equipment_type"
        sql = f"""SELECT t.id, t.sheet_id, t.{tag_col} as tag,
                         {desc_expr}, {type_expr},
                         s.discipline, s.drawing_number
                  FROM {table_name} t
                  JOIN sheets s ON t.sheet_id = s.id
                  WHERE s.project_id = ?"""
    else:
        # Table without sheet_id — skip or handle differently
        return

    try:
        rows = conn.execute(sql, (project_id,)).fetchall()
    except Exception as e:
        logger.debug("Could not scan %s: %s", table_name, e)
        return

    for row in rows:
        r = dict(row)
        tag = r.get("tag")
        if not tag:
            continue
        disc = discipline_override or r.get("discipline", "Unknown")
        tag_map.setdefault(tag, []).append({
            "discipline": disc,
            "sheet_id": r.get("sheet_id"),
            "drawing_number": r.get("drawing_number", ""),
            "description": r.get("description", ""),
            "equipment_type": r.get("equipment_type", ""),
            "source_table": table_name,
            "source_id": r.get("id"),
            "confidence": 1.0,
            "attrs": {},
        })


def _infer_type_name(tag: str, entries: List[Dict]) -> Tuple[str, str]:
    """Infer equipment type name and category from tag and extraction data.

    Returns (type_name, category).
    """
    # Check if any entry has an equipment_type
    for e in entries:
        if e.get("equipment_type") and e["equipment_type"] != "Instrument":
            return e["equipment_type"], e["equipment_type"]

    # Infer from tag prefix
    tag_upper = tag.upper()
    if tag_upper.startswith("RCU"):
        return "Condensing Unit", "Condensing Unit"
    if tag_upper.startswith("RAHU"):
        return "Refrigeration AHU", "Refrigeration AHU"
    if tag_upper.startswith("AHU"):
        return "Air Handling Unit", "Air Handling Unit"
    if tag_upper.startswith("EF-") or tag_upper.startswith("WEF"):
        return "Exhaust Fan", "Exhaust Fan"
    if tag_upper.startswith("HVLS"):
        return "HVLS Fan", "HVLS Fan"
    if tag_upper.startswith("RTU"):
        return "Rooftop Unit", "Rooftop Unit"
    if tag_upper.startswith("VAV"):
        return "VAV Box", "VAV Box"
    if tag_upper.startswith("FPB"):
        return "Fan Powered Box", "Fan Powered Box"
    if tag_upper.startswith("ERV"):
        return "Energy Recovery", "Energy Recovery"
    if tag_upper.startswith("CRAC") or tag_upper.startswith("ACCU"):
        return "Computer Room AC", "Computer Room AC"
    if re.match(r"\dH(MSB|H|L|MCC)", tag_upper):
        if "MSB" in tag_upper:
            return "Switchboard", "Switchboard"
        if "MCC" in tag_upper:
            return "Motor Control Center", "Motor Control Center"
        if "L" in tag_upper.split("H")[-1][:1]:
            return "Lighting Panel", "Lighting Panel"
        return "Distribution Panel", "Distribution Panel"
    if re.match(r"\dHP", tag_upper):
        return "Power Panel", "Power Panel"
    if re.match(r"\dTG", tag_upper):
        return "Transformer", "Transformer"
    if re.match(r"\dLG", tag_upper):
        return "Panelboard", "Panelboard"
    if re.match(r"\dTUTIL", tag_upper):
        return "Transformer", "Transformer"
    if re.match(r"\d(SH)?ATS", tag_upper):
        return "Automatic Transfer Switch", "Automatic Transfer Switch"
    if tag_upper.startswith("GEN"):
        return "Generator", "Generator"
    if tag_upper.startswith("P-"):
        return "Pump", "Pump"
    if tag_upper.startswith("B-"):
        return "Boiler", "Boiler"
    if tag_upper.startswith("CH-"):
        return "Chiller", "Chiller"
    if tag_upper.startswith("AC-"):
        return "Air Compressor", "Air Compressor"
    if tag_upper.startswith("AD"):
        return "Air Dryer", "Air Dryer"
    if tag_upper.startswith("GWH") or tag_upper.startswith("EWH"):
        return "Water Heater", "Water Heater"
    if tag_upper.startswith("TH-"):
        return "Trench Heater", "Trench Heater"
    if tag_upper.startswith("ACT"):
        return "Air Curtain", "Air Curtain"
    if tag_upper.startswith("UH-") or tag_upper.startswith("CUH"):
        return "Unit Heater", "Unit Heater"
    if tag_upper.startswith("WS-"):
        return "Water Softener", "Water Softener"
    if tag_upper.startswith("HWT"):
        return "Storage Tank", "Storage Tank"

    # Fallback: use first entry's equipment_type or "Unknown"
    for e in entries:
        if e.get("equipment_type"):
            return e["equipment_type"], e["equipment_type"]
    return "Unknown", "Unknown"


def _best_description(entries: List[Dict]) -> str:
    """Pick the most detailed description from all appearances."""
    best = ""
    for e in entries:
        desc = e.get("description", "")
        if desc and len(desc) > len(best):
            best = desc
    return best


def _primary_discipline(entries: List[Dict]) -> str:
    """Determine primary discipline for an equipment tag."""
    disciplines = set(e["discipline"] for e in entries)
    # Priority order for primary discipline
    for d in ["Refrigeration", "Mechanical", "Plumbing", "Electrical",
              "Controls", "Utility", "Structural"]:
        if d in disciplines:
            return d
    return entries[0]["discipline"] if entries else "Unknown"


def _build_systems(conn, project_id: int, tag_map: Dict) -> Dict[str, int]:
    """Create equipment systems and return {system_tag: system_id}."""
    system_ids = {}

    # Refrigeration systems: group RCU-N with RAHU units
    rcu_tags = sorted(t for t in tag_map if t.upper().startswith("RCU-"))
    for rcu_tag in rcu_tags:
        num = re.search(r"(\d+)", rcu_tag)
        if not num:
            continue
        sys_tag = f"RS-{num.group(1)}"
        if sys_tag not in system_ids:
            sid = create_system(
                project_id, sys_tag,
                f"Refrigeration System {num.group(1)}",
                "Refrigeration", "Refrigeration",
                description=f"RCU-{num.group(1)} and associated RAHUs",
                cx_required=True,
            )
            system_ids[sys_tag] = sid

    # Electrical services: group by prefix (1xxx=Svc1, 2xxx=Svc2, 3xxx=Svc3)
    for svc_num in ["1", "2", "3"]:
        svc_tags = [t for t in tag_map if t.startswith(svc_num) and
                    re.match(rf"{svc_num}[HLTGS]", t)]
        if svc_tags:
            sys_tag = f"ELEC-SVC-{svc_num}"
            sid = create_system(
                project_id, sys_tag,
                f"Electrical Service {svc_num}",
                "Electrical", "Electrical",
                description=f"Service {svc_num} distribution",
            )
            system_ids[sys_tag] = sid

    # HVAC systems: group AHU with associated VAV/FPB
    ahu_tags = sorted(t for t in tag_map if t.upper().startswith("AHU-"))
    for ahu_tag in ahu_tags:
        num = re.search(r"(\d+)", ahu_tag)
        if not num:
            continue
        sys_tag = f"HVAC-AHU-{num.group(1)}"
        sid = create_system(
            project_id, sys_tag,
            f"HVAC System AHU-{num.group(1)}",
            "HVAC", "Mechanical",
            description=f"AHU-{num.group(1)} and associated terminal units",
        )
        system_ids[sys_tag] = sid

    return system_ids


def _assign_systems(conn, project_id: int, tag_map: Dict, system_ids: Dict):
    """Assign equipment instances to their systems."""
    for tag in tag_map:
        tag_upper = tag.upper()
        instance = conn.execute(
            "SELECT id FROM equipment_instances WHERE project_id = ? AND tag = ?",
            (project_id, tag),
        ).fetchone()
        if not instance:
            continue

        instance_id = instance["id"]

        # Refrigeration: RCU and RAHU
        if tag_upper.startswith("RCU-"):
            num = re.search(r"(\d+)", tag)
            if num:
                sys_tag = f"RS-{num.group(1)}"
                if sys_tag in system_ids:
                    assign_to_system(instance_id, system_ids[sys_tag])

        elif tag_upper.startswith("RAHU-"):
            # RAHU assignment is complex — for now, skip auto-assign
            pass

        # Electrical: by prefix
        elif re.match(r"[123][HLTGS]", tag_upper):
            svc_num = tag[0]
            sys_tag = f"ELEC-SVC-{svc_num}"
            if sys_tag in system_ids:
                assign_to_system(instance_id, system_ids[sys_tag])

        # HVAC: VAV/FPB assigned to their AHU system
        elif tag_upper.startswith("VAV-") or tag_upper.startswith("FPB-"):
            # Extract AHU number from tag (VAV-2-1 → AHU-2, FPB-4-3 → AHU-4)
            parts = tag.split("-")
            if len(parts) >= 2:
                ahu_num = parts[1]
                sys_tag = f"HVAC-AHU-{ahu_num}"
                if sys_tag in system_ids:
                    assign_to_system(instance_id, system_ids[sys_tag])


def _build_relationships(conn, project_id: int, tag_map: Dict):
    """Build equipment relationships from extraction data."""
    # Electrical panel → equipment feed relationships
    # Parse descriptions that mention "fed from" patterns
    for tag, entries in tag_map.items():
        for entry in entries:
            desc = (entry.get("description") or "").lower()
            # Look for "fed from XXXX" pattern
            fed_match = re.search(r"fed from (\w+)", desc)
            if fed_match:
                source_tag = fed_match.group(1).upper()
                if source_tag in tag_map or any(
                    t.upper() == source_tag for t in tag_map
                ):
                    add_relationship(
                        project_id, source_tag, tag,
                        "feeds", entry["discipline"],
                        entry.get("drawing_number"),
                    )

    # Refrigeration: RCU serves RAHU (from P&ID data)
    rcu_tags = [t for t in tag_map if t.upper().startswith("RCU-")]
    rahu_tags = [t for t in tag_map if t.upper().startswith("RAHU-")]

    # Simple mapping: RCU-1 serves RAHU-1,2,3 (groups of ~3 per RCU)
    # This is approximate — real mapping comes from P&ID piping connections
    for rcu_tag in rcu_tags:
        rcu_num = re.search(r"(\d+)", rcu_tag)
        if not rcu_num:
            continue
        n = int(rcu_num.group(1))
        # Each RCU serves approximately 2-3 RAHUs
        for rahu_tag in rahu_tags:
            rahu_num = re.search(r"(\d+)", rahu_tag)
            if not rahu_num:
                continue
            rn = int(rahu_num.group(1))
            # Map based on P&ID groupings we extracted:
            # RCU-1/2/3 → RAHU-1..7 (R7002), RCU-4/5/6 → RAHU-8..15 (R7003), etc.
            if n <= 3 and rn <= 7:
                add_relationship(project_id, rcu_tag, rahu_tag, "serves",
                                 "Refrigeration")
            elif 4 <= n <= 6 and 8 <= rn <= 15:
                add_relationship(project_id, rcu_tag, rahu_tag, "serves",
                                 "Refrigeration")
            elif 7 <= n <= 9 and 16 <= rn <= 23:
                add_relationship(project_id, rcu_tag, rahu_tag, "serves",
                                 "Refrigeration")
            elif 10 <= n <= 12 and 21 <= rn <= 29:
                add_relationship(project_id, rcu_tag, rahu_tag, "serves",
                                 "Refrigeration")
            elif n == 13 and 30 <= rn <= 31:
                add_relationship(project_id, rcu_tag, rahu_tag, "serves",
                                 "Refrigeration")


def reconcile_project(project_id: int, dry_run: bool = False) -> ReconcileResult:
    """Reconcile all extraction data into the equipment registry.

    Args:
        project_id: Project to reconcile.
        dry_run: If True, scan and report but don't write to database.

    Returns:
        ReconcileResult with counts and timing.
    """
    start = time.time()
    result = ReconcileResult()

    with get_db(readonly=True) as conn:
        # Verify project exists
        project = conn.execute(
            "SELECT id, name FROM projects WHERE id = ?", (project_id,),
        ).fetchone()
        if not project:
            result.errors.append(f"Project {project_id} not found")
            return result

        logger.info("Reconciling project: %s (id=%d)", project["name"], project_id)

        # Step 1: Extract all equipment tags across disciplines
        tag_map = _extract_all_equipment_tags(conn, project_id)
        logger.info("Found %d unique equipment tags across all disciplines", len(tag_map))

        if dry_run:
            result.instances = len(tag_map)
            result.duration_ms = int((time.time() - start) * 1000)
            return result

    # Step 2: Create/update equipment type records
    type_cache: Dict[str, int] = {}  # category → type_id

    with get_db() as conn:
        for tag, entries in tag_map.items():
            type_name, category = _infer_type_name(tag, entries)
            if category not in type_cache:
                existing = conn.execute(
                    "SELECT id FROM equipment_types WHERE name = ?",
                    (type_name,),
                ).fetchone()
                if existing:
                    type_cache[category] = existing["id"]
                else:
                    expected = EXPECTED_DISCIPLINES.get(category, [])
                    cursor = conn.execute(
                        """INSERT INTO equipment_types (name, expected_disciplines)
                           VALUES (?, ?)""",
                        (type_name, json.dumps(expected)),
                    )
                    type_cache[category] = cursor.lastrowid
                    result.types += 1
        conn.commit()

    # Step 3: Create equipment instances
    for tag, entries in tag_map.items():
        type_name, category = _infer_type_name(tag, entries)
        type_id = type_cache.get(category)
        description = _best_description(entries)
        primary_disc = _primary_discipline(entries)

        instance_id = create_equipment_instance(
            project_id, tag,
            type_id=type_id,
            discipline_primary=primary_disc,
        )
        result.instances += 1

        # Step 4: Create appearances
        seen = set()
        for entry in entries:
            key = (entry["discipline"], entry["sheet_id"])
            if key in seen:
                continue
            seen.add(key)
            add_appearance(
                instance_id,
                entry["discipline"],
                entry["sheet_id"],
                entry.get("drawing_number", ""),
                attributes_on_sheet=entry.get("attrs"),
                source_table=entry.get("source_table"),
                source_id=entry.get("source_id"),
            )
            result.appearances += 1

    # Step 5: Build systems
    with get_db(readonly=True) as conn:
        system_ids = _build_systems(conn, project_id, tag_map)
        result.systems = len(system_ids)

    # Step 6: Assign equipment to systems
    with get_db() as conn:
        _assign_systems(conn, project_id, tag_map, system_ids)

    # Step 7: Build relationships
    _build_relationships(None, project_id, tag_map)

    with get_db(readonly=True) as conn:
        result.relationships = conn.execute(
            "SELECT COUNT(*) as cnt FROM equipment_relationships WHERE project_id = ?",
            (project_id,),
        ).fetchone()["cnt"]

    result.duration_ms = int((time.time() - start) * 1000)

    logger.info(
        "Reconciliation complete: %d instances, %d appearances, %d systems, "
        "%d relationships, %d types (%dms)",
        result.instances, result.appearances, result.systems,
        result.relationships, result.types, result.duration_ms,
    )

    return result
