from __future__ import annotations

import typer

from joan.cli._common import load_config_or_exit
from joan.core.git import create_branch_args, infer_branch_name, push_branch_args
from joan.shell.git_runner import run_git

app = typer.Typer(help="Create and manage review branches.")


@app.command("create")
def branch_create(name: str | None = typer.Argument(default=None)) -> None:
    config = load_config_or_exit()
    branch = name or infer_branch_name()

    run_git(create_branch_args(branch))
    run_git(push_branch_args(config.remotes.review, branch, set_upstream=True))
    typer.echo(f"Created and pushed branch: {branch}")
