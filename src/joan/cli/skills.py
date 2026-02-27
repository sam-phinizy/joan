from __future__ import annotations

import os
import shutil
from pathlib import Path

import typer

app = typer.Typer(help="Manage Joan skills and agent plugins.")

_SUPPORTED_AGENTS = {"claude", "codex"}

_AGENT_SOURCE_DIR = {
    "claude": "claude-plugin",
    "codex": "codex-skills",
}


def _install_dest(agent: str) -> Path:
    if agent == "claude":
        return Path.cwd() / ".claude" / "plugins" / "joan"
    codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    return codex_home / "skills" / "joan"


def _source_for(agent: str) -> Path:
    return Path(__file__).parent.parent / "data" / _AGENT_SOURCE_DIR[agent]


def _normalize_claude_layout(dest: Path) -> None:
    meta_dir = dest / ".claude-plugin"
    if not meta_dir.is_dir():
        return
    for entry in meta_dir.iterdir():
        shutil.move(str(entry), str(dest / entry.name))
    shutil.rmtree(meta_dir)


@app.command("install")
def skills_install(
    agent: str = typer.Option(..., help=f"Agent to install skills/plugin for. Supported: {', '.join(sorted(_SUPPORTED_AGENTS))}"),
) -> None:
    if agent not in _SUPPORTED_AGENTS:
        typer.echo(f"Unknown agent '{agent}'. Supported agents: {', '.join(sorted(_SUPPORTED_AGENTS))}", err=True)
        raise typer.Exit(code=1)

    src = _source_for(agent)
    if not src.exists():
        typer.echo(f"Install source not found for {agent}: {src}", err=True)
        raise typer.Exit(code=1)

    dest = _install_dest(agent)

    if dest.exists():
        typer.echo(f"Existing install found at {dest}. Reinstalling...")
        shutil.rmtree(dest)

    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dest)
    if agent == "claude":
        _normalize_claude_layout(dest)
    if agent == "claude":
        typer.echo(f"Installed joan plugin for {agent} at {dest}")
    else:
        typer.echo(f"Installed joan skills for {agent} at {dest}")
