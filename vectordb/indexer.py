"""
VectorDB Content Indexer

Reads content from quality.db (Quality Manual, reference standards,
specifications, drawing extractions) and indexes it into ChromaDB
collections for semantic search.

Run after loading new content into the SQLite database.
"""

from typing import Any, Dict, List

from qms.core import get_db, get_logger

logger = get_logger("qms.vectordb.indexer")

# Batch size for ChromaDB upserts
_BATCH_SIZE = 100

# Standard collection descriptions
COLLECTIONS: Dict[str, str] = {
    "qm_content": "Quality Manual content blocks from XML modules",
    "ref_clauses": "Reference standard clauses (ASME, AWS, ISO, etc.)",
    "specifications": "Project specification requirements and items",
    "procedures": "SOPs, Work Instructions, and Policies",
    "drawings": "Drawing metadata and extracted annotations",
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _require_chromadb():
    """Raise a clear error if chromadb is not installed."""
    try:
        import chromadb  # noqa: F401
    except ImportError:
        raise ImportError(
            "chromadb is required for indexing. Install: pip install chromadb"
        )


def _get_collection(name: str):
    """Get or create a ChromaDB collection via the search module."""
    from qms.vectordb.search import get_chromadb_collection

    return get_chromadb_collection(name, description=COLLECTIONS.get(name))


def _clear_collection(collection) -> None:
    """Delete all documents from a collection."""
    existing = collection.count()
    if existing > 0:
        logger.info("Clearing %d existing documents from %s...", existing, collection.name)
        all_docs = collection.get()
        if all_docs["ids"]:
            collection.delete(ids=all_docs["ids"])


def _index_batch(collection, documents: List[str], metadatas: List[dict], ids: List[str]) -> None:
    """Add documents to a collection in batches."""
    from qms.vectordb.search import add_documents_to_collection

    for i in range(0, len(documents), _BATCH_SIZE):
        batch_docs = documents[i : i + _BATCH_SIZE]
        batch_meta = metadatas[i : i + _BATCH_SIZE]
        batch_ids = ids[i : i + _BATCH_SIZE]

        collection.add(documents=batch_docs, metadatas=batch_meta, ids=batch_ids)
        logger.info(
            "Indexed %s batch %d: %d documents",
            collection.name,
            i // _BATCH_SIZE + 1,
            len(batch_docs),
        )


# ---------------------------------------------------------------------------
# Quality Manual
# ---------------------------------------------------------------------------

def index_qm_content(rebuild: bool = False) -> int:
    """
    Index Quality Manual content blocks into the ``qm_content`` collection.

    Args:
        rebuild: Delete existing documents and rebuild from scratch.

    Returns:
        Number of new documents indexed.
    """
    _require_chromadb()
    collection = _get_collection("qm_content")

    if rebuild:
        _clear_collection(collection)

    with get_db(readonly=True) as conn:
        cursor = conn.execute("""
            SELECT
                cb.id,
                m.module_number,
                s.section_number,
                sub.full_ref,
                sub.title as subsection_title,
                sub.subsection_type,
                cb.block_type,
                cb.content
            FROM qm_content_blocks cb
            JOIN qm_subsections sub ON cb.subsection_id = sub.id
            JOIN qm_sections s ON sub.section_id = s.id
            JOIN qm_modules m ON s.module_id = m.id
            WHERE cb.content IS NOT NULL
              AND cb.content != ''
              AND length(cb.content) > 20
            ORDER BY m.module_number, s.section_number, sub.letter, cb.display_order
        """)
        rows = cursor.fetchall()

    if not rows:
        logger.warning("No QM content found to index")
        return 0

    documents: List[str] = []
    metadatas: List[dict] = []
    ids: List[str] = []

    for row in rows:
        doc_id = f"qm_{row['module_number']}_{row['full_ref']}_{row['id']}"

        if not rebuild:
            existing = collection.get(ids=[doc_id])
            if existing["ids"]:
                continue

        doc_text = f"{row['subsection_title']}\n{row['content']}"
        documents.append(doc_text)
        metadatas.append({
            "source": "quality_manual",
            "module": row["module_number"],
            "section": row["section_number"],
            "subsection": row["full_ref"],
            "subsection_type": row["subsection_type"] or "General",
            "block_type": row["block_type"],
            "db_id": row["id"],
        })
        ids.append(doc_id)

    if documents:
        _index_batch(collection, documents, metadatas, ids)

    total = collection.count()
    logger.info("QM content indexed: %d total documents", total)
    return len(documents)


# ---------------------------------------------------------------------------
# Reference Standards
# ---------------------------------------------------------------------------

def index_ref_clauses(rebuild: bool = False) -> int:
    """
    Index reference standard clauses into the ``ref_clauses`` collection.

    Args:
        rebuild: Delete existing documents and rebuild from scratch.

    Returns:
        Number of new documents indexed.
    """
    _require_chromadb()
    collection = _get_collection("ref_clauses")

    if rebuild:
        _clear_collection(collection)

    with get_db(readonly=True) as conn:
        # Check table exists
        if not conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='ref_clauses'"
        ).fetchone():
            logger.warning("ref_clauses table not found - skipping")
            return 0

        cursor = conn.execute("""
            SELECT
                c.id,
                r.standard_id,
                r.title as standard_title,
                COALESCE(rs.section_title, 'General') as section_name,
                c.clause_number,
                c.clause_title,
                cb.block_type,
                cb.content
            FROM ref_clauses c
            JOIN ref_content_blocks cb ON cb.clause_id = c.id
            LEFT JOIN ref_sections rs ON c.section_id = rs.id
            JOIN qm_references r ON c.reference_id = r.id
            WHERE cb.content IS NOT NULL
              AND cb.content != ''
              AND length(cb.content) > 20
            ORDER BY r.standard_id, c.clause_number, cb.display_order
        """)
        rows = cursor.fetchall()

    if not rows:
        logger.warning("No reference clauses found to index")
        return 0

    documents: List[str] = []
    metadatas: List[dict] = []
    ids: List[str] = []

    for idx, row in enumerate(rows):
        doc_id = f"ref_{row['standard_id']}_{row['clause_number']}_{idx}"

        if not rebuild:
            existing = collection.get(ids=[doc_id])
            if existing["ids"]:
                continue

        doc_text = f"{row['clause_number']} {row['clause_title']}\n{row['content']}"
        documents.append(doc_text)
        metadatas.append({
            "source": "reference_standard",
            "standard_id": row["standard_id"],
            "standard_title": row["standard_title"],
            "section": row["section_name"],
            "clause_number": row["clause_number"],
            "clause_title": row["clause_title"],
            "block_type": row["block_type"],
            "db_id": row["id"],
        })
        ids.append(doc_id)

    if documents:
        _index_batch(collection, documents, metadatas, ids)

    total = collection.count()
    logger.info("Reference clauses indexed: %d total documents", total)
    return len(documents)


# ---------------------------------------------------------------------------
# Specifications
# ---------------------------------------------------------------------------

def index_specifications(rebuild: bool = False) -> int:
    """
    Index specification items into the ``specifications`` collection.

    Args:
        rebuild: Delete existing documents and rebuild from scratch.

    Returns:
        Number of new documents indexed.
    """
    _require_chromadb()
    collection = _get_collection("specifications")

    if rebuild:
        _clear_collection(collection)

    with get_db(readonly=True) as conn:
        if not conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='spec_items'"
        ).fetchone():
            logger.warning("spec_items table not found - skipping")
            return 0

        cursor = conn.execute("""
            SELECT
                si.id,
                s.spec_number,
                s.title as spec_title,
                COALESCE(ss.section_number, 'General') as section_number,
                COALESCE(ss.section_title, 'General') as section_title,
                si.item_key,
                si.raw_text,
                si.details,
                si.item_type,
                si.material,
                si.size_range
            FROM spec_items si
            LEFT JOIN spec_sections ss ON si.section_id = ss.id
            JOIN specifications s ON si.spec_id = s.id
            WHERE (si.raw_text IS NOT NULL AND si.raw_text != '' AND length(si.raw_text) > 10)
               OR (si.details IS NOT NULL AND si.details != '' AND length(si.details) > 10)
            ORDER BY s.spec_number, COALESCE(ss.section_number, 'ZZZ'), si.item_key
        """)
        rows = cursor.fetchall()

    if not rows:
        logger.warning("No specification items found to index")
        return 0

    documents: List[str] = []
    metadatas: List[dict] = []
    ids: List[str] = []

    for row in rows:
        doc_id = f"spec_{row['spec_number']}_{row['section_number']}_{row['id']}"

        if not rebuild:
            existing = collection.get(ids=[doc_id])
            if existing["ids"]:
                continue

        content_parts: List[str] = []
        if row["section_title"]:
            content_parts.append(row["section_title"])
        if row["item_key"]:
            content_parts.append(row["item_key"])
        if row["material"]:
            content_parts.append(f"Material: {row['material']}")
        if row["size_range"]:
            content_parts.append(f"Size: {row['size_range']}")
        if row["raw_text"]:
            content_parts.append(row["raw_text"])
        if row["details"]:
            content_parts.append(row["details"])

        doc_text = "\n".join(content_parts)
        documents.append(doc_text)

        meta: Dict[str, Any] = {"source": "specification", "db_id": row["id"]}
        for key in (
            "spec_number", "spec_title", "section_number",
            "section_title", "item_key", "item_type", "material",
        ):
            if row[key] is not None:
                meta[key] = row[key]
        metadatas.append(meta)
        ids.append(doc_id)

    if documents:
        _index_batch(collection, documents, metadatas, ids)

    total = collection.count()
    logger.info("Specifications indexed: %d total documents", total)
    return len(documents)


# ---------------------------------------------------------------------------
# Drawings (P&ID extracted data)
# ---------------------------------------------------------------------------

def index_drawings(rebuild: bool = False) -> int:
    """
    Index extracted drawing data (lines, equipment, instruments, welds)
    into the ``drawings`` collection.

    Args:
        rebuild: Delete existing documents and rebuild from scratch.

    Returns:
        Number of new documents indexed.
    """
    _require_chromadb()
    collection = _get_collection("drawings")

    if rebuild:
        _clear_collection(collection)

    documents: List[str] = []
    metadatas: List[dict] = []
    ids: List[str] = []

    with get_db(readonly=True) as conn:
        existing_tables = {
            row[0]
            for row in conn.execute(
                """SELECT name FROM sqlite_master
                   WHERE type='table'
                     AND name IN ('lines', 'equipment', 'instruments', 'welds', 'sheets')"""
            ).fetchall()
        }

        if not existing_tables:
            logger.warning("No drawing tables found - skipping")
            return 0

        # --- Lines ---
        if "lines" in existing_tables and "sheets" in existing_tables:
            for row in conn.execute("""
                SELECT l.id, l.line_number, l.size, l.material, l.spec_class,
                       l.from_location, l.to_location, l.service,
                       s.drawing_number, s.discipline,
                       p.number as project_number
                FROM lines l
                JOIN sheets s ON l.sheet_id = s.id
                LEFT JOIN projects p ON s.project_id = p.id
                WHERE l.line_number IS NOT NULL AND l.line_number != ''
            """).fetchall():
                doc_id = f"line_{row['drawing_number']}_{row['id']}"
                if not rebuild:
                    ex = collection.get(ids=[doc_id])
                    if ex["ids"]:
                        continue

                parts = [f"Line {row['line_number']}"]
                if row["size"]:
                    parts.append(f"{row['size']} size")
                if row["material"]:
                    parts.append(f"{row['material']} material")
                if row["spec_class"]:
                    parts.append(f"spec class {row['spec_class']}")
                if row["from_location"] and row["to_location"]:
                    parts.append(f"from {row['from_location']} to {row['to_location']}")
                elif row["from_location"]:
                    parts.append(f"from {row['from_location']}")
                elif row["to_location"]:
                    parts.append(f"to {row['to_location']}")
                if row["service"]:
                    parts.append(f"{row['service']} service")

                documents.append(", ".join(parts))
                meta: Dict[str, Any] = {
                    "source": "drawing", "item_type": "line",
                    "drawing_number": row["drawing_number"], "db_id": row["id"],
                }
                for key in ("discipline", "project_number", "line_number", "size", "material", "service"):
                    if row[key]:
                        meta[key] = row[key]
                metadatas.append(meta)
                ids.append(doc_id)

            logger.info("Prepared %d line documents", sum(1 for m in metadatas if m.get("item_type") == "line"))

        # --- Equipment ---
        if "equipment" in existing_tables and "sheets" in existing_tables:
            for row in conn.execute("""
                SELECT e.id, e.tag, e.description, e.equipment_type,
                       s.drawing_number, s.discipline,
                       p.number as project_number
                FROM equipment e
                JOIN sheets s ON e.sheet_id = s.id
                LEFT JOIN projects p ON s.project_id = p.id
                WHERE e.tag IS NOT NULL AND e.tag != ''
            """).fetchall():
                doc_id = f"equip_{row['drawing_number']}_{row['id']}"
                if not rebuild:
                    ex = collection.get(ids=[doc_id])
                    if ex["ids"]:
                        continue

                parts = [f"Equipment {row['tag']}"]
                if row["equipment_type"]:
                    parts.append(row["equipment_type"])
                if row["description"]:
                    parts.append(row["description"])

                documents.append(", ".join(parts))
                meta = {
                    "source": "drawing", "item_type": "equipment",
                    "drawing_number": row["drawing_number"], "db_id": row["id"],
                }
                for key in ("discipline", "project_number", "tag", "equipment_type"):
                    if row[key]:
                        meta[key] = row[key]
                metadatas.append(meta)
                ids.append(doc_id)

            logger.info("Prepared %d equipment documents", sum(1 for m in metadatas if m.get("item_type") == "equipment"))

        # --- Instruments ---
        if "instruments" in existing_tables and "sheets" in existing_tables:
            for row in conn.execute("""
                SELECT i.id, i.tag, i.instrument_type, i.loop_number,
                       i.service, i.description, i.location,
                       s.drawing_number, s.discipline,
                       p.number as project_number
                FROM instruments i
                JOIN sheets s ON i.sheet_id = s.id
                LEFT JOIN projects p ON s.project_id = p.id
                WHERE i.tag IS NOT NULL AND i.tag != ''
            """).fetchall():
                doc_id = f"inst_{row['drawing_number']}_{row['id']}"
                if not rebuild:
                    ex = collection.get(ids=[doc_id])
                    if ex["ids"]:
                        continue

                parts = [f"Instrument {row['tag']}"]
                if row["instrument_type"]:
                    parts.append(row["instrument_type"])
                if row["loop_number"]:
                    parts.append(f"loop {row['loop_number']}")
                if row["service"]:
                    parts.append(f"{row['service']} service")
                if row["description"]:
                    parts.append(row["description"])
                if row["location"]:
                    parts.append(f"at {row['location']}")

                documents.append(", ".join(parts))
                meta = {
                    "source": "drawing", "item_type": "instrument",
                    "drawing_number": row["drawing_number"], "db_id": row["id"],
                }
                for key in ("discipline", "project_number", "tag", "instrument_type", "loop_number", "service"):
                    if row[key]:
                        meta[key] = row[key]
                metadatas.append(meta)
                ids.append(doc_id)

            logger.info("Prepared %d instrument documents", sum(1 for m in metadatas if m.get("item_type") == "instrument"))

        # --- Welds ---
        if "welds" in existing_tables and "sheets" in existing_tables:
            for row in conn.execute("""
                SELECT w.id, w.weld_id, w.weld_type, w.size,
                       w.joint_type, w.nde_required,
                       s.drawing_number, s.discipline,
                       p.number as project_number
                FROM welds w
                JOIN sheets s ON w.sheet_id = s.id
                LEFT JOIN projects p ON s.project_id = p.id
                WHERE w.weld_id IS NOT NULL AND w.weld_id != ''
            """).fetchall():
                doc_id = f"weld_{row['drawing_number']}_{row['id']}"
                if not rebuild:
                    ex = collection.get(ids=[doc_id])
                    if ex["ids"]:
                        continue

                parts = [f"Weld {row['weld_id']}"]
                if row["weld_type"]:
                    parts.append(row["weld_type"])
                if row["size"]:
                    parts.append(f"{row['size']} size")
                if row["joint_type"]:
                    parts.append(f"{row['joint_type']} joint")
                if row["nde_required"]:
                    parts.append(f"NDE: {row['nde_required']}")

                documents.append(", ".join(parts))
                meta = {
                    "source": "drawing", "item_type": "weld",
                    "drawing_number": row["drawing_number"], "db_id": row["id"],
                }
                for key in ("discipline", "project_number", "weld_id", "weld_type", "nde_required"):
                    if row[key]:
                        meta[key] = row[key]
                metadatas.append(meta)
                ids.append(doc_id)

            logger.info("Prepared %d weld documents", sum(1 for m in metadatas if m.get("item_type") == "weld"))

    if documents:
        _index_batch(collection, documents, metadatas, ids)

    total = collection.count()
    logger.info("Drawings indexed: %d total documents", total)
    return len(documents)


# ---------------------------------------------------------------------------
# Index all
# ---------------------------------------------------------------------------

def index_all(rebuild: bool = False) -> Dict[str, int]:
    """
    Index all content types (QM, refs, specs, drawings).

    Args:
        rebuild: Delete existing and rebuild from scratch.

    Returns:
        Dict mapping collection name to number of documents indexed.
    """
    logger.info("=" * 50)
    logger.info("Starting full index...")
    logger.info("=" * 50)

    results = {
        "qm_content": index_qm_content(rebuild=rebuild),
        "ref_clauses": index_ref_clauses(rebuild=rebuild),
        "specifications": index_specifications(rebuild=rebuild),
        "drawings": index_drawings(rebuild=rebuild),
    }

    logger.info("=" * 50)
    logger.info("Indexing complete!")
    logger.info("Total indexed: %d documents", sum(results.values()))
    logger.info("=" * 50)

    return results
