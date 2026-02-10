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
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Host address"),
):
    """Launch the QMS web interface."""
    from qms.api import create_app

    web = create_app()
    typer.echo(f"Starting QMS web server at http://{host}:{port}")
    web.run(host=host, port=port, debug=False)


def _register_modules():
    """Register module CLI sub-apps. Silently skips modules missing a cli.py."""
    module_registry = [
        ("qms.welding.cli", "welding", "Welding program management"),
        ("qms.workforce.cli", "workforce", "Employee & workforce management"),
        ("qms.projects.cli", "projects", "Projects, customers & jobs"),
        ("qms.pipeline.cli", "pipeline", "Drawing extraction & conflict detection"),
        ("qms.qualitydocs.cli", "docs", "Quality manual & documents"),
        ("qms.references.cli", "refs", "Reference standards library"),
        ("qms.engineering.cli", "eng", "Engineering calculations"),
        ("qms.reporting.cli", "report", "Reports & dashboards"),
        ("qms.vectordb.cli", "vectordb", "Vector search & embeddings"),
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
