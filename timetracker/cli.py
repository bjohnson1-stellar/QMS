"""Time Tracker CLI sub-commands."""

import typer

app = typer.Typer(no_args_is_help=True)


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
      1. --start/--end only  -> auto-detects months, handles cross-month
      2. --year/--month      -> single month (with optional --start/--end)
      3. --period            -> by period ID (with optional --start/--end)
    """
    import json
    from datetime import date as _date

    from qms.core import get_db
    from qms.timetracker.timecard import (
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
    typer.echo(f"  {chr(9472)*12} {chr(9472)*10} {chr(9472)*25} {chr(9472)*18} {chr(9472)*25} {chr(9472)*6}")

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
