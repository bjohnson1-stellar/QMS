"""Engineering CLI sub-commands."""

import typer

app = typer.Typer(no_args_is_help=True)


@app.command()
def history(limit: int = typer.Option(20, help="Number of records")):
    """Show recent calculation history."""
    from qms.core import get_db

    with get_db(readonly=True) as conn:
        rows = conn.execute(
            "SELECT timestamp, discipline, calculation_type, equipment_tag, line_number "
            "FROM eng_calculations ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        ).fetchall()

    if not rows:
        typer.echo("No calculations recorded.")
        return

    for r in rows:
        tag = r['equipment_tag'] or r['line_number'] or ''
        typer.echo(f"  {r['timestamp'][:16]}  {r['discipline']:<12} {r['calculation_type']:<20} {tag}")
