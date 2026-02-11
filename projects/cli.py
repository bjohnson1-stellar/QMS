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


@app.command("export-timecard")
def export_timecard(
    period_id: int = typer.Option(None, "--period", "-p", help="Projection period ID"),
    year: int = typer.Option(None, "--year", "-y", help="Period year (alternative to --period)"),
    month: int = typer.Option(None, "--month", "-m", help="Period month (alternative to --period)"),
    start_date: str = typer.Option(None, "--start", help="Start date YYYY-MM-DD (default: 1st of month)"),
    end_date: str = typer.Option(None, "--end", help="End date YYYY-MM-DD (default: last of month)"),
    output_format: str = typer.Option("table", "--format", "-f", help="Output format: table | json"),
):
    """Export timecard entries from a projection for UKG entry.

    Three modes:
      1. --start/--end only  → auto-detects months, handles cross-month
      2. --year/--month      → single month (with optional --start/--end)
      3. --period            → by period ID (with optional --start/--end)
    """
    import json
    from datetime import date as _date

    from qms.core import get_db
    from qms.projects.timecard import (
        generate_timecard_entries,
        generate_timecard_for_pay_period,
    )

    # Parse optional date overrides
    sd = _date.fromisoformat(start_date) if start_date else None
    ed = _date.fromisoformat(end_date) if end_date else None

    # Mode 1: date-only (cross-month capable)
    if period_id is None and year is None:
        if sd is None or ed is None:
            typer.echo(
                "Provide --start and --end, or --year/--month, or --period."
            )
            raise typer.Exit(1)
        with get_db(readonly=True) as conn:
            result = generate_timecard_for_pay_period(conn, sd, ed)
    else:
        # Mode 2/3: resolve a single period
        if period_id is None:
            if month is None:
                typer.echo("Provide --month with --year.")
                raise typer.Exit(1)
            with get_db(readonly=True) as conn:
                row = conn.execute(
                    "SELECT id FROM projection_periods WHERE year = ? AND month = ?",
                    (year, month),
                ).fetchone()
                if not row:
                    typer.echo(f"No projection period found for {year}-{month:02d}.")
                    raise typer.Exit(1)
                period_id = row["id"]

        with get_db(readonly=True) as conn:
            result = generate_timecard_entries(
                conn, period_id, start_date=sd, end_date=ed
            )

    if "error" in result:
        typer.echo(f"Error: {result['error']}")
        raise typer.Exit(1)

    if output_format == "json":
        typer.echo(json.dumps(result, indent=2))
        return

    # Table output
    typer.echo(
        f"\n  Timecard: {result['date_range']['start']} to {result['date_range']['end']}"
    )
    if "periods" in result:
        # Cross-month response
        for pd in result["periods"]:
            typer.echo(
                f"    {pd['year']}-{pd['month']:02d}: "
                f"{pd['working_days']} days, {pd['hours']:.2f} hrs"
            )
    elif "snapshot_version" in result:
        typer.echo(f"  Snapshot v{result['snapshot_version']}")
    typer.echo(
        f"  {result['working_days']} working days  |  "
        f"{result['total_hours']} total hours  |  "
        f"{result['entry_count']} entries"
    )

    if result["warnings"]:
        typer.echo("\n  Warnings:")
        for w in result["warnings"]:
            typer.echo(f"    ! {w}")

    # Group by date for readable output
    typer.echo(f"\n  {'Date':<12} {'Day':<10} {'Project':<25} {'Job Code':<18} {'Transfer':<25} {'Hours':>6}")
    typer.echo(f"  {'─'*12} {'─'*10} {'─'*25} {'─'*18} {'─'*25} {'─'*6}")

    current_date = None
    for e in result["entries"]:
        date_str = e["date"] if e["date"] != current_date else ""
        day_str = e["day_name"] if e["date"] != current_date else ""
        current_date = e["date"]
        typer.echo(
            f"  {date_str:<12} {day_str:<10} {e['project_name']:<25} "
            f"{e['cleaned_job_number']:<18} {e['transfer']:<25} {e['amount']:>6.2f}"
        )

    typer.echo(f"\n  Total: {result['total_hours']:.2f} hours across {result['entry_count']} entries")


@app.command("migrate-timetracker")
def migrate_timetracker(
    db_path: str = typer.Argument(
        r"D:\Time Tracker\time_tracker.db",
        help="Path to Time Tracker SQLite database",
    ),
):
    """One-time import from Time Tracker database into QMS."""
    from pathlib import Path

    from qms.projects.migrate_timetracker import migrate

    src = Path(db_path)
    if not src.exists():
        typer.echo(f"Database not found: {src}")
        raise typer.Exit(1)

    result = migrate(str(src))
    typer.echo(f"\nMigration complete:")
    typer.echo(f"  Business units: {result['business_units_migrated']}")
    typer.echo(f"  Projects matched: {result['projects_matched']}")
    typer.echo(f"  Projects created: {result['projects_created']}")
    typer.echo(f"  Budgets created: {result['budgets_created']}")
    typer.echo(f"  Allocations created: {result['allocations_created']}")
    typer.echo(f"  Transactions: {result['transactions_migrated']}")
    typer.echo(f"  Settings: {'migrated' if result['settings_migrated'] else 'skipped'}")
    typer.echo(f"  Projection periods: {result['periods_migrated']}")
    if result["errors"]:
        typer.echo(f"\n  Errors ({len(result['errors'])}):")
        for err in result["errors"][:10]:
            typer.echo(f"    - {err}")
