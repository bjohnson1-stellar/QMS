---
module: vectordb
cli_name: vectordb
status: Complete
commands: [index, search, status, queue]
depends_on: [core, qualitydocs, references, pipeline]
depended_by: []
tables: [embed_queue]
external_storage: ChromaDB
api_blueprint: "-"
source_dir: vectordb/
schema_file: "-"
tags: [qms-module, semantic-search, ai, embeddings]
created: 2026-02-10
updated: 2026-02-10
---

# Vector Database

Provides **semantic search** across all QMS content using vector embeddings. Indexes quality manual content, reference standard clauses, drawing extractions, and specifications into ChromaDB collections.

## Architecture

- Uses **ChromaDB** for vector storage (not SQLite — external dependency)
- Embedding queue (`embed_queue` table) manages pending embeddings
- Sync check ensures SQLite source data matches ChromaDB state
- Supports multiple embedding providers (sentence-transformers default)
- Four indexable content types: QM content, reference clauses, drawings, specifications

```
SQLite (source of truth) → embed_queue → ChromaDB (vector index)
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `qms vectordb index [target] [--rebuild]` | Build/rebuild vector index (targets: all, qm, refs, specs, drawings) |
| `qms vectordb search <query> [--collection]` | Semantic search across indexed content |
| `qms vectordb status` | Show vector database status (collections, counts, provider) |
| `qms vectordb queue <action>` | Manage embedding queue (add, process, sync, clear, status) |

## Database Tables

| Table | Purpose |
|-------|---------|
| `embed_queue` | Embedding job queue (created dynamically by `embedder.py`) |

> **Note:** Vector data stored in ChromaDB at `data/vectordb/`, not in SQLite.

## Key Functions

| Function | Location | Description |
|----------|----------|-------------|
| `index_all()` | `vectordb/indexer.py` | Index all content types |
| `index_qm_content()` | `vectordb/indexer.py` | Index quality manual content |
| `index_ref_clauses()` | `vectordb/indexer.py` | Index reference standard clauses |
| `index_drawings()` | `vectordb/indexer.py` | Index drawing extractions |
| `index_specifications()` | `vectordb/indexer.py` | Index specifications |
| `search_collection()` | `vectordb/search.py` | Search single collection |
| `search_multiple_collections()` | `vectordb/search.py` | Search across all collections |
| `process_queue()` | `vectordb/embedder.py` | Process pending embeddings |
| `sync_check()` | `vectordb/embedder.py` | Check sync status (SQLite vs ChromaDB) |

## Dependencies

### Depends On
- [[core]] — Database, logging, config
- [[qualitydocs]] — Index QM content
- [[references]] — Index reference clauses
- [[pipeline]] — Index drawings and specifications

### Depended By
None — leaf module (consumer of all content modules).

## Related Notes
- [[qualitydocs]] — Source content for QM collection
- [[references]] — Source content for refs collection
- [[pipeline]] — Source content for drawings/specs collections
