#!/usr/bin/env python3
"""
SIS Vector Database Module

Provides ChromaDB integration with local embeddings.
Supports two embedding providers:
  - "lm_studio": Requires LM Studio server running (default)
  - "local": Uses sentence-transformers directly (no server needed)

Usage:
    from vector_db import get_vectordb, get_collection, search, add_documents

Example:
    # Get a collection
    qm = get_collection("qm_content")

    # Add documents
    add_documents(qm,
        documents=["Welding shall comply with AWS D1.1"],
        metadatas=[{"module": 5, "section": "5.2A"}],
        ids=["qm_5_5.2A_1"]
    )

    # Search
    results = search(qm, "weld quality requirements", n_results=5)
"""

import chromadb
from chromadb import EmbeddingFunction, Embeddings, Documents
from typing import List, Dict, Any, Optional
from pathlib import Path

# Import shared config
from sis_common import get_config, SIS_PATHS, get_logger

logger = get_logger('vector_db')

# =============================================================================
# EMBEDDING FUNCTIONS
# =============================================================================

class LMStudioEmbeddings(EmbeddingFunction):
    """
    Embedding function using LM Studio's OpenAI-compatible API.
    Requires LM Studio server running with an embedding model loaded.
    """

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:1234/v1",
        model: str = "text-embedding-nomic-embed-text-v1.5@q8_0",
        batch_size: int = 32
    ):
        from openai import OpenAI
        self.client = OpenAI(
            base_url=base_url,
            api_key="lm-studio"  # LM Studio doesn't require a real key
        )
        self.model = model
        self.batch_size = batch_size
        self.provider = "lm_studio"

    def __call__(self, input: Documents) -> Embeddings:
        """Generate embeddings for a list of documents."""
        embeddings = []

        for i in range(0, len(input), self.batch_size):
            batch = input[i:i + self.batch_size]
            response = self.client.embeddings.create(
                model=self.model,
                input=batch
            )
            batch_embeddings = [item.embedding for item in response.data]
            embeddings.extend(batch_embeddings)

        return embeddings


class LocalEmbeddings(EmbeddingFunction):
    """
    Embedding function using sentence-transformers directly.
    No server required - runs entirely in Python.

    Install: pip install sentence-transformers
    """

    def __init__(
        self,
        model: str = "nomic-ai/nomic-embed-text-v1.5",
        batch_size: int = 32,
        device: str = None  # "cuda", "cpu", or None for auto
    ):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise ImportError(
                "sentence-transformers not installed. Run: pip install sentence-transformers"
            )

        self.model_name = model
        self.batch_size = batch_size
        self.provider = "local"

        # Load model (downloads on first use, ~500MB)
        logger.info(f"Loading local embedding model: {model}")
        self.model = SentenceTransformer(model, trust_remote_code=True, device=device)
        logger.info(f"Model loaded on device: {self.model.device}")

    def __call__(self, input: Documents) -> Embeddings:
        """Generate embeddings for a list of documents."""
        # sentence-transformers handles batching internally
        embeddings = self.model.encode(
            input,
            batch_size=self.batch_size,
            show_progress_bar=len(input) > 100,
            convert_to_numpy=True
        )
        return embeddings.tolist()


# =============================================================================
# CHROMADB CLIENT & COLLECTIONS
# =============================================================================

# Singleton client instance
_client: Optional[chromadb.PersistentClient] = None
_embedding_fn: Optional[EmbeddingFunction] = None


def _check_lm_studio_available(base_url: str) -> bool:
    """Check if LM Studio server is responding."""
    try:
        import urllib.request
        import urllib.error
        req = urllib.request.Request(f"{base_url}/models", method='GET')
        req.add_header('Connection', 'close')
        with urllib.request.urlopen(req, timeout=2) as response:
            return response.status == 200
    except:
        return False


def get_embedding_function(force_provider: str = None) -> EmbeddingFunction:
    """
    Get the configured embedding function (singleton).

    Args:
        force_provider: Override config - use "lm_studio" or "local"

    Provider selection (in order of priority):
        1. force_provider argument
        2. config.yaml embeddings.provider setting
        3. Auto-detect: use LM Studio if available, else local

    Returns:
        Configured embedding function
    """
    global _embedding_fn

    if _embedding_fn is None:
        config = get_config()
        embed_config = config.get('embeddings', {})

        provider = force_provider or embed_config.get('provider', 'auto')
        base_url = embed_config.get('base_url', 'http://127.0.0.1:1234/v1')

        # Auto-detect provider
        if provider == 'auto':
            if _check_lm_studio_available(base_url):
                provider = 'lm_studio'
                logger.info("Auto-detected LM Studio server")
            else:
                provider = 'local'
                logger.info("LM Studio not available, using local embeddings")

        if provider == 'lm_studio':
            _embedding_fn = LMStudioEmbeddings(
                base_url=base_url,
                model=embed_config.get('model', 'text-embedding-nomic-embed-text-v1.5@q8_0'),
                batch_size=embed_config.get('batch_size', 32)
            )
            logger.info(f"Initialized LM Studio embeddings: {_embedding_fn.model}")

        elif provider == 'local':
            _embedding_fn = LocalEmbeddings(
                model=embed_config.get('local_model', 'nomic-ai/nomic-embed-text-v1.5'),
                batch_size=embed_config.get('batch_size', 32),
                device=embed_config.get('device', None)
            )
            logger.info(f"Initialized local embeddings: {_embedding_fn.model_name}")

        else:
            raise ValueError(f"Unknown embedding provider: {provider}")

    return _embedding_fn


def reset_embedding_function():
    """Reset the singleton embedding function (for switching providers)."""
    global _embedding_fn
    _embedding_fn = None


def get_vectordb() -> chromadb.PersistentClient:
    """Get the ChromaDB client (singleton with persistent storage)."""
    global _client

    if _client is None:
        db_path = SIS_PATHS.vector_database
        db_path.mkdir(parents=True, exist_ok=True)

        _client = chromadb.PersistentClient(path=str(db_path))
        logger.info(f"ChromaDB initialized at {db_path}")

    return _client


def get_collection(
    name: str,
    description: str = None,
    create_if_missing: bool = True
) -> chromadb.Collection:
    """
    Get or create a ChromaDB collection with LM Studio embeddings.

    Args:
        name: Collection name (e.g., "qm_content", "ref_clauses")
        description: Optional description for new collections
        create_if_missing: Create collection if it doesn't exist

    Returns:
        ChromaDB Collection with configured embedding function
    """
    client = get_vectordb()
    embedding_fn = get_embedding_function()

    metadata = {}
    if description:
        metadata["description"] = description

    if create_if_missing:
        return client.get_or_create_collection(
            name=name,
            embedding_function=embedding_fn,
            metadata=metadata if metadata else None
        )
    else:
        return client.get_collection(
            name=name,
            embedding_function=embedding_fn
        )


def list_collections() -> List[Dict[str, Any]]:
    """List all collections with their document counts."""
    client = get_vectordb()
    collections = []

    for col in client.list_collections():
        # Get collection with embedding function to access count
        full_col = get_collection(col.name, create_if_missing=False)
        collections.append({
            "name": col.name,
            "count": full_col.count(),
            "metadata": col.metadata
        })

    return collections


# =============================================================================
# DOCUMENT OPERATIONS
# =============================================================================

def add_documents(
    collection: chromadb.Collection,
    documents: List[str],
    metadatas: List[Dict[str, Any]] = None,
    ids: List[str] = None
) -> None:
    """
    Add documents to a collection.

    Args:
        collection: ChromaDB collection
        documents: List of text documents to embed and store
        metadatas: Optional list of metadata dicts for each document
        ids: Optional list of unique IDs (auto-generated if not provided)
    """
    if ids is None:
        # Generate IDs based on collection name and count
        base = collection.count()
        ids = [f"{collection.name}_{base + i}" for i in range(len(documents))]

    collection.add(
        documents=documents,
        metadatas=metadatas,
        ids=ids
    )

    logger.info(f"Added {len(documents)} documents to {collection.name}")


def search(
    collection: chromadb.Collection,
    query: str,
    n_results: int = 5,
    where: Dict[str, Any] = None,
    include: List[str] = None
) -> Dict[str, Any]:
    """
    Search for similar documents.

    Args:
        collection: ChromaDB collection to search
        query: Search query text
        n_results: Number of results to return
        where: Optional metadata filter (e.g., {"module": 5})
        include: What to include in results (default: documents, metadatas, distances)

    Returns:
        Dict with ids, documents, metadatas, distances
    """
    if include is None:
        include = ["documents", "metadatas", "distances"]

    results = collection.query(
        query_texts=[query],
        n_results=n_results,
        where=where,
        include=include
    )

    return results


def search_multiple(
    collection: chromadb.Collection,
    queries: List[str],
    n_results: int = 5,
    where: Dict[str, Any] = None
) -> List[Dict[str, Any]]:
    """
    Search with multiple queries at once (batch search).

    Args:
        collection: ChromaDB collection to search
        queries: List of search query texts
        n_results: Number of results per query
        where: Optional metadata filter

    Returns:
        List of result dicts, one per query
    """
    results = collection.query(
        query_texts=queries,
        n_results=n_results,
        where=where,
        include=["documents", "metadatas", "distances"]
    )

    # Restructure to list of individual results
    output = []
    for i in range(len(queries)):
        output.append({
            "query": queries[i],
            "ids": results["ids"][i],
            "documents": results["documents"][i],
            "metadatas": results["metadatas"][i],
            "distances": results["distances"][i]
        })

    return output


def delete_documents(
    collection: chromadb.Collection,
    ids: List[str] = None,
    where: Dict[str, Any] = None
) -> None:
    """
    Delete documents from a collection.

    Args:
        collection: ChromaDB collection
        ids: List of document IDs to delete
        where: Metadata filter for deletion
    """
    collection.delete(ids=ids, where=where)
    logger.info(f"Deleted documents from {collection.name}")


# =============================================================================
# COLLECTION DEFINITIONS (SIS-specific)
# =============================================================================

# Standard collection names and descriptions
COLLECTIONS = {
    "qm_content": "Quality Manual content blocks from XML modules",
    "ref_clauses": "Reference standard clauses (ASME, AWS, ISO, etc.)",
    "specifications": "Project specification requirements and items",
    "procedures": "SOPs, Work Instructions, and Policies",
    "drawings": "Drawing metadata and extracted annotations"
}


def init_collections() -> Dict[str, chromadb.Collection]:
    """
    Initialize all standard SIS collections.

    Returns:
        Dict mapping collection names to Collection objects
    """
    collections = {}
    for name, description in COLLECTIONS.items():
        collections[name] = get_collection(name, description)
        logger.info(f"Collection '{name}': {collections[name].count()} documents")

    return collections


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def test_connection(provider: str = None) -> Dict[str, Any]:
    """
    Test embedding function.

    Args:
        provider: Force specific provider ("lm_studio" or "local")

    Returns:
        Dict with success status, provider info, and any error
    """
    result = {"success": False, "provider": None, "error": None}

    try:
        if provider:
            reset_embedding_function()

        embed_fn = get_embedding_function(force_provider=provider)
        result["provider"] = embed_fn.provider

        # Test embedding generation
        test_result = embed_fn(["test embedding"])
        if len(test_result) == 1 and len(test_result[0]) > 0:
            result["success"] = True
            result["dimensions"] = len(test_result[0])
        else:
            result["error"] = "Empty embedding returned"

    except Exception as e:
        result["error"] = str(e)
        logger.error(f"Embedding test failed: {e}")

    return result


def get_stats() -> Dict[str, Any]:
    """Get vector database statistics."""
    collections = list_collections()

    return {
        "path": str(SIS_PATHS.vector_database),
        "collections": len(collections),
        "total_documents": sum(c["count"] for c in collections),
        "details": collections
    }


# =============================================================================
# CLI INTERFACE
# =============================================================================

def main():
    """CLI for testing and basic operations."""
    import argparse

    parser = argparse.ArgumentParser(description="SIS Vector Database CLI")
    parser.add_argument("--test", action="store_true", help="Test embedding connection")
    parser.add_argument("--provider", type=str, choices=["lm_studio", "local", "auto"],
                       help="Force embedding provider (default: auto-detect)")
    parser.add_argument("--stats", action="store_true", help="Show database statistics")
    parser.add_argument("--init", action="store_true", help="Initialize all collections")
    parser.add_argument("--search", type=str, help="Search query")
    parser.add_argument("--collection", type=str, default="qm_content", help="Collection to search")

    args = parser.parse_args()

    if args.test:
        provider = args.provider if args.provider != "auto" else None
        print(f"Testing embedding connection (provider: {args.provider or 'auto'})...")

        result = test_connection(provider=provider)

        if result["success"]:
            print(f"SUCCESS: Embeddings working")
            print(f"  Provider: {result['provider']}")
            print(f"  Dimensions: {result['dimensions']}")
        else:
            print(f"FAILED: {result['error']}")
            if result["provider"] == "lm_studio" or args.provider == "lm_studio":
                print("  Make sure LM Studio is running with an embedding model loaded")
            print("\nTry: python vector_db.py --test --provider local")

    elif args.stats:
        stats = get_stats()
        print(f"\nVector Database: {stats['path']}")
        print(f"Total documents: {stats['total_documents']}")
        print(f"\nCollections ({stats['collections']}):")
        for col in stats['details']:
            print(f"  {col['name']}: {col['count']} documents")

    elif args.init:
        print("Initializing collections...")
        collections = init_collections()
        print(f"Initialized {len(collections)} collections")

    elif args.search:
        print(f"Searching '{args.collection}' for: {args.search}")
        col = get_collection(args.collection)
        results = search(col, args.search, n_results=5)

        for i, (doc, meta, dist) in enumerate(zip(
            results['documents'][0],
            results['metadatas'][0],
            results['distances'][0]
        )):
            print(f"\n--- Result {i+1} (distance: {dist:.4f}) ---")
            print(f"Metadata: {meta}")
            print(f"Content: {doc[:200]}..." if len(doc) > 200 else f"Content: {doc}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
