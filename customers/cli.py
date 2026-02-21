"""
Customer profile CLI commands.

Usage:
    qms customers list
    qms customers profile <id>
    qms customers requirements <id>
"""

import typer

app = typer.Typer(no_args_is_help=True)


@app.command("list")
def list_customers(
    status: str = typer.Option("active", help="Filter by status (active/inactive)"),
    tier: str = typer.Option(None, help="Filter by tier (key/strategic/standard)"),
):
    """List all customers with project counts."""
    from qms.core import get_db
    from qms.customers.db import list_customers as _list

    with get_db(readonly=True) as conn:
        rows = _list(conn, status=status, tier=tier)

    if not rows:
        typer.echo("No customers found.")
        raise typer.Exit()

    typer.echo(f"{'ID':<5} {'Name':<30} {'Tier':<10} {'Industry':<20} {'Projects':<9} {'Reqs':<5} {'Specs':<5}")
    typer.echo("-" * 84)
    for r in rows:
        typer.echo(
            f"{r['id']:<5} {r['name']:<30} {(r['tier'] or '-'):<10} "
            f"{(r['industry'] or '-'):<20} {r['project_count']:<9} "
            f"{r['requirement_count']:<5} {r['spec_count']:<5}"
        )


@app.command("profile")
def profile(customer_id: int = typer.Argument(..., help="Customer ID")):
    """Show full customer profile."""
    from qms.core import get_db
    from qms.customers.db import get_customer_summary

    with get_db(readonly=True) as conn:
        summary = get_customer_summary(conn, customer_id)

    if not summary:
        typer.echo(f"Customer {customer_id} not found.")
        raise typer.Exit(1)

    c = summary["customer"]
    typer.echo(f"Customer: {c['name']} (ID {c['id']})")
    typer.echo(f"Tier: {c.get('tier', 'standard')}  |  Industry: {c.get('industry', '-')}")
    typer.echo(f"Contact: {c.get('contact_name', '-')}  |  {c.get('contact_email', '-')}")
    typer.echo(f"Projects: {len(summary['projects'])}  |  Facilities: {len(summary['facilities'])}")
    typer.echo(f"Requirements: {len(summary['requirements'])}  |  Specs: {len(summary['specifications'])}")

    if summary["requirements"]:
        typer.echo("\nEngineering Requirements:")
        for r in summary["requirements"]:
            flag = "*" if r["mandatory"] else " "
            typer.echo(f"  [{flag}] {r['category']:14s} {r['title']}")
            if r["reference_code"]:
                typer.echo(f"       Ref: {r['reference_code']}")

    if summary["specifications"]:
        typer.echo("\nSpecifications:")
        for s in summary["specifications"]:
            rev = f" Rev {s['revision']}" if s["revision"] else ""
            typer.echo(f"  {s['spec_type']:20s} {s['title']}{rev}")

    if summary["projects"]:
        typer.echo("\nProjects:")
        for p in summary["projects"]:
            typer.echo(f"  {p['number'] or '-':8s} {p['name']:40s} {p['stage'] or ''}")


@app.command("requirements")
def requirements(customer_id: int = typer.Argument(..., help="Customer ID")):
    """List engineering requirements for a customer."""
    from qms.core import get_db
    from qms.customers.db import list_requirements

    with get_db(readonly=True) as conn:
        rows = list_requirements(conn, customer_id)

    if not rows:
        typer.echo(f"No requirements for customer {customer_id}.")
        raise typer.Exit()

    typer.echo(f"{'ID':<5} {'Category':<14} {'Title':<30} {'Mandatory':<10} {'Reference':<15} {'Applies To'}")
    typer.echo("-" * 90)
    for r in rows:
        typer.echo(
            f"{r['id']:<5} {r['category']:<14} {r['title']:<30} "
            f"{'Yes' if r['mandatory'] else 'No':<10} "
            f"{(r['reference_code'] or '-'):<15} {r['applies_to'] or 'all'}"
        )
