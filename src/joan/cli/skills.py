from __future__ import annotations

import os
import shutil
from pathlib import Path

import typer

app = typer.Typer(help="Manage Joan skills and agent plugins.")

_SUPPORTED_AGENTS = {"claude", "codex"}

_CLAUDE_SKILL_NAMES = ("joan-setup", "joan-review", "joan-resolve-pr-comments")


def _install_dest(agent: str) -> Path:
    if agent == "claude":
        return Path.home() / ".claude" / "plugins" / "joan"
    codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    return codex_home / "skills" / "joan"


def _source_for(agent: str) -> Path:
    if agent == "claude":
        return Path(__file__).parent.parent / "data" / "claude-plugin"
    return Path(__file__).parent.parent / "data" / "codex-skills"


def _normalize_claude_layout(dest: Path) -> None:
    meta_dir = dest / ".claude-plugin"
    if not meta_dir.is_dir():
        return
    for entry in meta_dir.iterdir():
        shutil.move(str(entry), str(dest / entry.name))
    shutil.rmtree(meta_dir)


def _remove_legacy_claude(cwd: Path) -> None:
    # Legacy 1: per-repo skills in .claude/skills/
    removed = False
    for name in _CLAUDE_SKILL_NAMES:
        legacy = cwd / ".claude" / "skills" / name
        if legacy.exists():
            shutil.rmtree(legacy)
            removed = True
    if removed:
        typer.echo(f"Removed legacy per-repo skills from {cwd / '.claude' / 'skills'}.")


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
        _remove_legacy_claude(Path.cwd())

        if dest.exists():
            typer.echo(f"Existing install found at {dest}. Reinstalling...")
            shutil.rmtree(dest)

        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, dest)
        _normalize_claude_layout(dest)
        typer.echo(f"Installed joan plugin for {agent} at {dest}")
    else:
        if dest.exists():
            typer.echo(f"Existing install found at {dest}. Reinstalling...")
            shutil.rmtree(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, dest)
        typer.echo(f"Installed joan skills for {agent} at {dest}")
