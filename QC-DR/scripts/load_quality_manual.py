#!/usr/bin/env python3
"""
SIS Quality Manual Database Loader

Loads Quality Manual XML module files into SQLite database tables.
Creates tables if they don't exist, handles re-runs gracefully,
detects prose references, and populates full-text search index.

Usage:
    python load_quality_manual.py                     # Scan cwd for module*.xml files
    python load_quality_manual.py file1.xml file2.xml # Load specific files
"""

import sqlite3
import xml.etree.ElementTree as ET
import re
import os
import sys
from pathlib import Path
from collections import defaultdict

# Add parent directory to path for sis_common import
SCRIPT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(SCRIPT_DIR.parent))

# Import shared utilities
from sis_common import get_db_path, get_logger, SIS_PATHS

DB_PATH = str(get_db_path())
logger = get_logger('load_quality_manual')

# XML namespace
NS = {'sis': 'http://stellarindustrial.com/quality-manual'}

# Regex patterns for prose reference detection
SECTION_REF_PATTERN = re.compile(r'Section\s+(\d+\.\d+)([A-Z])?', re.IGNORECASE)

CODE_PATTERNS = [
    (re.compile(r'\b(ASME\s+(?:BPV\s+)?Section\s+[IVX]+(?:\s*,\s*[A-Z0-9\-\.]+)?)', re.I), 'ASME'),
    (re.compile(r'\b(ASME\s+B\d+\.\d+)', re.I), 'ASME'),
    (re.compile(r'\b(AWS\s+[A-Z]\d+(?:\.\d+)?)', re.I), 'AWS'),
    (re.compile(r'\b(NFPA\s+\d+(?:\w+)?)', re.I), 'NFPA'),
    (re.compile(r'\b(NEC)\b', re.I), 'NFPA'),
    (re.compile(r'\b(OSHA\s+[\d\.]+)', re.I), 'OSHA'),
    (re.compile(r'\b(NIST)\b', re.I), 'NIST'),
    (re.compile(r'\b(API\s+\d+)', re.I), 'API'),
    (re.compile(r'\b(ASTM\s+[A-Z]\d+)', re.I), 'ASTM'),
    (re.compile(r'\b(ISO\s+\d+)', re.I), 'ISO'),
]


# =============================================================================
# DDL Statements
# =============================================================================

CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS qm_modules (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    module_number   INTEGER UNIQUE NOT NULL,
    version         TEXT,
    effective_date  TEXT,
    status          TEXT CHECK(status IN ('Draft','UnderReview','Approved','Superseded','Obsolete')),
    title           TEXT,
    description     TEXT,
    xml_source      TEXT,
    loaded_at       TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS qm_sections (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    module_id         INTEGER NOT NULL REFERENCES qm_modules(id) ON DELETE CASCADE,
    section_number    TEXT NOT NULL,
    title             TEXT,
    display_order     INTEGER,
    related_sections  TEXT,
    related_modules   TEXT,
    UNIQUE(module_id, section_number)
);

CREATE TABLE IF NOT EXISTS qm_subsections (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    section_id       INTEGER NOT NULL REFERENCES qm_sections(id) ON DELETE CASCADE,
    letter           TEXT NOT NULL,
    title            TEXT,
    subsection_type  TEXT CHECK(subsection_type IN (
                         'PurposeAndScope','Requirements','Procedures',
                         'Responsibilities','Documentation',
                         'VerificationAndCompliance','General'
                     )),
    display_order    INTEGER,
    full_ref         TEXT,
    UNIQUE(section_id, letter)
);

CREATE TABLE IF NOT EXISTS qm_content_blocks (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    subsection_id   INTEGER NOT NULL REFERENCES qm_subsections(id) ON DELETE CASCADE,
    block_type      TEXT NOT NULL CHECK(block_type IN (
                        'HeadingParagraph','Paragraph','SubHeading',
                        'BulletList','NumberedList','Table','Note',
                        'ResponsibilityBlock'
                    )),
    content         TEXT,
    level           INTEGER,
    display_order   INTEGER,
    xml_fragment    TEXT
);

CREATE TABLE IF NOT EXISTS qm_cross_references (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    source_module_id       INTEGER REFERENCES qm_modules(id),
    source_subsection_id   INTEGER REFERENCES qm_subsections(id),
    source_content_id      INTEGER REFERENCES qm_content_blocks(id),
    target_module          INTEGER,
    target_section         TEXT,
    target_subsection      TEXT,
    ref_type               TEXT CHECK(ref_type IN ('internal','external','code','standard')),
    detection_method       TEXT CHECK(detection_method IN ('explicit','prose_detected')),
    original_text          TEXT,
    is_valid               INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS qm_code_references (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    subsection_id     INTEGER REFERENCES qm_subsections(id),
    content_block_id  INTEGER REFERENCES qm_content_blocks(id),
    code              TEXT NOT NULL,
    organization      TEXT,
    code_section      TEXT,
    original_text     TEXT,
    detection_method  TEXT CHECK(detection_method IN ('explicit','prose_detected'))
);

CREATE TABLE IF NOT EXISTS qm_responsibility_assignments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    subsection_id   INTEGER REFERENCES qm_subsections(id),
    role            TEXT NOT NULL,
    responsibility  TEXT,
    display_order   INTEGER
);
"""

CREATE_INDEXES_SQL = """
CREATE INDEX IF NOT EXISTS idx_sections_module       ON qm_sections(module_id);
CREATE INDEX IF NOT EXISTS idx_sections_number       ON qm_sections(section_number);
CREATE INDEX IF NOT EXISTS idx_subsections_section   ON qm_subsections(section_id);
CREATE INDEX IF NOT EXISTS idx_subsections_type      ON qm_subsections(subsection_type);
CREATE INDEX IF NOT EXISTS idx_subsections_fullref   ON qm_subsections(full_ref);
CREATE INDEX IF NOT EXISTS idx_content_subsection    ON qm_content_blocks(subsection_id);
CREATE INDEX IF NOT EXISTS idx_content_type          ON qm_content_blocks(block_type);
CREATE INDEX IF NOT EXISTS idx_xref_source_module    ON qm_cross_references(source_module_id);
CREATE INDEX IF NOT EXISTS idx_xref_target           ON qm_cross_references(target_section);
CREATE INDEX IF NOT EXISTS idx_xref_valid            ON qm_cross_references(is_valid);
CREATE INDEX IF NOT EXISTS idx_coderef_code          ON qm_code_references(code);
CREATE INDEX IF NOT EXISTS idx_coderef_org           ON qm_code_references(organization);
CREATE INDEX IF NOT EXISTS idx_responsibility_role   ON qm_responsibility_assignments(role);
"""

CREATE_FTS_SQL = """
-- Note: Using standalone FTS5 table (not external content) because the denormalized
-- columns (module_number, section_number, etc.) come from JOINs, not qm_content_blocks directly.
-- This duplicates some storage but ensures correct operation.
CREATE VIRTUAL TABLE IF NOT EXISTS qm_content_fts USING fts5(
    module_number,
    section_number,
    subsection_ref,
    subsection_type,
    block_type,
    content,
    tokenize='porter unicode61'
);
"""


# =============================================================================
# Helper Functions
# =============================================================================

def get_local_tag(elem):
    """Strip namespace from element tag to get local name."""
    tag = elem.tag
    if '}' in tag:
        return tag.split('}')[1]
    return tag


def get_element_text(elem):
    """Get direct text content of element, or empty string if None."""
    return elem.text.strip() if elem.text else ''


def get_full_text(elem):
    """Get all text content including nested elements."""
    return ''.join(elem.itertext()).strip()


def serialize_table(table_elem):
    """Convert a Table element to readable text representation."""
    lines = []

    # Look for header row
    header = table_elem.find('.//sis:HeaderRow', NS) or table_elem.find('.//sis:Header', NS)
    if header is not None:
        cells = []
        for cell in header.findall('.//sis:Cell', NS) or header.findall('.//sis:HeaderCell', NS):
            cells.append(get_full_text(cell))
        if cells:
            lines.append(' | '.join(cells))
            lines.append('-' * 40)

    # Look for data rows
    for row in table_elem.findall('.//sis:Row', NS) or table_elem.findall('.//sis:DataRow', NS):
        cells = []
        for cell in row.findall('.//sis:Cell', NS):
            cells.append(get_full_text(cell))
        if cells:
            lines.append(' | '.join(cells))

    return '\n'.join(lines) if lines else get_full_text(table_elem)


# =============================================================================
# Database Operations
# =============================================================================

def create_tables(conn):
    """Create all required tables, indexes, and FTS virtual table."""
    cursor = conn.cursor()

    # Enable foreign key support
    cursor.execute("PRAGMA foreign_keys = ON")

    # Create main tables
    cursor.executescript(CREATE_TABLES_SQL)

    # Create indexes
    cursor.executescript(CREATE_INDEXES_SQL)

    # Create FTS virtual table
    cursor.executescript(CREATE_FTS_SQL)

    conn.commit()


def delete_module_data(conn, module_number):
    """Delete all existing data for a module before re-loading."""
    cursor = conn.cursor()

    # Get the module ID if it exists
    cursor.execute("SELECT id FROM qm_modules WHERE module_number = ?", (module_number,))
    row = cursor.fetchone()

    if row:
        module_id = row[0]

        # Delete in reverse order of dependencies
        # cross_references and code_references have FKs to content_blocks, so delete them first
        cursor.execute("""
            DELETE FROM qm_cross_references WHERE source_module_id = ?
        """, (module_id,))

        cursor.execute("""
            DELETE FROM qm_code_references WHERE subsection_id IN (
                SELECT sub.id FROM qm_subsections sub
                JOIN qm_sections s ON sub.section_id = s.id
                WHERE s.module_id = ?
            )
        """, (module_id,))

        cursor.execute("""
            DELETE FROM qm_responsibility_assignments WHERE subsection_id IN (
                SELECT sub.id FROM qm_subsections sub
                JOIN qm_sections s ON sub.section_id = s.id
                WHERE s.module_id = ?
            )
        """, (module_id,))

        # Now safe to delete content_blocks (no more FK references to it)
        cursor.execute("""
            DELETE FROM qm_content_blocks WHERE subsection_id IN (
                SELECT sub.id FROM qm_subsections sub
                JOIN qm_sections s ON sub.section_id = s.id
                WHERE s.module_id = ?
            )
        """, (module_id,))

        cursor.execute("""
            DELETE FROM qm_subsections WHERE section_id IN (
                SELECT id FROM qm_sections WHERE module_id = ?
            )
        """, (module_id,))

        cursor.execute("DELETE FROM qm_sections WHERE module_id = ?", (module_id,))
        cursor.execute("DELETE FROM qm_modules WHERE id = ?", (module_id,))

    conn.commit()


# =============================================================================
# XML Parsing and Loading
# =============================================================================

def load_module(conn, xml_path, stats):
    """Parse and load a single XML module file."""
    cursor = conn.cursor()

    # Read the XML file
    with open(xml_path, 'r', encoding='utf-8') as f:
        xml_source = f.read()

    # Parse XML
    try:
        root = ET.fromstring(xml_source)
    except ET.ParseError as e:
        print(f"  ERROR: Failed to parse {xml_path}: {e}")
        return None

    # Extract module attributes
    module_number = int(root.get('moduleNumber', 0))
    version = root.get('version', '')
    effective_date = root.get('effectiveDate', '')
    status = root.get('status', '')

    # Extract title and description from DocumentHeader
    header = root.find('.//sis:DocumentHeader', NS)
    title = ''
    description = ''
    if header is not None:
        title_elem = header.find('sis:ModuleTitle', NS)
        desc_elem = header.find('sis:ModuleDescription', NS)
        if title_elem is not None:
            title = get_element_text(title_elem)
        if desc_elem is not None:
            description = get_full_text(desc_elem)

    # Delete existing data for this module (for safe re-runs)
    delete_module_data(conn, module_number)

    # Insert module
    cursor.execute("""
        INSERT INTO qm_modules (module_number, version, effective_date, status, title, description, xml_source)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (module_number, version, effective_date, status, title, description, xml_source))

    module_id = cursor.lastrowid

    # Initialize module stats
    module_stats = {
        'module_number': module_number,
        'version': version,
        'sections': 0,
        'subsections': 0,
        'content_blocks': 0,
        'explicit_xrefs': 0,
        'explicit_coderefs': 0,
        'responsibilities': defaultdict(int),
    }

    # Process sections
    sections = root.find('.//sis:Sections', NS)
    if sections is not None:
        for section_order, section_elem in enumerate(sections.findall('sis:Section', NS)):
            section_number = section_elem.get('number', '')
            section_title_elem = section_elem.find('sis:Title', NS)
            section_title = get_element_text(section_title_elem) if section_title_elem is not None else ''

            related_sections = section_elem.get('relatedSections', '')
            related_modules = section_elem.get('relatedModules', '')

            cursor.execute("""
                INSERT INTO qm_sections (module_id, section_number, title, display_order, related_sections, related_modules)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (module_id, section_number, section_title, section_order, related_sections, related_modules))

            section_id = cursor.lastrowid
            module_stats['sections'] += 1

            # Process subsections
            subsections_elem = section_elem.find('sis:Subsections', NS)
            if subsections_elem is not None:
                for subsection_order, subsection_elem in enumerate(subsections_elem.findall('sis:Subsection', NS)):
                    letter = subsection_elem.get('letter', '')
                    subsection_type = subsection_elem.get('subsectionType', 'General')

                    subsection_title_elem = subsection_elem.find('sis:Title', NS)
                    subsection_title = get_element_text(subsection_title_elem) if subsection_title_elem is not None else ''

                    full_ref = f"{section_number}-{letter}"

                    cursor.execute("""
                        INSERT INTO qm_subsections (section_id, letter, title, subsection_type, display_order, full_ref)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (section_id, letter, subsection_title, subsection_type, subsection_order, full_ref))

                    subsection_id = cursor.lastrowid
                    module_stats['subsections'] += 1

                    # Process content
                    content_elem = subsection_elem.find('sis:Content', NS)
                    if content_elem is not None:
                        content_order = 0
                        for child in content_elem:
                            tag = get_local_tag(child)

                            # Skip CrossReference and CodeReference - handle separately
                            if tag == 'CrossReference':
                                # Insert explicit cross-reference
                                target_module = child.get('targetModule')
                                target_section = child.get('targetSection', '')
                                target_subsection = child.get('targetSubsection', '')
                                ref_type = child.get('refType', 'internal')
                                original_text = get_full_text(child)

                                cursor.execute("""
                                    INSERT INTO qm_cross_references
                                    (source_module_id, source_subsection_id, target_module, target_section, target_subsection, ref_type, detection_method, original_text)
                                    VALUES (?, ?, ?, ?, ?, ?, 'explicit', ?)
                                """, (module_id, subsection_id, target_module, target_section, target_subsection or None, ref_type, original_text))

                                module_stats['explicit_xrefs'] += 1
                                continue

                            if tag == 'CodeReference':
                                # Insert explicit code reference
                                code = child.get('code', '')
                                organization = child.get('organization', '')
                                code_section = child.get('section', '')
                                original_text = get_full_text(child)

                                cursor.execute("""
                                    INSERT INTO qm_code_references
                                    (subsection_id, code, organization, code_section, original_text, detection_method)
                                    VALUES (?, ?, ?, ?, ?, 'explicit')
                                """, (subsection_id, code, organization, code_section, original_text))

                                module_stats['explicit_coderefs'] += 1
                                continue

                            # Determine block type and content
                            block_type = None
                            content = None
                            level = None
                            xml_fragment = ET.tostring(child, encoding='unicode')

                            if tag == 'HeadingParagraph':
                                block_type = 'HeadingParagraph'
                                content = get_full_text(child)
                                level = child.get('level')
                                if level:
                                    level = int(level)

                            elif tag == 'Paragraph':
                                block_type = 'Paragraph'
                                content = get_full_text(child)
                                # Skip "END OF SECTION" paragraphs
                                if content.strip().upper() == 'END OF SECTION':
                                    continue

                            elif tag == 'SubHeading':
                                block_type = 'SubHeading'
                                content = get_full_text(child)
                                level = child.get('level')
                                if level:
                                    level = int(level)

                            elif tag == 'BulletList':
                                block_type = 'BulletList'
                                items = [get_full_text(item) for item in child.findall('sis:Item', NS)]
                                content = '\n'.join(items)

                            elif tag == 'NumberedList':
                                block_type = 'NumberedList'
                                items = [get_full_text(item) for item in child.findall('sis:Item', NS)]
                                content = '\n'.join(items)

                            elif tag == 'Table':
                                block_type = 'Table'
                                content = serialize_table(child)

                            elif tag == 'Note':
                                block_type = 'Note'
                                content = get_full_text(child)

                            elif tag == 'ResponsibilityBlock':
                                block_type = 'ResponsibilityBlock'
                                role_elem = child.find('sis:Role', NS)
                                role = get_element_text(role_elem) if role_elem is not None else ''

                                resp_elem = child.find('sis:Responsibilities', NS)
                                items = []
                                if resp_elem is not None:
                                    items = [get_full_text(item) for item in resp_elem.findall('sis:Item', NS)]

                                content = role + '\n' + '\n'.join(items)

                                # Also insert responsibility assignments
                                for resp_order, item_text in enumerate(items):
                                    cursor.execute("""
                                        INSERT INTO qm_responsibility_assignments (subsection_id, role, responsibility, display_order)
                                        VALUES (?, ?, ?, ?)
                                    """, (subsection_id, role, item_text, resp_order))
                                    module_stats['responsibilities'][role] += 1

                            else:
                                # Unknown tag - skip or handle as paragraph
                                continue

                            if block_type:
                                cursor.execute("""
                                    INSERT INTO qm_content_blocks (subsection_id, block_type, content, level, display_order, xml_fragment)
                                    VALUES (?, ?, ?, ?, ?, ?)
                                """, (subsection_id, block_type, content, level, content_order, xml_fragment))

                                module_stats['content_blocks'] += 1
                                content_order += 1

    conn.commit()
    stats['modules'].append(module_stats)
    return module_id


def detect_prose_references(conn, stats):
    """Scan content blocks for references in prose text."""
    cursor = conn.cursor()

    # Get all content blocks with their context
    cursor.execute("""
        SELECT cb.id, cb.content, cb.subsection_id, sub.full_ref, s.module_id, m.module_number
        FROM qm_content_blocks cb
        JOIN qm_subsections sub ON cb.subsection_id = sub.id
        JOIN qm_sections s ON sub.section_id = s.id
        JOIN qm_modules m ON s.module_id = m.id
        WHERE cb.content IS NOT NULL AND cb.content != ''
    """)

    rows = cursor.fetchall()

    prose_xrefs = 0
    prose_coderefs = defaultdict(int)

    for cb_id, content, subsection_id, full_ref, module_id, module_number in rows:
        # Detect section references
        for match in SECTION_REF_PATTERN.finditer(content):
            target_section = match.group(1)
            target_subsection = match.group(2)  # May be None

            # Infer target module from section number (e.g., "2.3" -> module 2)
            target_module = int(target_section.split('.')[0])

            cursor.execute("""
                INSERT INTO qm_cross_references
                (source_module_id, source_subsection_id, source_content_id, target_module, target_section, target_subsection, ref_type, detection_method, original_text)
                VALUES (?, ?, ?, ?, ?, ?, 'internal', 'prose_detected', ?)
            """, (module_id, subsection_id, cb_id, target_module, target_section, target_subsection, match.group(0)))

            prose_xrefs += 1

        # Detect code/standard references
        for pattern, org in CODE_PATTERNS:
            for match in pattern.finditer(content):
                code = match.group(1)

                # Check if this exact code reference already exists for this subsection
                cursor.execute("""
                    SELECT id FROM qm_code_references
                    WHERE subsection_id = ? AND code = ?
                """, (subsection_id, code))

                if cursor.fetchone() is None:
                    cursor.execute("""
                        INSERT INTO qm_code_references
                        (subsection_id, content_block_id, code, organization, original_text, detection_method)
                        VALUES (?, ?, ?, ?, ?, 'prose_detected')
                    """, (subsection_id, cb_id, code, org, match.group(0)))

                    prose_coderefs[org] += 1

    conn.commit()
    stats['prose_xrefs'] = prose_xrefs
    stats['prose_coderefs'] = dict(prose_coderefs)


def validate_cross_references(conn, stats):
    """Mark cross-references as valid if their targets exist."""
    cursor = conn.cursor()

    # Reset all to invalid first
    cursor.execute("UPDATE qm_cross_references SET is_valid = 0")

    # Validate references without subsection target
    cursor.execute("""
        UPDATE qm_cross_references
        SET is_valid = 1
        WHERE target_subsection IS NULL AND id IN (
            SELECT cr.id
            FROM qm_cross_references cr
            INNER JOIN qm_sections s ON s.section_number = cr.target_section
            INNER JOIN qm_modules m ON s.module_id = m.id AND m.module_number = cr.target_module
        )
    """)

    # Validate references with subsection target
    cursor.execute("""
        UPDATE qm_cross_references
        SET is_valid = 1
        WHERE target_subsection IS NOT NULL AND id IN (
            SELECT cr.id
            FROM qm_cross_references cr
            INNER JOIN qm_sections s ON s.section_number = cr.target_section
            INNER JOIN qm_modules m ON s.module_id = m.id AND m.module_number = cr.target_module
            INNER JOIN qm_subsections sub ON sub.section_id = s.id AND sub.letter = cr.target_subsection
        )
    """)

    conn.commit()

    # Get validation stats
    cursor.execute("SELECT COUNT(*) FROM qm_cross_references WHERE is_valid = 1")
    stats['valid_xrefs'] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM qm_cross_references WHERE is_valid = 0")
    stats['invalid_xrefs'] = cursor.fetchone()[0]


def populate_fts_index(conn, stats):
    """Populate the full-text search index."""
    cursor = conn.cursor()

    # Clear existing FTS data
    cursor.execute("DELETE FROM qm_content_fts")

    # Populate with joined data
    cursor.execute("""
        INSERT INTO qm_content_fts(rowid, module_number, section_number, subsection_ref, subsection_type, block_type, content)
        SELECT
            cb.id,
            m.module_number,
            s.section_number,
            sub.full_ref,
            sub.subsection_type,
            cb.block_type,
            cb.content
        FROM qm_content_blocks cb
        JOIN qm_subsections sub ON cb.subsection_id = sub.id
        JOIN qm_sections s ON sub.section_id = s.id
        JOIN qm_modules m ON s.module_id = m.id
        WHERE cb.content IS NOT NULL AND cb.content != ''
    """)

    conn.commit()

    # Get row count
    cursor.execute("SELECT COUNT(*) FROM qm_content_fts")
    stats['fts_rows'] = cursor.fetchone()[0]


def print_report(conn, stats):
    """Print the summary report."""
    cursor = conn.cursor()

    print("\n" + "=" * 50)
    print("=== SIS Quality Manual Database Load Report ===")
    print("=" * 50)
    print(f"Database: {DB_PATH}")
    print()

    # Module summary
    print(f"Modules loaded: {len(stats['modules'])}")
    for mod in stats['modules']:
        print(f"  Module {mod['module_number']} (v{mod['version']}): "
              f"{mod['sections']} sections, {mod['subsections']} subsections, "
              f"{mod['content_blocks']} content blocks")
    print()

    # Reference detection summary
    total_explicit_xrefs = sum(m['explicit_xrefs'] for m in stats['modules'])
    total_xrefs = total_explicit_xrefs + stats.get('prose_xrefs', 0)

    print("Reference detection:")
    print(f"  Cross-references:    {total_xrefs} total ({total_explicit_xrefs} explicit, {stats.get('prose_xrefs', 0)} prose-detected)")
    print(f"    Valid:             {stats.get('valid_xrefs', 0)}")
    print(f"    Unresolvable:      {stats.get('invalid_xrefs', 0)} (target module not loaded)")

    # Code references
    total_explicit_coderefs = sum(m['explicit_coderefs'] for m in stats['modules'])
    prose_coderefs = stats.get('prose_coderefs', {})
    total_prose_coderefs = sum(prose_coderefs.values())
    total_coderefs = total_explicit_coderefs + total_prose_coderefs

    print(f"  Code references:     {total_coderefs} total ({total_explicit_coderefs} explicit, {total_prose_coderefs} prose-detected)")
    if prose_coderefs:
        code_summary = ', '.join(f"{org}: {count}" for org, count in sorted(prose_coderefs.items()))
        print(f"    {code_summary}")
    print()

    # Responsibility assignments
    all_responsibilities = defaultdict(int)
    for mod in stats['modules']:
        for role, count in mod['responsibilities'].items():
            all_responsibilities[role] += count

    total_resp = sum(all_responsibilities.values())
    print(f"Responsibility assignments: {total_resp}")
    for role, count in sorted(all_responsibilities.items(), key=lambda x: -x[1]):
        print(f"  {role}: {count}")
    print()

    # FTS index
    print(f"FTS index: {stats.get('fts_rows', 0)} rows indexed")
    print()

    # Verification queries
    print("Verification queries:")

    cursor.execute("SELECT count(*) FROM qm_content_fts WHERE content MATCH 'welder'")
    welder_count = cursor.fetchone()[0]
    print(f"  SELECT count(*) FROM qm_content_fts WHERE content MATCH 'welder'; -> {welder_count} rows")

    cursor.execute("SELECT count(*) FROM qm_cross_references WHERE is_valid = 0")
    invalid_count = cursor.fetchone()[0]
    print(f"  SELECT count(*) FROM qm_cross_references WHERE is_valid = 0; -> {invalid_count} rows")

    print()


def find_xml_files():
    """Find all module XML files in current directory and subdirectories."""
    xml_files = []

    for pattern in ['module*_output.xml', 'module*.xml']:
        xml_files.extend(Path('.').rglob(pattern))

    # Remove duplicates while preserving order
    seen = set()
    unique_files = []
    for f in xml_files:
        resolved = f.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique_files.append(f)

    return unique_files


def main():
    """Main entry point."""
    # Determine XML files to process
    if len(sys.argv) > 1:
        xml_files = [Path(f) for f in sys.argv[1:]]
    else:
        xml_files = find_xml_files()

    # Connect to database
    conn = sqlite3.connect(DB_PATH)

    # Enable foreign keys
    conn.execute("PRAGMA foreign_keys = ON")

    # Create tables
    print(f"Creating tables in {DB_PATH}...")
    create_tables(conn)

    if not xml_files:
        print("\nNo XML files found matching module*_output.xml or module*.xml")
        print("Tables have been created. Re-run with XML files present to load data.")
        conn.close()
        return

    print(f"\nFound {len(xml_files)} XML file(s) to process:")
    for f in xml_files:
        print(f"  {f}")
    print()

    # Initialize stats
    stats = {
        'modules': [],
    }

    # Load each module
    for xml_file in xml_files:
        print(f"Loading {xml_file}...")
        try:
            load_module(conn, xml_file, stats)
            print(f"  Done.")
        except Exception as e:
            print(f"  ERROR: {e}")

    # Detect prose references
    print("\nDetecting prose references...")
    detect_prose_references(conn, stats)
    print("  Done.")

    # Validate cross-references
    print("Validating cross-references...")
    validate_cross_references(conn, stats)
    print("  Done.")

    # Populate FTS index
    print("Populating FTS index...")
    populate_fts_index(conn, stats)
    print("  Done.")

    # Print report
    print_report(conn, stats)

    conn.close()


if __name__ == '__main__':
    main()
