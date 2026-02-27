from __future__ import annotations

import shutil
from pathlib import Path

import typer

app = typer.Typer(help="Manage the local Forgejo instance.")

_COMPOSE_SOURCE = Path(__file__).parent.parent / "data" / "forge" / "docker-compose.yml"


@app.command("install")
def forge_install(
    path: Path = typer.Argument(
        default=Path.home() / "joan-forge",
        help="Directory to install Forgejo compose files into.",
    ),
) -> None:
    """Copy the Forgejo docker-compose.yml to a directory and print start instructions."""
    path = path.expanduser().resolve()
    path.mkdir(parents=True, exist_ok=True)

    dest = path / "docker-compose.yml"
    shutil.copy2(_COMPOSE_SOURCE, dest)
    typer.echo(f"Installed Forgejo compose file to {dest}")
    typer.echo("")
    typer.echo("To start Forgejo:")
    typer.echo(f"  cd {path}")
    typer.echo("  FORGE_ADMIN_PASSWORD=yourpassword docker compose up -d")
    typer.echo("")
    typer.echo("Forgejo will be available at http://localhost:3000")
    typer.echo("Admin username defaults to your $USER (or 'forgeadmin' if $USER is unset).")
    typer.echo("Override with FORGE_ADMIN_USERNAME and FORGE_ADMIN_EMAIL env vars.")
