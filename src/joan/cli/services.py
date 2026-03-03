from __future__ import annotations

import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import typer


@dataclass(frozen=True)
class ServiceBundle:
    key: str
    display_name: str
    description: str
    compose_source: Path
    default_dir: Path
    print_instructions: Callable[[Path], None]


def _print_forgejo_instructions(path: Path) -> None:
    typer.echo("To start Forgejo:")
    typer.echo(f"  cd {path}")
    typer.echo("  FORGE_ADMIN_PASSWORD=yourpassword docker compose up -d")
    typer.echo("")
    typer.echo("Forgejo will be available at http://localhost:3000")
    typer.echo("Admin username defaults to your $USER (or 'forgeadmin' if $USER is unset).")
    typer.echo("Override with FORGE_ADMIN_USERNAME and FORGE_ADMIN_EMAIL env vars.")


_SERVICE_BUNDLES = {
    "forgejo": ServiceBundle(
        key="forgejo",
        display_name="Forgejo",
        description="Local Forgejo review server.",
        compose_source=Path(__file__).parent.parent / "data" / "forge" / "docker-compose.yml",
        default_dir=Path.home() / "joan-forge",
        print_instructions=_print_forgejo_instructions,
    ),
}


app = typer.Typer(help="Install bundled local service stacks Joan can use, starting with Forgejo.")


def available_service_names() -> tuple[str, ...]:
    return tuple(sorted(_SERVICE_BUNDLES))


def get_service_bundle(name: str) -> ServiceBundle | None:
    return _SERVICE_BUNDLES.get(name.strip().lower())


def install_service_bundle(name: str, path: Path | None = None) -> tuple[ServiceBundle, Path]:
    bundle = get_service_bundle(name)
    if bundle is None:
        raise KeyError(name)

    target_dir = (path or bundle.default_dir).expanduser().resolve()
    target_dir.mkdir(parents=True, exist_ok=True)

    dest = target_dir / "docker-compose.yml"
    shutil.copy2(bundle.compose_source, dest)
    return bundle, dest


def announce_install(bundle: ServiceBundle, dest: Path) -> None:
    typer.echo(f"Installed {bundle.display_name} compose file to {dest}")
    typer.echo("")
    bundle.print_instructions(dest.parent)


@app.command("install", help="Copy a bundled docker-compose stack into a reusable directory.")
def install_command(
    service: str = typer.Argument(
        ...,
        help="Service bundle to install.",
    ),
    path: Path | None = typer.Argument(
        default=None,
        help="Destination directory for the compose file. Defaults to the service's standard directory.",
    ),
) -> None:
    try:
        bundle, dest = install_service_bundle(service, path)
    except KeyError:
        supported = ", ".join(available_service_names())
        typer.echo(f"Unknown service '{service}'. Available services: {supported}.", err=True)
        raise typer.Exit(code=2)

    announce_install(bundle, dest)


@app.command("list", help="Show the bundled service stacks Joan can install.")
def list_command() -> None:
    for name in available_service_names():
        bundle = _SERVICE_BUNDLES[name]
        typer.echo(f"{bundle.key}: {bundle.description}")
