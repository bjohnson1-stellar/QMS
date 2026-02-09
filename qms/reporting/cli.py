"""Reporting CLI sub-commands."""

import typer

app = typer.Typer(no_args_is_help=True)


@app.command()
def system():
    """Show system-wide quality dashboard."""
    from qms.core import get_db

    with get_db(readonly=True) as conn:
        projects = conn.execute("SELECT COUNT(*) as n FROM projects WHERE status='active'").fetchone()
        employees = conn.execute("SELECT COUNT(*) as n FROM employees WHERE status='active'").fetchone()
        sheets = conn.execute("SELECT COUNT(*) as n FROM sheets WHERE is_current=1").fetchone()
        conflicts = conn.execute("SELECT COUNT(*) as n FROM conflicts WHERE resolved=0").fetchone()

    typer.echo("QMS System Dashboard")
    typer.echo("=" * 30)
    typer.echo(f"  Active projects:    {projects['n']}")
    typer.echo(f"  Active employees:   {employees['n']}")
    typer.echo(f"  Current sheets:     {sheets['n']}")
    typer.echo(f"  Open conflicts:     {conflicts['n']}")
