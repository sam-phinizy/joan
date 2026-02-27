from __future__ import annotations

import os
import shutil
from pathlib import Path

import typer

app = typer.Typer(help="Manage Joan skills and agent plugins.")

_SUPPORTED_AGENTS = {"claude", "codex"}

def _install_dest(agent: str) -> Path:
    if agent == "claude":
        return Path.cwd() / ".claude" / "skills"
    codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    return codex_home / "skills" / "joan"


def _source_for(agent: str) -> Path:
    if agent == "claude":
        return Path(__file__).parent.parent / "data" / "claude-plugin" / "skills"
    return Path(__file__).parent.parent / "data" / "codex-skills"


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

    if agent == "claude":
        legacy = Path.cwd() / ".claude" / "plugins" / "joan"
        if legacy.exists():
            shutil.rmtree(legacy)
            typer.echo(f"Removed legacy plugin install at {legacy}.")

        skill_names = [s.name for s in src.iterdir() if s.is_dir()]
        if any((dest / name).exists() for name in skill_names):
            typer.echo(f"Existing install found at {dest}. Reinstalling...")
            for name in skill_names:
                skill_dest = dest / name
                if skill_dest.exists():
                    shutil.rmtree(skill_dest)
        dest.mkdir(parents=True, exist_ok=True)
        for skill_dir in src.iterdir():
            if skill_dir.is_dir():
                shutil.copytree(skill_dir, dest / skill_dir.name)
    else:
        if dest.exists():
            typer.echo(f"Existing install found at {dest}. Reinstalling...")
            shutil.rmtree(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, dest)

    typer.echo(f"Installed joan skills for {agent} at {dest}")
