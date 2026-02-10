"""Projects CLI sub-commands."""

import typer

app = typer.Typer(no_args_is_help=True)


@app.command("list")
def list_projects(
    status: str = typer.Option(
        None, "--status", "-s", help="Filter by status (e.g. active)"
    ),
):
    """List all projects in the database."""
    from qms.projects.scanner import list_projects as _list_projects

    projects = _list_projects(status=status)

    if not projects:
        typer.echo("No projects found.")
        return

    for p in projects:
        flag = f" [{p['status']}]" if p["status"] != "active" else ""
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
    if result.get("client"):
        typer.echo(f"  Client: {result['client']}")
    if result.get("pm"):
        typer.echo(f"  PM:     {result['pm']}")
    if result.get("path"):
        typer.echo(f"  Path:   {result['path']}")

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
