"""CLI registration for the system tray app."""

import typer

app = typer.Typer(no_args_is_help=False, invoke_without_command=True)


@app.callback(invoke_without_command=True)
def tray(
    port: int = typer.Option(5000, "--port", "-p", help="Server port"),
):
    """Launch the QMS system tray app for server control."""
    from qms.tray.app import main

    main(port=port)
