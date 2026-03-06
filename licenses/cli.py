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
