"""Spec compliance checking for equipment instances.

Validates equipment attributes against defined requirements in
equipment_spec_requirements, generating spec_violation conflicts
in equipment_conflicts.

Part of v0.4 Equipment-Centric Platform (Phase 21).
"""

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from qms.core import get_db, get_logger
from qms.pipeline.conflict_detector import _normalize_voltage, _parse_numeric as _parse_numeric_base

logger = get_logger("qms.pipeline.spec_checker")


def _parse_numeric(val) -> Optional[float]:
    """Extended numeric parser that handles more unit suffixes than base."""
    if val is None:
        return None
    # Strip extra suffixes not handled by base parser (AIC, etc.)
    s = str(val).strip()
    s = re.sub(r'\s*(aic|mlo|mcb|at|af)\s*$', '', s, flags=re.IGNORECASE)
    return _parse_numeric_base(s)


@dataclass
class ComplianceResult:
    """Result of a spec compliance check run."""
    total_checked: int = 0
    violations: int = 0
    cleared: int = 0
    by_severity: Dict[str, int] = field(default_factory=lambda: {
        "critical": 0, "warning": 0, "info": 0,
    })
    by_type: Dict[str, int] = field(default_factory=dict)
    duration_ms: int = 0
    errors: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Compliance check logic
# ---------------------------------------------------------------------------

def _check_value(actual, expected_value: str, check_type: str,
                 attribute_name: str) -> bool:
    """Check if an actual value meets a spec requirement.

    Returns True if the value PASSES (compliant).
    Returns False if the value FAILS (violation).
    """
    if actual is None:
        return True  # Can't check what doesn't exist — not a violation

    actual_str = str(actual).strip()
    if not actual_str:
        return True

    if check_type == "exact":
        # Normalize for comparison
        if attribute_name in ("voltage", "primary_voltage", "secondary_voltage"):
            na = _normalize_voltage(actual_str)
            ne = _normalize_voltage(expected_value)
            if na is not None and ne is not None:
                return na == ne
        return actual_str.lower() == expected_value.strip().lower()

    elif check_type == "one_of":
        # expected_value is a JSON array: '["480V","480/277V"]'
        try:
            allowed = json.loads(expected_value)
        except (json.JSONDecodeError, TypeError):
            return True  # Bad config — don't flag

        # For voltage, normalize before comparing
        if attribute_name in ("voltage", "primary_voltage", "secondary_voltage"):
            na = _normalize_voltage(actual_str)
            if na is not None:
                return any(
                    _normalize_voltage(str(a)) == na
                    for a in allowed
                    if _normalize_voltage(str(a)) is not None
                )

        return actual_str.lower() in [str(a).strip().lower() for a in allowed]

    elif check_type == "min":
        na = _parse_numeric(actual_str)
        ne = _parse_numeric(expected_value)
        if na is None or ne is None:
            return True
        return na >= ne

    elif check_type == "max":
        na = _parse_numeric(actual_str)
        ne = _parse_numeric(expected_value)
        if na is None or ne is None:
            return True
        return na <= ne

    elif check_type == "range":
        # expected_value is JSON: "[min, max]"
        try:
            bounds = json.loads(expected_value)
            lo, hi = float(bounds[0]), float(bounds[1])
        except (json.JSONDecodeError, TypeError, ValueError, IndexError):
            return True
        na = _parse_numeric(actual_str)
        if na is None:
            return True
        return lo <= na <= hi

    elif check_type == "regex":
        try:
            return bool(re.match(expected_value, actual_str, re.IGNORECASE))
        except re.error:
            return True

    return True  # Unknown check type — don't flag


def _find_attr_in_appearances(appearances: List[Dict], attr_name: str):
    """Find an attribute value across appearance records.

    Returns (value, discipline, drawing_number) or (None, None, None).
    """
    # Aliases for cross-discipline attribute names
    aliases = {
        "voltage": ["voltage", "primary_voltage", "power_voltage"],
        "primary_voltage": ["primary_voltage", "voltage"],
        "secondary_voltage": ["secondary_voltage"],
        "phases": ["phases"],
        "aic_rating": ["aic_rating"],
        "bus_rating": ["bus_rating"],
        "hp": ["hp", "hp_rating", "power_hp", "bhp"],
        "amperage": ["amperage", "current_rating", "fla"],
        "refrigerant": ["refrigerant"],
        "kva_rating": ["kva_rating", "kva"],
    }
    names_to_check = aliases.get(attr_name, [attr_name])

    for app in appearances:
        attrs = app.get("attrs", {})
        for name in names_to_check:
            val = attrs.get(name)
            if val is not None:
                return val, app["discipline"], app.get("drawing", "")
    return None, None, None


# ---------------------------------------------------------------------------
# Main compliance checker
# ---------------------------------------------------------------------------

def check_compliance(project_id: int, clear_existing: bool = True) -> ComplianceResult:
    """Run spec compliance checks for all equipment in a project.

    Compares equipment attributes against equipment_spec_requirements,
    storing violations in equipment_conflicts with conflict_type='spec_violation'.
    """
    start = time.time()
    result = ComplianceResult()

    with get_db() as conn:
        project = conn.execute(
            "SELECT id, name FROM projects WHERE id = ?", (project_id,),
        ).fetchone()
        if not project:
            result.errors.append(f"Project {project_id} not found")
            return result

        logger.info("Checking spec compliance for: %s (id=%d)",
                     project["name"], project_id)

        # Clear existing spec_violation conflicts
        if clear_existing:
            cursor = conn.execute(
                """DELETE FROM equipment_conflicts
                   WHERE project_id = ? AND conflict_type = 'spec_violation'
                   AND status = 'new'""",
                (project_id,),
            )
            result.cleared = cursor.rowcount
            conn.commit()
            if result.cleared:
                logger.info("Cleared %d existing spec_violation conflicts",
                            result.cleared)

        # Load active spec requirements
        requirements = [dict(r) for r in conn.execute(
            "SELECT * FROM equipment_spec_requirements WHERE active = 1"
        ).fetchall()]

        if not requirements:
            logger.warning("No active spec requirements found")
            result.duration_ms = int((time.time() - start) * 1000)
            return result

        # Group requirements by type_name (type_id match is also supported)
        req_by_type_name = {}
        req_by_type_id = {}
        for req in requirements:
            if req.get("type_id"):
                req_by_type_id.setdefault(req["type_id"], []).append(req)
            if req.get("type_name"):
                req_by_type_name.setdefault(req["type_name"], []).append(req)

        # Get all equipment instances with their type info
        instances = conn.execute(
            """SELECT ei.id, ei.tag, ei.type_id,
                      et.name as type_name,
                      ei.hp, ei.voltage, ei.amperage, ei.weight_lbs,
                      ei.pipe_size, ei.attributes
               FROM equipment_instances ei
               LEFT JOIN equipment_types et ON ei.type_id = et.id
               WHERE ei.project_id = ?""",
            (project_id,),
        ).fetchall()

        for inst in instances:
            inst = dict(inst)
            tag = inst["tag"]
            type_name = inst.get("type_name", "")
            type_id = inst.get("type_id")

            # Find applicable requirements
            applicable = []
            if type_id and type_id in req_by_type_id:
                applicable.extend(req_by_type_id[type_id])
            if type_name and type_name in req_by_type_name:
                applicable.extend(req_by_type_name[type_name])

            if not applicable:
                continue

            result.total_checked += 1

            # Load appearances for attribute lookup
            appearances = []
            for app in conn.execute(
                """SELECT discipline, drawing_number, attributes_on_sheet
                   FROM equipment_appearances
                   WHERE instance_id = ?
                   AND attributes_on_sheet IS NOT NULL
                   AND attributes_on_sheet != '{}'""",
                (inst["id"],),
            ).fetchall():
                app = dict(app)
                try:
                    attrs = json.loads(app["attributes_on_sheet"])
                except (json.JSONDecodeError, TypeError):
                    continue
                appearances.append({
                    "discipline": app["discipline"],
                    "drawing": app.get("drawing_number", ""),
                    "attrs": attrs,
                })

            # Check each requirement
            for req in applicable:
                attr_name = req["attribute_name"]

                # Look for attribute: first in appearances, then in instance columns
                actual, discipline, drawing = _find_attr_in_appearances(
                    appearances, attr_name)

                # Fallback to instance-level columns
                if actual is None and attr_name in (
                    "hp", "voltage", "amperage", "weight_lbs", "pipe_size",
                ):
                    actual = inst.get(attr_name)
                    if actual is not None:
                        discipline = inst.get("discipline_primary", "")
                        drawing = ""

                # Also check JSON overflow attributes on instance
                if actual is None and inst.get("attributes"):
                    try:
                        overflow = json.loads(inst["attributes"])
                        actual = overflow.get(attr_name)
                        if actual is not None:
                            discipline = inst.get("discipline_primary", "")
                            drawing = ""
                    except (json.JSONDecodeError, TypeError):
                        pass

                if actual is None:
                    continue  # Attribute not found — can't check

                # Run compliance check
                if not _check_value(actual, req["expected_value"],
                                    req["check_type"], attr_name):
                    # Violation found
                    sev = req["severity"]
                    conn.execute(
                        """INSERT INTO equipment_conflicts
                           (project_id, equipment_tag, conflict_type,
                            attribute_name, discipline_a, drawing_a, value_a,
                            discipline_b, drawing_b, value_b,
                            severity, status)
                           VALUES (?, ?, 'spec_violation',
                                   ?, 'Spec', ?, ?, ?, ?, ?,
                                   ?, 'new')""",
                        (project_id, tag,
                         attr_name,
                         req.get("source_spec", ""),
                         req["expected_value"],
                         discipline or "", drawing or "", str(actual),
                         sev),
                    )
                    result.violations += 1
                    result.by_severity[sev] = result.by_severity.get(sev, 0) + 1
                    result.by_type[type_name] = result.by_type.get(type_name, 0) + 1

        conn.commit()

    result.duration_ms = int((time.time() - start) * 1000)
    logger.info(
        "Spec compliance check complete: %d equipment checked, %d violations "
        "(%d critical, %d warning) in %dms",
        result.total_checked, result.violations,
        result.by_severity.get("critical", 0),
        result.by_severity.get("warning", 0),
        result.duration_ms,
    )
    return result


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

def get_compliance_summary(project_id: int) -> Dict[str, Any]:
    """Get spec compliance summary for a project."""
    with get_db(readonly=True) as conn:
        total = conn.execute(
            """SELECT COUNT(*) as cnt FROM equipment_conflicts
               WHERE project_id = ? AND conflict_type = 'spec_violation'""",
            (project_id,),
        ).fetchone()["cnt"]

        by_severity = {r["severity"]: r["cnt"] for r in conn.execute(
            """SELECT severity, COUNT(*) as cnt
               FROM equipment_conflicts
               WHERE project_id = ? AND conflict_type = 'spec_violation'
               GROUP BY severity""",
            (project_id,),
        ).fetchall()}

        by_attr = {r["attribute_name"]: r["cnt"] for r in conn.execute(
            """SELECT attribute_name, COUNT(*) as cnt
               FROM equipment_conflicts
               WHERE project_id = ? AND conflict_type = 'spec_violation'
               GROUP BY attribute_name
               ORDER BY cnt DESC""",
            (project_id,),
        ).fetchall()}

        top_equipment = conn.execute(
            """SELECT equipment_tag, COUNT(*) as cnt
               FROM equipment_conflicts
               WHERE project_id = ? AND conflict_type = 'spec_violation'
               GROUP BY equipment_tag
               ORDER BY cnt DESC LIMIT 10""",
            (project_id,),
        ).fetchall()

        return {
            "total": total,
            "by_severity": by_severity,
            "by_attribute": by_attr,
            "top_equipment": [(r["equipment_tag"], r["cnt"]) for r in top_equipment],
        }


def get_violations(
    project_id: int,
    severity: Optional[str] = None,
    type_name: Optional[str] = None,
) -> List[Dict]:
    """Get spec violation records with optional filtering."""
    sql = """SELECT ec.*, et.name as type_name
             FROM equipment_conflicts ec
             LEFT JOIN equipment_instances ei ON ec.equipment_tag = ei.tag
                 AND ec.project_id = ei.project_id
             LEFT JOIN equipment_types et ON ei.type_id = et.id
             WHERE ec.project_id = ? AND ec.conflict_type = 'spec_violation'"""
    params: list = [project_id]

    if severity:
        sql += " AND ec.severity = ?"
        params.append(severity)
    if type_name:
        sql += " AND et.name = ?"
        params.append(type_name)

    sql += " ORDER BY ec.severity DESC, ec.equipment_tag"

    with get_db(readonly=True) as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
