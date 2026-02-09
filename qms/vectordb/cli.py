"""VectorDB CLI sub-commands."""

import typer
from typing import Optional

app = typer.Typer(no_args_is_help=True)


@app.command()
def index(
    target: Optional[str] = typer.Argument(
        None,
        help="What to index: all, qm, refs, specs, drawings (default: all)",
    ),
    rebuild: bool = typer.Option(False, "--rebuild", help="Delete existing and rebuild"),
):
    """Build or rebuild vector search index from quality.db content."""
    from qms.vectordb.indexer import (
        index_all,
        index_drawings,
        index_qm_content,
        index_ref_clauses,
        index_specifications,
    )

    target = (target or "all").lower()

    dispatch = {
        "all": lambda: index_all(rebuild=rebuild),
        "qm": lambda: {"qm_content": index_qm_content(rebuild=rebuild)},
        "refs": lambda: {"ref_clauses": index_ref_clauses(rebuild=rebuild)},
        "specs": lambda: {"specifications": index_specifications(rebuild=rebuild)},
        "drawings": lambda: {"drawings": index_drawings(rebuild=rebuild)},
    }

    fn = dispatch.get(target)
    if fn is None:
        typer.echo(f"Unknown target: {target}")
        typer.echo("Valid targets: all, qm, refs, specs, drawings")
        raise typer.Exit(1)

    results = fn()

    typer.echo()
    typer.echo("Index Results")
    typer.echo("=" * 40)
    for name, count in results.items():
        typer.echo(f"  {name}: {count} documents indexed")
    typer.echo(f"  Total: {sum(results.values())} documents")


@app.command()
def search(
    query: str = typer.Argument(..., help="Search query text"),
    collection: Optional[str] = typer.Option(
        None, "--collection", "-c", help="Collection to search (default: all)"
    ),
    n: int = typer.Option(5, "--results", "-n", help="Number of results"),
):
    """Semantic search across indexed content."""
    if collection:
        from qms.vectordb.search import search_collection

        results = search_collection(collection, query, n_results=n)

        typer.echo(f"\nSearching '{collection}' for: {query}")
        typer.echo("-" * 60)

        if not results:
            typer.echo("No results found.")
            return

        for i, r in enumerate(results, 1):
            dist = r.get("distance", 0)
            meta = r.get("metadata", {})
            doc = r.get("document", "")
            preview = doc[:200] + "..." if len(doc) > 200 else doc

            typer.echo(f"\n--- Result {i} (distance: {dist:.4f}) ---")
            typer.echo(f"  Source: {meta.get('source', 'unknown')}")
            for k, v in meta.items():
                if k not in ("source",):
                    typer.echo(f"  {k}: {v}")
            typer.echo(f"  Content: {preview}")
    else:
        from qms.vectordb.search import search_multiple_collections

        all_results = search_multiple_collections(query, n_results=n)

        typer.echo(f"\nSearching all collections for: {query}")
        typer.echo("=" * 60)

        total = 0
        for coll_name, results in all_results.items():
            if not results:
                continue
            total += len(results)
            typer.echo(f"\n  [{coll_name}] ({len(results)} results)")
            for i, r in enumerate(results, 1):
                dist = r.get("distance", 0)
                doc = r.get("document", "")
                preview = doc[:120] + "..." if len(doc) > 120 else doc
                typer.echo(f"    {i}. (d={dist:.4f}) {preview}")

        if total == 0:
            typer.echo("\nNo results found in any collection.")


@app.command()
def status():
    """Show vector database status (collection sizes, path)."""
    from qms.vectordb.search import get_stats, test_connection, HAS_CHROMADB

    if not HAS_CHROMADB:
        typer.echo("ChromaDB is not installed.")
        typer.echo("Install: pip install chromadb")
        return

    # Test embedding connectivity
    conn = test_connection()
    typer.echo()
    typer.echo("VectorDB Status")
    typer.echo("=" * 40)
    typer.echo(f"  Embeddings:  {'OK' if conn['success'] else 'UNAVAILABLE'}")
    if conn["success"]:
        typer.echo(f"  Provider:    {conn['provider']}")
        typer.echo(f"  Dimensions:  {conn['dimensions']}")
    elif conn["error"]:
        typer.echo(f"  Error:       {conn['error']}")

    try:
        stats = get_stats()
        typer.echo(f"  DB path:     {stats['path']}")
        typer.echo(f"  Collections: {stats['collections']}")
        typer.echo(f"  Total docs:  {stats['total_documents']}")

        if stats["details"]:
            typer.echo()
            typer.echo("  Collections:")
            for col in stats["details"]:
                desc = (col.get("metadata") or {}).get("description", "")
                typer.echo(f"    {col['name']}: {col['count']} documents")
                if desc:
                    typer.echo(f"      {desc}")
    except Exception as exc:
        typer.echo(f"  DB error:    {exc}")

    # Queue stats
    try:
        from qms.vectordb.embedder import get_queue_stats

        qstats = get_queue_stats()
        typer.echo()
        typer.echo("  Embedding Queue:")
        typer.echo(f"    Pending:    {qstats['pending']}")
        typer.echo(f"    Processing: {qstats['processing']}")
        typer.echo(f"    Completed:  {qstats['completed']}")
        typer.echo(f"    Failed:     {qstats['failed']}")
    except Exception:
        pass


@app.command()
def queue(
    action: str = typer.Argument(
        ..., help="Queue action: add, process, sync, clear"
    ),
    target: Optional[str] = typer.Option(None, "--target", "-t", help="File path or collection name"),
    collection: Optional[str] = typer.Option(None, "--collection", "-c", help="Target collection"),
    reindex: bool = typer.Option(False, "--reindex", help="Queue a collection reindex"),
    priority: int = typer.Option(5, "--priority", help="Priority 1-10 (lower = higher)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without changes"),
    max_items: int = typer.Option(50, "--max", help="Max items to process"),
    days: int = typer.Option(7, "--days", help="Clear items older than N days"),
):
    """Manage the embedding queue (add, process, sync, clear)."""
    from qms.vectordb.embedder import (
        add_to_queue,
        clear_completed,
        get_queue_stats,
        process_queue,
        sync_check,
        sync_queue,
    )
    from pathlib import Path

    action = action.lower()

    if action == "add":
        if reindex:
            coll = collection or target or "all"
            add_to_queue("collection", coll, priority=priority)
            typer.echo(f"Queued reindex for: {coll}")
        elif target:
            add_to_queue("file", target, collection, priority=priority)
            typer.echo(f"Queued file: {target}")
        else:
            typer.echo("Specify --target (file) or --reindex (collection)")

    elif action == "process":
        stats = process_queue(max_items=max_items)
        typer.echo()
        typer.echo(f"Processed: {stats['processed']}")
        typer.echo(f"Failed:    {stats['failed']}")
        typer.echo(f"Skipped:   {stats['skipped']}")

    elif action == "sync":
        report = sync_check()

        typer.echo()
        typer.echo("Sync Check")
        typer.echo("=" * 40)
        typer.echo("\nCollections:")
        for name, info in report["collections"].items():
            sync_status = "synced" if info["synced"] else f"{info['gap']} unembedded"
            typer.echo(f"  {name}:")
            typer.echo(f"    SQLite:   {info['sqlite']} documents")
            typer.echo(f"    ChromaDB: {info['chromadb']} documents")
            typer.echo(f"    Status:   {sync_status}")

        if report["files"]:
            typer.echo(f"\nUnembedded files: {len(report['files'])}")
            for f in report["files"][:10]:
                typer.echo(f"  - {Path(f['path']).name} ({f['collection']})")
            if len(report["files"]) > 10:
                typer.echo(f"  ... and {len(report['files']) - 10} more")

        typer.echo(
            f"\nTotal gap: {report['total_gap']} documents + {len(report['files'])} files"
        )

        if report["total_gap"] > 0 or report["files"]:
            if dry_run:
                typer.echo("\n[Dry run] Would queue:")
                sync_queue(dry_run=True)
            else:
                typer.echo("\nQueueing unembedded content...")
                queued = sync_queue(dry_run=False)
                typer.echo(
                    f"\nQueued: {queued['collections']} collections, {queued['files']} files"
                )
                typer.echo("Run: qms vectordb queue process")
        else:
            typer.echo("\nEverything is synced!")

    elif action == "clear":
        deleted = clear_completed(days_old=days)
        typer.echo(f"Cleared {deleted} completed items older than {days} days")

    elif action == "status":
        qstats = get_queue_stats()
        typer.echo()
        typer.echo("Embedding Queue Status")
        typer.echo("=" * 40)
        typer.echo(f"  Pending:    {qstats['pending']}")
        typer.echo(f"  Processing: {qstats['processing']}")
        typer.echo(f"  Completed:  {qstats['completed']}")
        typer.echo(f"  Failed:     {qstats['failed']}")

        if qstats["recent"]:
            typer.echo("\n  Recent items:")
            for item in qstats["recent"][:5]:
                typer.echo(f"    [{item['status']}] {item['task_type']}: {item['target']}")
    else:
        typer.echo(f"Unknown action: {action}")
        typer.echo("Valid actions: add, process, sync, clear, status")
