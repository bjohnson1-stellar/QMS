#!/usr/bin/env python3
"""
SIS Embedding Queue Manager

Queue-based embedding workflow that runs standalone (outside Claude Code).
Supports scheduling files for later processing and batch operations.

Usage:
    # Add files/content to queue
    python embed_queue.py add --file "D:/Quality Documents/References/new-standard.pdf"
    python embed_queue.py add --collection qm_content --reindex

    # Process the queue (run this when LM Studio is available)
    python embed_queue.py process

    # Check queue status
    python embed_queue.py status

    # Watch mode - continuously process new items
    python embed_queue.py watch --interval 60

    # Schedule via Windows Task Scheduler:
    #   Program: python
    #   Arguments: D:\\QC-DR\\embed_queue.py process
    #   Trigger: Daily at 2:00 AM (or when LM Studio is running)
"""

import argparse
import json
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from sis_common import get_config, get_db_connection, get_logger, SIS_PATHS

logger = get_logger('embed_queue')

# Queue database location
QUEUE_DB = SIS_PATHS.vector_database / "embed_queue.db"


# =============================================================================
# QUEUE DATABASE
# =============================================================================

def init_queue_db():
    """Initialize the queue database."""
    conn = sqlite3.connect(str(QUEUE_DB))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS embed_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_type TEXT NOT NULL,  -- 'file', 'collection', 'document'
            target TEXT NOT NULL,     -- file path, collection name, or doc ID
            collection TEXT,          -- target collection
            metadata TEXT,            -- JSON metadata
            priority INTEGER DEFAULT 5,
            status TEXT DEFAULT 'pending',  -- pending, processing, completed, failed
            error_message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            processed_at TIMESTAMP,
            retry_count INTEGER DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_queue_status ON embed_queue(status)
    """)
    conn.commit()
    conn.close()


def get_queue_connection():
    """Get a connection to the queue database."""
    init_queue_db()
    conn = sqlite3.connect(str(QUEUE_DB))
    conn.row_factory = sqlite3.Row
    return conn


# =============================================================================
# QUEUE OPERATIONS
# =============================================================================

def add_to_queue(
    task_type: str,
    target: str,
    collection: str = None,
    metadata: dict = None,
    priority: int = 5
) -> int:
    """
    Add an item to the embedding queue.

    Args:
        task_type: 'file', 'collection', or 'document'
        target: File path, collection name, or document specification
        collection: Target collection for the embeddings
        metadata: Additional metadata as dict
        priority: 1-10 (lower = higher priority)

    Returns:
        Queue item ID
    """
    conn = get_queue_connection()
    cursor = conn.execute("""
        INSERT INTO embed_queue (task_type, target, collection, metadata, priority)
        VALUES (?, ?, ?, ?, ?)
    """, (task_type, target, collection, json.dumps(metadata) if metadata else None, priority))
    item_id = cursor.lastrowid
    conn.commit()
    conn.close()

    logger.info(f"Added to queue: {task_type} - {target} (ID: {item_id})")
    return item_id


def get_pending_items(limit: int = 10) -> List[Dict]:
    """Get pending items from the queue, ordered by priority."""
    conn = get_queue_connection()
    cursor = conn.execute("""
        SELECT * FROM embed_queue
        WHERE status = 'pending'
        ORDER BY priority ASC, created_at ASC
        LIMIT ?
    """, (limit,))
    items = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return items


def update_item_status(
    item_id: int,
    status: str,
    error_message: str = None
):
    """Update the status of a queue item."""
    conn = get_queue_connection()
    if status == 'completed' or status == 'failed':
        conn.execute("""
            UPDATE embed_queue
            SET status = ?, error_message = ?, processed_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (status, error_message, item_id))
    else:
        conn.execute("""
            UPDATE embed_queue
            SET status = ?, error_message = ?
            WHERE id = ?
        """, (status, error_message, item_id))
    conn.commit()
    conn.close()


def increment_retry(item_id: int):
    """Increment retry count and reset to pending."""
    conn = get_queue_connection()
    conn.execute("""
        UPDATE embed_queue
        SET retry_count = retry_count + 1, status = 'pending'
        WHERE id = ?
    """, (item_id,))
    conn.commit()
    conn.close()


def get_queue_stats() -> Dict[str, Any]:
    """Get queue statistics."""
    conn = get_queue_connection()
    stats = {}

    for status in ['pending', 'processing', 'completed', 'failed']:
        cursor = conn.execute(
            "SELECT COUNT(*) FROM embed_queue WHERE status = ?",
            (status,)
        )
        stats[status] = cursor.fetchone()[0]

    # Recent items
    cursor = conn.execute("""
        SELECT * FROM embed_queue
        ORDER BY created_at DESC
        LIMIT 10
    """)
    stats['recent'] = [dict(row) for row in cursor.fetchall()]

    conn.close()
    return stats


def clear_completed(days_old: int = 7):
    """Clear completed items older than N days."""
    conn = get_queue_connection()
    conn.execute("""
        DELETE FROM embed_queue
        WHERE status = 'completed'
          AND processed_at < datetime('now', ?)
    """, (f'-{days_old} days',))
    conn.commit()
    conn.close()


# =============================================================================
# EMBEDDING SERVER CHECK
# =============================================================================

def check_embedding_server() -> bool:
    """Check if LM Studio embedding server is available."""
    try:
        from vector_db import test_connection
        return test_connection()
    except Exception as e:
        logger.warning(f"Embedding server not available: {e}")
        return False


# =============================================================================
# TASK PROCESSORS
# =============================================================================

def process_collection_reindex(item: Dict) -> bool:
    """Process a collection reindex task."""
    from index_vectordb import (
        index_qm_content, index_ref_clauses, index_specifications
    )

    collection_name = item['target']
    logger.info(f"Reindexing collection: {collection_name}")

    try:
        if collection_name == 'qm_content':
            index_qm_content(rebuild=True)
        elif collection_name == 'ref_clauses':
            index_ref_clauses(rebuild=True)
        elif collection_name == 'specifications':
            index_specifications(rebuild=True)
        elif collection_name == 'all':
            index_qm_content(rebuild=True)
            index_ref_clauses(rebuild=True)
            index_specifications(rebuild=True)
        else:
            logger.error(f"Unknown collection: {collection_name}")
            return False

        return True
    except Exception as e:
        logger.error(f"Reindex failed: {e}")
        raise


def process_file_embedding(item: Dict) -> bool:
    """Process a file embedding task (e.g., new PDF)."""
    from vector_db import get_collection, add_documents

    file_path = Path(item['target'])
    collection_name = item['collection'] or 'documents'

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    logger.info(f"Embedding file: {file_path}")

    # Read file content based on type
    if file_path.suffix.lower() == '.pdf':
        try:
            from pypdf import PdfReader
            reader = PdfReader(str(file_path))
            text_chunks = []
            for i, page in enumerate(reader.pages):
                text = page.extract_text()
                if text and len(text.strip()) > 50:
                    text_chunks.append({
                        'content': text,
                        'page': i + 1
                    })
        except ImportError:
            raise ImportError("pypdf required for PDF processing. Install: pip install pypdf")

    elif file_path.suffix.lower() in ['.txt', '.md']:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        # Split into chunks of ~1000 chars
        text_chunks = []
        for i in range(0, len(content), 1000):
            chunk = content[i:i+1000]
            if len(chunk.strip()) > 50:
                text_chunks.append({
                    'content': chunk,
                    'chunk': i // 1000
                })
    else:
        raise ValueError(f"Unsupported file type: {file_path.suffix}")

    if not text_chunks:
        logger.warning(f"No content extracted from {file_path}")
        return True

    # Add to vector database
    collection = get_collection(collection_name)

    metadata_base = json.loads(item['metadata']) if item['metadata'] else {}
    metadata_base['source_file'] = str(file_path)
    metadata_base['file_name'] = file_path.name

    documents = []
    metadatas = []
    ids = []

    for i, chunk in enumerate(text_chunks):
        documents.append(chunk['content'])
        meta = metadata_base.copy()
        meta.update({k: v for k, v in chunk.items() if k != 'content'})
        metadatas.append(meta)
        ids.append(f"file_{file_path.stem}_{i}")

    add_documents(collection, documents, metadatas, ids)
    logger.info(f"Added {len(documents)} chunks from {file_path.name}")

    return True


def process_item(item: Dict) -> bool:
    """Process a single queue item."""
    task_type = item['task_type']

    if task_type == 'collection':
        return process_collection_reindex(item)
    elif task_type == 'file':
        return process_file_embedding(item)
    else:
        logger.error(f"Unknown task type: {task_type}")
        return False


# =============================================================================
# MAIN PROCESS LOOP
# =============================================================================

def process_queue(max_items: int = 50, max_retries: int = 3) -> Dict[str, int]:
    """
    Process pending items in the queue.

    Args:
        max_items: Maximum items to process in one run
        max_retries: Maximum retries for failed items

    Returns:
        Dict with counts of processed, failed items
    """
    if not check_embedding_server():
        logger.error("Embedding server not available. Start LM Studio first.")
        return {'processed': 0, 'failed': 0, 'skipped': 0}

    stats = {'processed': 0, 'failed': 0, 'skipped': 0}
    items = get_pending_items(limit=max_items)

    if not items:
        logger.info("No pending items in queue")
        return stats

    logger.info(f"Processing {len(items)} queue items...")

    for item in items:
        item_id = item['id']

        # Skip items that have exceeded retries
        if item['retry_count'] >= max_retries:
            update_item_status(item_id, 'failed', 'Max retries exceeded')
            stats['skipped'] += 1
            continue

        update_item_status(item_id, 'processing')

        try:
            success = process_item(item)
            if success:
                update_item_status(item_id, 'completed')
                stats['processed'] += 1
            else:
                increment_retry(item_id)
                stats['failed'] += 1

        except Exception as e:
            logger.error(f"Error processing item {item_id}: {e}")
            update_item_status(item_id, 'failed', str(e))
            increment_retry(item_id)
            stats['failed'] += 1

    logger.info(f"Queue processing complete: {stats}")
    return stats


def watch_mode(interval: int = 60):
    """
    Watch mode - continuously process queue at intervals.

    Args:
        interval: Seconds between processing runs
    """
    logger.info(f"Starting watch mode (interval: {interval}s)")
    logger.info("Press Ctrl+C to stop")

    while True:
        try:
            if check_embedding_server():
                stats = process_queue()
                if stats['processed'] > 0:
                    logger.info(f"Processed {stats['processed']} items")
            else:
                logger.debug("Embedding server not available, waiting...")

            time.sleep(interval)

        except KeyboardInterrupt:
            logger.info("Watch mode stopped")
            break
        except Exception as e:
            logger.error(f"Watch mode error: {e}")
            time.sleep(interval)


# =============================================================================
# SYNC - FIND UNEMBEDDED CONTENT
# =============================================================================

def get_sqlite_doc_count(table: str, content_field: str = 'content') -> int:
    """Get count of documents in SQLite that have content."""
    with get_db_connection(readonly=True) as conn:
        try:
            cursor = conn.execute(f"""
                SELECT COUNT(*) FROM {table}
                WHERE {content_field} IS NOT NULL
                  AND {content_field} != ''
                  AND length({content_field}) > 20
            """)
            return cursor.fetchone()[0]
        except Exception as e:
            logger.warning(f"Could not count {table}: {e}")
            return 0


def get_chromadb_count(collection_name: str) -> int:
    """Get count of documents in ChromaDB collection."""
    try:
        from vector_db import get_collection
        collection = get_collection(collection_name, create_if_missing=False)
        return collection.count()
    except Exception as e:
        logger.warning(f"Could not count {collection_name}: {e}")
        return 0


def find_unembedded_files() -> List[Dict]:
    """Find PDF files that haven't been embedded yet."""
    from vector_db import get_collection

    unembedded = []

    # Check reference PDFs
    ref_path = Path(SIS_PATHS.quality_documents) / "References"
    if ref_path.exists():
        collection = get_collection("ref_clauses")
        existing = collection.get(include=[])

        # Get files already embedded (from metadata)
        embedded_files = set()
        if existing['ids']:
            full_data = collection.get(include=['metadatas'])
            for meta in full_data['metadatas']:
                if meta and 'source_file' in meta:
                    embedded_files.add(Path(meta['source_file']).name)

        for pdf in ref_path.glob("*.pdf"):
            if pdf.name not in embedded_files:
                unembedded.append({
                    'path': str(pdf),
                    'collection': 'ref_clauses',
                    'type': 'reference'
                })

    # Check procedure PDFs
    proc_path = Path(SIS_PATHS.quality_documents) / "Procedures"
    if proc_path.exists():
        collection = get_collection("procedures")
        existing = collection.get(include=[])

        embedded_files = set()
        if existing['ids']:
            full_data = collection.get(include=['metadatas'])
            for meta in full_data['metadatas']:
                if meta and 'source_file' in meta:
                    embedded_files.add(Path(meta['source_file']).name)

        for pdf in proc_path.glob("**/*.pdf"):
            if pdf.name not in embedded_files:
                unembedded.append({
                    'path': str(pdf),
                    'collection': 'procedures',
                    'type': 'procedure'
                })

    return unembedded


def sync_check() -> Dict[str, Any]:
    """
    Check what content needs to be embedded.

    Returns dict with counts and gaps for each collection.
    """
    report = {
        'collections': {},
        'files': [],
        'total_gap': 0
    }

    # Check QM content
    sqlite_qm = get_sqlite_doc_count('qm_content_blocks', 'content')
    chroma_qm = get_chromadb_count('qm_content')
    gap_qm = max(0, sqlite_qm - chroma_qm)
    report['collections']['qm_content'] = {
        'sqlite': sqlite_qm,
        'chromadb': chroma_qm,
        'gap': gap_qm,
        'synced': gap_qm == 0
    }
    report['total_gap'] += gap_qm

    # Check reference clauses (content blocks, not clauses)
    sqlite_ref = get_sqlite_doc_count('ref_content_blocks', 'content')
    chroma_ref = get_chromadb_count('ref_clauses')
    gap_ref = max(0, sqlite_ref - chroma_ref)
    report['collections']['ref_clauses'] = {
        'sqlite': sqlite_ref,
        'chromadb': chroma_ref,
        'gap': gap_ref,
        'synced': gap_ref == 0
    }
    report['total_gap'] += gap_ref

    # Check specifications
    sqlite_spec = get_sqlite_doc_count('spec_items', 'raw_text')
    chroma_spec = get_chromadb_count('specifications')
    gap_spec = max(0, sqlite_spec - chroma_spec)
    report['collections']['specifications'] = {
        'sqlite': sqlite_spec,
        'chromadb': chroma_spec,
        'gap': gap_spec,
        'synced': gap_spec == 0
    }
    report['total_gap'] += gap_spec

    # Check for unembedded files
    try:
        report['files'] = find_unembedded_files()
    except Exception as e:
        logger.warning(f"Could not scan for unembedded files: {e}")
        report['files'] = []

    return report


def sync_queue(dry_run: bool = False) -> Dict[str, int]:
    """
    Queue all unembedded content for processing.

    Args:
        dry_run: If True, just report what would be queued

    Returns:
        Dict with counts of queued items
    """
    report = sync_check()
    queued = {'collections': 0, 'files': 0}

    # Queue collections with gaps
    for name, info in report['collections'].items():
        if info['gap'] > 0:
            if dry_run:
                logger.info(f"Would queue reindex: {name} ({info['gap']} documents)")
            else:
                add_to_queue('collection', name, priority=3)
                logger.info(f"Queued reindex: {name} ({info['gap']} documents)")
            queued['collections'] += 1

    # Queue unembedded files
    for file_info in report['files']:
        if dry_run:
            logger.info(f"Would queue file: {file_info['path']}")
        else:
            add_to_queue('file', file_info['path'], file_info['collection'], priority=5)
            logger.info(f"Queued file: {Path(file_info['path']).name}")
        queued['files'] += 1

    return queued


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="SIS Embedding Queue Manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Find and queue all unembedded content
  python embed_queue.py sync

  # Check what would be queued (dry run)
  python embed_queue.py sync --dry-run

  # Queue a file for embedding
  python embed_queue.py add --file "D:/docs/new-standard.pdf" --collection ref_clauses

  # Queue collection reindex
  python embed_queue.py add --collection qm_content --reindex

  # Process the queue
  python embed_queue.py process

  # Watch mode (continuous processing)
  python embed_queue.py watch --interval 60

  # Check status
  python embed_queue.py status
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Add command
    add_parser = subparsers.add_parser('add', help='Add item to queue')
    add_parser.add_argument('--file', type=str, help='File path to embed')
    add_parser.add_argument('--collection', type=str, help='Target collection')
    add_parser.add_argument('--reindex', action='store_true', help='Reindex collection')
    add_parser.add_argument('--priority', type=int, default=5, help='Priority (1-10, lower=higher)')

    # Process command
    process_parser = subparsers.add_parser('process', help='Process pending queue items')
    process_parser.add_argument('--max', type=int, default=50, help='Max items to process')

    # Watch command
    watch_parser = subparsers.add_parser('watch', help='Watch mode - continuous processing')
    watch_parser.add_argument('--interval', type=int, default=60, help='Seconds between runs')

    # Status command
    status_parser = subparsers.add_parser('status', help='Show queue status')

    # Clear command
    clear_parser = subparsers.add_parser('clear', help='Clear old completed items')
    clear_parser.add_argument('--days', type=int, default=7, help='Clear items older than N days')

    # Sync command
    sync_parser = subparsers.add_parser('sync', help='Find and queue all unembedded content')
    sync_parser.add_argument('--dry-run', action='store_true', help='Show what would be queued without queueing')
    sync_parser.add_argument('--check', action='store_true', help='Just show sync status, don\'t queue')

    args = parser.parse_args()

    if args.command == 'add':
        if args.reindex:
            collection = args.collection or 'all'
            add_to_queue('collection', collection, priority=args.priority)
            print(f"Queued reindex for: {collection}")
        elif args.file:
            add_to_queue('file', args.file, args.collection, priority=args.priority)
            print(f"Queued file: {args.file}")
        else:
            print("Error: Specify --file or --reindex")

    elif args.command == 'process':
        stats = process_queue(max_items=args.max)
        print(f"\nProcessed: {stats['processed']}")
        print(f"Failed: {stats['failed']}")
        print(f"Skipped: {stats['skipped']}")

    elif args.command == 'watch':
        watch_mode(interval=args.interval)

    elif args.command == 'status':
        stats = get_queue_stats()
        print(f"\n=== Embedding Queue Status ===")
        print(f"Pending:    {stats['pending']}")
        print(f"Processing: {stats['processing']}")
        print(f"Completed:  {stats['completed']}")
        print(f"Failed:     {stats['failed']}")

        if stats['recent']:
            print(f"\nRecent items:")
            for item in stats['recent'][:5]:
                print(f"  [{item['status']}] {item['task_type']}: {item['target']}")

    elif args.command == 'clear':
        clear_completed(days_old=args.days)
        print(f"Cleared completed items older than {args.days} days")

    elif args.command == 'sync':
        print("\n=== Sync Check ===")
        report = sync_check()

        print("\nCollections:")
        for name, info in report['collections'].items():
            status = "[OK] synced" if info['synced'] else f"[!!] {info['gap']} unembedded"
            print(f"  {name}:")
            print(f"    SQLite:   {info['sqlite']} documents")
            print(f"    ChromaDB: {info['chromadb']} documents")
            print(f"    Status:   {status}")

        if report['files']:
            print(f"\nUnembedded files: {len(report['files'])}")
            for f in report['files'][:10]:
                print(f"  - {Path(f['path']).name} ({f['collection']})")
            if len(report['files']) > 10:
                print(f"  ... and {len(report['files']) - 10} more")

        print(f"\nTotal gap: {report['total_gap']} documents + {len(report['files'])} files")

        if not args.check:
            if report['total_gap'] > 0 or report['files']:
                if args.dry_run:
                    print("\n[Dry run] Would queue:")
                    sync_queue(dry_run=True)
                else:
                    print("\nQueueing unembedded content...")
                    queued = sync_queue(dry_run=False)
                    print(f"\nQueued: {queued['collections']} collections, {queued['files']} files")
                    print("Run 'python embed_queue.py process' to process the queue")
            else:
                print("\n[OK] Everything is synced!")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
