"""Cross-discipline conflict detection and negative space analysis.

Detects attribute mismatches between disciplines for the same equipment
and identifies missing discipline coverage based on expected_disciplines
per equipment type.

Part of v0.4 Equipment-Centric Platform (Phase 20).
"""

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from qms.core import get_db, get_logger

logger = get_logger("qms.pipeline.conflict_detector")


@dataclass
class DetectionResult:
    """Result of a conflict detection run."""
    attribute_conflicts: int = 0
    missing_discipline_conflicts: int = 0
    cleared: int = 0
    by_severity: Dict[str, int] = field(default_factory=lambda: {
        "critical": 0, "warning": 0, "info": 0,
    })
    duration_ms: int = 0
    errors: List[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.attribute_conflicts + self.missing_discipline_conflicts


# ---------------------------------------------------------------------------
# Value normalization helpers
# ---------------------------------------------------------------------------

def _normalize_voltage(val: str) -> Optional[float]:
    """Extract primary numeric voltage from various formats.

    '480V' → 480.0, '480/277V' → 480.0, '208/120V' → 208.0, '480' → 480.0
    """
    if val is None:
        return None
    s = str(val).strip().upper().replace("V", "")
    # Take first number in slash-separated values (primary voltage)
    parts = s.split("/")
    try:
        return float(parts[0].replace(",", ""))
    except (ValueError, IndexError):
        return None


def _parse_numeric(val) -> Optional[float]:
    """Parse a numeric value, handling strings with units."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    # Remove common suffixes
    s = re.sub(r'\s*(hp|lbs?|a|amps?|kva|cfm|tons?|mbh|kw|psi|gpm)\s*$',
               '', s, flags=re.IGNORECASE)
    s = s.replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


def _values_conflict(val_a, val_b, rule: Dict) -> bool:
    """Check if two values conflict according to a comparison rule.

    Returns True if there IS a conflict.
    """
    comparison = rule["comparison_type"]

    if comparison == "exact":
        # Normalize strings for comparison
        a = str(val_a).strip().lower() if val_a is not None else ""
        b = str(val_b).strip().lower() if val_b is not None else ""
        # For voltage, compare normalized numeric values
        if rule["attribute_name"] in ("voltage", "pipe_size", "refrigerant"):
            if rule["attribute_name"] == "voltage":
                na = _normalize_voltage(str(val_a))
                nb = _normalize_voltage(str(val_b))
                if na is not None and nb is not None:
                    return na != nb
            return a != b
        return a != b

    elif comparison == "numeric_tolerance":
        na = _parse_numeric(val_a)
        nb = _parse_numeric(val_b)
        if na is None or nb is None:
            return False  # Can't compare non-numeric — not a conflict
        if na == 0 and nb == 0:
            return False

        tolerance = rule.get("tolerance_value") or 0
        tol_type = rule.get("tolerance_type", "percent")

        if tol_type == "percent":
            # Percent difference relative to the larger value
            base = max(abs(na), abs(nb))
            if base == 0:
                return False
            pct_diff = abs(na - nb) / base * 100
            return pct_diff > tolerance
        else:
            # Absolute tolerance
            return abs(na - nb) > tolerance

    elif comparison == "presence":
        # Flag if one has the attribute and the other doesn't
        a_present = val_a is not None and str(val_a).strip() != ""
        b_present = val_b is not None and str(val_b).strip() != ""
        return a_present != b_present

    return False


# ---------------------------------------------------------------------------
# Attribute name mapping across discipline sources
# ---------------------------------------------------------------------------

# Maps canonical attribute names to possible column names in different tables
_ATTR_ALIASES = {
    "hp": ["hp", "hp_rating", "power_hp", "bhp"],
    "voltage": ["voltage", "primary_voltage", "power_voltage"],
    "amperage": ["amperage", "current_rating", "fla",
                 "total_demand_current"],
    "weight_lbs": ["weight_lbs", "operating_weight_lbs"],
    "pipe_size": ["pipe_size", "inlet_size", "outlet_size"],
    "refrigerant": ["refrigerant"],
}


def _find_attr_value(attrs: Dict, canonical_name: str):
    """Find an attribute value using alias mapping.

    Returns the first non-None value found for any alias of the canonical name.
    """
    aliases = _ATTR_ALIASES.get(canonical_name, [canonical_name])
    for alias in aliases:
        val = attrs.get(alias)
        if val is not None:
            return val
    return None


# ---------------------------------------------------------------------------
# Pass 1: Attribute Conflicts
# ---------------------------------------------------------------------------

def detect_attribute_conflicts(project_id: int, conn) -> int:
    """Detect attribute mismatches between disciplines for same equipment.

    Compares attributes_on_sheet across appearances for each instance,
    using conflict_rules for comparison type and tolerance.

    Returns count of conflicts created.
    """
    count = 0

    # Load active conflict rules
    rules = [dict(r) for r in conn.execute(
        "SELECT * FROM conflict_rules WHERE active = 1"
    ).fetchall()]

    if not rules:
        logger.warning("No active conflict rules found")
        return 0

    # Get all instances with 2+ appearances that have attributes
    instances = conn.execute(
        """SELECT ei.id, ei.tag, ei.type_id
           FROM equipment_instances ei
           WHERE ei.project_id = ?
             AND (SELECT COUNT(*) FROM equipment_appearances ea
                  WHERE ea.instance_id = ei.id) >= 2""",
        (project_id,),
    ).fetchall()

    for inst in instances:
        inst = dict(inst)
        instance_id = inst["id"]
        tag = inst["tag"]

        # Get all appearances with attributes
        appearances = conn.execute(
            """SELECT discipline, drawing_number, attributes_on_sheet,
                      source_table
               FROM equipment_appearances
               WHERE instance_id = ?
                 AND attributes_on_sheet IS NOT NULL
                 AND attributes_on_sheet != '{}'
                 AND attributes_on_sheet != 'null'
               ORDER BY discipline""",
            (instance_id,),
        ).fetchall()

        if len(appearances) < 2:
            continue

        # Parse attributes for each appearance
        parsed = []
        for app in appearances:
            app = dict(app)
            try:
                attrs = json.loads(app["attributes_on_sheet"])
            except (json.JSONDecodeError, TypeError):
                continue
            if not attrs:
                continue
            parsed.append({
                "discipline": app["discipline"],
                "drawing": app.get("drawing_number", ""),
                "attrs": attrs,
            })

        if len(parsed) < 2:
            continue

        # Compare each pair of appearances against each rule
        for rule in rules:
            attr_name = rule["attribute_name"]

            for i in range(len(parsed)):
                for j in range(i + 1, len(parsed)):
                    a = parsed[i]
                    b = parsed[j]

                    val_a = _find_attr_value(a["attrs"], attr_name)
                    val_b = _find_attr_value(b["attrs"], attr_name)

                    # Both must have the attribute to compare
                    if val_a is None or val_b is None:
                        continue

                    if _values_conflict(val_a, val_b, rule):
                        conn.execute(
                            """INSERT INTO equipment_conflicts
                               (project_id, equipment_tag, conflict_type,
                                attribute_name, discipline_a, drawing_a,
                                value_a, discipline_b, drawing_b, value_b,
                                rule_id, severity, status)
                               VALUES (?,?,'attribute',?,?,?,?,?,?,?,?,?,
                                       'new')""",
                            (project_id, tag, attr_name,
                             a["discipline"], a["drawing"], str(val_a),
                             b["discipline"], b["drawing"], str(val_b),
                             rule["id"], rule["severity"]),
                        )
                        count += 1

    conn.commit()
    return count


# ---------------------------------------------------------------------------
# Pass 2: Missing Discipline (Negative Space)
# ---------------------------------------------------------------------------

def detect_missing_disciplines(project_id: int, conn) -> int:
    """Detect equipment missing from expected discipline drawings.

    Compares actual disciplines in equipment_appearances against
    expected_disciplines from the equipment_type definition.

    Returns count of conflicts created.
    """
    count = 0

    instances = conn.execute(
        """SELECT ei.id, ei.tag, ei.discipline_primary,
                  et.name as type_name, et.expected_disciplines
           FROM equipment_instances ei
           JOIN equipment_types et ON ei.type_id = et.id
           WHERE ei.project_id = ?
             AND et.expected_disciplines IS NOT NULL
             AND et.expected_disciplines != '[]'""",
        (project_id,),
    ).fetchall()

    for inst in instances:
        inst = dict(inst)
        tag = inst["tag"]
        primary = inst["discipline_primary"]
        type_name = inst["type_name"]

        try:
            expected = json.loads(inst["expected_disciplines"])
        except (json.JSONDecodeError, TypeError):
            continue
        if not expected:
            continue

        # Get actual disciplines
        actual_rows = conn.execute(
            """SELECT DISTINCT discipline FROM equipment_appearances
               WHERE instance_id = ?""",
            (inst["id"],),
        ).fetchall()
        actual = {r["discipline"] for r in actual_rows}

        for disc in expected:
            if disc not in actual:
                # Missing discipline — is it critical?
                # Critical if it's the primary expected discipline
                # (first in the list) or matches equipment's primary
                severity = "warning"
                if disc == expected[0] and disc != primary:
                    severity = "critical"
                elif disc == primary:
                    severity = "critical"

                # Get the first actual discipline/drawing for reference
                first_actual = conn.execute(
                    """SELECT discipline, drawing_number
                       FROM equipment_appearances
                       WHERE instance_id = ?
                       LIMIT 1""",
                    (inst["id"],),
                ).fetchone()
                ref_disc = first_actual["discipline"] if first_actual else primary
                ref_drawing = first_actual["drawing_number"] if first_actual else ""

                conn.execute(
                    """INSERT INTO equipment_conflicts
                       (project_id, equipment_tag, conflict_type,
                        attribute_name, discipline_a, drawing_a, value_a,
                        discipline_b, drawing_b, value_b,
                        severity, status)
                       VALUES (?,?,'missing_discipline',
                               ?,?,?,?,?,?,?,?,
                               'new')""",
                    (project_id, tag,
                     type_name,  # attribute_name stores the type for context
                     disc, "", "not found",
                     ref_disc, ref_drawing, "present",
                     severity),
                )
                count += 1

    conn.commit()
    return count


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def detect_conflicts(
    project_id: int,
    clear_existing: bool = True,
) -> DetectionResult:
    """Run all conflict detection passes for a project.

    Args:
        project_id: Project to scan.
        clear_existing: If True, clear existing 'new' status conflicts first.

    Returns:
        DetectionResult with counts and timing.
    """
    start = time.time()
    result = DetectionResult()

    with get_db() as conn:
        # Verify project exists
        project = conn.execute(
            "SELECT id, name FROM projects WHERE id = ?", (project_id,),
        ).fetchone()
        if not project:
            result.errors.append(f"Project {project_id} not found")
            return result

        logger.info("Detecting conflicts for project: %s (id=%d)",
                     project["name"], project_id)

        # Clear existing unresolved conflicts (preserves resolved/false_positive)
        if clear_existing:
            cursor = conn.execute(
                """DELETE FROM equipment_conflicts
                   WHERE project_id = ? AND status = 'new'""",
                (project_id,),
            )
            result.cleared = cursor.rowcount
            conn.commit()
            if result.cleared:
                logger.info("Cleared %d existing 'new' conflicts", result.cleared)

        # Pass 1: Attribute conflicts
        result.attribute_conflicts = detect_attribute_conflicts(
            project_id, conn)
        logger.info("Attribute conflicts: %d", result.attribute_conflicts)

        # Pass 2: Missing discipline (negative space)
        result.missing_discipline_conflicts = detect_missing_disciplines(
            project_id, conn)
        logger.info("Missing discipline conflicts: %d",
                     result.missing_discipline_conflicts)

        # Tally by severity
        for row in conn.execute(
            """SELECT severity, COUNT(*) as cnt
               FROM equipment_conflicts
               WHERE project_id = ? AND status = 'new'
               GROUP BY severity""",
            (project_id,),
        ).fetchall():
            result.by_severity[row["severity"]] = row["cnt"]

    result.duration_ms = int((time.time() - start) * 1000)

    logger.info(
        "Conflict detection complete: %d attribute, %d missing discipline "
        "(%d critical, %d warning, %d info) in %dms",
        result.attribute_conflicts, result.missing_discipline_conflicts,
        result.by_severity.get("critical", 0),
        result.by_severity.get("warning", 0),
        result.by_severity.get("info", 0),
        result.duration_ms,
    )

    return result


# ---------------------------------------------------------------------------
# Query helpers (for CLI / API consumption)
# ---------------------------------------------------------------------------

def get_conflict_summary(project_id: int) -> Dict[str, Any]:
    """Get conflict summary stats for a project."""
    with get_db(readonly=True) as conn:
        total = conn.execute(
            "SELECT COUNT(*) as cnt FROM equipment_conflicts WHERE project_id = ?",
            (project_id,),
        ).fetchone()["cnt"]

        by_type = {r["conflict_type"]: r["cnt"] for r in conn.execute(
            """SELECT conflict_type, COUNT(*) as cnt
               FROM equipment_conflicts WHERE project_id = ?
               GROUP BY conflict_type""",
            (project_id,),
        ).fetchall()}

        by_severity = {r["severity"]: r["cnt"] for r in conn.execute(
            """SELECT severity, COUNT(*) as cnt
               FROM equipment_conflicts WHERE project_id = ?
               GROUP BY severity""",
            (project_id,),
        ).fetchall()}

        by_status = {r["status"]: r["cnt"] for r in conn.execute(
            """SELECT status, COUNT(*) as cnt
               FROM equipment_conflicts WHERE project_id = ?
               GROUP BY status""",
            (project_id,),
        ).fetchall()}

        top_equipment = conn.execute(
            """SELECT equipment_tag, COUNT(*) as cnt
               FROM equipment_conflicts WHERE project_id = ?
               GROUP BY equipment_tag
               ORDER BY cnt DESC LIMIT 10""",
            (project_id,),
        ).fetchall()

        return {
            "total": total,
            "by_type": by_type,
            "by_severity": by_severity,
            "by_status": by_status,
            "top_equipment": [(r["equipment_tag"], r["cnt"]) for r in top_equipment],
        }


def get_conflicts(
    project_id: int,
    conflict_type: Optional[str] = None,
    severity: Optional[str] = None,
    status: str = "new",
) -> List[Dict]:
    """Get conflict records with optional filtering."""
    sql = "SELECT * FROM equipment_conflicts WHERE project_id = ?"
    params: list = [project_id]

    if conflict_type:
        sql += " AND conflict_type = ?"
        params.append(conflict_type)
    if severity:
        sql += " AND severity = ?"
        params.append(severity)
    if status:
        sql += " AND status = ?"
        params.append(status)

    sql += " ORDER BY severity DESC, equipment_tag"

    with get_db(readonly=True) as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def format_rfi(conflicts: List[Dict]) -> str:
    """Format conflicts as RFI-ready text grouped by equipment tag."""
    if not conflicts:
        return "No conflicts to report."

    # Group by tag
    by_tag: Dict[str, List[Dict]] = {}
    for c in conflicts:
        by_tag.setdefault(c["equipment_tag"], []).append(c)

    lines = []
    lines.append("=" * 60)
    lines.append("REQUEST FOR INFORMATION — Cross-Discipline Conflicts")
    lines.append("=" * 60)
    lines.append("")

    for tag in sorted(by_tag):
        items = by_tag[tag]
        lines.append(f"Equipment: {tag}")
        lines.append("-" * 40)
        for c in items:
            if c["conflict_type"] == "attribute":
                lines.append(
                    f"  [{c['severity'].upper()}] {c['attribute_name']} mismatch: "
                    f"{c['discipline_a']} shows \"{c['value_a']}\" "
                    f"(dwg {c['drawing_a']}), "
                    f"{c['discipline_b']} shows \"{c['value_b']}\" "
                    f"(dwg {c['drawing_b']})"
                )
            elif c["conflict_type"] == "missing_discipline":
                lines.append(
                    f"  [{c['severity'].upper()}] Missing from {c['discipline_a']} "
                    f"drawings — expected per {c['attribute_name']} "
                    f"coordination requirements "
                    f"(present in {c['discipline_b']} dwg {c['drawing_b']})"
                )
        lines.append("")

    lines.append(f"Total: {len(conflicts)} conflict(s) across "
                 f"{len(by_tag)} equipment item(s)")
    return "\n".join(lines)
