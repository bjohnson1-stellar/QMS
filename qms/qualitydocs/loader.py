"""
Quality Manual XML Loader

Parses Quality Manual XML module files and loads them into the database.
Handles re-runs gracefully (deletes existing module data before re-inserting),
detects prose references to codes/standards and internal cross-references,
validates cross-references, and populates the full-text search index.

Usage (from Python):
    from qms.qualitydocs.loader import load_module_from_file, get_manual_summary

Usage (from CLI):
    qms docs load-module path/to/module01.xml
"""

import re
import sqlite3
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from qms.core import get_db, get_logger

logger = get_logger("qms.qualitydocs.loader")

# ---------------------------------------------------------------------------
# XML namespace
# ---------------------------------------------------------------------------

NS = {"sis": "http://stellarindustrial.com/quality-manual"}

# ---------------------------------------------------------------------------
# Regex patterns for prose reference detection
# ---------------------------------------------------------------------------

SECTION_REF_PATTERN = re.compile(r"Section\s+(\d+\.\d+)([A-Z])?", re.IGNORECASE)

CODE_PATTERNS: List[tuple] = [
    (re.compile(r"\b(ASME\s+(?:BPV\s+)?Section\s+[IVX]+(?:\s*,\s*[A-Z0-9\-\.]+)?)", re.I), "ASME"),
    (re.compile(r"\b(ASME\s+B\d+\.\d+)", re.I), "ASME"),
    (re.compile(r"\b(AWS\s+[A-Z]\d+(?:\.\d+)?)", re.I), "AWS"),
    (re.compile(r"\b(NFPA\s+\d+(?:\w+)?)", re.I), "NFPA"),
    (re.compile(r"\b(NEC)\b", re.I), "NFPA"),
    (re.compile(r"\b(OSHA\s+[\d\.]+)", re.I), "OSHA"),
    (re.compile(r"\b(NIST)\b", re.I), "NIST"),
    (re.compile(r"\b(API\s+\d+)", re.I), "API"),
    (re.compile(r"\b(ASTM\s+[A-Z]\d+)", re.I), "ASTM"),
    (re.compile(r"\b(ISO\s+\d+)", re.I), "ISO"),
]


# ---------------------------------------------------------------------------
# XML Helpers
# ---------------------------------------------------------------------------

def _get_local_tag(elem: ET.Element) -> str:
    """Strip namespace from element tag to get local name."""
    tag = elem.tag
    if "}" in tag:
        return tag.split("}")[1]
    return tag


def _get_element_text(elem: ET.Element) -> str:
    """Get direct text content of element, or empty string if None."""
    return elem.text.strip() if elem.text else ""


def _get_full_text(elem: ET.Element) -> str:
    """Get all text content including nested elements."""
    return "".join(elem.itertext()).strip()


def _serialize_table(table_elem: ET.Element) -> str:
    """Convert a Table element to readable text representation."""
    lines: List[str] = []

    # Look for header row
    header = table_elem.find(".//sis:HeaderRow", NS) or table_elem.find(".//sis:Header", NS)
    if header is not None:
        cells = []
        for cell in header.findall(".//sis:Cell", NS) or header.findall(".//sis:HeaderCell", NS):
            cells.append(_get_full_text(cell))
        if cells:
            lines.append(" | ".join(cells))
            lines.append("-" * 40)

    # Look for data rows
    for row in table_elem.findall(".//sis:Row", NS) or table_elem.findall(".//sis:DataRow", NS):
        cells = []
        for cell in row.findall(".//sis:Cell", NS):
            cells.append(_get_full_text(cell))
        if cells:
            lines.append(" | ".join(cells))

    return "\n".join(lines) if lines else _get_full_text(table_elem)


# ---------------------------------------------------------------------------
# Module deletion (for idempotent re-loads)
# ---------------------------------------------------------------------------

def _delete_module_data(conn: sqlite3.Connection, module_number: int) -> None:
    """Delete all existing data for a module before re-loading."""
    row = conn.execute(
        "SELECT id FROM qm_modules WHERE module_number = ?", (module_number,)
    ).fetchone()

    if not row:
        return

    module_id = row["id"]

    # Delete in reverse FK dependency order
    conn.execute(
        "DELETE FROM qm_cross_references WHERE source_module_id = ?",
        (module_id,),
    )
    conn.execute(
        "DELETE FROM qm_code_references WHERE subsection_id IN ("
        "  SELECT sub.id FROM qm_subsections sub"
        "  JOIN qm_sections s ON sub.section_id = s.id"
        "  WHERE s.module_id = ?"
        ")",
        (module_id,),
    )
    conn.execute(
        "DELETE FROM qm_responsibility_assignments WHERE subsection_id IN ("
        "  SELECT sub.id FROM qm_subsections sub"
        "  JOIN qm_sections s ON sub.section_id = s.id"
        "  WHERE s.module_id = ?"
        ")",
        (module_id,),
    )
    conn.execute(
        "DELETE FROM qm_content_blocks WHERE subsection_id IN ("
        "  SELECT sub.id FROM qm_subsections sub"
        "  JOIN qm_sections s ON sub.section_id = s.id"
        "  WHERE s.module_id = ?"
        ")",
        (module_id,),
    )
    conn.execute(
        "DELETE FROM qm_subsections WHERE section_id IN ("
        "  SELECT id FROM qm_sections WHERE module_id = ?"
        ")",
        (module_id,),
    )
    conn.execute("DELETE FROM qm_sections WHERE module_id = ?", (module_id,))
    conn.execute("DELETE FROM qm_modules WHERE id = ?", (module_id,))

    conn.commit()
    logger.debug("Deleted existing data for module %d", module_number)


# ---------------------------------------------------------------------------
# Content block processing
# ---------------------------------------------------------------------------

def _process_content_block(
    conn: sqlite3.Connection,
    child: ET.Element,
    subsection_id: int,
    module_id: int,
    content_order: int,
    stats: Dict[str, Any],
) -> Optional[int]:
    """
    Process a single content element and insert into DB.

    Returns the next content_order value (incremented if a block was inserted),
    or None if the element was a CrossReference/CodeReference handled separately.
    """
    tag = _get_local_tag(child)

    # Handle explicit cross-references
    if tag == "CrossReference":
        target_module = child.get("targetModule")
        target_section = child.get("targetSection", "")
        target_subsection = child.get("targetSubsection", "")
        ref_type = child.get("refType", "internal")
        original_text = _get_full_text(child)

        conn.execute(
            "INSERT INTO qm_cross_references"
            " (source_module_id, source_subsection_id, target_module,"
            "  target_section, target_subsection, ref_type,"
            "  detection_method, original_text)"
            " VALUES (?, ?, ?, ?, ?, ?, 'explicit', ?)",
            (module_id, subsection_id, target_module, target_section,
             target_subsection or None, ref_type, original_text),
        )
        stats["explicit_xrefs"] += 1
        return None

    # Handle explicit code references
    if tag == "CodeReference":
        code = child.get("code", "")
        organization = child.get("organization", "")
        code_section = child.get("section", "")
        original_text = _get_full_text(child)

        conn.execute(
            "INSERT INTO qm_code_references"
            " (subsection_id, code, organization, code_section,"
            "  original_text, detection_method)"
            " VALUES (?, ?, ?, ?, ?, 'explicit')",
            (subsection_id, code, organization, code_section, original_text),
        )
        stats["explicit_coderefs"] += 1
        return None

    # Determine block type and content
    block_type: Optional[str] = None
    content: Optional[str] = None
    level: Optional[int] = None
    xml_fragment = ET.tostring(child, encoding="unicode")

    if tag == "HeadingParagraph":
        block_type = "HeadingParagraph"
        content = _get_full_text(child)
        raw_level = child.get("level")
        if raw_level:
            level = int(raw_level)

    elif tag == "Paragraph":
        block_type = "Paragraph"
        content = _get_full_text(child)
        # Skip "END OF SECTION" paragraphs
        if content.strip().upper() == "END OF SECTION":
            return content_order

    elif tag == "SubHeading":
        block_type = "SubHeading"
        content = _get_full_text(child)
        raw_level = child.get("level")
        if raw_level:
            level = int(raw_level)

    elif tag == "BulletList":
        block_type = "BulletList"
        items = [_get_full_text(item) for item in child.findall("sis:Item", NS)]
        content = "\n".join(items)

    elif tag == "NumberedList":
        block_type = "NumberedList"
        items = [_get_full_text(item) for item in child.findall("sis:Item", NS)]
        content = "\n".join(items)

    elif tag == "Table":
        block_type = "Table"
        content = _serialize_table(child)

    elif tag == "Note":
        block_type = "Note"
        content = _get_full_text(child)

    elif tag == "ResponsibilityBlock":
        block_type = "ResponsibilityBlock"
        role_elem = child.find("sis:Role", NS)
        role = _get_element_text(role_elem) if role_elem is not None else ""

        resp_elem = child.find("sis:Responsibilities", NS)
        items: List[str] = []
        if resp_elem is not None:
            items = [_get_full_text(item) for item in resp_elem.findall("sis:Item", NS)]

        content = role + "\n" + "\n".join(items)

        # Also insert responsibility assignments
        for resp_order, item_text in enumerate(items):
            conn.execute(
                "INSERT INTO qm_responsibility_assignments"
                " (subsection_id, role, responsibility, display_order)"
                " VALUES (?, ?, ?, ?)",
                (subsection_id, role, item_text, resp_order),
            )
            stats["responsibilities"][role] += 1

    else:
        # Unknown tag -- skip
        return content_order

    if block_type:
        conn.execute(
            "INSERT INTO qm_content_blocks"
            " (subsection_id, block_type, content, level, display_order, xml_fragment)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (subsection_id, block_type, content, level, content_order, xml_fragment),
        )
        stats["content_blocks"] += 1
        return content_order + 1

    return content_order


# ---------------------------------------------------------------------------
# Single-module loader
# ---------------------------------------------------------------------------

def _load_module_xml(
    conn: sqlite3.Connection,
    xml_source: str,
    xml_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Parse an XML string and load one quality manual module into the DB.

    Args:
        conn: Active database connection (caller manages transaction).
        xml_source: Raw XML string.
        xml_path: Optional file path (for logging only).

    Returns:
        Dict with module stats (module_number, version, sections, subsections, etc.)

    Raises:
        ET.ParseError: If XML is malformed.
    """
    root = ET.fromstring(xml_source)

    # Module attributes
    module_number = int(root.get("moduleNumber", "0"))
    version = root.get("version", "")
    effective_date = root.get("effectiveDate", "")
    status = root.get("status", "")

    # Title and description from DocumentHeader
    header = root.find(".//sis:DocumentHeader", NS)
    title = ""
    description = ""
    if header is not None:
        title_elem = header.find("sis:ModuleTitle", NS)
        desc_elem = header.find("sis:ModuleDescription", NS)
        if title_elem is not None:
            title = _get_element_text(title_elem)
        if desc_elem is not None:
            description = _get_full_text(desc_elem)

    # Delete existing data for idempotent re-runs
    _delete_module_data(conn, module_number)

    # Insert module row
    cursor = conn.execute(
        "INSERT INTO qm_modules"
        " (module_number, version, effective_date, status, title, description, xml_source)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (module_number, version, effective_date, status, title, description, xml_source),
    )
    module_id = cursor.lastrowid

    # Stats accumulator
    stats: Dict[str, Any] = {
        "module_number": module_number,
        "version": version,
        "title": title,
        "sections": 0,
        "subsections": 0,
        "content_blocks": 0,
        "explicit_xrefs": 0,
        "explicit_coderefs": 0,
        "responsibilities": defaultdict(int),
    }

    # Process sections
    sections_elem = root.find(".//sis:Sections", NS)
    if sections_elem is not None:
        for section_order, section_elem in enumerate(
            sections_elem.findall("sis:Section", NS)
        ):
            section_number = section_elem.get("number", "")
            section_title_elem = section_elem.find("sis:Title", NS)
            section_title = (
                _get_element_text(section_title_elem) if section_title_elem is not None else ""
            )
            related_sections = section_elem.get("relatedSections", "")
            related_modules = section_elem.get("relatedModules", "")

            cur = conn.execute(
                "INSERT INTO qm_sections"
                " (module_id, section_number, title, display_order,"
                "  related_sections, related_modules)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (module_id, section_number, section_title, section_order,
                 related_sections, related_modules),
            )
            section_id = cur.lastrowid
            stats["sections"] += 1

            # Process subsections
            subsections_elem = section_elem.find("sis:Subsections", NS)
            if subsections_elem is None:
                continue

            for subsection_order, subsection_elem in enumerate(
                subsections_elem.findall("sis:Subsection", NS)
            ):
                letter = subsection_elem.get("letter", "")
                subsection_type = subsection_elem.get("subsectionType", "General")
                subsection_title_elem = subsection_elem.find("sis:Title", NS)
                subsection_title = (
                    _get_element_text(subsection_title_elem)
                    if subsection_title_elem is not None
                    else ""
                )
                full_ref = f"{section_number}-{letter}"

                sub_cur = conn.execute(
                    "INSERT INTO qm_subsections"
                    " (section_id, letter, title, subsection_type,"
                    "  display_order, full_ref)"
                    " VALUES (?, ?, ?, ?, ?, ?)",
                    (section_id, letter, subsection_title, subsection_type,
                     subsection_order, full_ref),
                )
                subsection_id = sub_cur.lastrowid
                stats["subsections"] += 1

                # Process content blocks
                content_elem = subsection_elem.find("sis:Content", NS)
                if content_elem is None:
                    continue

                content_order = 0
                for child in content_elem:
                    result = _process_content_block(
                        conn, child, subsection_id, module_id, content_order, stats
                    )
                    if result is not None:
                        content_order = result

    conn.commit()
    logger.info(
        "Loaded module %d (v%s): %d sections, %d subsections, %d content blocks",
        stats["module_number"],
        stats["version"],
        stats["sections"],
        stats["subsections"],
        stats["content_blocks"],
    )
    return stats


# ---------------------------------------------------------------------------
# Prose reference detection
# ---------------------------------------------------------------------------

def detect_prose_references(conn: sqlite3.Connection) -> Dict[str, Any]:
    """
    Scan all content blocks for references embedded in prose text.

    Detects:
      - Internal section references (e.g. "Section 2.3A")
      - Code/standard references (ASME, AWS, NFPA, etc.)

    Returns:
        Dict with prose_xrefs count and prose_coderefs breakdown by org.
    """
    rows = conn.execute(
        "SELECT cb.id, cb.content, cb.subsection_id, sub.full_ref,"
        "       s.module_id, m.module_number"
        " FROM qm_content_blocks cb"
        " JOIN qm_subsections sub ON cb.subsection_id = sub.id"
        " JOIN qm_sections s ON sub.section_id = s.id"
        " JOIN qm_modules m ON s.module_id = m.id"
        " WHERE cb.content IS NOT NULL AND cb.content != ''"
    ).fetchall()

    prose_xrefs = 0
    prose_coderefs: Dict[str, int] = defaultdict(int)

    for row in rows:
        cb_id = row["id"]
        content = row["content"]
        subsection_id = row["subsection_id"]
        module_id = row["module_id"]

        # Detect section references
        for match in SECTION_REF_PATTERN.finditer(content):
            target_section = match.group(1)
            target_subsection = match.group(2)  # May be None
            target_module = int(target_section.split(".")[0])

            conn.execute(
                "INSERT INTO qm_cross_references"
                " (source_module_id, source_subsection_id, source_content_id,"
                "  target_module, target_section, target_subsection,"
                "  ref_type, detection_method, original_text)"
                " VALUES (?, ?, ?, ?, ?, ?, 'internal', 'prose_detected', ?)",
                (module_id, subsection_id, cb_id, target_module,
                 target_section, target_subsection, match.group(0)),
            )
            prose_xrefs += 1

        # Detect code/standard references
        for pattern, org in CODE_PATTERNS:
            for match in pattern.finditer(content):
                code = match.group(1)

                # Skip if already exists for this subsection
                existing = conn.execute(
                    "SELECT id FROM qm_code_references"
                    " WHERE subsection_id = ? AND code = ?",
                    (subsection_id, code),
                ).fetchone()

                if existing is None:
                    conn.execute(
                        "INSERT INTO qm_code_references"
                        " (subsection_id, content_block_id, code,"
                        "  organization, original_text, detection_method)"
                        " VALUES (?, ?, ?, ?, ?, 'prose_detected')",
                        (subsection_id, cb_id, code, org, match.group(0)),
                    )
                    prose_coderefs[org] += 1

    conn.commit()
    logger.info(
        "Prose detection: %d cross-refs, %d code refs",
        prose_xrefs,
        sum(prose_coderefs.values()),
    )
    return {"prose_xrefs": prose_xrefs, "prose_coderefs": dict(prose_coderefs)}


# ---------------------------------------------------------------------------
# Cross-reference validation
# ---------------------------------------------------------------------------

def validate_cross_references(conn: sqlite3.Connection) -> Dict[str, int]:
    """
    Mark cross-references as valid when their targets exist in the DB.

    Returns:
        Dict with valid_xrefs and invalid_xrefs counts.
    """
    # Reset all to invalid
    conn.execute("UPDATE qm_cross_references SET is_valid = 0")

    # Validate references without subsection target
    conn.execute(
        "UPDATE qm_cross_references SET is_valid = 1"
        " WHERE target_subsection IS NULL AND id IN ("
        "   SELECT cr.id FROM qm_cross_references cr"
        "   INNER JOIN qm_sections s ON s.section_number = cr.target_section"
        "   INNER JOIN qm_modules m ON s.module_id = m.id"
        "     AND m.module_number = cr.target_module"
        " )"
    )

    # Validate references with subsection target
    conn.execute(
        "UPDATE qm_cross_references SET is_valid = 1"
        " WHERE target_subsection IS NOT NULL AND id IN ("
        "   SELECT cr.id FROM qm_cross_references cr"
        "   INNER JOIN qm_sections s ON s.section_number = cr.target_section"
        "   INNER JOIN qm_modules m ON s.module_id = m.id"
        "     AND m.module_number = cr.target_module"
        "   INNER JOIN qm_subsections sub ON sub.section_id = s.id"
        "     AND sub.letter = cr.target_subsection"
        " )"
    )

    conn.commit()

    valid = conn.execute(
        "SELECT COUNT(*) AS n FROM qm_cross_references WHERE is_valid = 1"
    ).fetchone()["n"]
    invalid = conn.execute(
        "SELECT COUNT(*) AS n FROM qm_cross_references WHERE is_valid = 0"
    ).fetchone()["n"]

    logger.info("Cross-ref validation: %d valid, %d invalid", valid, invalid)
    return {"valid_xrefs": valid, "invalid_xrefs": invalid}


# ---------------------------------------------------------------------------
# FTS index management
# ---------------------------------------------------------------------------

def populate_fts_index(conn: sqlite3.Connection) -> int:
    """
    Rebuild the qm_content_fts full-text search index.

    Returns:
        Number of rows indexed.
    """
    conn.execute("DELETE FROM qm_content_fts")
    conn.execute(
        "INSERT INTO qm_content_fts"
        " (rowid, module_number, section_number, subsection_ref,"
        "  subsection_type, block_type, content)"
        " SELECT cb.id, m.module_number, s.section_number,"
        "        sub.full_ref, sub.subsection_type, cb.block_type, cb.content"
        " FROM qm_content_blocks cb"
        " JOIN qm_subsections sub ON cb.subsection_id = sub.id"
        " JOIN qm_sections s ON sub.section_id = s.id"
        " JOIN qm_modules m ON s.module_id = m.id"
        " WHERE cb.content IS NOT NULL AND cb.content != ''"
    )
    conn.commit()

    row = conn.execute("SELECT COUNT(*) AS n FROM qm_content_fts").fetchone()
    count = row["n"]
    logger.info("FTS index: %d rows indexed", count)
    return count


# ---------------------------------------------------------------------------
# Public API: load from file
# ---------------------------------------------------------------------------

def load_module_from_file(xml_path: str) -> Dict[str, Any]:
    """
    Load a single quality manual module XML file into the database.

    Reads the XML file, loads the module data, detects prose references,
    validates cross-references, and rebuilds the FTS index.

    Args:
        xml_path: Path to a quality manual XML module file.

    Returns:
        Dict containing load stats:
            module_number, version, title, sections, subsections,
            content_blocks, explicit_xrefs, explicit_coderefs,
            prose_xrefs, prose_coderefs, valid_xrefs, invalid_xrefs,
            fts_rows
    """
    path = Path(xml_path)
    if not path.exists():
        raise FileNotFoundError(f"XML file not found: {xml_path}")

    logger.info("Loading module from %s", path)
    xml_source = path.read_text(encoding="utf-8")

    with get_db() as conn:
        module_stats = _load_module_xml(conn, xml_source, xml_path=str(path))

        # Post-processing: prose detection, validation, FTS rebuild
        prose = detect_prose_references(conn)
        validation = validate_cross_references(conn)
        fts_rows = populate_fts_index(conn)

    # Merge all stats into a single result dict
    # Convert defaultdict to regular dict for serialization
    result = dict(module_stats)
    result["responsibilities"] = dict(result["responsibilities"])
    result.update(prose)
    result.update(validation)
    result["fts_rows"] = fts_rows
    return result


def load_modules_from_files(xml_paths: List[str]) -> Dict[str, Any]:
    """
    Load multiple quality manual module XML files into the database.

    Each module is loaded individually, then prose detection, validation,
    and FTS indexing are run once across all modules.

    Args:
        xml_paths: List of paths to quality manual XML module files.

    Returns:
        Dict with aggregated load report.
    """
    module_results: List[Dict[str, Any]] = []
    errors: List[Dict[str, str]] = []

    with get_db() as conn:
        for xml_path in xml_paths:
            path = Path(xml_path)
            if not path.exists():
                errors.append({"file": str(path), "error": "File not found"})
                logger.warning("File not found: %s", path)
                continue

            logger.info("Loading module from %s", path)
            try:
                xml_source = path.read_text(encoding="utf-8")
                stats = _load_module_xml(conn, xml_source, xml_path=str(path))
                stats["responsibilities"] = dict(stats["responsibilities"])
                module_results.append(stats)
            except ET.ParseError as e:
                errors.append({"file": str(path), "error": f"XML parse error: {e}"})
                logger.error("Failed to parse %s: %s", path, e)
            except Exception as e:
                errors.append({"file": str(path), "error": str(e)})
                logger.error("Error loading %s: %s", path, e)

        # Post-processing runs once after all modules loaded
        prose = detect_prose_references(conn)
        validation = validate_cross_references(conn)
        fts_rows = populate_fts_index(conn)

    return {
        "modules_loaded": len(module_results),
        "modules": module_results,
        "errors": errors,
        "prose_xrefs": prose["prose_xrefs"],
        "prose_coderefs": prose["prose_coderefs"],
        "valid_xrefs": validation["valid_xrefs"],
        "invalid_xrefs": validation["invalid_xrefs"],
        "fts_rows": fts_rows,
    }


# ---------------------------------------------------------------------------
# Public API: queries
# ---------------------------------------------------------------------------

def get_manual_summary() -> Dict[str, Any]:
    """
    Return a summary of all loaded quality manual modules.

    Returns:
        Dict with modules list and aggregate counts.
    """
    with get_db(readonly=True) as conn:
        modules = conn.execute(
            "SELECT module_number, version, effective_date, status, title,"
            " (SELECT COUNT(*) FROM qm_sections s WHERE s.module_id = m.id) AS section_count,"
            " (SELECT COUNT(*) FROM qm_subsections sub"
            "    JOIN qm_sections s2 ON sub.section_id = s2.id"
            "    WHERE s2.module_id = m.id) AS subsection_count"
            " FROM qm_modules m"
            " ORDER BY module_number"
        ).fetchall()

        total_content = conn.execute(
            "SELECT COUNT(*) AS n FROM qm_content_blocks"
        ).fetchone()["n"]

        total_xrefs = conn.execute(
            "SELECT COUNT(*) AS n FROM qm_cross_references"
        ).fetchone()["n"]

        valid_xrefs = conn.execute(
            "SELECT COUNT(*) AS n FROM qm_cross_references WHERE is_valid = 1"
        ).fetchone()["n"]

        total_coderefs = conn.execute(
            "SELECT COUNT(*) AS n FROM qm_code_references"
        ).fetchone()["n"]

        total_responsibilities = conn.execute(
            "SELECT COUNT(*) AS n FROM qm_responsibility_assignments"
        ).fetchone()["n"]

        fts_rows = conn.execute(
            "SELECT COUNT(*) AS n FROM qm_content_fts"
        ).fetchone()["n"]

    return {
        "modules": [dict(m) for m in modules],
        "total_modules": len(modules),
        "total_content_blocks": total_content,
        "total_cross_references": total_xrefs,
        "valid_cross_references": valid_xrefs,
        "total_code_references": total_coderefs,
        "total_responsibilities": total_responsibilities,
        "fts_indexed_rows": fts_rows,
    }


def search_content(query: str, limit: int = 20) -> List[Dict[str, Any]]:
    """
    Search quality manual content using full-text search.

    Args:
        query: FTS5 match expression (e.g. "welder", "safety AND inspection").
        limit: Maximum number of results.

    Returns:
        List of dicts with module_number, section_number, subsection_ref,
        subsection_type, block_type, and content snippet.
    """
    with get_db(readonly=True) as conn:
        rows = conn.execute(
            "SELECT module_number, section_number, subsection_ref,"
            "       subsection_type, block_type, content"
            " FROM qm_content_fts"
            " WHERE qm_content_fts MATCH ?"
            " LIMIT ?",
            (query, limit),
        ).fetchall()

    return [dict(r) for r in rows]


def get_module_detail(module_number: int) -> Optional[Dict[str, Any]]:
    """
    Get detailed information about a specific quality manual module.

    Args:
        module_number: The module number to look up.

    Returns:
        Dict with module info, sections list, cross-refs, and code-refs,
        or None if not found.
    """
    with get_db(readonly=True) as conn:
        mod = conn.execute(
            "SELECT * FROM qm_modules WHERE module_number = ?",
            (module_number,),
        ).fetchone()

        if not mod:
            return None

        module_id = mod["id"]
        result = dict(mod)
        # Remove raw XML from detail view to keep output manageable
        result.pop("xml_source", None)

        sections = conn.execute(
            "SELECT id, section_number, title, display_order,"
            "       related_sections, related_modules"
            " FROM qm_sections WHERE module_id = ?"
            " ORDER BY display_order",
            (module_id,),
        ).fetchall()
        result["sections"] = [dict(s) for s in sections]

        xrefs = conn.execute(
            "SELECT target_module, target_section, target_subsection,"
            "       ref_type, detection_method, original_text, is_valid"
            " FROM qm_cross_references WHERE source_module_id = ?"
            " ORDER BY target_section",
            (module_id,),
        ).fetchall()
        result["cross_references"] = [dict(x) for x in xrefs]

        coderefs = conn.execute(
            "SELECT cr.code, cr.organization, cr.code_section,"
            "       cr.original_text, cr.detection_method"
            " FROM qm_code_references cr"
            " JOIN qm_subsections sub ON cr.subsection_id = sub.id"
            " JOIN qm_sections s ON sub.section_id = s.id"
            " WHERE s.module_id = ?"
            " ORDER BY cr.organization, cr.code",
            (module_id,),
        ).fetchall()
        result["code_references"] = [dict(c) for c in coderefs]

    return result


def find_xml_files(directory: str = ".") -> List[str]:
    """
    Find all quality manual module XML files in a directory tree.

    Looks for files matching module*_output.xml or module*.xml.

    Args:
        directory: Root directory to search (default: current directory).

    Returns:
        Deduplicated list of resolved file path strings.
    """
    root = Path(directory)
    xml_files: List[Path] = []

    for pattern in ["module*_output.xml", "module*.xml"]:
        xml_files.extend(root.rglob(pattern))

    # Deduplicate while preserving order
    seen: set = set()
    unique: List[str] = []
    for f in xml_files:
        resolved = str(f.resolve())
        if resolved not in seen:
            seen.add(resolved)
            unique.append(resolved)

    return unique
