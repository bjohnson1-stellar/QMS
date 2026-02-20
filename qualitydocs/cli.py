"""Quality Documents CLI sub-commands."""

import typer
from typing import Optional

app = typer.Typer(no_args_is_help=True)


@app.command()
def load_module(
    files: list[str] = typer.Argument(None, help="XML file path(s). If omitted, scans cwd for module*.xml."),
    directory: Optional[str] = typer.Option(None, "--dir", "-d", help="Directory to scan for module XML files."),
):
    """Load quality manual module(s) from XML into the database."""
    from qms.qualitydocs.loader import (
        find_xml_files,
        load_module_from_file,
        load_modules_from_files,
    )

    # Resolve which files to load
    if files:
        xml_paths = files
    elif directory:
        xml_paths = find_xml_files(directory)
    else:
        xml_paths = find_xml_files(".")

    if not xml_paths:
        typer.echo("No XML files found matching module*_output.xml or module*.xml")
        raise typer.Exit(code=1)

    typer.echo(f"Found {len(xml_paths)} XML file(s) to process:")
    for p in xml_paths:
        typer.echo(f"  {p}")
    typer.echo()

    if len(xml_paths) == 1:
        result = load_module_from_file(xml_paths[0])
        typer.echo(
            f"Loaded module {result['module_number']} (v{result['version']}): "
            f"{result['sections']} sections, "
            f"{result['subsections']} subsections, "
            f"{result['content_blocks']} content blocks"
        )
        typer.echo(
            f"References: {result['explicit_xrefs']} explicit xrefs, "
            f"{result['prose_xrefs']} prose xrefs, "
            f"{result['explicit_coderefs']} explicit code refs"
        )
        typer.echo(
            f"Validation: {result['valid_xrefs']} valid, "
            f"{result['invalid_xrefs']} invalid cross-refs"
        )
        typer.echo(f"FTS index: {result['fts_rows']} rows")
    else:
        result = load_modules_from_files(xml_paths)
        typer.echo(f"Modules loaded: {result['modules_loaded']}")
        for mod in result["modules"]:
            typer.echo(
                f"  Module {mod['module_number']} (v{mod['version']}): "
                f"{mod['sections']} sections, {mod['subsections']} subsections, "
                f"{mod['content_blocks']} content blocks"
            )
        if result["errors"]:
            typer.echo(f"\nErrors ({len(result['errors'])}):")
            for err in result["errors"]:
                typer.echo(f"  {err['file']}: {err['error']}")
        typer.echo(
            f"\nProse detection: {result['prose_xrefs']} cross-refs, "
            f"{sum(result['prose_coderefs'].values())} code refs"
        )
        typer.echo(
            f"Validation: {result['valid_xrefs']} valid, "
            f"{result['invalid_xrefs']} invalid cross-refs"
        )
        typer.echo(f"FTS index: {result['fts_rows']} rows")


@app.command()
def summary():
    """Show quality manual summary/status."""
    from qms.qualitydocs.loader import get_manual_summary

    result = get_manual_summary()

    typer.echo("Quality Manual Summary")
    typer.echo("=" * 60)

    if not result["modules"]:
        typer.echo("  No modules loaded.")
        return

    typer.echo(f"  Modules loaded: {result['total_modules']}")
    typer.echo()

    for mod in result["modules"]:
        status_tag = f" [{mod['status']}]" if mod["status"] else ""
        typer.echo(
            f"  Module {mod['module_number']:>2}  v{mod['version'] or '?':<6}"
            f"  {mod['title'] or '(no title)'}"
            f"{status_tag}"
        )
        typer.echo(
            f"             {mod['section_count']} sections, "
            f"{mod['subsection_count']} subsections"
        )

    typer.echo()
    typer.echo(f"  Content blocks:       {result['total_content_blocks']}")
    typer.echo(
        f"  Cross-references:     {result['total_cross_references']}"
        f" ({result['valid_cross_references']} valid)"
    )
    typer.echo(f"  Code references:      {result['total_code_references']}")
    typer.echo(f"  Responsibilities:     {result['total_responsibilities']}")
    typer.echo(f"  FTS indexed rows:     {result['fts_indexed_rows']}")


@app.command()
def search(
    query: str = typer.Argument(..., help="FTS5 search expression"),
    limit: int = typer.Option(20, "--limit", "-n", help="Max results"),
):
    """Search quality manual content (full-text)."""
    from qms.qualitydocs.loader import search_content

    results = search_content(query, limit=limit)

    if not results:
        typer.echo(f"No results for '{query}'.")
        return

    for r in results:
        ref = f"M{r['module_number']}.{r['section_number']}.{r['subsection_ref']}"
        snippet = r["content"][:120].replace("\n", " ") if r["content"] else ""
        typer.echo(f"  {ref:<20} {snippet}...")

    typer.echo(f"\n  {len(results)} result(s)")


@app.command()
def export(
    module_number: int = typer.Argument(..., help="Module number to export"),
    format: str = typer.Option("pdf", "--format", "-f", help="Output format: pdf or html"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file path"),
):
    """Export a quality manual module as a formatted PDF."""
    from qms.qualitydocs.export import export_module_html, export_module_pdf

    try:
        if format == "html":
            path = export_module_html(module_number, output_path=output)
        else:
            path = export_module_pdf(module_number, output_path=output)
        typer.echo(f"Exported: {path}")
    except ImportError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)
    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)


@app.command()
def detail(
    module_number: int = typer.Argument(..., help="Module number to inspect"),
):
    """Show detailed information about a specific quality manual module."""
    from qms.qualitydocs.loader import get_module_detail

    result = get_module_detail(module_number)

    if result is None:
        typer.echo(f"Module {module_number} not found.")
        raise typer.Exit(code=1)

    typer.echo(f"Module {result['module_number']}: {result['title'] or '(no title)'}")
    typer.echo(f"  Version:        {result['version']}")
    typer.echo(f"  Effective date: {result['effective_date']}")
    typer.echo(f"  Status:         {result['status']}")
    typer.echo()

    if result["sections"]:
        typer.echo("Sections:")
        for s in result["sections"]:
            typer.echo(f"  {s['section_number']:<10} {s['title'] or ''}")

    if result["cross_references"]:
        typer.echo(f"\nCross-references ({len(result['cross_references'])}):")
        for x in result["cross_references"][:15]:
            valid = "ok" if x["is_valid"] else "??"
            typer.echo(
                f"  [{valid}] -> Module {x['target_module']}, "
                f"Section {x['target_section']}"
                f"{('.' + x['target_subsection']) if x['target_subsection'] else ''}"
                f"  ({x['detection_method']})"
            )
        if len(result["cross_references"]) > 15:
            typer.echo(f"  ... and {len(result['cross_references']) - 15} more")

    if result["code_references"]:
        typer.echo(f"\nCode references ({len(result['code_references'])}):")
        for c in result["code_references"][:15]:
            typer.echo(f"  {c['organization'] or '?':<8} {c['code']}")
        if len(result["code_references"]) > 15:
            typer.echo(f"  ... and {len(result['code_references']) - 15} more")
