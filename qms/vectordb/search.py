"""
VectorDB Semantic Search Interface

Provides query embedding, similarity search, result formatting,
and multi-collection search over ChromaDB collections.

ChromaDB and sentence-transformers are optional dependencies.
"""

import urllib.request
import urllib.error
from pathlib import Path
from typing import Any, Dict, List, Optional

from qms.core import get_config, get_logger, QMS_PATHS

logger = get_logger("qms.vectordb.search")

# ---------------------------------------------------------------------------
# Optional dependency guards
# ---------------------------------------------------------------------------

try:
    import chromadb
    from chromadb import EmbeddingFunction, Embeddings, Documents

    HAS_CHROMADB = True
except ImportError:
    HAS_CHROMADB = False
    chromadb = None  # type: ignore[assignment]

try:
    from sentence_transformers import SentenceTransformer

    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    HAS_SENTENCE_TRANSFORMERS = False
    SentenceTransformer = None  # type: ignore[assignment,misc]


def _require_chromadb() -> None:
    if not HAS_CHROMADB:
        raise ImportError(
            "chromadb is required for vector search. Install: pip install chromadb"
        )


# ---------------------------------------------------------------------------
# Embedding functions
# ---------------------------------------------------------------------------

if HAS_CHROMADB:

    class LMStudioEmbeddings(EmbeddingFunction):
        """Embedding function using LM Studio's OpenAI-compatible API."""

        def __init__(
            self,
            base_url: str = "http://127.0.0.1:1234/v1",
            model: str = "text-embedding-nomic-embed-text-v1.5@q8_0",
            batch_size: int = 32,
        ):
            try:
                from openai import OpenAI
            except ImportError:
                raise ImportError(
                    "openai package required for LM Studio embeddings. "
                    "Install: pip install openai"
                )
            self.client = OpenAI(base_url=base_url, api_key="lm-studio")
            self.model = model
            self.batch_size = batch_size
            self.provider = "lm_studio"

        def __call__(self, input: "Documents") -> "Embeddings":
            embeddings: list = []
            for i in range(0, len(input), self.batch_size):
                batch = input[i : i + self.batch_size]
                response = self.client.embeddings.create(model=self.model, input=batch)
                embeddings.extend(item.embedding for item in response.data)
            return embeddings

    class LocalEmbeddings(EmbeddingFunction):
        """Embedding function using sentence-transformers (no server needed)."""

        def __init__(
            self,
            model: str = "nomic-ai/nomic-embed-text-v1.5",
            batch_size: int = 32,
            device: Optional[str] = None,
        ):
            if not HAS_SENTENCE_TRANSFORMERS:
                raise ImportError(
                    "sentence-transformers required. "
                    "Install: pip install sentence-transformers"
                )
            self.model_name = model
            self.batch_size = batch_size
            self.provider = "local"
            logger.info("Loading local embedding model: %s", model)
            self.model = SentenceTransformer(model, trust_remote_code=True, device=device)
            logger.info("Model loaded on device: %s", self.model.device)

        def __call__(self, input: "Documents") -> "Embeddings":
            embeddings = self.model.encode(
                input,
                batch_size=self.batch_size,
                show_progress_bar=len(input) > 100,
                convert_to_numpy=True,
            )
            return embeddings.tolist()


# ---------------------------------------------------------------------------
# ChromaDB client / embedding singletons
# ---------------------------------------------------------------------------

_client = None
_embedding_fn = None


def _check_lm_studio(base_url: str) -> bool:
    """Return True if LM Studio server is responding."""
    try:
        req = urllib.request.Request(f"{base_url}/models", method="GET")
        req.add_header("Connection", "close")
        with urllib.request.urlopen(req, timeout=2) as resp:
            return resp.status == 200
    except Exception:
        return False


def get_embedding_function(force_provider: Optional[str] = None):
    """
    Get the configured embedding function (singleton).

    Provider selection order:
        1. *force_provider* argument
        2. ``config.yaml`` ``embeddings.provider`` setting
        3. Auto-detect: LM Studio if reachable, else local

    Args:
        force_provider: ``'lm_studio'``, ``'local'``, or ``None`` for auto.

    Returns:
        An EmbeddingFunction instance.
    """
    _require_chromadb()

    global _embedding_fn
    if _embedding_fn is not None and force_provider is None:
        return _embedding_fn

    config = get_config()
    embed_config = config.get("embeddings", {})

    provider = force_provider or embed_config.get("provider", "auto")
    base_url = embed_config.get("base_url", "http://127.0.0.1:1234/v1")

    if provider == "auto":
        if _check_lm_studio(base_url):
            provider = "lm_studio"
            logger.info("Auto-detected LM Studio server")
        else:
            provider = "local"
            logger.info("LM Studio not available, using local embeddings")

    if provider == "lm_studio":
        _embedding_fn = LMStudioEmbeddings(
            base_url=base_url,
            model=embed_config.get("model", "text-embedding-nomic-embed-text-v1.5@q8_0"),
            batch_size=embed_config.get("batch_size", 32),
        )
        logger.info("Initialized LM Studio embeddings: %s", _embedding_fn.model)
    elif provider == "local":
        _embedding_fn = LocalEmbeddings(
            model=embed_config.get("local_model", "nomic-ai/nomic-embed-text-v1.5"),
            batch_size=embed_config.get("batch_size", 32),
            device=embed_config.get("device", None),
        )
        logger.info("Initialized local embeddings: %s", _embedding_fn.model_name)
    else:
        raise ValueError(f"Unknown embedding provider: {provider}")

    return _embedding_fn


def reset_embedding_function() -> None:
    """Reset the singleton embedding function (e.g. to switch providers)."""
    global _embedding_fn
    _embedding_fn = None


def _get_client():
    """Get the ChromaDB PersistentClient singleton."""
    _require_chromadb()

    global _client
    if _client is None:
        db_path = QMS_PATHS.vector_database
        db_path.mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(path=str(db_path))
        logger.info("ChromaDB initialized at %s", db_path)
    return _client


# ---------------------------------------------------------------------------
# Collection helpers
# ---------------------------------------------------------------------------

def get_chromadb_collection(
    name: str,
    description: Optional[str] = None,
    create_if_missing: bool = True,
):
    """
    Get or create a ChromaDB collection.

    Args:
        name: Collection name.
        description: Optional description stored in collection metadata.
        create_if_missing: When False, raises if the collection does not exist.

    Returns:
        chromadb.Collection with the configured embedding function.
    """
    _require_chromadb()

    client = _get_client()
    embedding_fn = get_embedding_function()

    metadata = {}
    if description:
        metadata["description"] = description

    if create_if_missing:
        return client.get_or_create_collection(
            name=name,
            embedding_function=embedding_fn,
            metadata=metadata if metadata else None,
        )
    else:
        return client.get_collection(name=name, embedding_function=embedding_fn)


def add_documents_to_collection(
    collection_name: str,
    documents: List[str],
    metadatas: Optional[List[Dict[str, Any]]] = None,
    ids: Optional[List[str]] = None,
) -> None:
    """
    Convenience wrapper: add documents to a named collection.

    Args:
        collection_name: Target collection name.
        documents: Text documents to embed and store.
        metadatas: Optional per-document metadata.
        ids: Optional unique IDs (auto-generated if omitted).
    """
    collection = get_chromadb_collection(collection_name)

    if ids is None:
        base = collection.count()
        ids = [f"{collection_name}_{base + i}" for i in range(len(documents))]

    collection.add(documents=documents, metadatas=metadatas, ids=ids)
    logger.info("Added %d documents to %s", len(documents), collection_name)


def list_collections() -> List[Dict[str, Any]]:
    """
    List all collections with document counts.

    Returns:
        List of dicts with 'name', 'count', and 'metadata' keys.
    """
    _require_chromadb()

    client = _get_client()
    result: List[Dict[str, Any]] = []

    for col in client.list_collections():
        try:
            full_col = get_chromadb_collection(col.name, create_if_missing=False)
            result.append({
                "name": col.name,
                "count": full_col.count(),
                "metadata": col.metadata,
            })
        except Exception:
            result.append({"name": col.name, "count": 0, "metadata": col.metadata})

    return result


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

def search_collection(
    collection_name: str,
    query: str,
    n_results: int = 5,
    where: Optional[Dict[str, Any]] = None,
    include: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Search a single collection for semantically similar documents.

    Args:
        collection_name: Collection to search.
        query: Natural-language search query.
        n_results: Number of results to return.
        where: Optional ChromaDB metadata filter.
        include: Fields to include (default: documents, metadatas, distances).

    Returns:
        List of result dicts, each with 'id', 'document', 'metadata', 'distance'.
    """
    _require_chromadb()

    if include is None:
        include = ["documents", "metadatas", "distances"]

    collection = get_chromadb_collection(collection_name, create_if_missing=False)
    raw = collection.query(
        query_texts=[query],
        n_results=n_results,
        where=where,
        include=include,
    )

    results: List[Dict[str, Any]] = []
    if raw["ids"] and raw["ids"][0]:
        for i, doc_id in enumerate(raw["ids"][0]):
            entry: Dict[str, Any] = {"id": doc_id}
            if "documents" in include and raw.get("documents"):
                entry["document"] = raw["documents"][0][i]
            if "metadatas" in include and raw.get("metadatas"):
                entry["metadata"] = raw["metadatas"][0][i]
            if "distances" in include and raw.get("distances"):
                entry["distance"] = raw["distances"][0][i]
            results.append(entry)

    return results


def search_multiple_collections(
    query: str,
    collections: Optional[List[str]] = None,
    n_results: int = 5,
    where: Optional[Dict[str, Any]] = None,
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Search across multiple collections and return results keyed by name.

    Args:
        query: Natural-language search query.
        collections: Collection names to search (default: all existing).
        n_results: Results per collection.
        where: Optional metadata filter applied to each collection.

    Returns:
        Dict mapping collection name to list of result dicts.
    """
    _require_chromadb()

    if collections is None:
        collections = [c["name"] for c in list_collections()]

    output: Dict[str, List[Dict[str, Any]]] = {}
    for name in collections:
        try:
            output[name] = search_collection(name, query, n_results=n_results, where=where)
        except Exception as exc:
            logger.warning("Error searching %s: %s", name, exc)
            output[name] = []

    return output


# ---------------------------------------------------------------------------
# Utility / status
# ---------------------------------------------------------------------------

def test_connection(provider: Optional[str] = None) -> Dict[str, Any]:
    """
    Test embedding function connectivity.

    Args:
        provider: Force specific provider ('lm_studio' or 'local').

    Returns:
        Dict with 'success', 'provider', 'dimensions', and 'error' keys.
    """
    result: Dict[str, Any] = {"success": False, "provider": None, "error": None}

    try:
        _require_chromadb()

        if provider:
            reset_embedding_function()

        embed_fn = get_embedding_function(force_provider=provider)
        result["provider"] = embed_fn.provider

        test_result = embed_fn(["test embedding"])
        if len(test_result) == 1 and len(test_result[0]) > 0:
            result["success"] = True
            result["dimensions"] = len(test_result[0])
        else:
            result["error"] = "Empty embedding returned"

    except Exception as exc:
        result["error"] = str(exc)
        logger.error("Embedding test failed: %s", exc)

    return result


def get_stats() -> Dict[str, Any]:
    """
    Get vector database statistics.

    Returns:
        Dict with 'path', 'collections' count, 'total_documents', and 'details'.
    """
    _require_chromadb()

    collections = list_collections()
    return {
        "path": str(QMS_PATHS.vector_database),
        "collections": len(collections),
        "total_documents": sum(c["count"] for c in collections),
        "details": collections,
    }
