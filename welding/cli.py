"""Welding CLI sub-commands."""

import typer
from pathlib import Path
from typing import Optional

app = typer.Typer(no_args_is_help=True)


@app.command()
def dashboard():
    """Show welding program dashboard summary."""
    from qms.welding.intake import get_dashboard_data

    data = get_dashboard_data()

    typer.echo("Welding Program Dashboard")
    typer.echo("=" * 30)
    typer.echo(f"  Active welders:   {data['active_welders']}")
    typer.echo(f"  Active WPS:       {data['wps_count']}")
    typer.echo(f"  Active WPQ:       {data['wpq_count']}")
    typer.echo(f"  Active PQR:       {data['pqr_count']}")
    typer.echo(f"  Active BPS:       {data['bps_count']}")
    typer.echo(f"  Active BPQ:       {data['bpq_count']}")

    # Show notification summary if available
    try:
        from qms.welding.notifications import get_notification_summary

        summary = get_notification_summary()
        active_count = sum(summary.get("by_status", {}).get(s, 0) for s in ("active",))
        if active_count:
            typer.echo()
            typer.echo(f"  Notifications:    {active_count} active")
            for priority, count in summary.get("by_priority", {}).items():
                marker = {"urgent": "!!!", "high": "!!", "normal": "."}.get(priority, "")
                typer.echo(f"    {marker} {priority}: {count}")
    except Exception:
        pass


@app.command()
def continuity():
    """Show welder continuity status."""
    from qms.core import get_db

    with get_db(readonly=True) as conn:
        # Try the auto-status view first, fall back to manual query
        try:
            rows = conn.execute(
                "SELECT * FROM v_weld_continuity_auto_status ORDER BY days_remaining"
            ).fetchall()
        except Exception:
            rows = conn.execute(
                """SELECT
                       wr.welder_stamp,
                       wr.display_name as name,
                       wpq.process_type,
                       wpq.current_expiration_date,
                       CAST(JULIANDAY(wpq.current_expiration_date) - JULIANDAY(DATE('now'))
                            AS INTEGER) as days_remaining,
                       CASE
                           WHEN wpq.current_expiration_date < DATE('now') THEN 'LAPSED'
                           WHEN wpq.current_expiration_date < DATE('now', '+30 days') THEN 'AT_RISK'
                           ELSE 'OK'
                       END as continuity_status
                   FROM weld_wpq wpq
                   JOIN weld_welder_registry wr ON wpq.welder_id = wr.id
                   WHERE wpq.status = 'active' AND wr.status = 'active'
                     AND wpq.current_expiration_date IS NOT NULL
                   ORDER BY days_remaining"""
            ).fetchall()

    if not rows:
        typer.echo("No continuity data found.")
        return

    typer.echo(f"{'':2} {'Welder':<25} {'Process':<8} {'Days':>5}  Status")
    typer.echo("-" * 55)
    for r in rows:
        rd = dict(r)
        status = rd["continuity_status"]
        marker = "!!" if status in ("LAPSED", "AT_RISK") else "  "
        name = rd.get("name") or rd.get("display_name") or rd.get("welder_stamp") or "?"
        process = rd.get("process_type") or "N/A"
        days = rd.get("days_remaining")
        days_str = str(days) if days is not None else "?"
        typer.echo(
            f"{marker} {name:<25} {process:<8} "
            f"{days_str:>5}d  {status}"
        )


@app.command("import-wps")
def import_wps(
    file: Optional[str] = typer.Argument(None, help="Path to Excel file"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview changes only"),
    validate: bool = typer.Option(False, "--validate", help="Validate Excel structure only"),
    welder: Optional[str] = typer.Option(None, "--welder", help="Import single welder by stamp/number"),
):
    """Import WPS/welder data from Excel spreadsheet."""
    from qms.welding.importer import import_from_excel, validate_excel

    if validate:
        from pathlib import Path as P
        result = validate_excel(P(file) if file else None)
        if result["valid"]:
            typer.echo(f"Validation PASSED: {result['data_count']} data rows")
        else:
            typer.echo("Validation FAILED:")
            for err in result["errors"]:
                typer.echo(f"  - {err}")
        return

    from pathlib import Path as P
    excel_path = P(file) if file else None

    stats = import_from_excel(dry_run=dry_run, single_welder=welder, excel_path=excel_path)

    typer.echo()
    typer.echo("Import Summary")
    typer.echo("=" * 40)
    typer.echo(f"  Welders processed:  {stats.get('welders_processed', 0)}")
    typer.echo(f"    - Created:        {stats.get('welders_created', 0)}")
    typer.echo(f"    - Updated:        {stats.get('welders_updated', 0)}")
    typer.echo(f"    - Skipped:        {stats.get('welders_skipped', 0)}")
    typer.echo(f"  WPQs created:       {stats.get('wpqs_created', 0)}")
    typer.echo(f"  Parse warnings:     {stats.get('wpq_parse_errors', 0)}")

    errors = stats.get("errors", [])
    if errors:
        typer.echo(f"\n  Parse Issues ({len(errors)}):")
        for err in errors[:10]:
            typer.echo(f"    - {err}")
        if len(errors) > 10:
            typer.echo(f"    ... and {len(errors) - 10} more")


@app.command("import-weekly")
def import_weekly(
    file: str = typer.Argument(..., help="Path to Excel or CSV file"),
    week: Optional[str] = typer.Option(None, "--week", help="Week ending date (YYYY-MM-DD)"),
    preview: bool = typer.Option(False, "--preview", help="Preview without changes"),
):
    """Process weekly weld import from Excel or CSV."""
    from qms.welding.weekly import process_weekly_import, parse_date

    filepath = Path(file)
    if not filepath.exists():
        typer.echo(f"ERROR: File not found: {filepath}")
        raise typer.Exit(1)

    week_override = None
    if week:
        week_override = parse_date(week)
        if not week_override:
            typer.echo(f"ERROR: Invalid week date: {week}")
            raise typer.Exit(1)
        typer.echo(f"Using week ending date: {week_override}")

    stats = process_weekly_import(filepath, week_override, preview)

    typer.echo()
    typer.echo("Weekly Import Summary")
    typer.echo("=" * 40)
    typer.echo(f"  Records processed:     {stats['records_processed']}")
    typer.echo(f"  Production welds:      {stats['welds_created']}")
    typer.echo(f"  Continuity extended:   {stats['continuity_extended']}")

    if stats["welders_not_found"]:
        typer.echo(f"\n  Welders not found ({len(stats['welders_not_found'])}):")
        for welder_id, row in stats["welders_not_found"][:10]:
            typer.echo(f"    - {welder_id} (row {row})")

    if stats["date_errors"]:
        typer.echo(f"\n  Date errors ({len(stats['date_errors'])}):")
        for err in stats["date_errors"][:5]:
            typer.echo(f"    - {err}")

    if stats["errors"]:
        typer.echo(f"\n  Other errors ({len(stats['errors'])}):")
        for err in stats["errors"][:5]:
            typer.echo(f"    - {err}")


@app.command("check-notifications")
def check_notifications(
    generate: bool = typer.Option(False, "--generate", help="Generate new notifications"),
    summary: bool = typer.Option(False, "--summary", help="Show summary only"),
    acknowledge: Optional[int] = typer.Option(None, "--acknowledge", help="Acknowledge notification by ID"),
    resolve: Optional[int] = typer.Option(None, "--resolve", help="Resolve notification by ID"),
    cleanup: bool = typer.Option(False, "--cleanup", help="Remove old resolved notifications"),
    cleanup_days: int = typer.Option(90, "--cleanup-days", help="Days for cleanup threshold"),
):
    """Check and manage welding notifications."""
    from qms.core import get_db
    from qms.welding.notifications import (
        acknowledge_notification as ack_notif,
        cleanup_old_notifications,
        generate_all_notifications,
        get_notification_summary,
        list_active_notifications,
        resolve_notification as res_notif,
    )

    if acknowledge is not None:
        with get_db() as conn:
            if ack_notif(conn, acknowledge):
                typer.echo(f"Notification {acknowledge} acknowledged")
            else:
                typer.echo(f"Notification {acknowledge} not found or already acknowledged")
        return

    if resolve is not None:
        with get_db() as conn:
            if res_notif(conn, resolve):
                typer.echo(f"Notification {resolve} resolved")
            else:
                typer.echo(f"Notification {resolve} not found or already resolved")
        return

    if cleanup:
        with get_db() as conn:
            deleted = cleanup_old_notifications(conn, cleanup_days)
        typer.echo(f"Cleaned up {deleted} old notifications")
        return

    if generate:
        stats = generate_all_notifications()
        typer.echo()
        typer.echo("Notification Generation Summary")
        typer.echo("=" * 40)
        typer.echo(f"  WPQ expirations:     {stats['wpq_created']} new")
        typer.echo(f"  BPQR expirations:    {stats['bpqr_created']} new")
        typer.echo(f"  Continuity at risk:  {stats['continuity_created']} new")
        typer.echo(f"  Total created:       {stats['total_created']}")
        typer.echo(f"  Already existed:     {stats['total_skipped']}")

    if summary or generate:
        notif_summary = get_notification_summary()
        typer.echo()
        typer.echo("Notification Summary")
        typer.echo("=" * 40)

        typer.echo("\n  By Status:")
        for status, count in notif_summary.get("by_status", {}).items():
            typer.echo(f"    {status}: {count}")

        typer.echo("\n  Active by Priority:")
        for priority, count in notif_summary.get("by_priority", {}).items():
            marker = {"urgent": "!!!", "high": "!!", "normal": "."}.get(priority, "")
            typer.echo(f"    {marker} {priority}: {count}")

        typer.echo("\n  Active by Type:")
        for ntype, count in notif_summary.get("by_type", {}).items():
            typer.echo(f"    {ntype}: {count}")

        urgent = notif_summary.get("urgent", [])
        if urgent:
            typer.echo("\n  URGENT Items:")
            for item in urgent:
                typer.echo(f"    [{item['id']}] {item['title'][:50]} ({item['days_until_due']}d)")
        return

    # Default: list active notifications
    with get_db(readonly=True) as conn:
        notifications = list_active_notifications(conn)

    if not notifications:
        typer.echo("No active notifications")
        return

    typer.echo(f"\n{'ID':>5} {'Priority':<8} {'Type':<15} {'Days':<5} Title")
    typer.echo("-" * 75)
    for n in notifications:
        typer.echo(
            f"{n['id']:>5} {n['priority']:<8} {n['notification_type']:<15} "
            f"{n['days_until_due'] or 'N/A':<5} {n['title'][:45]}"
        )
