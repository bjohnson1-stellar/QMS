"""
Quality Issues CLI — import, query, and manage quality issues.

Usage:
    qms quality import-csv "path/to/observations.csv" --project 07645
    qms quality import-csv "path/to/observations.csv" --project 07645 --dry-run
    qms quality summary
    qms quality capture --folder /path/to/photos --project 07645
    qms quality capture --dry-run
"""

import typer

from qms.core import get_logger
from qms.core.db import get_db

logger = get_logger("qms.quality.cli")

app = typer.Typer()


@app.command("import-csv")
def import_csv(
    csv_path: str = typer.Argument(..., help="Path to CSV file"),
    project: str = typer.Option(..., help="Project number (e.g. 07645)"),
    source: str = typer.Option("procore", help="Source tag for imported issues"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show plan without executing"),
) -> None:
    """Import quality issues from a CSV file."""
    from qms.quality.import_engine import import_quality_csv

    with get_db() as conn:
        # Resolve project number → project_id
        row = conn.execute(
            "SELECT id, name FROM projects WHERE number = ?", (project,)
        ).fetchone()

        if not row:
            typer.echo(f"Error: Project '{project}' not found in database.", err=True)
            raise typer.Exit(1)

        project_id = row["id"]
        project_name = row["name"]

        if dry_run:
            typer.echo(f"DRY RUN — no changes will be made")

        typer.echo(f"Importing to project {project} ({project_name}, id={project_id})")
        typer.echo(f"Source: {source}")
        typer.echo(f"File: {csv_path}")
        typer.echo("---")

        result = import_quality_csv(
            conn,
            csv_path,
            project_id=project_id,
            source=source,
            dry_run=dry_run,
        )

        typer.echo(f"Rows processed: {result['rows_total']}")
        typer.echo(f"  Created: {result['issues_created']}")
        typer.echo(f"  Updated: {result['issues_updated']}")
        typer.echo(f"  Skipped: {result['issues_skipped']}")

        if result["errors"]:
            typer.echo(f"  Errors:  {len(result['errors'])}")
            for err in result["errors"][:5]:
                if isinstance(err, dict):
                    typer.echo(f"    Row {err.get('row', '?')}: {err.get('error', err)}")
                else:
                    typer.echo(f"    {err}")

        if result["skipped_details"]:
            typer.echo("  Skipped details:")
            for skip in result["skipped_details"][:5]:
                typer.echo(f"    Row {skip['row']}: {skip['reason']}")


@app.command("import-batch")
def import_batch_cmd(
    directory: str = typer.Argument(..., help="Directory containing observation CSV files"),
    project: str = typer.Option(None, help="Project number to use for all files (overrides filename detection)"),
    source: str = typer.Option("procore", help="Source tag for imported issues"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show plan without executing"),
) -> None:
    """Batch import quality issues from all CSVs in a directory."""
    from qms.quality.import_engine import import_batch

    with get_db() as conn:
        if dry_run:
            typer.echo("DRY RUN — no changes will be made")

        typer.echo(f"Scanning: {directory}")
        if project:
            typer.echo(f"All files → project {project}")
        typer.echo(f"Source: {source}")
        typer.echo("---")

        result = import_batch(
            conn,
            directory,
            source=source,
            dry_run=dry_run,
            project_number=project,
        )

        if result["errors"] and isinstance(result["errors"][0], str):
            for err in result["errors"]:
                typer.echo(f"Error: {err}", err=True)
            raise typer.Exit(1)

        # Per-file results
        for pf in result["per_file"]:
            typer.echo(
                f"  {pf['file']:40s} → {pf['project']:>6s}  "
                f"created={pf['created']} updated={pf['updated']} skipped={pf['skipped']}"
            )

        # Unresolved files
        if result["unresolved"]:
            typer.echo()
            typer.echo("Unresolved (skipped):")
            for u in result["unresolved"]:
                typer.echo(f"  {u['file']:40s} — {u['reason']}")

        # Totals
        typer.echo("---")
        typer.echo(f"Files processed: {result['files_processed']}")
        typer.echo(f"Files skipped:   {result['files_skipped']}")
        typer.echo(f"Total created:   {result['total_created']}")
        typer.echo(f"Total updated:   {result['total_updated']}")
        typer.echo(f"Total skipped:   {result['total_skipped']}")

        if result["errors"]:
            typer.echo(f"Errors: {len(result['errors'])}")
            for err in result["errors"]:
                if isinstance(err, dict):
                    typer.echo(f"  {err.get('file', '?')}: {err.get('error', err)}")


@app.command("import-procore")
def import_procore_cmd(
    csv_path: str = typer.Argument(..., help="Path to Procore observation CSV"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show plan without executing"),
) -> None:
    """Import a Procore observation CSV, auto-detecting the project from filename."""
    from pathlib import Path
    from qms.quality.import_engine import import_quality_csv, resolve_project_from_filename

    filename = Path(csv_path).name

    with get_db() as conn:
        resolved = resolve_project_from_filename(conn, filename)
        if not resolved:
            typer.echo(
                f"Error: Could not resolve project from filename '{filename}'.\n"
                f"Use: qms quality import-csv \"{csv_path}\" --project <NUMBER>",
                err=True,
            )
            raise typer.Exit(1)

        project_id, project_number = resolved

        if dry_run:
            typer.echo("DRY RUN — no changes will be made")

        typer.echo(f"File: {csv_path}")
        typer.echo(f"Auto-detected project: {project_number}")
        typer.echo("---")

        result = import_quality_csv(
            conn,
            csv_path,
            project_id=project_id,
            source="procore",
            dry_run=dry_run,
        )

        typer.echo(f"Rows processed: {result['rows_total']}")
        typer.echo(f"  Created: {result['issues_created']}")
        typer.echo(f"  Updated: {result['issues_updated']}")
        typer.echo(f"  Skipped: {result['issues_skipped']}")

        if result["errors"]:
            typer.echo(f"  Errors:  {len(result['errors'])}")
            for err in result["errors"][:5]:
                if isinstance(err, dict):
                    typer.echo(f"    Row {err.get('row', '?')}: {err.get('error', err)}")
                else:
                    typer.echo(f"    {err}")


@app.command("summary")
def summary() -> None:
    """Show summary of quality issues in the database."""
    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) as cnt FROM quality_issues").fetchone()["cnt"]

        if total == 0:
            typer.echo("No quality issues in database.")
            return

        typer.echo(f"Total quality issues: {total}")
        typer.echo()

        # By type
        typer.echo("By type:")
        rows = conn.execute(
            "SELECT type, COUNT(*) as cnt FROM quality_issues GROUP BY type ORDER BY cnt DESC"
        ).fetchall()
        for r in rows:
            typer.echo(f"  {r['type']:15s} {r['cnt']:>5d}")

        typer.echo()

        # By status
        typer.echo("By status:")
        rows = conn.execute(
            "SELECT status, COUNT(*) as cnt FROM quality_issues GROUP BY status ORDER BY cnt DESC"
        ).fetchall()
        for r in rows:
            typer.echo(f"  {r['status']:15s} {r['cnt']:>5d}")

        typer.echo()

        # By project
        typer.echo("By project:")
        rows = conn.execute(
            """SELECT p.number, p.name, COUNT(*) as cnt
               FROM quality_issues qi
               JOIN projects p ON p.id = qi.project_id
               GROUP BY qi.project_id
               ORDER BY cnt DESC
               LIMIT 10"""
        ).fetchall()
        for r in rows:
            typer.echo(f"  {r['number']:10s} {r['name'][:30]:30s} {r['cnt']:>5d}")

        typer.echo()

        # By source
        typer.echo("By source:")
        rows = conn.execute(
            "SELECT source, COUNT(*) as cnt FROM quality_issues GROUP BY source ORDER BY cnt DESC"
        ).fetchall()
        for r in rows:
            typer.echo(f"  {r['source']:15s} {r['cnt']:>5d}")


@app.command("capture")
def capture_cmd(
    folder: str = typer.Option(None, help="Override source folder path"),
    project: str = typer.Option(None, help="Project number to assign issues to (e.g. 07645)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Analyze without creating issues"),
) -> None:
    """Process mobile captures — analyze photos with AI and create quality issues."""
    from pathlib import Path
    from qms.quality.mobile_capture import process_captures

    project_id = None
    if project:
        with get_db() as conn:
            row = conn.execute(
                "SELECT id, name FROM projects WHERE number = ?", (project,)
            ).fetchone()
            if not row:
                typer.echo(f"Error: Project '{project}' not found in database.", err=True)
                raise typer.Exit(1)
            project_id = row["id"]
            typer.echo(f"Project: {project} ({row['name']})")

    folder_path = Path(folder) if folder else None

    if dry_run:
        typer.echo("DRY RUN — analyzing without creating issues")

    typer.echo("Processing mobile captures...")
    typer.echo("---")

    result = process_captures(
        folder=folder_path,
        project_id=project_id,
        dry_run=dry_run,
    )

    typer.echo(f"Folder: {result['folder']}")
    typer.echo(f"Processed: {result['processed']}")
    typer.echo(f"Failed:    {result['failed']}")
    typer.echo(f"Skipped:   {result['skipped']}")

    if result["issues_created"]:
        typer.echo()
        typer.echo("Issues created:")
        for item in result["issues_created"]:
            if "issue_id" in item:
                typer.echo(f"  #{item['issue_id']}: {item['title']} ({item['file']})")
            else:
                analysis = item.get("analysis", {})
                typer.echo(
                    f"  [DRY RUN] {analysis.get('title', '?')} "
                    f"({analysis.get('trade', '?')}, {analysis.get('severity', '?')}) "
                    f"← {item['file']}"
                )

    if result["errors"]:
        typer.echo()
        typer.echo("Errors:")
        for err in result["errors"]:
            typer.echo(f"  {err['file']}: {err['error']}")


@app.command("index")
def index_cmd(
    rebuild: bool = typer.Option(False, "--rebuild", help="Clear and rebuild index from scratch"),
) -> None:
    """Index quality issues into the vector database for semantic search."""
    try:
        from qms.vectordb.indexer import index_quality_issues
    except ImportError:
        typer.echo(
            "Error: chromadb is required for indexing. Install: pip install chromadb",
            err=True,
        )
        raise typer.Exit(1)

    if rebuild:
        typer.echo("Rebuilding quality issues index...")
    else:
        typer.echo("Indexing quality issues...")

    count = index_quality_issues(rebuild=rebuild)
    typer.echo(f"Indexed {count} quality issue documents.")
