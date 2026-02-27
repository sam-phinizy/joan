from __future__ import annotations

import json
from pathlib import Path

import typer

from joan.core.git import infer_branch_name, worktree_add_args, worktree_remove_args
from joan.shell.git_runner import run_git

app = typer.Typer(help="Manage local git worktrees.")


def _tracking_file() -> Path:
    return Path.cwd() / ".joan" / "worktrees.json"


def _load_tracking() -> dict[str, str]:
    path = _tracking_file()
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _save_tracking(data: dict[str, str]) -> None:
    path = _tracking_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


@app.command("create")
def worktree_create(name: str | None = typer.Argument(default=None)) -> None:
    branch = name or infer_branch_name("worktree")
    path = Path.cwd().parent / branch.replace("/", "-")

    run_git(worktree_add_args(str(path), branch=branch))

    tracking = _load_tracking()
    tracking[branch] = str(path)
    _save_tracking(tracking)
    typer.echo(f"Created worktree {branch} at {path}")


@app.command("remove")
def worktree_remove(name: str = typer.Argument(...)) -> None:
    tracking = _load_tracking()
    path = tracking.get(name)
    if not path:
        typer.echo(f"Unknown worktree '{name}'.", err=True)
        raise typer.Exit(code=1)

    run_git(worktree_remove_args(path))
    tracking.pop(name, None)
    _save_tracking(tracking)
    typer.echo(f"Removed worktree {name}")
