"""
Licenses CLI — auto-expire and license management commands.
"""

import typer

app = typer.Typer(help="License compliance management")


@app.command()
def auto_expire(
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would expire without changing"),
):
    """Mark active licenses past their expiration date as expired."""
    from qms.core import get_db
    from qms.licenses.db import auto_expire_licenses

    with get_db() as conn:
        result = auto_expire_licenses(conn, dry_run=dry_run)

    if dry_run:
        count = len(result["licenses"])
        if count == 0:
            typer.echo("No licenses past expiration date.")
        else:
            typer.echo(f"Would expire {count} license(s):")
            for lic in result["licenses"]:
                typer.echo(
                    f"  - {lic['holder_name']} ({lic['state_code']}) "
                    f"#{lic['license_number']} — expired {lic['expiration_date']}"
                )
    else:
        count = result["expired_count"]
        if count == 0:
            typer.echo("No licenses past expiration date.")
        else:
            typer.echo(f"Expired {count} license(s).")
            for lic in result["licenses"]:
                typer.echo(
                    f"  - {lic['holder_name']} ({lic['state_code']}) "
                    f"#{lic['license_number']}"
                )
