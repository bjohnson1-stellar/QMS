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


# =========================================================================
# REGISTRATION COMMANDS
# =========================================================================


@app.command("register")
def register_cmd(
    employee_number: Optional[str] = typer.Option(None, "--employee-number", "-e", help="Employee number"),
    first_name: Optional[str] = typer.Option(None, "--first-name", "-f", help="First name"),
    last_name: Optional[str] = typer.Option(None, "--last-name", "-l", help="Last name"),
    stamp: Optional[str] = typer.Option(None, "--stamp", help="Welder stamp (auto-assigned if omitted)"),
    department: Optional[str] = typer.Option(None, "--department", help="Department"),
    supervisor: Optional[str] = typer.Option(None, "--supervisor", help="Supervisor"),
    business_unit: Optional[str] = typer.Option(None, "--business-unit", help="Business unit"),
    batch: Optional[str] = typer.Option(None, "--batch", help="Path to CSV for batch registration"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without changes"),
):
    """Register a new welder (interactive, CLI args, or batch CSV)."""
    from qms.welding.registration import register_new_welder, register_batch

    if batch:
        from pathlib import Path as P
        csv_path = P(batch)
        stats = register_batch(csv_path, dry_run=dry_run)

        typer.echo()
        typer.echo("Batch Registration Summary")
        typer.echo("=" * 40)
        typer.echo(f"  Total rows:    {stats['total']}")
        typer.echo(f"  Created:       {stats['created']}")
        typer.echo(f"  Skipped:       {stats['skipped']}")
        typer.echo(f"  Errors:        {len(stats['errors'])}")

        if stats["errors"]:
            typer.echo("\n  Errors:")
            for err in stats["errors"][:10]:
                typer.echo(f"    Row {err.get('row', '?')}: {err.get('error', '')}")
        return

    # CLI args mode
    if employee_number and first_name and last_name:
        from qms.core import get_db

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
            )

        if result["errors"]:
            typer.echo("Registration FAILED:")
            for err in result["errors"]:
                typer.echo(f"  - {err}")
            raise typer.Exit(1)

        typer.echo(f"Registered: {result['name']} (stamp: {result['stamp']}, ID: {result['id']})")
        return

    # Interactive mode
    typer.echo("Interactive welder registration")
    typer.echo("-" * 30)
    emp = employee_number or typer.prompt("Employee number")
    first = first_name or typer.prompt("First name")
    last = last_name or typer.prompt("Last name")
    stmp = stamp or typer.prompt("Stamp (blank for auto)", default="")
    dept = department or typer.prompt("Department", default="")
    sup = supervisor or typer.prompt("Supervisor", default="")
    bu = business_unit or typer.prompt("Business unit", default="")

    from qms.core import get_db

    with get_db() as conn:
        result = register_new_welder(
            conn,
            employee_number=emp,
            first_name=first,
            last_name=last,
            stamp=stmp or None,
            department=dept or None,
            supervisor=sup or None,
            business_unit=bu or None,
        )

    if result["errors"]:
        typer.echo("Registration FAILED:")
        for err in result["errors"]:
            typer.echo(f"  - {err}")
        raise typer.Exit(1)

    typer.echo(f"\nRegistered: {result['name']} (stamp: {result['stamp']}, ID: {result['id']})")


@app.command("export-lookups")
def export_lookups_cmd(
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output Excel path"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview row counts only"),
):
    """Export welding lookup data to Excel for Power Automate."""
    from qms.welding.export_lookups import export_lookups

    output_path = Path(output) if output else None
    result = export_lookups(output_path=output_path, dry_run=dry_run)

    prefix = "[DRY RUN] " if dry_run else ""
    typer.echo(f"\n{prefix}Export Summary")
    typer.echo("=" * 40)
    for sheet, count in result["sheets"].items():
        typer.echo(f"  {sheet:<20} {count:>5} rows")
    typer.echo(f"  {'Total':<20} {result['total_rows']:>5} rows")
    typer.echo(f"\n  Output: {result['output_path']}")


# =========================================================================
# CERT REQUEST COMMANDS
# =========================================================================


@app.command("cert-requests")
def cert_requests_cmd(
    status: Optional[str] = typer.Option(None, "--status", "-s", help="Filter by status"),
    project: Optional[str] = typer.Option(None, "--project", "-p", help="Filter by project number"),
    welder: Optional[str] = typer.Option(None, "--welder", "-w", help="Filter by welder name/stamp"),
    limit: int = typer.Option(20, "--limit", "-n", help="Max results"),
    detail: Optional[str] = typer.Option(None, "--detail", "-d", help="Show detail for WCR number"),
):
    """List and view weld certification requests."""
    from qms.welding.cert_requests import list_cert_requests, get_cert_request_detail

    if detail:
        wcr = get_cert_request_detail(detail)
        if not wcr:
            typer.echo(f"WCR not found: {detail}")
            raise typer.Exit(1)

        typer.echo(f"\n{wcr['wcr_number']}  [{wcr['status']}]")
        typer.echo("=" * 50)
        typer.echo(f"  Welder:    {wcr['welder_name']} (stamp: {wcr['welder_stamp']})")
        typer.echo(f"  Project:   {wcr['project_number']} - {wcr['project_name']}")
        typer.echo(f"  Submitted: {wcr['submitted_by']} on {wcr['request_date']}")
        if wcr.get("approved_by"):
            typer.echo(f"  Approved:  {wcr['approved_by']} on {wcr.get('approved_at', '')[:10]}")
        if wcr.get("notes"):
            typer.echo(f"  Notes:     {wcr['notes']}")

        coupons = wcr.get("coupons", [])
        if coupons:
            typer.echo(f"\n  Coupons ({len(coupons)}):")
            typer.echo(f"  {'#':<3} {'Process':<10} {'Position':<8} {'WPS':<12} {'Status':<15} {'Result'}")
            typer.echo("  " + "-" * 60)
            for c in coupons:
                result_str = c.get("test_result", "") or ""
                typer.echo(
                    f"  {c['coupon_number']:<3} {(c['process'] or ''):<10} "
                    f"{(c['position'] or ''):<8} {(c['wps_number'] or ''):<12} "
                    f"{c['status']:<15} {result_str}"
                )
        return

    requests = list_cert_requests(status=status, project=project, welder=welder, limit=limit)

    if not requests:
        typer.echo("No cert requests found.")
        return

    typer.echo(f"\n{'WCR Number':<18} {'Status':<18} {'Welder':<20} {'Project':<10} {'Coupons':>7}")
    typer.echo("-" * 80)
    for r in requests:
        typer.echo(
            f"{r['wcr_number']:<18} {r['status']:<18} "
            f"{(r['welder_name'] or '')[:19]:<20} "
            f"{(r['project_number'] or ''):<10} {r['coupon_count']:>7}"
        )


@app.command("cert-results")
def cert_results_cmd(
    wcr_number: str = typer.Argument(..., help="WCR number (e.g. WCR-2026-0001)"),
    coupon: Optional[int] = typer.Option(None, "--coupon", "-c", help="Coupon number"),
    result: Optional[str] = typer.Option(None, "--result", "-r", help="pass or fail"),
    date_str: Optional[str] = typer.Option(None, "--date", help="Test date (YYYY-MM-DD)"),
    tester: Optional[str] = typer.Option(None, "--tester", help="Tested by"),
    notes: Optional[str] = typer.Option(None, "--notes", help="Notes"),
):
    """Enter test results for cert request coupons."""
    from qms.welding.cert_requests import enter_coupon_result, get_cert_request_detail

    if coupon and result:
        # Direct entry mode
        output = enter_coupon_result(
            wcr_number, coupon, result,
            test_date=date_str, tested_by=tester, notes=notes,
        )
        if output["errors"]:
            for err in output["errors"]:
                typer.echo(f"ERROR: {err}")
            raise typer.Exit(1)

        typer.echo(
            f"Coupon {coupon}: {output['status']} "
            f"(WCR status: {output['wcr_status']})"
        )
        return

    # Interactive mode — show WCR and prompt for each pending coupon
    wcr = get_cert_request_detail(wcr_number)
    if not wcr:
        typer.echo(f"WCR not found: {wcr_number}")
        raise typer.Exit(1)

    typer.echo(f"\n{wcr['wcr_number']} — {wcr['welder_name']}")
    coupons = [c for c in wcr.get("coupons", []) if c["status"] in ("pending", "testing")]

    if not coupons:
        typer.echo("No pending coupons to enter results for.")
        return

    for c in coupons:
        typer.echo(f"\n  Coupon {c['coupon_number']}: {c['process']} {c['position']}")
        res = typer.prompt("  Result (pass/fail/skip)", default="skip")
        if res.lower() == "skip":
            continue

        output = enter_coupon_result(
            wcr_number, c["coupon_number"], res.lower(),
            test_date=date_str, tested_by=tester,
        )
        if output["errors"]:
            for err in output["errors"]:
                typer.echo(f"  ERROR: {err}")
        else:
            typer.echo(f"  -> {output['status']}")


@app.command("approve-wcr")
def approve_wcr_cmd(
    wcr_number: str = typer.Argument(..., help="WCR number to approve"),
    approved_by: str = typer.Option(..., "--by", help="Approver name"),
):
    """Approve a pending cert request."""
    from qms.welding.cert_requests import approve_cert_request

    output = approve_cert_request(wcr_number, approved_by)
    if output["errors"]:
        for err in output["errors"]:
            typer.echo(f"ERROR: {err}")
        raise typer.Exit(1)

    typer.echo(f"Approved: {wcr_number}")


@app.command("assign-wpq")
def assign_wpq_cmd(
    wcr_number: str = typer.Argument(..., help="WCR number"),
    coupon: int = typer.Option(..., "--coupon", "-c", help="Coupon number"),
    months: Optional[int] = typer.Option(None, "--months", help="Expiration months (default from config)"),
):
    """Create a WPQ from a passed certification coupon."""
    from qms.welding.cert_requests import assign_wpq_from_coupon

    output = assign_wpq_from_coupon(wcr_number, coupon, expiration_months=months)
    if output["errors"]:
        for err in output["errors"]:
            typer.echo(f"ERROR: {err}")
        raise typer.Exit(1)

    typer.echo(f"Created WPQ: {output['wpq_number']}")
    typer.echo(f"  Expires: {output['expiration_date']}")


@app.command("schedule-retest")
def schedule_retest_cmd(
    wcr_number: str = typer.Argument(..., help="Original WCR number"),
    coupon: int = typer.Option(..., "--coupon", "-c", help="Failed coupon number"),
    notes: Optional[str] = typer.Option(None, "--notes", help="Notes"),
):
    """Schedule a retest for a failed certification coupon."""
    from qms.welding.cert_requests import schedule_retest

    output = schedule_retest(wcr_number, coupon, notes=notes)
    if output["errors"]:
        for err in output["errors"]:
            typer.echo(f"ERROR: {err}")
        raise typer.Exit(1)

    typer.echo(f"Retest scheduled: {output['new_wcr_number']}")


@app.command("process-requests")
def process_requests_cmd(
    file: Optional[str] = typer.Argument(None, help="Single JSON file to process"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without processing"),
):
    """Process weld cert request JSON files (alias for automation process)."""
    # Trigger handler registration
    import qms.welding.cert_requests  # noqa: F401
    from qms.automation.dispatcher import process_all, process_file

    if file:
        filepath = Path(file)
        if not filepath.exists():
            typer.echo(f"ERROR: File not found: {filepath}")
            raise typer.Exit(1)

        result = process_file(filepath, dry_run=dry_run)
        prefix = "[DRY RUN] " if dry_run else ""
        typer.echo(f"{prefix}{result['file']}: {result['status']}")
        if result["error"]:
            typer.echo(f"  Error: {result['error']}")
        if result["result_summary"]:
            typer.echo(f"  Result: {result['result_summary']}")
    else:
        results = process_all(dry_run=dry_run)
        if not results:
            typer.echo("No files to process.")
            return

        for r in results:
            status_marker = "OK" if r["status"] == "success" else r["status"].upper()
            typer.echo(f"  [{status_marker}] {r['file']} ({r['type'] or 'unknown'})")
            if r["error"]:
                typer.echo(f"         Error: {r['error']}")
