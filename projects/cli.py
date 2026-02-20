"""Projects CLI sub-commands."""

import typer

app = typer.Typer(no_args_is_help=True)


@app.command("list")
def list_projects(
    stage: str = typer.Option(
        None, "--stage", "-s", help="Filter by stage (e.g. 'Course of Construction')"
    ),
):
    """List all projects in the database."""
    from qms.projects.scanner import list_projects as _list_projects

    projects = _list_projects(status=stage)

    if not projects:
        typer.echo("No projects found.")
        return

    for p in projects:
        st = p.get("stage") or p.get("status") or ""
        flag = f" [{st}]" if st else ""
        typer.echo(
            f"  {p['number']:<10} {p['name']:<40} {p.get('pm') or ''}{flag}"
        )
    typer.echo(f"\n  {len(projects)} project(s)")


@app.command()
def summary(project: str = typer.Argument(..., help="Project number")):
    """Show project summary with discipline breakdown."""
    from qms.projects.scanner import get_project_summary

    result = get_project_summary(project)

    if not result:
        typer.echo(f"Project {project} not found.")
        raise typer.Exit(1)

    typer.echo(f"Project: {result['number']} - {result['name']}")
    typer.echo(f"  Status: {result['status'] or 'unknown'}")
    if result.get("description"):
        typer.echo(f"  Desc:   {result['description']}")
    if result.get("client"):
        typer.echo(f"  Client: {result['client']}")
    if result.get("pm"):
        typer.echo(f"  PM:     {result['pm']}")
    if result.get("path"):
        typer.echo(f"  Path:   {result['path']}")

    # Show allocation breakdown if available
    from qms.core import get_db
    from qms.projects.budget import get_project_allocations

    with get_db(readonly=True) as conn:
        allocs = get_project_allocations(conn, result["id"])
    if allocs:
        typer.echo(f"\n  BU Allocations ({len(allocs)}):")
        for a in allocs:
            typer.echo(
                f"    {a['job_code']:<15} {a['bu_name']:<20} "
                f"${a['allocated_budget']:>10,.0f}  {a['weight_adjustment']}x"
            )

    typer.echo(
        f"\n  Sheets: {result['total_sheets']} total, "
        f"{result['processed']} processed"
    )
    if result["open_flags"]:
        typer.echo(f"  Open flags: {result['open_flags']}")

    if result["disciplines"]:
        typer.echo("\n  Disciplines:")
        for d in result["disciplines"]:
            typer.echo(
                f"    {d['name']:<25} "
                f"{d['sheet_count']:>4} sheets  "
                f"{d['processed_count']:>4} processed"
            )


@app.command()
def scan(
    project: str = typer.Argument(
        None, help="Project number to scan (omit for all projects)"
    ),
    no_manifest: bool = typer.Option(
        False, "--no-manifest", help="Skip writing MANIFEST.json"
    ),
):
    """Scan project directories and update the database."""
    from qms.projects.scanner import (
        get_project,
        scan_all_projects,
        scan_and_sync_project,
    )

    write_manifest = not no_manifest

    if project:
        proj = get_project(project)
        if not proj:
            typer.echo(f"Project {project} not found in database.")
            raise typer.Exit(1)
        if not proj.get("path"):
            typer.echo(f"Project {project} has no path configured.")
            raise typer.Exit(1)

        result = scan_and_sync_project(
            proj["id"],
            proj["number"],
            proj["path"],
            write_manifest=write_manifest,
        )
        _print_scan_result(result)
    else:
        results = scan_all_projects(write_manifest=write_manifest)
        if not results:
            typer.echo("No projects with valid paths found.")
            return
        for result in results:
            _print_scan_result(result)
        typer.echo(f"\n  Scanned {len(results)} project(s)")


def _print_scan_result(result: dict) -> None:
    """Pretty-print a single scan result."""
    typer.echo(f"\n  {result['project_number']} ({result['path']})")
    typer.echo(f"    Disciplines:      {len(result['disciplines'])}")
    typer.echo(f"    PDFs on disk:     {result['total_pdfs_on_disk']}")
    typer.echo(f"    Already indexed:  {result.get('already_indexed', 0)}")
    typer.echo(f"    Newly indexed:    {result.get('newly_indexed', 0)}")
    inserted = result.get("inserted_count", 0)
    if inserted:
        typer.echo(f"    Inserted into DB: {inserted}")
    missing = result.get("missing_from_disk", 0)
    if missing:
        typer.echo(f"    Missing from disk: {missing}")
    if result.get("manifest_path"):
        typer.echo(f"    MANIFEST.json:   {result['manifest_path']}")


@app.command("import-procore")
def import_procore(
    csv_path: str = typer.Argument(..., help="Path to Procore Company Home CSV export"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview changes without writing to database"),
):
    """Import projects and jobs from a Procore Company Home CSV export."""
    from pathlib import Path

    from qms.core import get_db
    from qms.projects.procore_io import import_from_procore

    src = Path(csv_path)
    if not src.exists():
        typer.echo(f"File not found: {src}")
        raise typer.Exit(1)
    if not src.suffix.lower() == ".csv":
        typer.echo(f"Expected .csv file, got: {src.suffix}")
        raise typer.Exit(1)

    with get_db() as conn:
        result = import_from_procore(conn, str(src), dry_run=dry_run)

    prefix = "[DRY RUN] " if dry_run else ""
    typer.echo(f"\n{prefix}Procore import complete:")
    typer.echo(f"  Projects created:  {result['projects_created']}")
    typer.echo(f"  Projects updated:  {result['projects_updated']}")
    typer.echo(f"  Jobs created:      {result['jobs_created']}")
    typer.echo(f"  Jobs updated:      {result['jobs_updated']}")
    typer.echo(f"  Rows skipped:      {result['rows_skipped']}")

    if result["skipped_details"]:
        typer.echo(f"\n  Skipped rows:")
        for s in result["skipped_details"]:
            typer.echo(f"    Row {s['row']}: {s['number']} - {s['reason']}")

    if result["errors"]:
        typer.echo(f"\n  Errors ({len(result['errors'])}):")
        for err in result["errors"]:
            typer.echo(f"    Row {err['row']}: {err['name']} - {'; '.join(err['errors'])}")



# NOTE: export-timecard and migrate-timetracker commands moved to timetracker/cli.py
