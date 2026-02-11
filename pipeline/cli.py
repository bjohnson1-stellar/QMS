"""Pipeline CLI sub-commands."""

import typer
from pathlib import Path
from typing import Optional

app = typer.Typer(no_args_is_help=True)


@app.command()
def status(
    project: Optional[str] = typer.Argument(None, help="Project number (all if omitted)"),
):
    """Show extraction pipeline status."""
    from qms.pipeline.processor import get_pipeline_status

    data = get_pipeline_status(project)

    if 'error' in data:
        typer.echo(f"ERROR: {data['error']}")
        raise typer.Exit(1)

    if project:
        typer.echo(f"Project {data['project_number']} - {data['project_name']}")
        typer.echo("=" * 50)
        typer.echo(f"  Total sheets:     {data['total_sheets']}")
        typer.echo(f"  Extracted:        {data['extracted']}")
        typer.echo(f"  Pending queue:    {data['pending_queue']}")

        if data['disciplines']:
            typer.echo()
            typer.echo(f"  {'Discipline':<25} {'Processed':>10} / {'Total':>5}")
            typer.echo("  " + "-" * 45)
            for d in data['disciplines']:
                typer.echo(
                    f"  {d['name']:<25} {d['processed_count']:>10} / {d['sheet_count']:>5}"
                )
    else:
        typer.echo("Pipeline Status - All Projects")
        typer.echo("=" * 40)
        typer.echo(f"  Active projects:  {data['active_projects']}")
        typer.echo(f"  Total sheets:     {data['total_sheets']}")
        typer.echo(f"  Extracted:        {data['extracted']}")
        typer.echo(f"  Pending queue:    {data['pending_queue']}")
        typer.echo(f"  Open conflicts:   {data['open_conflicts']}")


@app.command()
def queue(
    status_filter: Optional[str] = typer.Option(
        None, "--status", "-s", help="Filter by status (pending/processing/completed/failed)"
    ),
    limit: int = typer.Option(20, "--limit", "-n", help="Max items to display"),
):
    """List and manage the extraction processing queue."""
    from qms.pipeline.importer import get_queue_status, list_queue_items

    # Show queue summary
    qs = get_queue_status()
    typer.echo("Processing Queue Summary")
    typer.echo("=" * 35)
    typer.echo(f"  Total:       {qs['total']}")
    typer.echo(f"  Pending:     {qs['pending']}")
    typer.echo(f"  Processing:  {qs['processing']}")
    typer.echo(f"  Completed:   {qs['completed']}")
    typer.echo(f"  Failed:      {qs['failed']}")

    if qs['by_priority']:
        typer.echo()
        typer.echo("  By Priority:")
        for priority, count in qs['by_priority'].items():
            typer.echo(f"    {priority}: {count}")

    # Show items
    items = list_queue_items(status=status_filter, limit=limit)
    if items:
        typer.echo()
        typer.echo(f"{'ID':>5} {'Status':<12} {'Priority':<8} {'Project':<10} {'Drawing':<20} Task")
        typer.echo("-" * 75)
        for item in items:
            proj_num = item.get('project_number') or '?'
            drawing = item.get('drawing_number') or '?'
            priority = item.get('priority') or 'normal'
            typer.echo(
                f"{item['id']:>5} {item['status']:<12} {priority:<8} "
                f"{proj_num:<10} {drawing:<20} {item['task']}"
            )
    elif status_filter:
        typer.echo(f"\nNo {status_filter} items in queue.")
    else:
        typer.echo("\nQueue is empty.")


@app.command("import-drawing")
def import_drawing(
    file: str = typer.Argument(..., help="Path to SIS Excel file"),
    week: Optional[str] = typer.Option(None, "--week", help="Week ending date (YYYY-MM-DD)"),
    preview: bool = typer.Option(False, "--preview", help="Preview without making changes"),
    output: Optional[str] = typer.Option(None, "--output", help="Save processed Excel output"),
):
    """Import a single SIS drawing/field location file."""
    from qms.pipeline.processor import process_and_import
    from qms.pipeline.common import parse_date

    filepath = Path(file)
    if not filepath.exists():
        typer.echo(f"ERROR: File not found: {filepath}")
        raise typer.Exit(1)

    week_override = None
    if week:
        week_override = parse_date(week)
        if not week_override:
            typer.echo(f"ERROR: Invalid date format: {week} (expected YYYY-MM-DD)")
            raise typer.Exit(1)
        typer.echo(f"Using week ending date: {week_override}")

    output_path = Path(output) if output else None

    try:
        stats = process_and_import(filepath, week_override, output_path, preview)
    except Exception as e:
        typer.echo(f"ERROR: Processing failed: {e}")
        raise typer.Exit(1)

    if preview:
        typer.echo()
        typer.echo("=== PREVIEW MODE ===")
        typer.echo(f"Would process {stats['jobsites_processed']} jobsites")
        typer.echo(f"Would process {stats['personnel_processed']} personnel")
        if output_path:
            typer.echo(f"Would save output to: {output_path}")
        return

    typer.echo()
    typer.echo("SIS Import Summary")
    typer.echo("=" * 60)
    typer.echo(f"Jobsites processed:      {stats['jobsites_processed']}")
    typer.echo(f"  - Created:             {stats['jobsites_created']}")
    typer.echo(f"  - Updated:             {stats['jobsites_updated']}")
    typer.echo(f"  - Active (w/personnel):{stats['jobsites_active']}")
    typer.echo(f"  - Inactive (no staff): {stats['jobsites_inactive']}")
    skipped = stats.get('projects_skipped', set())
    if skipped:
        typer.echo(f"Projects skipped:        {len(skipped)} (not in Projects table)")
        for pn in sorted(skipped):
            typer.echo(f"  ⚠ {pn} — create this project first, then re-import")

    if stats.get('projects_activated', 0) > 0 or stats.get('projects_deactivated', 0) > 0:
        typer.echo(f"  - Activated:           {stats['projects_activated']}")
        typer.echo(f"  - Deactivated:         {stats['projects_deactivated']}")

    typer.echo(f"Personnel processed:     {stats['personnel_processed']}")
    typer.echo(f"  - Unassigned:          {stats['unassigned_personnel']}")

    if stats.get('employees_processed', 0) > 0:
        typer.echo()
        typer.echo(f"Employees imported:      {stats['employees_processed']}")
        typer.echo(f"  - Created:             {stats['employees_created']}")
        typer.echo(f"  - Updated:             {stats['employees_updated']}")
        typer.echo(f"  - Job assigned:        {stats['employees_job_assigned']}")
        typer.echo(f"  - Skipped:             {stats.get('employees_skipped', 0)}")

    typer.echo()
    typer.echo("Welder Continuity:")
    typer.echo(f"  - Welders matched:     {stats['welders_matched']}")
    if stats.get('welders_active', 0) > 0 or stats.get('welders_inactive', 0) > 0:
        typer.echo(f"    - Active welders:    {stats['welders_active']}")
        typer.echo(f"    - Inactive welders:  {stats['welders_inactive']}")
    typer.echo(f"  - Non-welders:         {stats['non_welders']}")
    typer.echo(f"Continuity events:       {stats['continuity_events_created']}")
    typer.echo(f"Processes linked:        {stats['continuity_processes_linked']}")

    if stats['errors']:
        typer.echo(f"\nErrors ({len(stats['errors'])}):")
        for err in stats['errors'][:10]:
            typer.echo(f"  - {err}")
        if len(stats['errors']) > 10:
            typer.echo(f"  ... and {len(stats['errors']) - 10} more")


@app.command("import-batch")
def import_batch_cmd(
    directory: Optional[str] = typer.Option(None, "--directory", "-d", help="Directory containing SIS files"),
    files: Optional[list[str]] = typer.Argument(None, help="Specific files to import (in order)"),
    preview: bool = typer.Option(False, "--preview", help="Preview without making changes"),
    start: Optional[str] = typer.Option(None, "--start", help="Start date filter (YYYY-MM-DD)"),
    end: Optional[str] = typer.Option(None, "--end", help="End date filter (YYYY-MM-DD)"),
):
    """Batch import SIS files from a directory (oldest to newest)."""
    from datetime import datetime as dt

    from qms.pipeline.common import extract_date_from_filename
    from qms.pipeline.importer import (
        find_field_location_files,
        import_batch,
        import_from_directory,
    )

    start_date = None
    end_date = None
    if start:
        try:
            start_date = dt.strptime(start, '%Y-%m-%d').date()
        except ValueError:
            typer.echo(f"ERROR: Invalid start date: {start}")
            raise typer.Exit(1)
    if end:
        try:
            end_date = dt.strptime(end, '%Y-%m-%d').date()
        except ValueError:
            typer.echo(f"ERROR: Invalid end date: {end}")
            raise typer.Exit(1)

    if directory:
        dir_path = Path(directory)
        if not dir_path.exists():
            typer.echo(f"ERROR: Directory not found: {dir_path}")
            raise typer.Exit(1)

        stats = import_from_directory(dir_path, start_date, end_date, preview)

    elif files:
        from qms.pipeline.common import parse_date as _parse_date

        files_with_dates = []
        for file_str in files:
            file_path = Path(file_str)
            if not file_path.exists():
                typer.echo(f"ERROR: File not found: {file_path}")
                raise typer.Exit(1)

            week_date = extract_date_from_filename(file_path)
            if not week_date:
                typer.echo(f"ERROR: Could not extract date from: {file_path.name}")
                raise typer.Exit(1)

            files_with_dates.append((file_path, week_date))

        files_with_dates.sort(key=lambda x: x[1])

        # Show file list
        typer.echo()
        typer.echo("Files to import (chronological order):")
        typer.echo("=" * 60)
        for i, (fp, wd) in enumerate(files_with_dates, 1):
            typer.echo(f"  {i:3d}. {wd} - {fp.name}")
        typer.echo(f"  Total: {len(files_with_dates)} files")

        stats = import_batch(files_with_dates, preview=preview)

    else:
        typer.echo("ERROR: Must specify either --directory or file names")
        raise typer.Exit(1)

    # Print summary
    typer.echo()
    typer.echo("Batch Import Summary")
    typer.echo("=" * 50)
    typer.echo(f"Files processed:      {stats.get('files_processed', 0)}")
    typer.echo(f"Files failed:         {stats.get('files_failed', 0)}")
    typer.echo(f"Total jobsites:       {stats.get('total_jobsites', 0)}")
    typer.echo(f"Total personnel:      {stats.get('total_personnel', 0)}")
    typer.echo(f"Employees created:    {stats.get('total_employees_created', 0)}")
    typer.echo(f"Employees updated:    {stats.get('total_employees_updated', 0)}")
    typer.echo(f"Job changes tracked:  {stats.get('total_job_changes', 0)}")

    if stats.get('errors'):
        typer.echo(f"\nErrors ({len(stats['errors'])}):")
        for err in stats['errors'][:5]:
            if isinstance(err, dict):
                typer.echo(f"  - {err.get('file', '?')}: {err.get('error', '?')}")
            else:
                typer.echo(f"  - {err}")


@app.command()
def process(
    project: Optional[str] = typer.Argument(None, help="Project number to process"),
    limit: int = typer.Option(10, "--limit", "-n", help="Max items to process"),
):
    """Run extraction processing on queued items."""
    from qms.core import get_db
    from qms.pipeline.importer import list_queue_items

    items = list_queue_items(status='pending', limit=limit)

    if project:
        items = [i for i in items if i.get('project_number') == project]

    if not items:
        typer.echo("No pending items to process.")
        if project:
            typer.echo(f"(filtered to project {project})")
        return

    typer.echo(f"Processing {len(items)} pending queue items...")
    typer.echo("-" * 50)

    processed = 0
    failed = 0

    with get_db() as conn:
        for item in items:
            item_id = item['id']
            drawing = item.get('drawing_number') or '?'
            proj = item.get('project_number') or '?'

            typer.echo(f"  [{item_id}] {proj}/{drawing} - {item['task']}...", nl=False)

            try:
                # Mark as processing
                conn.execute(
                    "UPDATE processing_queue SET status = 'processing', started_at = CURRENT_TIMESTAMP "
                    "WHERE id = ?",
                    (item_id,)
                )
                conn.commit()

                # TODO: actual extraction logic will go here when AI extraction is integrated
                # For now, mark as completed
                conn.execute(
                    "UPDATE processing_queue SET status = 'completed', completed_at = CURRENT_TIMESTAMP "
                    "WHERE id = ?",
                    (item_id,)
                )
                conn.commit()

                typer.echo(" done")
                processed += 1

            except Exception as e:
                conn.execute(
                    "UPDATE processing_queue SET status = 'failed', error = ? "
                    "WHERE id = ?",
                    (str(e), item_id)
                )
                conn.commit()

                typer.echo(f" FAILED: {e}")
                failed += 1

    typer.echo()
    typer.echo(f"Processed: {processed}, Failed: {failed}")


@app.command()
def intake(
    file: Optional[str] = typer.Option(None, "--file", "-f", help="Classify a single file"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without moving files"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show destination paths and patterns"),
):
    """Classify and route inbox documents to their destinations."""
    from qms.pipeline.classifier import (
        classify_file,
        compile_patterns,
        process_files,
        scan_inbox,
    )

    # Single file mode
    if file:
        filepath = Path(file)
        if not filepath.exists():
            typer.echo(f"ERROR: File not found: {filepath}")
            raise typer.Exit(1)

        compiled = compile_patterns()
        result = classify_file(filepath.name, filepath, compiled)

        _STATUS_ICON = {"matched": "[+]", "incomplete": "[?]", "unrecognized": "[X]"}
        icon = _STATUS_ICON.get(result.status, "[ ]")

        typer.echo(f"  {icon} {result.filename}")
        typer.echo(f"      Type:    {result.doc_type or '-'}")
        typer.echo(f"      Status:  {result.status}")
        typer.echo(f"      Handler: {result.handler or '-'}")
        if verbose and result.matched_pattern:
            typer.echo(f"      Pattern: {result.matched_pattern}")
        if result.destination:
            typer.echo(f"      Dest:    {result.destination}")
        if result.notes:
            typer.echo(f"      Notes:   {result.notes}")

        if not dry_run and result.status in ("matched", "incomplete", "unrecognized"):
            if typer.confirm("\nRoute this file?"):
                actions = process_files([result], dry_run=False)
                for a in actions:
                    typer.echo(f"  -> {a.action}: {a.destination}")
        return

    # Full inbox scan
    results = scan_inbox()

    if not results:
        typer.echo("Inbox is empty.")
        return

    # Count by status
    matched = sum(1 for r in results if r.status == "matched")
    incomplete = sum(1 for r in results if r.status == "incomplete")
    unrecognized = sum(1 for r in results if r.status == "unrecognized")

    typer.echo(f"Inbox Scan: {len(results)} files")
    typer.echo("=" * 80)
    typer.echo(
        f"  {'Filename':<36} {'Type':<20} {'Status':<14} Handler"
    )
    typer.echo("-" * 80)

    _STATUS_ICON = {"matched": "[+]", "incomplete": "[?]", "unrecognized": "[X]"}

    for r in results:
        icon = _STATUS_ICON.get(r.status, "[ ]")
        doc_type = r.doc_type or "-"
        handler = r.handler or "-"
        typer.echo(f"{icon} {r.filename:<36} {doc_type:<20} {r.status:<14} {handler}")
        if verbose:
            if r.matched_pattern:
                typer.echo(f"     pattern: {r.matched_pattern}")
            if r.destination:
                typer.echo(f"     dest:    {r.destination}")
            if r.notes:
                typer.echo(f"     notes:   {r.notes}")

    typer.echo("-" * 80)
    typer.echo(f"  Matched: {matched}  |  Incomplete: {incomplete}  |  Unrecognized: {unrecognized}")

    if dry_run:
        typer.echo("\n[DRY RUN] No files moved.")
        actions = process_files(results, dry_run=True)
        for a in actions:
            typer.echo(f"  {a.action}: {a.filename} -> {a.destination}")
        return

    if matched + incomplete + unrecognized == 0:
        return

    if not typer.confirm(f"\nProcess {len(results)} files?"):
        typer.echo("Aborted.")
        return

    actions = process_files(results, dry_run=False)
    routed = sum(1 for a in actions if a.action == "routed")
    review = sum(1 for a in actions if a.action == "needs_review")
    dupes = sum(1 for a in actions if a.action == "duplicate")
    typer.echo(f"\nDone: {routed} routed, {review} to NEEDS-REVIEW, {dupes} duplicates")
