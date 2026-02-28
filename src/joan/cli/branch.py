from __future__ import annotations

import typer

from joan.cli._common import load_config_or_exit
from joan.core.git import create_branch_args, current_branch_args, push_branch_args, review_branch_name
from joan.shell.git_runner import run_git

app = typer.Typer(help="Create and manage review branches.")


@app.command("create")
def branch_create(name: str | None = typer.Argument(default=None)) -> None:
    config = load_config_or_exit()
    working_branch = run_git(current_branch_args())
    review_branch = name or review_branch_name(working_branch)

    if review_branch == working_branch:
        typer.echo("Review branch must be different from the current working branch.", err=True)
        raise typer.Exit(code=2)

    run_git(push_branch_args(config.remotes.review, working_branch, set_upstream=False))
    run_git(create_branch_args(review_branch))
    typer.echo(f"Created review branch: {review_branch} (base: {working_branch})")


@app.command("push")
def branch_push() -> None:
    config = load_config_or_exit()
    branch = run_git(current_branch_args())
    run_git(push_branch_args(config.remotes.review, branch, set_upstream=True))
    typer.echo(f"Pushed branch: {branch}")
