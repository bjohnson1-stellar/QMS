"""Automation CLI sub-commands."""

import typer
from pathlib import Path
from typing import Optional

app = typer.Typer(no_args_is_help=True)


@app.command("process")
def process_cmd(
    file: Optional[str] = typer.Argument(None, help="Single JSON file to process"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without processing"),
):
    """Process automation request files from the incoming directory."""
    # Lazy-import to trigger handler registration
    try:
        import qms.welding.cert_requests  # noqa: F401
    except ImportError:
        pass

    from qms.automation.dispatcher import process_all, process_file

    if file:
        filepath = Path(file)
        if not filepath.exists():
            typer.echo(f"ERROR: File not found: {filepath}")
            raise typer.Exit(1)

        result = process_file(filepath, dry_run=dry_run)
        prefix = "[DRY RUN] " if dry_run else ""
        typer.echo(f"{prefix}{result['file']}: {result['status']}")
        if result["error"]:
            typer.echo(f"  Error: {result['error']}")
        if result["result_summary"]:
            typer.echo(f"  Result: {result['result_summary']}")
    else:
        results = process_all(dry_run=dry_run)
        if not results:
            typer.echo("No files to process.")
            return

        prefix = "[DRY RUN] " if dry_run else ""
        typer.echo(f"\n{prefix}Processing Summary")
        typer.echo("=" * 50)
        for r in results:
            status_marker = "OK" if r["status"] == "success" else r["status"].upper()
            typer.echo(f"  [{status_marker}] {r['file']} ({r['type'] or 'unknown'})")
            if r["error"]:
                typer.echo(f"         Error: {r['error']}")

        success = sum(1 for r in results if r["status"] == "success")
        failed = sum(1 for r in results if r["status"] == "failed")
        typer.echo(f"\n  Total: {len(results)}  Success: {success}  Failed: {failed}")


@app.command("status")
def status_cmd(
    limit: int = typer.Option(20, "--limit", "-n", help="Number of entries to show"),
    type: Optional[str] = typer.Option(None, "--type", "-t", help="Filter by request type"),
    status: Optional[str] = typer.Option(None, "--status", "-s", help="Filter by status"),
):
    """Show automation processing log."""
    from qms.automation.dispatcher import get_processing_log

    entries = get_processing_log(limit=limit, status=status, request_type=type)

    if not entries:
        typer.echo("No processing log entries found.")
        return

    typer.echo(f"\n{'ID':>5} {'Status':<10} {'Type':<22} {'File':<35} {'Processed'}")
    typer.echo("-" * 90)
    for e in entries:
        processed = (e.get("processed_at") or "")[:19]
        typer.echo(
            f"{e['id']:>5} {e['status']:<10} {e['request_type']:<22} "
            f"{e['file_name'][:34]:<35} {processed}"
        )
        if e.get("error_message"):
            typer.echo(f"      Error: {e['error_message'][:70]}")
