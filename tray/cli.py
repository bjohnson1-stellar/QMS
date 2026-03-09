"""CLI registration for the system tray app."""

import typer

app = typer.Typer(no_args_is_help=False, invoke_without_command=True)


@app.callback(invoke_without_command=True)
def tray(
    ctx: typer.Context,
    port: int = typer.Option(5000, "--port", "-p", help="Server port"),
    auto_start: bool = typer.Option(False, "--auto-start", help="Start the server automatically on launch"),
):
    """Launch the QMS system tray app for server control."""
    if ctx.invoked_subcommand is not None:
        return
    from qms.tray.app import main

    main(port=port, auto_start=auto_start)


@app.command()
def install_startup(
    port: int = typer.Option(5000, "--port", "-p", help="Server port"),
):
    """Add QMS tray app to Windows Startup (launches on login)."""
    import sys
    from pathlib import Path

    startup_dir = Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    shortcut_path = startup_dir / "SIS QMS Tray.vbs"

    python_exe = sys.executable
    # Use pythonw.exe to avoid a console window on startup
    pythonw = Path(python_exe).parent / "pythonw.exe"
    exe = str(pythonw) if pythonw.exists() else python_exe

    # VBScript wrapper to launch without a visible console window
    vbs_content = f'CreateObject("Wscript.Shell").Run """{exe}"" -m qms tray --auto-start --port {port}", 0, False\n'

    shortcut_path.write_text(vbs_content)
    typer.echo(f"Startup shortcut created: {shortcut_path}")
    typer.echo(f"QMS tray will auto-start the server on port {port} at login.")


@app.command()
def remove_startup():
    """Remove QMS tray app from Windows Startup."""
    from pathlib import Path

    shortcut_path = Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / "SIS QMS Tray.vbs"
    if shortcut_path.exists():
        shortcut_path.unlink()
        typer.echo(f"Removed startup shortcut: {shortcut_path}")
    else:
        typer.echo("No startup shortcut found.")
