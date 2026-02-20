"""
QMS CLI - Main Entry Point

Unified Typer CLI that assembles all module sub-commands.

Usage:
    qms version
    qms migrate
    qms welding [command]
    qms workforce [command]
    qms projects [command]
    qms pipeline [command]
    qms docs [command]
    qms refs [command]
    qms eng [command]
    qms report [command]
"""

import typer

import qms

app = typer.Typer(
    name="qms",
    help="Quality Management System for MEP division operations.",
    no_args_is_help=True,
)


@app.command()
def version():
    """Show QMS version and module status."""
    typer.echo(f"qms {qms.__version__}")


@app.command()
def migrate():
    """Run database schema migrations for all modules."""
    from qms.core.db import migrate_all

    migrate_all()
    typer.echo("Database migration complete.")


@app.command()
def serve(
    port: int = typer.Option(5000, "--port", "-p", help="Port number"),
    host: str = typer.Option(None, "--host", "-h", help="Host address (default: 0.0.0.0 prod, 127.0.0.1 debug)"),
    debug: bool = typer.Option(False, "--debug", help="Use Flask dev server with auto-reload (localhost only)"),
    threads: int = typer.Option(8, "--threads", "-t", help="Waitress worker threads (production only)"),
):
    """Launch the QMS web interface.

    Default: Waitress production server on 0.0.0.0 (LAN accessible).
    With --debug: Flask dev server on 127.0.0.1 with auto-reload.
    """
    from qms.api import create_app

    web = create_app()

    if debug:
        _host = host or "127.0.0.1"
        typer.echo(f"Starting Flask dev server at http://{_host}:{port}")
        typer.echo("Debug mode ON — auto-reloads on file changes")
        web.run(host=_host, port=port, debug=True)
    else:
        _host = host or "0.0.0.0"
        try:
            from waitress import serve as waitress_serve
        except ImportError:
            typer.echo("waitress not installed — falling back to Flask dev server")
            typer.echo("Install with: pip install waitress")
            web.run(host=_host, port=port, debug=False)
            return
        typer.echo(f"Starting Waitress production server on {_host}:{port} ({threads} threads)")
        if _host == "0.0.0.0":
            import socket
            hostname = socket.gethostname()
            typer.echo(f"LAN access: http://{hostname}:{port}")
        waitress_serve(web, host=_host, port=port, threads=threads)


def _register_modules():
    """Register module CLI sub-apps. Silently skips modules missing a cli.py."""
    module_registry = [
        ("qms.welding.cli", "welding", "Welding program management"),
        ("qms.workforce.cli", "workforce", "Employee & workforce management"),
        ("qms.projects.cli", "projects", "Projects, customers & jobs"),
        ("qms.timetracker.cli", "timetracker", "Time tracking & projections"),
        ("qms.pipeline.cli", "pipeline", "Drawing extraction & conflict detection"),
        ("qms.qualitydocs.cli", "docs", "Quality manual & documents"),
        ("qms.references.cli", "refs", "Reference standards library"),
        ("qms.engineering.cli", "eng", "Engineering calculations"),
        ("qms.automation.cli", "automation", "Automation request processing"),
        ("qms.reporting.cli", "report", "Reports & dashboards"),
        ("qms.vectordb.cli", "vectordb", "Vector search & embeddings"),
        ("qms.auth.cli", "auth", "User account management"),
    ]

    for module_path, name, help_text in module_registry:
        try:
            import importlib

            mod = importlib.import_module(module_path)
            app.add_typer(mod.app, name=name, help=help_text)
        except (ImportError, AttributeError):
            pass


_register_modules()


def main():
    """Entry point for the qms CLI."""
    app()


if __name__ == "__main__":
    main()
