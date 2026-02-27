from __future__ import annotations

import shutil
from pathlib import Path

import typer

app = typer.Typer(help="Manage Joan skills and agent plugins.")

_SUPPORTED_AGENTS = {"claude"}

_AGENT_PLUGIN_DEST = {
    "claude": Path(".claude") / "plugins" / "joan",
}


def _plugin_source() -> Path:
    return Path(__file__).parent.parent / "data" / "claude-plugin"


@app.command("install")
def skills_install(
    agent: str = typer.Option(..., help=f"Agent to install the plugin for. Supported: {', '.join(_SUPPORTED_AGENTS)}"),
) -> None:
    if agent not in _SUPPORTED_AGENTS:
        typer.echo(f"Unknown agent '{agent}'. Supported agents: {', '.join(_SUPPORTED_AGENTS)}", err=True)
        raise typer.Exit(code=1)

    src = _plugin_source()
    if not src.exists():
        typer.echo(f"Plugin source not found: {src}", err=True)
        raise typer.Exit(code=1)

    dest = Path.cwd() / _AGENT_PLUGIN_DEST[agent]

    if dest.exists():
        typer.echo(f"Plugin already installed at {dest}. Reinstalling...")
        shutil.rmtree(dest)

    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dest)
    typer.echo(f"Installed joan plugin for {agent} at {dest}")
