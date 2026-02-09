"""References CLI sub-commands."""

import typer

app = typer.Typer(no_args_is_help=True)


@app.command()
def extract(
    pdf_path: str = typer.Argument(..., help="Path to the reference standard PDF"),
    standard_id: str = typer.Option(..., "--standard-id", "-s", help="Standard ID (e.g. ISO-9001-2015)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Parse only, do not load to database"),
):
    """Extract reference standard content from a PDF into the database."""
    from qms.references.extractor import extract_and_load

    try:
        result = extract_and_load(pdf_path, standard_id, dry_run=dry_run)
    except FileNotFoundError as exc:
        typer.echo(f"Error: {exc}")
        raise typer.Exit(code=1)
    except ValueError as exc:
        typer.echo(f"Error: {exc}")
        raise typer.Exit(code=1)
    except RuntimeError as exc:
        typer.echo(f"Error: {exc}")
        raise typer.Exit(code=1)

    typer.echo(f"Standard:   {result['standard_id']}")
    typer.echo(f"Publisher:  {result['publisher']}")
    typer.echo(f"Characters: {result['characters_extracted']:,}")
    typer.echo(f"Clauses:    {result['clauses_parsed']}")

    if result.get("sample_clauses"):
        typer.echo("\nSample clauses:")
        for c in result["sample_clauses"]:
            typer.echo(f"  {c['number']}: {c['title'][:60]}")

    if result.get("dry_run"):
        typer.echo("\n[DRY RUN] No data written to database.")
    else:
        typer.echo(f"\nBlocks:     {result.get('blocks_loaded', 0)}")
        typer.echo(f"Status:     {result.get('message', 'Done')}")


@app.command("list")
def list_refs(
    status: str = typer.Option(None, "--status", help="Filter by status (CURRENT, SUPERSEDED, WITHDRAWN)"),
    extracted_only: bool = typer.Option(False, "--extracted", help="Show only standards with extracted content"),
):
    """List reference standards in the database."""
    from qms.core import get_db
    from qms.references.extractor import list_references

    with get_db(readonly=True) as conn:
        refs = list_references(conn, status=status, extracted_only=extracted_only)

    if not refs:
        typer.echo("No reference standards found.")
        return

    for r in refs:
        extracted = "*" if r.get("content_extracted") else " "
        typer.echo(
            f"  {extracted} {r['standard_id']:<25} {r['title']:<50} "
            f"{r.get('edition') or '':<10} {r.get('status') or ''}"
        )
    typer.echo(f"\n  {len(refs)} standard(s)  (* = content extracted)")


@app.command()
def search(
    query: str = typer.Argument(..., help="Search text (FTS5 match expression)"),
    content: bool = typer.Option(False, "--content", "-c", help="Search content blocks instead of clause metadata"),
    limit: int = typer.Option(20, "--limit", "-n", help="Maximum results"),
):
    """Search reference standards (full-text search)."""
    from qms.core import get_db
    from qms.references.extractor import search_clauses, search_content

    with get_db(readonly=True) as conn:
        if content:
            results = search_content(conn, query, limit=limit)
        else:
            results = search_clauses(conn, query, limit=limit)

    if not results:
        typer.echo(f"No results for '{query}'.")
        return

    if content:
        for r in results:
            typer.echo(
                f"  {r['standard_id']:<15} {r['clause_number']:<12} "
                f"[{r['block_type']}] {r.get('snippet', '')[:80]}"
            )
    else:
        for r in results:
            snippet = (r.get("requirement_summary") or r.get("clause_title") or "")[:100]
            typer.echo(f"  {r['standard_id']:<15} {r['clause_number']:<12} {snippet}")

    typer.echo(f"\n  {len(results)} result(s)")


@app.command()
def clauses(
    standard_id: str = typer.Argument(..., help="Standard ID to list clauses for"),
):
    """List extracted clauses for a specific standard."""
    from qms.core import get_db
    from qms.references.extractor import list_clauses

    with get_db(readonly=True) as conn:
        results = list_clauses(conn, standard_id)

    if not results:
        typer.echo(f"No clauses found for '{standard_id}'.")
        return

    for r in results:
        typer.echo(f"  {r['clause_number']:<15} {r.get('clause_title', '')}")

    typer.echo(f"\n  {len(results)} clause(s)")
