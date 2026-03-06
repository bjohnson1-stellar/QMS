"""
Licenses CLI — auto-expire, notifications, and license management commands.
"""

from typing import Optional

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


@app.command()
def check_notifications(
    generate: bool = typer.Option(False, "--generate", help="Generate new notifications from rules"),
    summary: bool = typer.Option(False, "--summary", help="Show summary counts only"),
    acknowledge: Optional[int] = typer.Option(None, "--acknowledge", help="Acknowledge notification by ID"),
    resolve: Optional[int] = typer.Option(None, "--resolve", help="Resolve notification by ID"),
    cleanup: bool = typer.Option(False, "--cleanup", help="Remove old resolved notifications"),
    cleanup_days: int = typer.Option(90, "--cleanup-days", help="Age threshold for cleanup (days)"),
):
    """Check, generate, and manage license notifications."""
    from qms.core import get_db
    from qms.licenses.notifications import (
        acknowledge_notification,
        cleanup_old_notifications,
        generate_all_notifications,
        get_notification_summary,
        list_active_notifications,
        resolve_notification,
    )

    with get_db() as conn:
        if acknowledge is not None:
            ok = acknowledge_notification(conn, acknowledge, "cli")
            conn.commit()
            if ok:
                typer.echo(f"Notification {acknowledge} acknowledged.")
            else:
                typer.echo(f"Notification {acknowledge} not found or already acknowledged.")
            return

        if resolve is not None:
            ok = resolve_notification(conn, resolve, "cli")
            conn.commit()
            if ok:
                typer.echo(f"Notification {resolve} resolved.")
            else:
                typer.echo(f"Notification {resolve} not found or already resolved.")
            return

        if cleanup:
            deleted = cleanup_old_notifications(conn, cleanup_days)
            conn.commit()
            typer.echo(f"Cleaned up {deleted} resolved notification(s) older than {cleanup_days} days.")
            return

        if generate:
            stats = generate_all_notifications(conn)
            conn.commit()
            typer.echo("Notification generation complete:")
            typer.echo(f"  Expiration warnings: {stats['expiration_created']} created")
            typer.echo(f"  CE deadlines:        {stats['ce_created']} created")
            typer.echo(f"  Renewal reminders:   {stats['renewal_created']} created")
            typer.echo(f"  Total: {stats['total_created']} created, {stats['total_skipped']} skipped")
            return

        if summary:
            s = get_notification_summary(conn)
            typer.echo("Notification Summary")
            typer.echo("=" * 40)

            typer.echo("\nBy Status:")
            for status, count in sorted(s.get("by_status", {}).items()):
                typer.echo(f"  {status:15s} {count}")

            typer.echo("\nBy Priority (active):")
            for priority, count in sorted(s.get("by_priority", {}).items()):
                typer.echo(f"  {priority:15s} {count}")

            typer.echo("\nBy Type (active):")
            for ntype, count in sorted(s.get("by_type", {}).items()):
                typer.echo(f"  {ntype:25s} {count}")

            urgent = s.get("urgent", [])
            if urgent:
                typer.echo(f"\nUrgent ({len(urgent)}):")
                for item in urgent:
                    typer.echo(f"  [{item['id']}] {item['title']} — due {item['due_date']}")
            else:
                typer.echo("\nNo urgent notifications.")
            return

        # Default: list active notifications
        notifications = list_active_notifications(conn)
        if not notifications:
            typer.echo("No active notifications.")
            return

        # Print table header
        typer.echo(f"{'ID':>5}  {'Priority':8}  {'Type':20}  {'Days':>4}  Title")
        typer.echo("-" * 80)
        for n in notifications:
            days = str(n["days_until_due"]) if n["days_until_due"] is not None else "—"
            typer.echo(
                f"{n['id']:>5}  {n['priority']:8}  "
                f"{n['notification_type']:20}  {days:>4}  {n['title'][:40]}"
            )


@app.command()
def seed_requirements():
    """Seed state regulatory requirements for SIS operating states.

    Populates renewal, bond, insurance, and CE requirements with
    realistic fee amounts. Idempotent — safe to run multiple times.
    """
    from qms.core import get_db
    from qms.licenses.db import seed_state_requirements

    # SIS operating states with common MEP contractor requirements
    requirements = [
        # Ohio — no state GC license; licenses electrical, HVAC, plumbing, refrigeration
        {"state_code": "OH", "license_type": "Electrical Contractor",
         "requirement_type": "renewal", "fee_amount": 100.0, "fee_frequency": "annual",
         "renewal_period_months": 12, "authority_name": "Ohio CILB",
         "description": "Annual electrical contractor license renewal"},
        {"state_code": "OH", "license_type": "Electrical Contractor",
         "requirement_type": "insurance", "fee_frequency": "annual",
         "description": "General liability insurance required"},
        {"state_code": "OH", "license_type": "HVAC Contractor",
         "requirement_type": "renewal", "fee_amount": 100.0, "fee_frequency": "annual",
         "renewal_period_months": 12, "authority_name": "Ohio CILB",
         "description": "Annual HVAC contractor license renewal"},
        {"state_code": "OH", "license_type": "Plumbing Contractor",
         "requirement_type": "renewal", "fee_amount": 100.0, "fee_frequency": "annual",
         "renewal_period_months": 12, "authority_name": "Ohio CILB",
         "description": "Annual plumbing contractor license renewal"},

        # Pennsylvania — state HIC registration only; trades are municipal
        {"state_code": "PA", "license_type": "Home Improvement Contractor",
         "requirement_type": "renewal", "fee_amount": 50.0, "fee_frequency": "annual",
         "renewal_period_months": 12, "authority_name": "PA Attorney General",
         "description": "Annual HIC registration renewal"},
        {"state_code": "PA", "license_type": "Home Improvement Contractor",
         "requirement_type": "insurance", "fee_frequency": "annual",
         "description": "General liability insurance required ($50K minimum)"},

        # West Virginia
        {"state_code": "WV", "license_type": "Contractor",
         "requirement_type": "renewal", "fee_amount": 150.0, "fee_frequency": "annual",
         "renewal_period_months": 12, "authority_name": "WV Contractor Licensing Board",
         "description": "Annual contractor license renewal"},
        {"state_code": "WV", "license_type": "Contractor",
         "requirement_type": "bond", "fee_frequency": "annual",
         "description": "Surety bond required for contractor license"},
        {"state_code": "WV", "license_type": "Contractor",
         "requirement_type": "insurance", "fee_frequency": "annual",
         "description": "General liability insurance required"},

        # Kentucky — licenses electrical, plumbing, HVAC, boiler
        {"state_code": "KY", "license_type": "Master Electrician",
         "requirement_type": "renewal", "fee_amount": 50.0, "fee_frequency": "annual",
         "renewal_period_months": 12, "authority_name": "KY DHBC",
         "description": "Annual master electrician license renewal"},
        {"state_code": "KY", "license_type": "Master Plumber",
         "requirement_type": "renewal", "fee_amount": 50.0, "fee_frequency": "annual",
         "renewal_period_months": 12, "authority_name": "KY DHBC",
         "description": "Annual master plumber license renewal"},
        {"state_code": "KY", "license_type": "HVAC Journeyman",
         "requirement_type": "renewal", "fee_amount": 30.0, "fee_frequency": "annual",
         "renewal_period_months": 12, "authority_name": "KY DHBC",
         "description": "Annual HVAC journeyman license renewal"},

        # Virginia — Class A/B/C contractors
        {"state_code": "VA", "license_type": "Class A Contractor",
         "requirement_type": "renewal", "fee_amount": 420.0, "fee_frequency": "biennial",
         "renewal_period_months": 24, "authority_name": "VA DPOR",
         "description": "Biennial Class A contractor license renewal"},
        {"state_code": "VA", "license_type": "Class A Contractor",
         "requirement_type": "insurance", "fee_frequency": "annual",
         "description": "General liability insurance required"},
        {"state_code": "VA", "license_type": "Class A Contractor",
         "requirement_type": "bond", "fee_frequency": "biennial",
         "description": "Surety bond required ($50K+ depending on classification)"},

        # North Carolina
        {"state_code": "NC", "license_type": "General Contractor",
         "requirement_type": "renewal", "fee_amount": 275.0, "fee_frequency": "annual",
         "renewal_period_months": 12, "authority_name": "NC LBGC",
         "description": "Annual general contractor license renewal"},
        {"state_code": "NC", "license_type": "Plumbing/Heating/Fire Sprinkler",
         "requirement_type": "renewal", "fee_amount": 100.0, "fee_frequency": "annual",
         "renewal_period_months": 12, "authority_name": "NC Board of Examiners",
         "description": "Annual plumbing/heating license renewal"},
        {"state_code": "NC", "license_type": "Plumbing/Heating/Fire Sprinkler",
         "requirement_type": "ce_requirement",
         "description": "8 hours CE annually",
         "authority_name": "NC Board of Examiners"},

        # South Carolina
        {"state_code": "SC", "license_type": "Mechanical Contractor",
         "requirement_type": "renewal", "fee_amount": 200.0, "fee_frequency": "biennial",
         "renewal_period_months": 24, "authority_name": "SC LLR",
         "description": "Biennial mechanical contractor license renewal"},
        {"state_code": "SC", "license_type": "Mechanical Contractor",
         "requirement_type": "ce_requirement",
         "description": "4 hours CE per renewal period",
         "authority_name": "SC LLR"},

        # Georgia
        {"state_code": "GA", "license_type": "Conditioned Air Contractor",
         "requirement_type": "renewal", "fee_amount": 150.0, "fee_frequency": "biennial",
         "renewal_period_months": 24, "authority_name": "GA SoS",
         "description": "Biennial conditioned air contractor renewal"},
        {"state_code": "GA", "license_type": "Conditioned Air Contractor",
         "requirement_type": "ce_requirement",
         "description": "6 hours CE per renewal period",
         "authority_name": "GA Division of Conditioned Air Contractors"},
        {"state_code": "GA", "license_type": "Master Plumber",
         "requirement_type": "renewal", "fee_amount": 100.0, "fee_frequency": "biennial",
         "renewal_period_months": 24, "authority_name": "GA SoS",
         "description": "Biennial master plumber license renewal"},

        # Florida
        {"state_code": "FL", "license_type": "Mechanical Contractor",
         "requirement_type": "renewal", "fee_amount": 299.0, "fee_frequency": "biennial",
         "renewal_period_months": 24, "authority_name": "FL DBPR",
         "description": "Biennial mechanical contractor license renewal"},
        {"state_code": "FL", "license_type": "Mechanical Contractor",
         "requirement_type": "ce_requirement",
         "description": "14 hours CE per renewal period (1hr safety, 1hr workers comp, 1hr business)",
         "authority_name": "FL DBPR"},
        {"state_code": "FL", "license_type": "Mechanical Contractor",
         "requirement_type": "insurance", "fee_frequency": "annual",
         "description": "General liability and workers compensation insurance required"},
        {"state_code": "FL", "license_type": "Plumbing Contractor",
         "requirement_type": "renewal", "fee_amount": 299.0, "fee_frequency": "biennial",
         "renewal_period_months": 24, "authority_name": "FL DBPR",
         "description": "Biennial plumbing contractor license renewal"},
        {"state_code": "FL", "license_type": "Plumbing Contractor",
         "requirement_type": "ce_requirement",
         "description": "14 hours CE per renewal period",
         "authority_name": "FL DBPR"},

        # Texas — TDLR for electricians/HVAC, separate board for plumbing
        {"state_code": "TX", "license_type": "Master Plumber",
         "requirement_type": "renewal", "fee_amount": 254.0, "fee_frequency": "annual",
         "renewal_period_months": 12, "authority_name": "TSBPE",
         "description": "Annual master plumber license renewal"},
        {"state_code": "TX", "license_type": "Master Plumber",
         "requirement_type": "ce_requirement",
         "description": "8 hours CE annually",
         "authority_name": "TSBPE"},
        {"state_code": "TX", "license_type": "HVAC/Refrigeration Technician",
         "requirement_type": "renewal", "fee_amount": 75.0, "fee_frequency": "annual",
         "renewal_period_months": 12, "authority_name": "TDLR",
         "description": "Annual HVAC/refrigeration technician renewal"},

        # California — CSLB single board
        {"state_code": "CA", "license_type": "C-20 HVAC",
         "requirement_type": "renewal", "fee_amount": 450.0, "fee_frequency": "biennial",
         "renewal_period_months": 24, "authority_name": "CSLB",
         "description": "Biennial C-20 HVAC contractor renewal"},
        {"state_code": "CA", "license_type": "C-20 HVAC",
         "requirement_type": "bond", "fee_amount": 25000.0, "fee_frequency": "biennial",
         "description": "Contractor license bond ($25,000)"},
        {"state_code": "CA", "license_type": "C-36 Plumbing",
         "requirement_type": "renewal", "fee_amount": 450.0, "fee_frequency": "biennial",
         "renewal_period_months": 24, "authority_name": "CSLB",
         "description": "Biennial C-36 plumbing contractor renewal"},
        {"state_code": "CA", "license_type": "C-36 Plumbing",
         "requirement_type": "bond", "fee_amount": 25000.0, "fee_frequency": "biennial",
         "description": "Contractor license bond ($25,000)"},
        {"state_code": "CA", "license_type": "C-10 Electrical",
         "requirement_type": "renewal", "fee_amount": 450.0, "fee_frequency": "biennial",
         "renewal_period_months": 24, "authority_name": "CSLB",
         "description": "Biennial C-10 electrical contractor renewal"},
    ]

    with get_db() as conn:
        count = seed_state_requirements(conn, requirements)

    typer.echo(f"Seeded {count} state requirements across SIS operating states.")
    if count == 0:
        typer.echo("(All requirements already existed — no duplicates created.)")
