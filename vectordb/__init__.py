"""
QMS VectorDB Module

ChromaDB-powered semantic search over quality management content.
Provides embedding queue management, content indexing from quality.db,
and similarity search across Quality Manual, reference standards,
specifications, and drawing extractions.

Optional dependencies:
    pip install chromadb sentence-transformers
"""

from qms.vectordb.embedder import (
    add_to_queue,
    clear_completed,
    get_pending_items,
    get_queue_stats,
    process_queue,
    sync_check,
    sync_queue,
    update_item_status,
)
from qms.vectordb.indexer import (
    index_all,
    index_drawings,
    index_qm_content,
    index_ref_clauses,
    index_specifications,
)
from qms.vectordb.search import (
    get_stats,
    list_collections,
    search_collection,
    search_multiple_collections,
    test_connection,
)

__all__ = [
    # embedder (queue)
    "add_to_queue",
    "clear_completed",
    "get_pending_items",
    "get_queue_stats",
    "process_queue",
    "sync_check",
    "sync_queue",
    "update_item_status",
    # indexer
    "index_all",
    "index_drawings",
    "index_qm_content",
    "index_ref_clauses",
    "index_specifications",
    # search
    "get_stats",
    "list_collections",
    "search_collection",
    "search_multiple_collections",
    "test_connection",
]
