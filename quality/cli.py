"""
Quality Issues CLI — import, query, and manage quality issues.

Usage:
    qms quality import-csv "path/to/observations.csv" --project 07645
    qms quality import-csv "path/to/observations.csv" --project 07645 --dry-run
    qms quality summary
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
