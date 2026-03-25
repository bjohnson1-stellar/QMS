"""Equipment impact chain analysis via relationship graph traversal.

Provides forward/reverse impact analysis through equipment_relationships,
drawing-based impact assessment, and violation propagation tracing.

Part of v0.4 Equipment-Centric Platform (Phase 21).
"""

from collections import deque
from typing import Any, Dict, List, Optional

from qms.core import get_db, get_logger

logger = get_logger("qms.pipeline.impact_analyzer")


# ---------------------------------------------------------------------------
# Graph traversal helpers
# ---------------------------------------------------------------------------

def _build_adjacency(conn, project_id: int):
    """Build forward and reverse adjacency lists from equipment_relationships.

    Forward: source → targets (downstream: what this equipment feeds/serves)
    Reverse: target → sources (upstream: what feeds/serves this equipment)
    """
    forward = {}  # source_tag → [(target_tag, relationship_type, discipline)]
    reverse = {}  # target_tag → [(source_tag, relationship_type, discipline)]

    rows = conn.execute(
        """SELECT source_tag, target_tag, relationship_type, discipline
           FROM equipment_relationships
           WHERE project_id = ?""",
        (project_id,),
    ).fetchall()

    for r in rows:
        r = dict(r)
        src = r["source_tag"]
        tgt = r["target_tag"]
        rel = r["relationship_type"]
        disc = r.get("discipline", "")

        forward.setdefault(src, []).append((tgt, rel, disc))
        reverse.setdefault(tgt, []).append((src, rel, disc))

    return forward, reverse


def _get_type_name(conn, project_id: int, tag: str) -> str:
    """Look up equipment type name for a tag."""
    row = conn.execute(
        """SELECT et.name FROM equipment_instances ei
           JOIN equipment_types et ON ei.type_id = et.id
           WHERE ei.project_id = ? AND ei.tag = ?""",
        (project_id, tag),
    ).fetchone()
    return row["name"] if row else ""


# ---------------------------------------------------------------------------
# Forward impact (downstream)
# ---------------------------------------------------------------------------

def get_forward_impact(
    project_id: int,
    tag: str,
    max_depth: int = 10,
) -> List[Dict[str, Any]]:
    """Trace downstream impact from an equipment tag.

    BFS through equipment_relationships following forward edges
    (source→target for feeds/serves/connects_to).

    Returns list of {tag, type_name, depth, path, relationship_type}.
    """
    with get_db(readonly=True) as conn:
        forward, _ = _build_adjacency(conn, project_id)

        results = []
        visited = {tag}
        queue = deque()

        # Seed with direct downstream
        for tgt, rel, disc in forward.get(tag, []):
            if tgt not in visited:
                queue.append((tgt, 1, [tag, tgt], rel))
                visited.add(tgt)

        while queue:
            current, depth, path, rel_type = queue.popleft()
            if depth > max_depth:
                continue

            type_name = _get_type_name(conn, project_id, current)
            results.append({
                "tag": current,
                "type_name": type_name,
                "depth": depth,
                "path": path,
                "relationship_type": rel_type,
            })

            # Continue traversal
            for tgt, rel, disc in forward.get(current, []):
                if tgt not in visited:
                    visited.add(tgt)
                    queue.append((tgt, depth + 1, path + [tgt], rel))

    results.sort(key=lambda x: (x["depth"], x["tag"]))
    return results


# ---------------------------------------------------------------------------
# Reverse trace (upstream)
# ---------------------------------------------------------------------------

def get_reverse_trace(
    project_id: int,
    tag: str,
    max_depth: int = 10,
) -> List[Dict[str, Any]]:
    """Trace upstream dependencies for an equipment tag.

    BFS through equipment_relationships following reverse edges
    (target→source for feeds/serves).

    Returns list of {tag, type_name, depth, path, relationship_type}.
    """
    with get_db(readonly=True) as conn:
        _, reverse = _build_adjacency(conn, project_id)

        results = []
        visited = {tag}
        queue = deque()

        for src, rel, disc in reverse.get(tag, []):
            if src not in visited:
                queue.append((src, 1, [tag, src], rel))
                visited.add(src)

        while queue:
            current, depth, path, rel_type = queue.popleft()
            if depth > max_depth:
                continue

            type_name = _get_type_name(conn, project_id, current)
            results.append({
                "tag": current,
                "type_name": type_name,
                "depth": depth,
                "path": path,
                "relationship_type": rel_type,
            })

            for src, rel, disc in reverse.get(current, []):
                if src not in visited:
                    visited.add(src)
                    queue.append((src, depth + 1, path + [src], rel))

    results.sort(key=lambda x: (x["depth"], x["tag"]))
    return results


# ---------------------------------------------------------------------------
# Drawing impact
# ---------------------------------------------------------------------------

def get_drawing_impact(
    project_id: int,
    drawing_number: str,
) -> Dict[str, Any]:
    """Assess impact of a drawing revision.

    Finds all equipment on the drawing, then traces their downstream
    relationship chains to determine total blast radius.

    Returns {direct: [...], indirect: [...], summary: {direct, indirect, total}}.
    """
    with get_db(readonly=True) as conn:
        # Find equipment on this drawing
        rows = conn.execute(
            """SELECT DISTINCT ei.tag, et.name as type_name, ea.discipline
               FROM equipment_appearances ea
               JOIN equipment_instances ei ON ea.instance_id = ei.id
               LEFT JOIN equipment_types et ON ei.type_id = et.id
               WHERE ei.project_id = ? AND ea.drawing_number = ?""",
            (project_id, drawing_number),
        ).fetchall()

        direct = [dict(r) for r in rows]
        direct_tags = {r["tag"] for r in direct}

    # Trace downstream for each direct equipment
    all_indirect = {}
    for equip in direct:
        downstream = get_forward_impact(project_id, equip["tag"])
        for item in downstream:
            if item["tag"] not in direct_tags and item["tag"] not in all_indirect:
                all_indirect[item["tag"]] = item

    indirect = sorted(all_indirect.values(), key=lambda x: (x["depth"], x["tag"]))

    return {
        "drawing": drawing_number,
        "direct": direct,
        "indirect": indirect,
        "summary": {
            "direct_count": len(direct),
            "indirect_count": len(indirect),
            "total": len(direct) + len(indirect),
        },
    }


# ---------------------------------------------------------------------------
# Violation propagation
# ---------------------------------------------------------------------------

def get_violation_impact(project_id: int) -> List[Dict[str, Any]]:
    """Analyze downstream impact of spec violations.

    For each equipment with a spec_violation conflict, traces downstream
    to show what else is potentially affected. Advisory only — does not
    create new conflict records.
    """
    with get_db(readonly=True) as conn:
        # Get unique tags with spec violations
        violation_tags = conn.execute(
            """SELECT DISTINCT equipment_tag, attribute_name, severity, value_a, value_b
               FROM equipment_conflicts
               WHERE project_id = ? AND conflict_type = 'spec_violation'
               AND status = 'new'""",
            (project_id,),
        ).fetchall()

    impacts = []
    for vt in violation_tags:
        vt = dict(vt)
        tag = vt["equipment_tag"]
        downstream = get_forward_impact(project_id, tag, max_depth=5)

        if downstream:
            impacts.append({
                "source_tag": tag,
                "violation_attribute": vt["attribute_name"],
                "violation_severity": vt["severity"],
                "expected": vt["value_a"],
                "actual": vt["value_b"],
                "downstream_count": len(downstream),
                "downstream": downstream,
            })

    impacts.sort(key=lambda x: -x["downstream_count"])
    return impacts


# ---------------------------------------------------------------------------
# Tree formatting
# ---------------------------------------------------------------------------

def format_impact_tree(
    root_tag: str,
    items: List[Dict],
    root_type: str = "",
) -> str:
    """Format impact chain as indented tree string."""
    lines = []
    label = f"{root_tag} ({root_type})" if root_type else root_tag
    lines.append(label)

    if not items:
        lines.append("  (no downstream equipment)")
        return "\n".join(lines)

    # Group by depth for tree display
    by_depth = {}
    for item in items:
        by_depth.setdefault(item["depth"], []).append(item)

    # Simple indented list with depth markers
    for item in items:
        indent = "  " * item["depth"]
        rel = item.get("relationship_type", "")
        type_name = item.get("type_name", "")
        label = f"{item['tag']}"
        if type_name:
            label += f" ({type_name})"
        if rel:
            label += f" [{rel}]"
        lines.append(f"{indent}{label}")

    return "\n".join(lines)
