"""Welding CLI sub-commands."""

import json

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


@app.command()
def register(
    employee_number: Optional[str] = typer.Option(None, "--employee-number", "-e", help="Employee number"),
    first_name: Optional[str] = typer.Option(None, "--first-name", "-f", help="First name"),
    last_name: Optional[str] = typer.Option(None, "--last-name", "-l", help="Last name"),
    stamp: Optional[str] = typer.Option(None, "--stamp", "-s", help="Welder stamp (auto-assigned if omitted)"),
    department: Optional[str] = typer.Option(None, "--department", help="Department"),
    supervisor: Optional[str] = typer.Option(None, "--supervisor", help="Supervisor name"),
    business_unit: Optional[str] = typer.Option(None, "--business-unit", help="Business unit"),
    preferred_name: Optional[str] = typer.Option(None, "--preferred-name", help="Preferred name / nickname"),
    process: Optional[str] = typer.Option(None, "--process", "-p", help="Initial WPQ process (SMAW, GTAW, etc.)"),
    batch: Optional[str] = typer.Option(None, "--batch", "-b", help="CSV file for batch registration"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without database changes"),
):
    """Register new welder(s) — interactive, by flags, or batch CSV."""
    from qms.core import get_db
    from qms.welding.registration import (
        add_initial_wpq,
        get_next_stamp,
        register_batch,
        register_new_welder,
    )

    # --- Batch mode ---
    if batch:
        csv_path = Path(batch)
        if not csv_path.exists():
            typer.echo(f"ERROR: File not found: {csv_path}")
            raise typer.Exit(1)

        stats = register_batch(csv_path, dry_run=dry_run)

        typer.echo()
        typer.echo("Batch Registration Summary")
        typer.echo("=" * 40)
        typer.echo(f"  Total rows:    {stats['total']}")
        typer.echo(f"  Created:       {stats['created']}")
        typer.echo(f"  Skipped:       {stats['skipped']}")

        if stats["errors"]:
            typer.echo(f"\n  Errors ({len(stats['errors'])}):")
            for err in stats["errors"][:10]:
                typer.echo(f"    Row {err['row']}: {err['error']}")
            if len(stats["errors"]) > 10:
                typer.echo(f"    ... and {len(stats['errors']) - 10} more")

        if stats["welders"] and not dry_run:
            typer.echo(f"\n  Registered:")
            for w in stats["welders"][:20]:
                typer.echo(f"    {w['stamp']:>6}  {w['name']}  (emp#: {w['employee_number']})")
        return

    # --- Interactive mode (if required fields not provided) ---
    if not employee_number or not first_name or not last_name:
        typer.echo("New Welder Registration")
        typer.echo("=" * 30)

        if not employee_number:
            employee_number = typer.prompt("Employee number")
        if not first_name:
            first_name = typer.prompt("First name")
        if not last_name:
            last_name = typer.prompt("Last name")
        if preferred_name is None:
            preferred_name = typer.prompt("Preferred name (enter to skip)", default="") or None
        if department is None:
            department = typer.prompt("Department (enter to skip)", default="") or None
        if supervisor is None:
            supervisor = typer.prompt("Supervisor (enter to skip)", default="") or None
        if business_unit is None:
            business_unit = typer.prompt("Business unit (enter to skip)", default="") or None

        # Show next stamp
        with get_db(readonly=True) as conn:
            next_stamp = get_next_stamp(conn)
        if stamp is None:
            stamp_input = typer.prompt(f"Welder stamp [auto: {next_stamp}]", default="")
            stamp = stamp_input if stamp_input else None

        if process is None:
            process = typer.prompt(
                "Initial WPQ process (SMAW/GTAW/GMAW/FCAW, enter to skip)", default=""
            ) or None

        typer.echo()
        typer.echo(f"  Employee #:  {employee_number}")
        typer.echo(f"  Name:        {first_name} {last_name}")
        typer.echo(f"  Stamp:       {stamp or '(auto-assign)'}")
        if department:
            typer.echo(f"  Department:  {department}")
        if process:
            typer.echo(f"  Process:     {process}")
        typer.echo()

        if not dry_run and not typer.confirm("Proceed with registration?"):
            typer.echo("Cancelled.")
            raise typer.Exit(0)

    # --- Register ---
    if dry_run:
        typer.echo("[DRY RUN] Would register:")
        typer.echo(f"  {first_name} {last_name} (emp#: {employee_number}, stamp: {stamp or 'auto'})")
        if process:
            typer.echo(f"  Initial WPQ: {process}")
        return

    with get_db() as conn:
        result = register_new_welder(
            conn,
            employee_number=employee_number,
            first_name=first_name,
            last_name=last_name,
            stamp=stamp,
            department=department,
            supervisor=supervisor,
            business_unit=business_unit,
            preferred_name=preferred_name,
        )

        if result["errors"]:
            typer.echo("Registration FAILED:")
            for err in result["errors"]:
                typer.echo(f"  - {err}")
            raise typer.Exit(1)

        typer.echo()
        typer.echo("Welder Registered")
        typer.echo("=" * 40)
        typer.echo(f"  ID:          {result['id']}")
        typer.echo(f"  Name:        {result['name']}")
        typer.echo(f"  Employee #:  {result['employee_number']}")
        typer.echo(f"  Stamp:       {result['stamp']}")

        # Add initial WPQ if process provided
        if process and result["id"] and result["stamp"]:
            wpq_result = add_initial_wpq(
                conn,
                welder_id=result["id"],
                welder_stamp=result["stamp"],
                process_type=process.upper(),
            )
            if wpq_result["errors"]:
                typer.echo(f"\n  WPQ Warning:")
                for err in wpq_result["errors"]:
                    typer.echo(f"    - {err}")
            else:
                typer.echo(f"  WPQ:         {wpq_result['wpq_number']}")
                typer.echo(f"  Expires:     {wpq_result['expiration_date']}")


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


@app.command("sync-sharepoint")
def sync_sharepoint(
    push: bool = typer.Option(False, "--push", help="Push lookup data to SharePoint"),
    pull: bool = typer.Option(False, "--pull", help="Pull form submissions from SharePoint"),
    status: bool = typer.Option(False, "--status", help="Check sync status"),
    list_name: Optional[str] = typer.Option(
        None, "--list", "-l",
        help="Specific list to sync (welders, processes, wps, positions, materials, fillers, wpq-status)",
    ),
    preview: bool = typer.Option(False, "--preview", help="Preview data without SharePoint connection"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Connect but don't write changes"),
):
    """Sync welding data with SharePoint Lists for Power App integration."""
    from qms.welding.sharepoint import (
        LIST_ALIASES,
        SharePointClient,
        preview_sync_data,
        pull_submissions,
        push_all,
        push_list,
        get_sync_status,
    )

    # --- Offline preview mode ---
    if preview:
        typer.echo("SharePoint Sync Preview (offline)")
        typer.echo("=" * 50)
        data = preview_sync_data(list_name)

        if "error" in data:
            typer.echo(f"ERROR: {data['error']}")
            typer.echo(f"  Valid lists: {', '.join(sorted(LIST_ALIASES.keys()))}")
            raise typer.Exit(1)

        for lname, items in data.items():
            typer.echo(f"\n{lname}: {len(items)} items")
            typer.echo("-" * 40)
            for item in items[:5]:
                typer.echo(f"  {json.dumps(item, default=str)}")
            if len(items) > 5:
                typer.echo(f"  ... and {len(items) - 5} more")
        return

    if not push and not pull and not status:
        typer.echo("Specify --push, --pull, --status, or --preview")
        typer.echo("Use --preview to see data without SharePoint connection")
        raise typer.Exit(1)

    # --- Connect to SharePoint ---
    try:
        client = SharePointClient.from_config()
    except ValueError as e:
        typer.echo(f"Configuration error: {e}")
        typer.echo()
        typer.echo("Add to config.yaml:")
        typer.echo("  sharepoint:")
        typer.echo("    tenant_id: <Azure AD tenant ID>")
        typer.echo("    client_id: <App registration client ID>")
        typer.echo("    client_secret: <App registration client secret>")
        typer.echo("    site_name: <SharePoint site name>")
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"SharePoint connection failed: {e}")
        raise typer.Exit(1)

    # --- Push ---
    if push:
        if list_name:
            resolved = LIST_ALIASES.get(list_name, list_name)
            typer.echo(f"Pushing {resolved} to SharePoint...")
            result = push_list(client, resolved, dry_run=dry_run)
            _print_push_result(result)
        else:
            typer.echo("Pushing all lists to SharePoint...")
            results = push_all(client, dry_run=dry_run)
            for lname, result in results.items():
                _print_push_result(result)
            typer.echo()
            total = sum(r.get("items_added", r.get("items_count", 0)) for r in results.values())
            typer.echo(f"Total items synced: {total}")

    # --- Pull ---
    if pull:
        typer.echo("Pulling form submissions from SharePoint...")
        result = pull_submissions(client, dry_run=dry_run)
        typer.echo()
        typer.echo("Submission Import")
        typer.echo("=" * 40)
        typer.echo(f"  Found:     {result['total_found']}")
        typer.echo(f"  Imported:  {result.get('imported', 0)}")
        if result.get("errors"):
            typer.echo(f"  Errors:    {len(result['errors'])}")
            for err in result["errors"][:5]:
                typer.echo(f"    - {err}")
        if result.get("preview"):
            typer.echo("\n  Preview:")
            for p in result["preview"]:
                typer.echo(f"    {p['welder']} / {p['process']} / {p['test_date']} / {p['result']}")

    # --- Status ---
    if status:
        typer.echo("SharePoint Sync Status")
        typer.echo("=" * 50)
        sp_status = get_sync_status(client)
        for lname, info in sp_status.items():
            marker = "OK" if info["exists"] else "--"
            count = info["item_count"] if info["exists"] else "not created"
            typer.echo(f"  [{marker}] {lname:<30} {count}")


def _print_push_result(result: dict) -> None:
    """Format a single push result for display."""
    name = result["list_name"]
    status = result.get("status", "unknown")
    if status == "success":
        typer.echo(
            f"  {name:<30} {result.get('items_added', 0)} items "
            f"(replaced {result.get('items_deleted', 0)})"
        )
    elif status == "dry_run":
        typer.echo(f"  {name:<30} {result.get('items_count', 0)} items (dry run)")
    elif status == "skipped":
        typer.echo(f"  {name:<30} skipped ({result.get('reason', '')})")
    else:
        typer.echo(f"  {name:<30} ERROR: {result.get('error', 'unknown')}")
