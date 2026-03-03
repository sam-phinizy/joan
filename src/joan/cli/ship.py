from __future__ import annotations

import typer

from joan.cli._common import current_branch, load_config_or_exit
from joan.core.git import (
    default_publish_branch_name,
    is_stage_branch,
    push_branch_args,
    reset_branch_args,
    stage_branch_name,
)
from joan.shell.git_runner import run_git


def _ensure_task_branch(branch: str) -> None:
    if branch in {"main", "master"} or branch.startswith("joan-review/") or is_stage_branch(branch):
        typer.echo("Run `joan ship` from a normal working task branch.", err=True)
        raise typer.Exit(code=2)


def ship_command(
    publish_branch: str | None = typer.Option(None, "--as", help="Optional publish branch name for the upstream remote."),
) -> None:
    config = load_config_or_exit()
    branch = current_branch()
    _ensure_task_branch(branch)

    stage_branch = stage_branch_name(branch)
    destination = (publish_branch or default_publish_branch_name(branch)).strip()
    if not destination:
        typer.echo("Publish branch cannot be empty.", err=True)
        raise typer.Exit(code=2)

    if not run_git(["ls-remote", config.remotes.review, f"refs/heads/{stage_branch}"]):
        typer.echo(
            f"Stage branch is missing on {config.remotes.review}: {stage_branch}. "
            "Create or finish a review first.",
            err=True,
        )
        raise typer.Exit(code=1)

    run_git(["fetch", config.remotes.review])
    run_git(reset_branch_args(destination, f"{config.remotes.review}/{stage_branch}"))
    run_git(push_branch_args(config.remotes.upstream, destination, set_upstream=True))
    typer.echo(
        f"Prepared {destination} from {stage_branch} and pushed it to {config.remotes.upstream}. "
        "Open the final GitHub PR manually."
    )
