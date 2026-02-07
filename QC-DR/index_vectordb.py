#!/usr/bin/env python3
"""
SIS Vector Database Indexer

Indexes content from quality.db into ChromaDB for semantic search.
Run this after loading new content into the SQLite database.

Usage:
    python index_vectordb.py --all              # Index everything
    python index_vectordb.py --qm               # Index Quality Manual content
    python index_vectordb.py --refs             # Index reference standard clauses
    python index_vectordb.py --specs            # Index specifications
    python index_vectordb.py --stats            # Show indexing statistics
"""

import argparse
import sqlite3
from typing import List, Dict, Any, Tuple
from datetime import datetime

from sis_common import get_db_connection, get_logger
from vector_db import (
    get_collection, add_documents, get_stats,
    delete_documents, COLLECTIONS
)

logger = get_logger('index_vectordb')

# =============================================================================
# QUALITY MANUAL INDEXING
# =============================================================================

def index_qm_content(rebuild: bool = False) -> int:
    """
    Index Quality Manual content blocks into vector database.

    Args:
        rebuild: If True, delete existing and rebuild from scratch

    Returns:
        Number of documents indexed
    """
    collection = get_collection("qm_content", COLLECTIONS["qm_content"])

    if rebuild:
        # Clear existing documents
        existing = collection.count()
        if existing > 0:
            logger.info(f"Clearing {existing} existing QM documents...")
            # Delete all by getting all IDs
            all_docs = collection.get()
            if all_docs['ids']:
                collection.delete(ids=all_docs['ids'])

    with get_db_connection(readonly=True) as conn:
        # Get content blocks with context
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

    # Prepare documents for indexing
    documents = []
    metadatas = []
    ids = []

    for row in rows:
        doc_id = f"qm_{row['module_number']}_{row['full_ref']}_{row['id']}"

        # Skip if already indexed (unless rebuilding)
        if not rebuild:
            existing = collection.get(ids=[doc_id])
            if existing['ids']:
                continue

        # Create searchable document with context
        doc_text = f"{row['subsection_title']}\n{row['content']}"

        documents.append(doc_text)
        metadatas.append({
            "source": "quality_manual",
            "module": row['module_number'],
            "section": row['section_number'],
            "subsection": row['full_ref'],
            "subsection_type": row['subsection_type'] or "General",
            "block_type": row['block_type'],
            "db_id": row['id']
        })
        ids.append(doc_id)

    if documents:
        # Index in batches
        batch_size = 100
        for i in range(0, len(documents), batch_size):
            batch_docs = documents[i:i + batch_size]
            batch_meta = metadatas[i:i + batch_size]
            batch_ids = ids[i:i + batch_size]

            add_documents(collection, batch_docs, batch_meta, batch_ids)
            logger.info(f"Indexed QM batch {i // batch_size + 1}: {len(batch_docs)} documents")

    total = collection.count()
    logger.info(f"QM content indexed: {total} total documents")
    return len(documents)


# =============================================================================
# REFERENCE STANDARDS INDEXING
# =============================================================================

def index_ref_clauses(rebuild: bool = False) -> int:
    """
    Index reference standard clauses into vector database.

    Returns:
        Number of documents indexed
    """
    collection = get_collection("ref_clauses", COLLECTIONS["ref_clauses"])

    if rebuild:
        existing = collection.count()
        if existing > 0:
            logger.info(f"Clearing {existing} existing reference documents...")
            all_docs = collection.get()
            if all_docs['ids']:
                collection.delete(ids=all_docs['ids'])

    with get_db_connection(readonly=True) as conn:
        # Check if ref_clauses table exists
        cursor = conn.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='ref_clauses'
        """)
        if not cursor.fetchone():
            logger.warning("ref_clauses table not found - skipping")
            return 0

        # Get clauses with content (LEFT JOIN on sections to include clauses without section_id)
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

    documents = []
    metadatas = []
    ids = []

    for idx, row in enumerate(rows):
        # Use row index to ensure uniqueness (id is clause_id, not block_id)
        doc_id = f"ref_{row['standard_id']}_{row['clause_number']}_{idx}"

        if not rebuild:
            existing = collection.get(ids=[doc_id])
            if existing['ids']:
                continue

        # Create searchable document
        doc_text = f"{row['clause_number']} {row['clause_title']}\n{row['content']}"

        documents.append(doc_text)
        metadatas.append({
            "source": "reference_standard",
            "standard_id": row['standard_id'],
            "standard_title": row['standard_title'],
            "section": row['section_name'],
            "clause_number": row['clause_number'],
            "clause_title": row['clause_title'],
            "block_type": row['block_type'],
            "db_id": row['id']
        })
        ids.append(doc_id)

    if documents:
        batch_size = 100
        for i in range(0, len(documents), batch_size):
            batch_docs = documents[i:i + batch_size]
            batch_meta = metadatas[i:i + batch_size]
            batch_ids = ids[i:i + batch_size]

            add_documents(collection, batch_docs, batch_meta, batch_ids)
            logger.info(f"Indexed refs batch {i // batch_size + 1}: {len(batch_docs)} documents")

    total = collection.count()
    logger.info(f"Reference clauses indexed: {total} total documents")
    return len(documents)


# =============================================================================
# SPECIFICATIONS INDEXING
# =============================================================================

def index_specifications(rebuild: bool = False) -> int:
    """
    Index specification items into vector database.

    Returns:
        Number of documents indexed
    """
    collection = get_collection("specifications", COLLECTIONS["specifications"])

    if rebuild:
        existing = collection.count()
        if existing > 0:
            logger.info(f"Clearing {existing} existing spec documents...")
            all_docs = collection.get()
            if all_docs['ids']:
                collection.delete(ids=all_docs['ids'])

    with get_db_connection(readonly=True) as conn:
        # Check if spec_items table exists
        cursor = conn.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='spec_items'
        """)
        if not cursor.fetchone():
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

    documents = []
    metadatas = []
    ids = []

    for row in rows:
        doc_id = f"spec_{row['spec_number']}_{row['section_number']}_{row['id']}"

        if not rebuild:
            existing = collection.get(ids=[doc_id])
            if existing['ids']:
                continue

        # Combine raw_text and details for searchable content
        content_parts = []
        if row['section_title']:
            content_parts.append(row['section_title'])
        if row['item_key']:
            content_parts.append(row['item_key'])
        if row['material']:
            content_parts.append(f"Material: {row['material']}")
        if row['size_range']:
            content_parts.append(f"Size: {row['size_range']}")
        if row['raw_text']:
            content_parts.append(row['raw_text'])
        if row['details']:
            content_parts.append(row['details'])

        doc_text = "\n".join(content_parts)

        documents.append(doc_text)

        # Build metadata, filtering out None values (ChromaDB requirement)
        meta = {
            "source": "specification",
            "db_id": row['id']
        }
        for key in ['spec_number', 'spec_title', 'section_number', 'section_title',
                    'item_key', 'item_type', 'material']:
            if row[key] is not None:
                meta[key] = row[key]

        metadatas.append(meta)
        ids.append(doc_id)

    if documents:
        batch_size = 100
        for i in range(0, len(documents), batch_size):
            batch_docs = documents[i:i + batch_size]
            batch_meta = metadatas[i:i + batch_size]
            batch_ids = ids[i:i + batch_size]

            add_documents(collection, batch_docs, batch_meta, batch_ids)
            logger.info(f"Indexed specs batch {i // batch_size + 1}: {len(batch_docs)} documents")

    total = collection.count()
    logger.info(f"Specifications indexed: {total} total documents")
    return len(documents)


# =============================================================================
# DRAWINGS INDEXING (P&ID extracted data)
# =============================================================================

def index_drawings(rebuild: bool = False) -> int:
    """
    Index extracted drawing data (lines, equipment, instruments, welds) into vector database.

    This indexes the structured data that SIS extraction skills have already pulled
    from P&IDs using Claude's vision capabilities.

    Returns:
        Number of documents indexed
    """
    collection = get_collection("drawings", COLLECTIONS["drawings"])

    if rebuild:
        existing = collection.count()
        if existing > 0:
            logger.info(f"Clearing {existing} existing drawing documents...")
            all_docs = collection.get()
            if all_docs['ids']:
                collection.delete(ids=all_docs['ids'])

    documents = []
    metadatas = []
    ids = []

    with get_db_connection(readonly=True) as conn:
        # Check if tables exist
        cursor = conn.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name IN ('lines', 'equipment', 'instruments', 'welds', 'sheets')
        """)
        existing_tables = {row[0] for row in cursor.fetchall()}

        if not existing_tables:
            logger.warning("No drawing tables found - skipping")
            return 0

        # Index LINES
        if 'lines' in existing_tables and 'sheets' in existing_tables:
            cursor = conn.execute("""
                SELECT
                    l.id,
                    l.line_number,
                    l.size,
                    l.material,
                    l.spec_class,
                    l.from_location,
                    l.to_location,
                    l.service,
                    l.confidence,
                    s.drawing_number,
                    s.title as sheet_title,
                    s.discipline,
                    p.number as project_number
                FROM lines l
                JOIN sheets s ON l.sheet_id = s.id
                LEFT JOIN projects p ON s.project_id = p.id
                WHERE l.line_number IS NOT NULL AND l.line_number != ''
            """)

            for row in cursor.fetchall():
                doc_id = f"line_{row['drawing_number']}_{row['id']}"

                if not rebuild:
                    existing = collection.get(ids=[doc_id])
                    if existing['ids']:
                        continue

                # Build searchable text from structured data
                parts = [f"Line {row['line_number']}"]
                if row['size']:
                    parts.append(f"{row['size']} size")
                if row['material']:
                    parts.append(f"{row['material']} material")
                if row['spec_class']:
                    parts.append(f"spec class {row['spec_class']}")
                if row['from_location'] and row['to_location']:
                    parts.append(f"from {row['from_location']} to {row['to_location']}")
                elif row['from_location']:
                    parts.append(f"from {row['from_location']}")
                elif row['to_location']:
                    parts.append(f"to {row['to_location']}")
                if row['service']:
                    parts.append(f"{row['service']} service")

                doc_text = ", ".join(parts)

                meta = {
                    "source": "drawing",
                    "item_type": "line",
                    "drawing_number": row['drawing_number'],
                    "db_id": row['id']
                }
                # Add optional metadata (ChromaDB requires non-None values)
                for key in ['discipline', 'project_number', 'line_number', 'size', 'material', 'service']:
                    if row[key]:
                        meta[key] = row[key]

                documents.append(doc_text)
                metadatas.append(meta)
                ids.append(doc_id)

            logger.info(f"Prepared {len([m for m in metadatas if m.get('item_type') == 'line'])} line documents")

        # Index EQUIPMENT
        if 'equipment' in existing_tables and 'sheets' in existing_tables:
            cursor = conn.execute("""
                SELECT
                    e.id,
                    e.tag,
                    e.description,
                    e.equipment_type,
                    e.confidence,
                    s.drawing_number,
                    s.title as sheet_title,
                    s.discipline,
                    p.number as project_number
                FROM equipment e
                JOIN sheets s ON e.sheet_id = s.id
                LEFT JOIN projects p ON s.project_id = p.id
                WHERE e.tag IS NOT NULL AND e.tag != ''
            """)

            for row in cursor.fetchall():
                doc_id = f"equip_{row['drawing_number']}_{row['id']}"

                if not rebuild:
                    existing = collection.get(ids=[doc_id])
                    if existing['ids']:
                        continue

                parts = [f"Equipment {row['tag']}"]
                if row['equipment_type']:
                    parts.append(row['equipment_type'])
                if row['description']:
                    parts.append(row['description'])

                doc_text = ", ".join(parts)

                meta = {
                    "source": "drawing",
                    "item_type": "equipment",
                    "drawing_number": row['drawing_number'],
                    "db_id": row['id']
                }
                for key in ['discipline', 'project_number', 'tag', 'equipment_type']:
                    if row[key]:
                        meta[key] = row[key]

                documents.append(doc_text)
                metadatas.append(meta)
                ids.append(doc_id)

            logger.info(f"Prepared {len([m for m in metadatas if m.get('item_type') == 'equipment'])} equipment documents")

        # Index INSTRUMENTS
        if 'instruments' in existing_tables and 'sheets' in existing_tables:
            cursor = conn.execute("""
                SELECT
                    i.id,
                    i.tag,
                    i.instrument_type,
                    i.loop_number,
                    i.service,
                    i.description,
                    i.location,
                    i.confidence,
                    s.drawing_number,
                    s.title as sheet_title,
                    s.discipline,
                    p.number as project_number
                FROM instruments i
                JOIN sheets s ON i.sheet_id = s.id
                LEFT JOIN projects p ON s.project_id = p.id
                WHERE i.tag IS NOT NULL AND i.tag != ''
            """)

            for row in cursor.fetchall():
                doc_id = f"inst_{row['drawing_number']}_{row['id']}"

                if not rebuild:
                    existing = collection.get(ids=[doc_id])
                    if existing['ids']:
                        continue

                parts = [f"Instrument {row['tag']}"]
                if row['instrument_type']:
                    parts.append(row['instrument_type'])
                if row['loop_number']:
                    parts.append(f"loop {row['loop_number']}")
                if row['service']:
                    parts.append(f"{row['service']} service")
                if row['description']:
                    parts.append(row['description'])
                if row['location']:
                    parts.append(f"at {row['location']}")

                doc_text = ", ".join(parts)

                meta = {
                    "source": "drawing",
                    "item_type": "instrument",
                    "drawing_number": row['drawing_number'],
                    "db_id": row['id']
                }
                for key in ['discipline', 'project_number', 'tag', 'instrument_type', 'loop_number', 'service']:
                    if row[key]:
                        meta[key] = row[key]

                documents.append(doc_text)
                metadatas.append(meta)
                ids.append(doc_id)

            logger.info(f"Prepared {len([m for m in metadatas if m.get('item_type') == 'instrument'])} instrument documents")

        # Index WELDS
        if 'welds' in existing_tables and 'sheets' in existing_tables:
            cursor = conn.execute("""
                SELECT
                    w.id,
                    w.weld_id,
                    w.weld_type,
                    w.size,
                    w.joint_type,
                    w.nde_required,
                    w.confidence,
                    s.drawing_number,
                    s.title as sheet_title,
                    s.discipline,
                    p.number as project_number
                FROM welds w
                JOIN sheets s ON w.sheet_id = s.id
                LEFT JOIN projects p ON s.project_id = p.id
                WHERE w.weld_id IS NOT NULL AND w.weld_id != ''
            """)

            for row in cursor.fetchall():
                doc_id = f"weld_{row['drawing_number']}_{row['id']}"

                if not rebuild:
                    existing = collection.get(ids=[doc_id])
                    if existing['ids']:
                        continue

                parts = [f"Weld {row['weld_id']}"]
                if row['weld_type']:
                    parts.append(row['weld_type'])
                if row['size']:
                    parts.append(f"{row['size']} size")
                if row['joint_type']:
                    parts.append(f"{row['joint_type']} joint")
                if row['nde_required']:
                    parts.append(f"NDE: {row['nde_required']}")

                doc_text = ", ".join(parts)

                meta = {
                    "source": "drawing",
                    "item_type": "weld",
                    "drawing_number": row['drawing_number'],
                    "db_id": row['id']
                }
                for key in ['discipline', 'project_number', 'weld_id', 'weld_type', 'nde_required']:
                    if row[key]:
                        meta[key] = row[key]

                documents.append(doc_text)
                metadatas.append(meta)
                ids.append(doc_id)

            logger.info(f"Prepared {len([m for m in metadatas if m.get('item_type') == 'weld'])} weld documents")

    if documents:
        batch_size = 100
        for i in range(0, len(documents), batch_size):
            batch_docs = documents[i:i + batch_size]
            batch_meta = metadatas[i:i + batch_size]
            batch_ids = ids[i:i + batch_size]

            add_documents(collection, batch_docs, batch_meta, batch_ids)
            logger.info(f"Indexed drawings batch {i // batch_size + 1}: {len(batch_docs)} documents")

    total = collection.count()
    logger.info(f"Drawings indexed: {total} total documents")
    return len(documents)


# =============================================================================
# MAIN
# =============================================================================

def index_all(rebuild: bool = False) -> Dict[str, int]:
    """Index all content types."""
    results = {}

    logger.info("=" * 50)
    logger.info("Starting full index...")
    logger.info("=" * 50)

    results['qm_content'] = index_qm_content(rebuild=rebuild)
    results['ref_clauses'] = index_ref_clauses(rebuild=rebuild)
    results['specifications'] = index_specifications(rebuild=rebuild)
    results['drawings'] = index_drawings(rebuild=rebuild)

    logger.info("=" * 50)
    logger.info("Indexing complete!")
    logger.info(f"Total indexed: {sum(results.values())} documents")
    logger.info("=" * 50)

    return results


def main():
    parser = argparse.ArgumentParser(description="SIS Vector Database Indexer")
    parser.add_argument("--all", action="store_true", help="Index all content")
    parser.add_argument("--qm", action="store_true", help="Index Quality Manual")
    parser.add_argument("--refs", action="store_true", help="Index reference standards")
    parser.add_argument("--specs", action="store_true", help="Index specifications")
    parser.add_argument("--drawings", action="store_true", help="Index drawing extractions (lines, equipment, instruments, welds)")
    parser.add_argument("--rebuild", action="store_true", help="Rebuild from scratch (delete existing)")
    parser.add_argument("--stats", action="store_true", help="Show indexing statistics")

    args = parser.parse_args()

    if args.stats:
        stats = get_stats()
        print(f"\nVector Database: {stats['path']}")
        print(f"Total documents: {stats['total_documents']}")
        print(f"\nCollections:")
        for col in stats['details']:
            desc = col.get('metadata', {}).get('description', '')
            print(f"  {col['name']}: {col['count']} documents")
            if desc:
                print(f"    {desc}")

    elif args.all:
        index_all(rebuild=args.rebuild)

    elif args.qm:
        index_qm_content(rebuild=args.rebuild)

    elif args.refs:
        index_ref_clauses(rebuild=args.rebuild)

    elif args.specs:
        index_specifications(rebuild=args.rebuild)

    elif args.drawings:
        index_drawings(rebuild=args.rebuild)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
