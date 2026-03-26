"""Equipment system builder — consolidation and auto-assignment.

Consolidates compressor circuits into logical refrigeration systems,
creates plumbing/HVAC systems, and assigns equipment based on
relationships and type patterns.

Part of v0.4 Equipment-Centric Platform (Phase 24).
"""

from typing import Any, Dict, List

from qms.core import get_db, get_logger

logger = get_logger("qms.pipeline.system_builder")


def _get_system_type_id(conn, code: str) -> int:
    """Look up system type ID by code."""
    row = conn.execute(
        "SELECT id FROM equipment_system_types WHERE code = ?", (code,),
    ).fetchone()
    return row["id"] if row else None


def _create_system(
    conn, project_id: int, system_tag: str, system_name: str,
    category: str, discipline: str, type_code: str,
    parent_system_id: int = None, description: str = None,
) -> int:
    """Create a system if it doesn't exist. Returns system ID."""
    existing = conn.execute(
        "SELECT id FROM equipment_systems WHERE project_id = ? AND system_tag = ?",
        (project_id, system_tag),
    ).fetchone()
    if existing:
        # Update type_id if not set
        type_id = _get_system_type_id(conn, type_code)
        if type_id:
            conn.execute(
                "UPDATE equipment_systems SET system_type_id = ? WHERE id = ?",
                (type_id, existing["id"]),
            )
        if parent_system_id:
            conn.execute(
                "UPDATE equipment_systems SET parent_system_id = ? WHERE id = ?",
                (parent_system_id, existing["id"]),
            )
        return existing["id"]

    type_id = _get_system_type_id(conn, type_code)
    cursor = conn.execute(
        """INSERT INTO equipment_systems
           (project_id, system_tag, system_name, system_category, discipline,
            description, system_type_id, parent_system_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (project_id, system_tag, system_name, category, discipline,
         description, type_id, parent_system_id),
    )
    return cursor.lastrowid


def _assign_to_system(conn, project_id: int, system_id: int, tags: List[str]) -> int:
    """Assign equipment instances to a system by tag. Returns count assigned."""
    count = 0
    for tag in tags:
        result = conn.execute(
            """UPDATE equipment_instances SET system_id = ?
               WHERE project_id = ? AND tag = ? AND (system_id IS NULL OR system_id = ?)""",
            (system_id, project_id, tag, system_id),
        )
        count += result.rowcount
    return count


def _assign_by_types(conn, project_id: int, system_id: int, type_names: List[str]) -> int:
    """Assign equipment to system by type name. Only assigns unassigned equipment."""
    count = 0
    for tn in type_names:
        result = conn.execute(
            """UPDATE equipment_instances SET system_id = ?
               WHERE project_id = ? AND system_id IS NULL
               AND type_id IN (SELECT id FROM equipment_types WHERE name = ?)""",
            (system_id, project_id, tn),
        )
        count += result.rowcount
    return count


def _assign_by_tag_prefix(conn, project_id: int, system_id: int, prefix: str) -> int:
    """Assign unassigned equipment matching a tag prefix to a system."""
    result = conn.execute(
        """UPDATE equipment_instances SET system_id = ?
           WHERE project_id = ? AND system_id IS NULL AND tag LIKE ?""",
        (system_id, project_id, f"{prefix}%"),
    )
    return result.rowcount


def _assign_children_to_parent_system(conn, project_id: int) -> int:
    """Assign sub-components to their parent's system if unassigned."""
    result = conn.execute(
        """UPDATE equipment_instances SET system_id = (
               SELECT p.system_id FROM equipment_instances p
               WHERE p.project_id = equipment_instances.project_id
               AND p.tag = equipment_instances.parent_tag
               AND p.system_id IS NOT NULL
           )
           WHERE project_id = ? AND parent_tag IS NOT NULL AND system_id IS NULL""",
        (project_id,),
    )
    return result.rowcount


# ---------------------------------------------------------------------------
# Refrigeration consolidation
# ---------------------------------------------------------------------------

def consolidate_refrigeration(project_id: int, conn) -> Dict[str, Any]:
    """Consolidate RS-* circuits into logical refrigeration systems.

    Groups RCUs by the set of primary RAHUs they serve. RCUs serving
    identical RAHU sets are in the same logical system.
    """
    stats = {"systems_created": 0, "equipment_assigned": 0, "circuits_linked": 0}

    # Build map: RCU tag → set of primary RAHUs served
    rels = conn.execute(
        """SELECT r.source_tag, r.target_tag
           FROM equipment_relationships r
           JOIN equipment_instances ei ON ei.project_id = r.project_id AND ei.tag = r.target_tag
           WHERE r.project_id = ? AND r.relationship_type = 'serves'
           AND ei.parent_tag IS NULL
           AND r.target_tag LIKE 'RAHU-%'""",
        (project_id,),
    ).fetchall()

    rcu_to_rahus = {}
    for r in rels:
        rcu_to_rahus.setdefault(r["source_tag"], set()).add(r["target_tag"])

    # Group RCUs by identical RAHU sets
    rahu_set_to_rcus = {}
    for rcu, rahus in rcu_to_rahus.items():
        key = frozenset(rahus)
        rahu_set_to_rcus.setdefault(key, []).append(rcu)

    # Create consolidated systems
    for idx, (rahu_set, rcus) in enumerate(
        sorted(rahu_set_to_rcus.items(), key=lambda x: min(x[0])), start=1
    ):
        sys_tag = f"REFRIG-{idx}"
        rahu_list = sorted(rahu_set)
        sys_name = f"Refrigeration System {idx} ({rahu_list[0]}..{rahu_list[-1]})"

        parent_id = _create_system(
            conn, project_id, sys_tag, sys_name,
            "Refrigeration", "Refrigeration", "REFRIG",
            description=f"{len(rcus)} compressors, {len(rahu_set)} evaporators",
        )
        stats["systems_created"] += 1

        # Link existing RS-* circuits as children
        for rcu in sorted(rcus):
            existing_sys = conn.execute(
                """SELECT es.id FROM equipment_systems es
                   JOIN equipment_instances ei ON ei.system_id = es.id
                   WHERE es.project_id = ? AND ei.tag = ?""",
                (project_id, rcu),
            ).fetchone()
            if existing_sys:
                conn.execute(
                    """UPDATE equipment_systems
                       SET parent_system_id = ?, system_type_id = ?
                       WHERE id = ?""",
                    (parent_id, _get_system_type_id(conn, "REFRIG"),
                     existing_sys["id"]),
                )
                stats["circuits_linked"] += 1

        # Assign RCUs to parent system (if not already in a child circuit)
        for rcu in rcus:
            conn.execute(
                """UPDATE equipment_instances SET system_id = ?
                   WHERE project_id = ? AND tag = ? AND system_id IS NULL""",
                (parent_id, project_id, rcu),
            )

        # Assign RAHUs + their sub-components to parent system
        for rahu in rahu_list:
            stats["equipment_assigned"] += _assign_to_system(
                conn, project_id, parent_id, [rahu])
            # Assign sub-components of this RAHU
            subs = conn.execute(
                """SELECT tag FROM equipment_instances
                   WHERE project_id = ? AND parent_tag = ?""",
                (project_id, rahu),
            ).fetchall()
            stats["equipment_assigned"] += _assign_to_system(
                conn, project_id, parent_id, [s["tag"] for s in subs])

    conn.commit()
    logger.info(
        "Refrigeration: %d systems, %d circuits linked, %d equipment assigned",
        stats["systems_created"], stats["circuits_linked"],
        stats["equipment_assigned"],
    )
    return stats


# ---------------------------------------------------------------------------
# Plumbing systems
# ---------------------------------------------------------------------------

def _dominant_discipline(conn, project_id: int, tags: list) -> str:
    """Find the most common discipline_primary for a set of tags."""
    if not tags:
        return "Unknown"
    placeholders = ",".join("?" * len(tags))
    row = conn.execute(
        f"""SELECT discipline_primary, COUNT(*) as cnt
            FROM equipment_instances
            WHERE project_id = ? AND tag IN ({placeholders})
            AND discipline_primary IS NOT NULL
            GROUP BY discipline_primary ORDER BY cnt DESC LIMIT 1""",
        [project_id] + list(tags),
    ).fetchone()
    return row["discipline_primary"] if row else "Unknown"


def create_plumbing_systems(project_id: int, conn) -> Dict[str, Any]:
    """Create systems for plumbing-discipline equipment, deriving discipline from drawings."""
    stats = {"systems_created": 0, "equipment_assigned": 0}

    systems = [
        ("PLMB-DHW", "Domestic Hot Water", "PLUMB-DHW",
         ["Boiler", "Water Heater", "Electric Water Heater", "Storage Tank"],
         ["P-H", "GWH", "EWH", "HWT"]),
        ("PLMB-DCW", "Domestic Cold Water", "PLUMB-DCW",
         ["Water Softener", "Backflow Preventer", "Booster Pump"],
         ["P-C", "P-D", "WS-", "RPBFP", "WPB"]),
        ("PLMB-CMP", "Compressed Air", "COMP-AIR",
         ["Compressor", "Air Dryer", "Air Receiver"],
         ["AC-", "AD", "CAR"]),
        ("PLMB-FIX", "Plumbing Fixtures", "PLUMB-FIX",
         ["Sink", "Water Closet", "Urinal", "Shower", "Mop Basin",
          "Floor Sink", "Water Cooler"],
         ["S-", "WC-", "UR-", "SHWR", "MS-", "FS-", "EWC"]),
        ("PLMB-DRN", "Drainage", "PLUMB-SAN",
         ["Floor Drain", "Floor Cleanout", "Hub Drain"],
         ["FD-", "FCO-", "HD-"]),
    ]

    for sys_tag, sys_name, type_code, type_names, tag_prefixes in systems:
        # Find candidate equipment to determine discipline from drawing data
        candidates = []
        for tn in type_names:
            rows = conn.execute(
                """SELECT tag FROM equipment_instances ei
                   JOIN equipment_types et ON ei.type_id = et.id
                   WHERE ei.project_id = ? AND et.name = ? AND ei.system_id IS NULL""",
                (project_id, tn),
            ).fetchall()
            candidates.extend(r["tag"] for r in rows)
        for prefix in tag_prefixes:
            rows = conn.execute(
                "SELECT tag FROM equipment_instances WHERE project_id = ? AND system_id IS NULL AND tag LIKE ?",
                (project_id, f"{prefix}%"),
            ).fetchall()
            candidates.extend(r["tag"] for r in rows)

        disc = _dominant_discipline(conn, project_id, candidates) if candidates else "Plumbing"

        sys_id = _create_system(
            conn, project_id, sys_tag, sys_name,
            disc, disc, type_code,
        )
        stats["systems_created"] += 1

        assigned = _assign_by_types(conn, project_id, sys_id, type_names)
        for prefix in tag_prefixes:
            assigned += _assign_by_tag_prefix(conn, project_id, sys_id, prefix)
        stats["equipment_assigned"] += assigned

    conn.commit()
    logger.info("Plumbing: %d systems, %d equipment assigned",
                stats["systems_created"], stats["equipment_assigned"])
    return stats


# ---------------------------------------------------------------------------
# HVAC system fixes
# ---------------------------------------------------------------------------

def fix_hvac_systems(project_id: int, conn) -> Dict[str, Any]:
    """Fix HVAC systems: assign AHUs to their systems, set type_id."""
    stats = {"ahus_assigned": 0, "type_ids_set": 0}

    hvac_type_id = _get_system_type_id(conn, "HVAC-AIR")

    # Get all HVAC-AHU-* systems
    systems = conn.execute(
        """SELECT id, system_tag FROM equipment_systems
           WHERE project_id = ? AND system_tag LIKE 'HVAC-AHU-%'""",
        (project_id,),
    ).fetchall()

    for sys in systems:
        # Set system_type_id
        conn.execute(
            "UPDATE equipment_systems SET system_type_id = ? WHERE id = ?",
            (hvac_type_id, sys["id"]),
        )
        stats["type_ids_set"] += 1

        # Extract AHU number from system tag (HVAC-AHU-2 → AHU-2)
        ahu_num = sys["system_tag"].replace("HVAC-AHU-", "")
        ahu_tag = f"AHU-{ahu_num}"

        # Assign AHU to its system
        result = conn.execute(
            """UPDATE equipment_instances SET system_id = ?
               WHERE project_id = ? AND tag = ? AND system_id IS NULL""",
            (sys["id"], project_id, ahu_tag),
        )
        stats["ahus_assigned"] += result.rowcount

    # Set type_id on electrical services too
    elec_type_id = _get_system_type_id(conn, "ELEC-NORMAL")
    if elec_type_id:
        conn.execute(
            """UPDATE equipment_systems SET system_type_id = ?
               WHERE project_id = ? AND system_tag LIKE 'ELEC-SVC-%'
               AND system_type_id IS NULL""",
            (elec_type_id, project_id),
        )

    conn.commit()
    logger.info("HVAC: %d AHUs assigned, %d system types set",
                stats["ahus_assigned"], stats["type_ids_set"])
    return stats


# ---------------------------------------------------------------------------
# Additional mechanical systems
# ---------------------------------------------------------------------------

def create_mechanical_systems(project_id: int, conn) -> Dict[str, Any]:
    """Create exhaust, ventilation, and hydronic systems."""
    stats = {"systems_created": 0, "equipment_assigned": 0}

    # Exhaust system — derive discipline from equipment
    exhaust_candidates = [r["tag"] for r in conn.execute(
        """SELECT tag FROM equipment_instances ei
           LEFT JOIN equipment_types et ON ei.type_id = et.id
           WHERE ei.project_id = ? AND ei.system_id IS NULL
           AND (et.name IN ('Exhaust Fan','Gravity Ventilator') OR ei.tag LIKE 'EF-%' OR ei.tag LIKE 'GRE-%' OR ei.tag LIKE 'GRI-%')""",
        (project_id,),
    ).fetchall()]
    exhaust_disc = _dominant_discipline(conn, project_id, exhaust_candidates) if exhaust_candidates else "Mechanical"
    exhaust_id = _create_system(
        conn, project_id, "MECH-EXHAUST", "Exhaust & Ventilation",
        exhaust_disc, exhaust_disc, "HVAC-EXHAUST",
    )
    assigned = _assign_by_types(
        conn, project_id, exhaust_id,
        ["Exhaust Fan", "Gravity Ventilator"],
    )
    assigned += _assign_by_tag_prefix(conn, project_id, exhaust_id, "EF-")
    assigned += _assign_by_tag_prefix(conn, project_id, exhaust_id, "GRE-")
    assigned += _assign_by_tag_prefix(conn, project_id, exhaust_id, "GRI-")
    stats["equipment_assigned"] += assigned
    stats["systems_created"] += 1

    # Ventilation (HVLS, ERV, louvers) — derive discipline from equipment
    vent_candidates = [r["tag"] for r in conn.execute(
        """SELECT tag FROM equipment_instances ei
           LEFT JOIN equipment_types et ON ei.type_id = et.id
           WHERE ei.project_id = ? AND ei.system_id IS NULL
           AND (et.name IN ('HVLS Fan','Energy Recovery') OR ei.tag LIKE 'HVLS-%' OR ei.tag LIKE 'ERV-%' OR ei.tag LIKE 'L-%')""",
        (project_id,),
    ).fetchall()]
    vent_disc = _dominant_discipline(conn, project_id, vent_candidates) if vent_candidates else "Mechanical"
    vent_id = _create_system(
        conn, project_id, "MECH-VENT", "Comfort Ventilation",
        vent_disc, vent_disc, "HVAC-VENTILATION",
    )
    assigned = _assign_by_types(
        conn, project_id, vent_id,
        ["HVLS Fan", "Energy Recovery"],
    )
    assigned += _assign_by_tag_prefix(conn, project_id, vent_id, "HVLS-")
    assigned += _assign_by_tag_prefix(conn, project_id, vent_id, "ERV-")
    assigned += _assign_by_tag_prefix(conn, project_id, vent_id, "L-")
    stats["equipment_assigned"] += assigned
    stats["systems_created"] += 1

    # Chilled water plant — derive discipline from equipment
    chw_candidates = [r["tag"] for r in conn.execute(
        """SELECT tag FROM equipment_instances ei
           LEFT JOIN equipment_types et ON ei.type_id = et.id
           WHERE ei.project_id = ? AND ei.system_id IS NULL
           AND (et.name IN ('Chiller','Cooling Tower') OR ei.tag LIKE 'CH-%' OR ei.tag LIKE 'CHU-%')""",
        (project_id,),
    ).fetchall()]
    chw_disc = _dominant_discipline(conn, project_id, chw_candidates) if chw_candidates else "Mechanical"
    chw_id = _create_system(
        conn, project_id, "MECH-CHW", "Chilled Water Plant",
        chw_disc, chw_disc, "HYDRO-CHW",
    )
    assigned = _assign_by_types(
        conn, project_id, chw_id,
        ["Chiller", "Cooling Tower"],
    )
    assigned += _assign_by_tag_prefix(conn, project_id, chw_id, "CH-")
    assigned += _assign_by_tag_prefix(conn, project_id, chw_id, "CHU-")
    stats["equipment_assigned"] += assigned
    stats["systems_created"] += 1

    conn.commit()
    logger.info("Mechanical: %d systems, %d equipment assigned",
                stats["systems_created"], stats["equipment_assigned"])
    return stats


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def build_systems(project_id: int) -> Dict[str, Any]:
    """Run all system builders for a project. Returns summary."""
    summary = {
        "before": 0,
        "after": 0,
        "refrigeration": {},
        "plumbing": {},
        "hvac": {},
        "mechanical": {},
        "children_assigned": 0,
    }

    with get_db() as conn:
        # Ensure migration has run
        from qms.pipeline.tag_parser import run_migration
        run_migration(conn)

        summary["before"] = conn.execute(
            """SELECT COUNT(*) FROM equipment_instances
               WHERE project_id = ? AND system_id IS NOT NULL""",
            (project_id,),
        ).fetchone()[0]

        total = conn.execute(
            "SELECT COUNT(*) FROM equipment_instances WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0]

        # Run builders in order
        summary["refrigeration"] = consolidate_refrigeration(project_id, conn)
        summary["plumbing"] = create_plumbing_systems(project_id, conn)
        summary["hvac"] = fix_hvac_systems(project_id, conn)
        summary["mechanical"] = create_mechanical_systems(project_id, conn)

        # Final pass: assign sub-components to their parent's system
        summary["children_assigned"] = _assign_children_to_parent_system(
            conn, project_id)
        conn.commit()

        summary["after"] = conn.execute(
            """SELECT COUNT(*) FROM equipment_instances
               WHERE project_id = ? AND system_id IS NOT NULL""",
            (project_id,),
        ).fetchone()[0]

    pct = round(100 * summary["after"] / total, 1) if total else 0
    logger.info(
        "System build complete: %d -> %d assigned (%s%% of %d total)",
        summary["before"], summary["after"], pct, total,
    )
    return summary
