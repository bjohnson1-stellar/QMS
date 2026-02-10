"""
Reference Standard Content Extractor

Extracts text content from purchased reference standard PDFs and loads
into the database for full-text searching and cross-linking.

Ported from QC-DR/extract_reference.py into the QMS module structure.
"""

import re
import sqlite3
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from qms.core import get_db, get_logger

logger = get_logger("qms.references.extractor")


# ---------------------------------------------------------------------------
# Constants: clause and block patterns
# ---------------------------------------------------------------------------

CLAUSE_PATTERNS: Dict[str, str] = {
    "ISO": r"^(\d+(?:\.\d+)*)\s+(.+?)(?:\n|$)",
    "ASME": r"^((?:BPV|B31|QW|QG)[\s-]?\d+(?:\.\d+)*)\s*(.+?)(?:\n|$)",
    "AWS": r"^(\d+(?:\.\d+)*)\s+(.+?)(?:\n|$)",
    "NFPA": r"^(\d+(?:\.\d+)*)\s+(.+?)(?:\n|$)",
    "API": r"^(\d+(?:\.\d+)*)\s+(.+?)(?:\n|$)",
    "DEFAULT": r"^(\d+(?:\.\d+)*)\s+(.+?)(?:\n|$)",
}

BLOCK_PATTERNS: List[tuple] = [
    (r"^NOTE\s*\d*[:\s]", "Note"),
    (r"^WARNING[:\s]", "Warning"),
    (r"^CAUTION[:\s]", "Caution"),
    (r"^EXCEPTION[:\s]", "Note"),
    (r"^\([a-z]\)\s", "NumberedList"),
    (r"^[a-z]\)\s", "NumberedList"),
    (r"^\d+\)\s", "NumberedList"),
    (r"^[\u2022\u2023\u25e6\u2043\u2219\u2022\u00b7]\s", "BulletList"),
    (r"^-\s+(?=[A-Z])", "BulletList"),
    (r"^Table\s+\d+", "Table"),
    (r"^Figure\s+\d+", "Figure"),
    (r"^EXAMPLE[:\s]", "Example"),
]


# ---------------------------------------------------------------------------
# Text extraction
# ---------------------------------------------------------------------------

def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Extract text from PDF using pdftotext (poppler-utils).

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        Extracted text content.

    Raises:
        FileNotFoundError: If the PDF file or pdftotext binary is missing.
        RuntimeError: If pdftotext returns a non-zero exit code.
    """
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    try:
        result = subprocess.run(
            ["pdftotext", "-layout", str(path), "-"],
            capture_output=True,
            text=True,
            check=True,
        )
        logger.info("Extracted %s characters from %s", f"{len(result.stdout):,}", path.name)
        return result.stdout
    except FileNotFoundError:
        raise FileNotFoundError(
            "pdftotext not found. Install poppler-utils (or poppler for Windows)."
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"pdftotext failed: {exc.stderr}")


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def detect_publisher(standard_id: str) -> str:
    """
    Detect publisher prefix from a standard ID string.

    Args:
        standard_id: Standard identifier (e.g. 'ISO-9001-2015', 'ASME-B31.3-2022').

    Returns:
        Publisher key matching CLAUSE_PATTERNS, or 'DEFAULT'.
    """
    prefixes = [
        "ISO", "ASME", "AWS", "NFPA", "API",
        "OSHA", "ASTM", "ANSI", "IEC", "IEEE", "NEC", "UL",
    ]
    upper = standard_id.upper()
    for prefix in prefixes:
        if upper.startswith(prefix):
            return prefix
    return "DEFAULT"


def detect_block_type(text: str) -> str:
    """
    Detect the content-block type of a line of text.

    Args:
        text: A single line of content.

    Returns:
        Block type string (e.g. 'Paragraph', 'Note', 'Warning').
    """
    for pattern, block_type in BLOCK_PATTERNS:
        if re.match(pattern, text, re.IGNORECASE):
            return block_type
    return "Paragraph"


def parse_clauses(text: str, publisher: str) -> List[Dict[str, Any]]:
    """
    Parse raw extracted text into a list of clause dicts.

    Each clause dict has keys: number, title, content (list of lines), start_page.

    Args:
        text: Raw text extracted from a PDF.
        publisher: Publisher key for clause-number regex selection.

    Returns:
        List of clause dicts.
    """
    pattern = CLAUSE_PATTERNS.get(publisher, CLAUSE_PATTERNS["DEFAULT"])

    clauses: List[Dict[str, Any]] = []
    current_clause: Optional[Dict[str, Any]] = None
    current_content: List[str] = []
    page_num = 1

    for line in text.split("\n"):
        # Track page breaks (form-feed character)
        if "\f" in line:
            page_num += line.count("\f")
            line = line.replace("\f", "")

        # Skip empty lines but preserve paragraph breaks
        if not line.strip():
            if current_content:
                current_content.append("")
            continue

        # Check for new clause heading
        match = re.match(pattern, line.strip())
        if match:
            # Save previous clause
            if current_clause:
                clauses.append({
                    "number": current_clause["number"],
                    "title": current_clause["title"],
                    "content": current_content,
                    "start_page": current_clause["start_page"],
                })

            current_clause = {
                "number": match.group(1).strip(),
                "title": match.group(2).strip(),
                "start_page": page_num,
            }
            current_content = []

            # Content after clause header on same line
            remaining = line[match.end():].strip()
            if remaining:
                current_content.append(remaining)
        else:
            if current_clause:
                current_content.append(line.strip())

    # Save final clause
    if current_clause:
        clauses.append({
            "number": current_clause["number"],
            "title": current_clause["title"],
            "content": current_content,
            "start_page": current_clause["start_page"],
        })

    logger.info("Parsed %d clauses (publisher pattern: %s)", len(clauses), publisher)
    return clauses


def split_into_blocks(content_lines: List[str]) -> List[Dict[str, str]]:
    """
    Split a list of content lines into typed blocks.

    Args:
        content_lines: Lines of text belonging to a single clause.

    Returns:
        List of dicts with 'type' and 'content' keys.
    """
    blocks: List[Dict[str, str]] = []
    current_block: List[str] = []
    current_type = "Paragraph"

    for line in content_lines:
        if not line:
            # Empty line -- end current block
            if current_block:
                blocks.append({
                    "type": current_type,
                    "content": "\n".join(current_block),
                })
                current_block = []
                current_type = "Paragraph"
            continue

        line_type = detect_block_type(line)

        if line_type != current_type and current_block:
            blocks.append({
                "type": current_type,
                "content": "\n".join(current_block),
            })
            current_block = []

        current_type = line_type
        current_block.append(line)

    # Save final block
    if current_block:
        blocks.append({
            "type": current_type,
            "content": "\n".join(current_block),
        })

    return blocks


# ---------------------------------------------------------------------------
# Database operations
# ---------------------------------------------------------------------------

def get_reference(conn: sqlite3.Connection, standard_id: str) -> Optional[Dict[str, Any]]:
    """
    Look up a reference standard by its standard_id.

    Args:
        conn: Active database connection.
        standard_id: Standard identifier (e.g. 'ISO-9001-2015').

    Returns:
        Dict of reference record, or None if not found.
    """
    row = conn.execute(
        "SELECT * FROM qm_references WHERE standard_id = ?", (standard_id,)
    ).fetchone()
    return dict(row) if row else None


def list_references(
    conn: sqlite3.Connection,
    status: Optional[str] = None,
    extracted_only: bool = False,
) -> List[Dict[str, Any]]:
    """
    List reference standards from the database.

    Args:
        conn: Active database connection.
        status: Filter by status ('CURRENT', 'SUPERSEDED', 'WITHDRAWN'). None = all.
        extracted_only: If True, only return standards with extracted content.

    Returns:
        List of reference dicts.
    """
    query = "SELECT * FROM qm_references"
    conditions: List[str] = []
    params: List[Any] = []

    if status:
        conditions.append("status = ?")
        params.append(status)
    if extracted_only:
        conditions.append("content_extracted = 1")

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY standard_id"

    rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def list_clauses(
    conn: sqlite3.Connection,
    standard_id: str,
) -> List[Dict[str, Any]]:
    """
    List all extracted clauses for a given standard.

    Args:
        conn: Active database connection.
        standard_id: Standard identifier.

    Returns:
        List of clause dicts, or empty list if standard not found.
    """
    ref = get_reference(conn, standard_id)
    if not ref:
        return []

    rows = conn.execute(
        "SELECT * FROM ref_clauses WHERE reference_id = ? ORDER BY clause_number",
        (ref["id"],),
    ).fetchall()
    return [dict(r) for r in rows]


def search_content(
    conn: sqlite3.Connection,
    query: str,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """
    Full-text search across reference content blocks.

    Args:
        conn: Active database connection.
        query: FTS5 match expression.
        limit: Maximum results to return.

    Returns:
        List of matching content dicts.
    """
    rows = conn.execute(
        "SELECT standard_id, clause_number, clause_title, block_type, "
        "snippet(ref_content_fts, 4, '>>>', '<<<', '...', 48) AS snippet "
        "FROM ref_content_fts WHERE ref_content_fts MATCH ? LIMIT ?",
        (query, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def search_clauses(
    conn: sqlite3.Connection,
    query: str,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """
    Full-text search across reference clause metadata (titles, summaries).

    Args:
        conn: Active database connection.
        query: FTS5 match expression.
        limit: Maximum results to return.

    Returns:
        List of matching clause dicts.
    """
    rows = conn.execute(
        "SELECT standard_id, clause_number, clause_title, requirement_summary, applicability "
        "FROM ref_clauses_fts WHERE ref_clauses_fts MATCH ? LIMIT ?",
        (query, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def load_to_database(
    conn: sqlite3.Connection,
    standard_id: str,
    clauses: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Load extracted clauses and content blocks into the database.

    Replaces any existing content for the given standard_id.

    Args:
        conn: Active database connection (will be committed on success).
        standard_id: Standard identifier.
        clauses: Parsed clause list from parse_clauses().

    Returns:
        Dict with keys: success, clauses_loaded, blocks_loaded, message.

    Raises:
        ValueError: If the standard_id is not registered in qm_references.
    """
    ref = get_reference(conn, standard_id)
    if not ref:
        raise ValueError(
            f"Standard '{standard_id}' not found in qm_references. "
            "Register it first before extracting content."
        )

    reference_id = ref["id"]

    # Clear existing content for this standard
    conn.execute(
        "DELETE FROM ref_content_blocks "
        "WHERE clause_id IN (SELECT id FROM ref_clauses WHERE reference_id = ?)",
        (reference_id,),
    )
    conn.execute(
        "DELETE FROM ref_clauses WHERE reference_id = ?", (reference_id,)
    )
    conn.execute(
        "DELETE FROM ref_content_fts WHERE standard_id = ?", (standard_id,)
    )

    total_blocks = 0
    seen_clauses: Dict[str, int] = {}

    for clause in clauses:
        # Handle duplicate clause numbers by adding suffix
        clause_num = clause["number"]
        if clause_num in seen_clauses:
            seen_clauses[clause_num] += 1
            clause_num = f"{clause_num}_{seen_clauses[clause_num]}"
        else:
            seen_clauses[clause_num] = 1

        # Insert clause
        cursor = conn.execute(
            "INSERT INTO ref_clauses (reference_id, clause_number, clause_title) "
            "VALUES (?, ?, ?)",
            (reference_id, clause_num, clause["title"]),
        )
        clause_id = cursor.lastrowid

        # Split into blocks and insert
        blocks = split_into_blocks(clause["content"])

        for i, block in enumerate(blocks):
            if not block["content"].strip():
                continue

            conn.execute(
                "INSERT INTO ref_content_blocks "
                "(clause_id, block_type, content, page_number, display_order) "
                "VALUES (?, ?, ?, ?, ?)",
                (clause_id, block["type"], block["content"], clause["start_page"], i),
            )

            # Add to FTS index
            conn.execute(
                "INSERT INTO ref_content_fts "
                "(standard_id, clause_number, clause_title, block_type, content) "
                "VALUES (?, ?, ?, ?, ?)",
                (standard_id, clause_num, clause["title"], block["type"], block["content"]),
            )

            total_blocks += 1

    # Update extraction status on the reference record
    conn.execute(
        "UPDATE qm_references "
        "SET content_extracted = 1, extraction_date = ?, extraction_method = 'pdftotext' "
        "WHERE id = ?",
        (datetime.now().isoformat(), reference_id),
    )

    conn.commit()

    logger.info(
        "Loaded %d clauses with %d content blocks for %s",
        len(clauses), total_blocks, standard_id,
    )

    return {
        "success": True,
        "standard_id": standard_id,
        "clauses_loaded": len(clauses),
        "blocks_loaded": total_blocks,
        "message": f"Loaded {len(clauses)} clauses with {total_blocks} content blocks",
    }


# ---------------------------------------------------------------------------
# High-level orchestration
# ---------------------------------------------------------------------------

def extract_and_load(
    pdf_path: str,
    standard_id: str,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Full extraction pipeline: PDF -> parse -> load to database.

    Args:
        pdf_path: Path to the PDF file.
        standard_id: Standard identifier (e.g. 'ISO-9001-2015').
        dry_run: If True, parse only without writing to the database.

    Returns:
        Dict summarising the extraction results.
    """
    # 1. Extract text
    text = extract_text_from_pdf(pdf_path)

    # 2. Detect publisher and parse clauses
    publisher = detect_publisher(standard_id)
    clauses = parse_clauses(text, publisher)

    result: Dict[str, Any] = {
        "standard_id": standard_id,
        "publisher": publisher,
        "characters_extracted": len(text),
        "clauses_parsed": len(clauses),
        "sample_clauses": [
            {"number": c["number"], "title": c["title"]}
            for c in clauses[:5]
        ],
    }

    if dry_run:
        result["dry_run"] = True
        result["message"] = "Dry run complete. No data written to database."
        logger.info("Dry run: parsed %d clauses for %s", len(clauses), standard_id)
        return result

    # 3. Load to database
    with get_db() as conn:
        load_result = load_to_database(conn, standard_id, clauses)
        result.update(load_result)

    return result
