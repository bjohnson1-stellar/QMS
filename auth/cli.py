"""
Auth CLI — user management commands for bootstrapping and administration.

Usage:
    qms auth create-user    → Create a new user interactively
    qms auth reset-password  → Reset a user's password
    qms auth list-users      → List all user accounts
"""

import typer

app = typer.Typer(no_args_is_help=True)


@app.command("create-user")
def create_user(
    email: str = typer.Option(..., prompt=True, help="User email address"),
    name: str = typer.Option(..., "--name", prompt="Display name", help="Display name"),
    password: str = typer.Option(
        ..., prompt=True, confirmation_prompt=True, hide_input=True, help="Password"
    ),
    role: str = typer.Option("admin", help="Role: admin, user, or viewer"),
):
    """Create a new user account."""
    if role not in ("admin", "user", "viewer"):
        typer.echo(f"Invalid role: {role}. Must be admin, user, or viewer.", err=True)
        raise typer.Exit(1)

    if len(password) < 8:
        typer.echo("Password must be at least 8 characters.", err=True)
        raise typer.Exit(1)

    from qms.core.db import get_db
    from qms.auth.db import create_user as do_create
    import sqlite3

    try:
        with get_db() as conn:
            user = do_create(
                conn, email.strip().lower(), name.strip(), password, role,
                must_change_password=False,
            )
        typer.echo(f"Created user: {user['display_name']} <{user['email']}> [{user['role']}]")
    except sqlite3.IntegrityError:
        typer.echo(f"Error: A user with email '{email}' already exists.", err=True)
        raise typer.Exit(1)


@app.command("reset-password")
def reset_password(
    email: str = typer.Option(..., prompt=True, help="User email address"),
    password: str = typer.Option(
        ..., prompt="New password", confirmation_prompt=True, hide_input=True,
        help="New password",
    ),
):
    """Reset a user's password."""
    if len(password) < 8:
        typer.echo("Password must be at least 8 characters.", err=True)
        raise typer.Exit(1)

    from qms.core.db import get_db
    from qms.auth.db import get_user_by_email, set_password

    with get_db() as conn:
        user = get_user_by_email(conn, email.strip().lower())
        if not user:
            typer.echo(f"No user found with email: {email}", err=True)
            raise typer.Exit(1)

        set_password(conn, user["id"], password, must_change=True)

    typer.echo(f"Password reset for {user['display_name']}. User will be prompted to change on next login.")


@app.command("list-users")
def list_users_cmd():
    """List all user accounts."""
    from qms.core.db import get_db
    from qms.auth.db import list_users

    with get_db(readonly=True) as conn:
        users = list_users(conn)

    if not users:
        typer.echo("No users found. Run 'qms auth create-user' to create the first admin.")
        return

    typer.echo(f"{'ID':>4}  {'Email':<30}  {'Name':<25}  {'Role':<8}  {'Active':<7}  {'Last Login'}")
    typer.echo("-" * 100)
    for u in users:
        active = "Yes" if u.get("is_active") else "No"
        typer.echo(
            f"{u['id']:>4}  {u['email']:<30}  {u['display_name']:<25}  "
            f"{u['role']:<8}  {active:<7}  {u.get('last_login', 'never')}"
        )
