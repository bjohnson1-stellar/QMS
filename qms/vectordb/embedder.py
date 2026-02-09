"""
VectorDB Embedding Queue Manager

Queue-based embedding workflow for scheduling and processing
embedding jobs against ChromaDB. Manages a local SQLite queue
database for pending, processing, completed, and failed jobs.

Supports:
    - Adding files and collections to the embedding queue
    - Batch processing of pending queue items
    - Queue statistics and housekeeping
    - Sync checks to find unembedded content in quality.db
"""

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from qms.core import get_config, get_db, get_logger, QMS_PATHS

logger = get_logger("qms.vectordb.embedder")

# Queue database lives alongside ChromaDB storage
QUEUE_DB_PATH = QMS_PATHS.vector_database / "embed_queue.db"


# ---------------------------------------------------------------------------
# Queue database management
# ---------------------------------------------------------------------------

def _init_queue_db() -> None:
    """Create the queue database tables if they do not exist."""
    db_path = QUEUE_DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS embed_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_type TEXT NOT NULL,
                target TEXT NOT NULL,
                collection TEXT,
                metadata TEXT,
                priority INTEGER DEFAULT 5,
                status TEXT DEFAULT 'pending',
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                processed_at TIMESTAMP,
                retry_count INTEGER DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_queue_status
            ON embed_queue(status)
        """)
        conn.commit()
    finally:
        conn.close()


def _get_queue_conn() -> sqlite3.Connection:
    """Get a connection to the queue database (auto-initialises)."""
    _init_queue_db()
    conn = sqlite3.connect(str(QUEUE_DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Queue CRUD operations
# ---------------------------------------------------------------------------

def add_to_queue(
    task_type: str,
    target: str,
    collection: Optional[str] = None,
    metadata: Optional[dict] = None,
    priority: int = 5,
) -> int:
    """
    Add an item to the embedding queue.

    Args:
        task_type: One of 'file', 'collection', or 'document'.
        target: File path, collection name, or document specification.
        collection: Target ChromaDB collection for the embeddings.
        metadata: Additional metadata dict (stored as JSON).
        priority: 1-10, lower number means higher priority.

    Returns:
        Newly created queue item ID.
    """
    conn = _get_queue_conn()
    try:
        cursor = conn.execute(
            """INSERT INTO embed_queue (task_type, target, collection, metadata, priority)
               VALUES (?, ?, ?, ?, ?)""",
            (
                task_type,
                target,
                collection,
                json.dumps(metadata) if metadata else None,
                priority,
            ),
        )
        item_id = cursor.lastrowid
        conn.commit()
        logger.info("Added to queue: %s - %s (ID: %d)", task_type, target, item_id)
        return item_id
    finally:
        conn.close()


def get_pending_items(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Retrieve pending items ordered by priority (ascending) then creation time.

    Args:
        limit: Maximum number of items to return.

    Returns:
        List of queue item dicts.
    """
    conn = _get_queue_conn()
    try:
        cursor = conn.execute(
            """SELECT * FROM embed_queue
               WHERE status = 'pending'
               ORDER BY priority ASC, created_at ASC
               LIMIT ?""",
            (limit,),
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def update_item_status(
    item_id: int,
    status: str,
    error_message: Optional[str] = None,
) -> None:
    """
    Update the status of a queue item.

    Args:
        item_id: Queue item ID.
        status: New status ('pending', 'processing', 'completed', 'failed').
        error_message: Optional error detail for failed items.
    """
    conn = _get_queue_conn()
    try:
        if status in ("completed", "failed"):
            conn.execute(
                """UPDATE embed_queue
                   SET status = ?, error_message = ?, processed_at = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (status, error_message, item_id),
            )
        else:
            conn.execute(
                """UPDATE embed_queue
                   SET status = ?, error_message = ?
                   WHERE id = ?""",
                (status, error_message, item_id),
            )
        conn.commit()
    finally:
        conn.close()


def _increment_retry(item_id: int) -> None:
    """Increment retry count and reset item to pending."""
    conn = _get_queue_conn()
    try:
        conn.execute(
            """UPDATE embed_queue
               SET retry_count = retry_count + 1, status = 'pending'
               WHERE id = ?""",
            (item_id,),
        )
        conn.commit()
    finally:
        conn.close()


def get_queue_stats() -> Dict[str, Any]:
    """
    Get queue statistics.

    Returns:
        Dict with counts per status and a list of recent items.
    """
    conn = _get_queue_conn()
    try:
        stats: Dict[str, Any] = {}
        for status in ("pending", "processing", "completed", "failed"):
            cursor = conn.execute(
                "SELECT COUNT(*) FROM embed_queue WHERE status = ?", (status,)
            )
            stats[status] = cursor.fetchone()[0]

        cursor = conn.execute(
            "SELECT * FROM embed_queue ORDER BY created_at DESC LIMIT 10"
        )
        stats["recent"] = [dict(row) for row in cursor.fetchall()]
        return stats
    finally:
        conn.close()


def clear_completed(days_old: int = 7) -> int:
    """
    Remove completed items older than *days_old* days.

    Args:
        days_old: Age threshold in days.

    Returns:
        Number of rows deleted.
    """
    conn = _get_queue_conn()
    try:
        cursor = conn.execute(
            """DELETE FROM embed_queue
               WHERE status = 'completed'
                 AND processed_at < datetime('now', ?)""",
            (f"-{days_old} days",),
        )
        conn.commit()
        deleted = cursor.rowcount
        logger.info("Cleared %d completed items older than %d days", deleted, days_old)
        return deleted
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Task processors
# ---------------------------------------------------------------------------

def _process_collection_reindex(item: Dict[str, Any]) -> bool:
    """Run a collection reindex task."""
    from qms.vectordb.indexer import (
        index_qm_content,
        index_ref_clauses,
        index_specifications,
        index_drawings,
    )

    collection_name = item["target"]
    logger.info("Reindexing collection: %s", collection_name)

    dispatch = {
        "qm_content": lambda: index_qm_content(rebuild=True),
        "ref_clauses": lambda: index_ref_clauses(rebuild=True),
        "specifications": lambda: index_specifications(rebuild=True),
        "drawings": lambda: index_drawings(rebuild=True),
    }

    if collection_name == "all":
        for fn in dispatch.values():
            fn()
        return True

    fn = dispatch.get(collection_name)
    if fn is None:
        logger.error("Unknown collection: %s", collection_name)
        return False

    fn()
    return True


def _process_file_embedding(item: Dict[str, Any]) -> bool:
    """Embed a single file (PDF or text) into a ChromaDB collection."""
    from qms.vectordb.search import get_chromadb_collection, add_documents_to_collection

    file_path = Path(item["target"])
    collection_name = item["collection"] or "documents"

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    logger.info("Embedding file: %s", file_path)

    text_chunks: List[Dict[str, Any]] = []

    if file_path.suffix.lower() == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError:
            raise ImportError(
                "pypdf required for PDF processing. Install: pip install pypdf"
            )
        reader = PdfReader(str(file_path))
        for i, page in enumerate(reader.pages):
            text = page.extract_text()
            if text and len(text.strip()) > 50:
                text_chunks.append({"content": text, "page": i + 1})

    elif file_path.suffix.lower() in (".txt", ".md"):
        content = file_path.read_text(encoding="utf-8", errors="ignore")
        for i in range(0, len(content), 1000):
            chunk = content[i : i + 1000]
            if len(chunk.strip()) > 50:
                text_chunks.append({"content": chunk, "chunk": i // 1000})
    else:
        raise ValueError(f"Unsupported file type: {file_path.suffix}")

    if not text_chunks:
        logger.warning("No content extracted from %s", file_path)
        return True

    metadata_base = json.loads(item["metadata"]) if item.get("metadata") else {}
    metadata_base["source_file"] = str(file_path)
    metadata_base["file_name"] = file_path.name

    documents: List[str] = []
    metadatas: List[Dict[str, Any]] = []
    ids: List[str] = []

    for i, chunk in enumerate(text_chunks):
        documents.append(chunk["content"])
        meta = metadata_base.copy()
        meta.update({k: v for k, v in chunk.items() if k != "content"})
        metadatas.append(meta)
        ids.append(f"file_{file_path.stem}_{i}")

    add_documents_to_collection(collection_name, documents, metadatas, ids)
    logger.info("Added %d chunks from %s", len(documents), file_path.name)
    return True


def _process_item(item: Dict[str, Any]) -> bool:
    """Route a single queue item to the appropriate processor."""
    task_type = item["task_type"]
    if task_type == "collection":
        return _process_collection_reindex(item)
    elif task_type == "file":
        return _process_file_embedding(item)
    else:
        logger.error("Unknown task type: %s", task_type)
        return False


# ---------------------------------------------------------------------------
# Main processing loop
# ---------------------------------------------------------------------------

def process_queue(
    max_items: int = 50,
    max_retries: int = 3,
) -> Dict[str, int]:
    """
    Process pending items in the embedding queue.

    Args:
        max_items: Maximum items to process in one run.
        max_retries: Maximum retry attempts per item.

    Returns:
        Dict with 'processed', 'failed', 'skipped' counts.
    """
    from qms.vectordb.search import test_connection

    conn_result = test_connection()
    if not conn_result["success"]:
        logger.error(
            "Embedding system not available: %s", conn_result.get("error", "unknown")
        )
        return {"processed": 0, "failed": 0, "skipped": 0}

    stats = {"processed": 0, "failed": 0, "skipped": 0}
    items = get_pending_items(limit=max_items)

    if not items:
        logger.info("No pending items in queue")
        return stats

    logger.info("Processing %d queue items...", len(items))

    for item in items:
        item_id = item["id"]

        if item["retry_count"] >= max_retries:
            update_item_status(item_id, "failed", "Max retries exceeded")
            stats["skipped"] += 1
            continue

        update_item_status(item_id, "processing")

        try:
            success = _process_item(item)
            if success:
                update_item_status(item_id, "completed")
                stats["processed"] += 1
            else:
                _increment_retry(item_id)
                stats["failed"] += 1
        except Exception as exc:
            logger.error("Error processing item %d: %s", item_id, exc)
            update_item_status(item_id, "failed", str(exc))
            _increment_retry(item_id)
            stats["failed"] += 1

    logger.info("Queue processing complete: %s", stats)
    return stats


def watch_queue(interval: int = 60) -> None:
    """
    Continuously process the queue at *interval* second intervals.

    Runs until interrupted (KeyboardInterrupt).

    Args:
        interval: Seconds between processing runs.
    """
    from qms.vectordb.search import test_connection

    logger.info("Starting watch mode (interval: %ds)", interval)

    while True:
        try:
            conn_result = test_connection()
            if conn_result["success"]:
                stats = process_queue()
                if stats["processed"] > 0:
                    logger.info("Processed %d items", stats["processed"])
            else:
                logger.debug("Embedding system not available, waiting...")
            time.sleep(interval)
        except KeyboardInterrupt:
            logger.info("Watch mode stopped")
            break
        except Exception as exc:
            logger.error("Watch mode error: %s", exc)
            time.sleep(interval)


# ---------------------------------------------------------------------------
# Sync: find unembedded content
# ---------------------------------------------------------------------------

def _get_sqlite_doc_count(table: str, content_field: str = "content") -> int:
    """Count rows in *table* that have meaningful content."""
    with get_db(readonly=True) as conn:
        try:
            cursor = conn.execute(
                f"""SELECT COUNT(*) FROM {table}
                    WHERE {content_field} IS NOT NULL
                      AND {content_field} != ''
                      AND length({content_field}) > 20"""
            )
            return cursor.fetchone()[0]
        except Exception as exc:
            logger.warning("Could not count %s: %s", table, exc)
            return 0


def _get_chromadb_count(collection_name: str) -> int:
    """Count documents in a ChromaDB collection."""
    try:
        from qms.vectordb.search import get_chromadb_collection
        collection = get_chromadb_collection(collection_name, create_if_missing=False)
        return collection.count()
    except Exception as exc:
        logger.warning("Could not count %s: %s", collection_name, exc)
        return 0


def _find_unembedded_files() -> List[Dict[str, Any]]:
    """Scan for PDF files that have not yet been embedded."""
    try:
        from qms.vectordb.search import get_chromadb_collection
    except Exception:
        return []

    unembedded: List[Dict[str, Any]] = []

    ref_path = QMS_PATHS.quality_documents / "References"
    if ref_path.exists():
        try:
            collection = get_chromadb_collection("ref_clauses")
            existing = collection.get(include=[])
            embedded_files: set = set()
            if existing["ids"]:
                full_data = collection.get(include=["metadatas"])
                for meta in full_data["metadatas"]:
                    if meta and "source_file" in meta:
                        embedded_files.add(Path(meta["source_file"]).name)
            for pdf in ref_path.glob("*.pdf"):
                if pdf.name not in embedded_files:
                    unembedded.append(
                        {"path": str(pdf), "collection": "ref_clauses", "type": "reference"}
                    )
        except Exception as exc:
            logger.warning("Error scanning references: %s", exc)

    proc_path = QMS_PATHS.quality_documents / "Procedures"
    if proc_path.exists():
        try:
            collection = get_chromadb_collection("procedures")
            existing = collection.get(include=[])
            embedded_files = set()
            if existing["ids"]:
                full_data = collection.get(include=["metadatas"])
                for meta in full_data["metadatas"]:
                    if meta and "source_file" in meta:
                        embedded_files.add(Path(meta["source_file"]).name)
            for pdf in proc_path.glob("**/*.pdf"):
                if pdf.name not in embedded_files:
                    unembedded.append(
                        {"path": str(pdf), "collection": "procedures", "type": "procedure"}
                    )
        except Exception as exc:
            logger.warning("Error scanning procedures: %s", exc)

    return unembedded


def sync_check() -> Dict[str, Any]:
    """
    Check what content in quality.db still needs to be embedded.

    Returns:
        Dict with 'collections' (per-collection gap info),
        'files' (list of unembedded file dicts), and 'total_gap' count.
    """
    report: Dict[str, Any] = {"collections": {}, "files": [], "total_gap": 0}

    checks = [
        ("qm_content", "qm_content_blocks", "content"),
        ("ref_clauses", "ref_content_blocks", "content"),
        ("specifications", "spec_items", "raw_text"),
    ]

    for collection_name, table, field in checks:
        sqlite_count = _get_sqlite_doc_count(table, field)
        chroma_count = _get_chromadb_count(collection_name)
        gap = max(0, sqlite_count - chroma_count)
        report["collections"][collection_name] = {
            "sqlite": sqlite_count,
            "chromadb": chroma_count,
            "gap": gap,
            "synced": gap == 0,
        }
        report["total_gap"] += gap

    try:
        report["files"] = _find_unembedded_files()
    except Exception as exc:
        logger.warning("Could not scan for unembedded files: %s", exc)
        report["files"] = []

    return report


def sync_queue(dry_run: bool = False) -> Dict[str, int]:
    """
    Queue all unembedded content for processing.

    Args:
        dry_run: If True, report what would be queued without creating items.

    Returns:
        Dict with 'collections' and 'files' counts.
    """
    report = sync_check()
    queued = {"collections": 0, "files": 0}

    for name, info in report["collections"].items():
        if info["gap"] > 0:
            if dry_run:
                logger.info("Would queue reindex: %s (%d documents)", name, info["gap"])
            else:
                add_to_queue("collection", name, priority=3)
                logger.info("Queued reindex: %s (%d documents)", name, info["gap"])
            queued["collections"] += 1

    for file_info in report["files"]:
        if dry_run:
            logger.info("Would queue file: %s", file_info["path"])
        else:
            add_to_queue("file", file_info["path"], file_info["collection"], priority=5)
            logger.info("Queued file: %s", Path(file_info["path"]).name)
        queued["files"] += 1

    return queued
