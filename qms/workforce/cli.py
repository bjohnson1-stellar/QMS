"""Workforce CLI sub-commands."""

from pathlib import Path
from typing import Optional

import typer

app = typer.Typer(no_args_is_help=True)


@app.command()
def list(active_only: bool = typer.Option(True, help="Show only active employees")):
    """List employees."""
    from qms.core import get_db

    with get_db(readonly=True) as conn:
        if active_only:
            rows = conn.execute(
                "SELECT employee_number, last_name, first_name, position "
                "FROM employees WHERE status = 'active' ORDER BY last_name"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT employee_number, last_name, first_name, position, status "
                "FROM employees ORDER BY last_name"
            ).fetchall()

    if not rows:
        typer.echo("No employees found.")
        return

    for r in rows:
        typer.echo(f"  {r['employee_number'] or '---':>8}  {r['last_name']}, {r['first_name']:<20} {r['position'] or ''}")
    typer.echo(f"\n  {len(rows)} employee(s)")


@app.command()
def import_csv(file: str = typer.Argument(..., help="Path to CSV file")):
    """Import employees from CSV file."""
    from qms.workforce.employees import import_from_csv

    result = import_from_csv(file)
    typer.echo(
        f"Imported: {result['inserted']} new, {result['updated']} updated, "
        f"{result['flagged_for_review']} flagged"
    )


@app.command("import-from-sis")
def import_from_sis(
    file: str = typer.Argument(..., help="Path to SIS Excel workbook"),
    week_ending: str = typer.Option(
        None,
        help="Week-ending date (YYYY-MM-DD). Auto-detected from sheet if omitted.",
    ),
):
    """Import employees from an SIS field-locations workbook."""
    from datetime import date as _date

    from qms.core import get_db, get_logger
    from qms.workforce.sis_import import format_import_summary, import_employees_from_sis

    logger = get_logger("qms.workforce.cli")
    src = Path(file)
    if not src.exists():
        typer.echo(f"File not found: {src}")
        raise typer.Exit(code=1)

    # Attempt to load the workbook and extract employee records.
    # The SIS parser is expected to live in qms.pipeline; fall back
    # gracefully if it is not yet wired up.
    try:
        from qms.pipeline.sis_common import parse_sis_sheet  # type: ignore[import-untyped]
    except ImportError:
        typer.echo(
            "SIS sheet parser (qms.pipeline.sis_common.parse_sis_sheet) is not "
            "available yet.  Please ensure the pipeline module has been ported."
        )
        raise typer.Exit(code=1)

    import openpyxl  # type: ignore[import-untyped]

    wb = openpyxl.load_workbook(str(src), data_only=True)
    jobsites, employees = parse_sis_sheet(wb)

    if week_ending:
        we = _date.fromisoformat(week_ending)
    else:
        # Try to pull it from the first jobsite record
        we = getattr(jobsites[0], "week_ending", None) if jobsites else None
        if we is None:
            typer.echo("Could not auto-detect week-ending date. Use --week-ending.")
            raise typer.Exit(code=1)

    with get_db() as conn:
        stats = import_employees_from_sis(conn, employees, we)

    typer.echo(format_import_summary(stats))


@app.command("bulk-update")
def bulk_update(
    file: str = typer.Argument(..., help="Path to CSV with id column and fields to update"),
):
    """Bulk-update employee records from a CSV file.

    Each row must contain an ``id`` column (employee UUID).  All other
    columns are treated as fields to update (only allowed fields are
    applied; unknown columns are silently ignored).
    """
    import csv

    from qms.core import get_db
    from qms.workforce.employees import update_employee

    src = Path(file)
    if not src.exists():
        typer.echo(f"File not found: {src}")
        raise typer.Exit(code=1)

    updated = 0
    skipped = 0
    with open(src, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        with get_db() as conn:
            for row in reader:
                eid = row.pop("id", None)
                if not eid:
                    skipped += 1
                    continue
                # Convert numeric-looking fields
                for key in ("department_id", "job_id", "role_id"):
                    if key in row and row[key]:
                        try:
                            row[key] = int(row[key])
                        except ValueError:
                            pass
                if update_employee(conn, eid, **row):
                    updated += 1
                else:
                    skipped += 1

    typer.echo(f"Bulk update complete: {updated} updated, {skipped} skipped.")
