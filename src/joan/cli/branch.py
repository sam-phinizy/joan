from __future__ import annotations

import typer

from joan.cli._common import ensure_branch_tracking, load_config_or_exit
from joan.core.branch_state import save_branch_start
from joan.core.git import (
    create_branch_args,
    current_branch_args,
    merge_base_args,
    push_branch_args,
    push_refspec_args,
    rev_parse_args,
    review_branch_name,
    working_branch_for_review,
)
from joan.shell.git_runner import run_git

app = typer.Typer(help="Create and push `joan-review/*` branches for the local Forgejo review flow.")


@app.command("adopt", help="Record a working branch's starting point so Joan can base the first review PR correctly.")
def branch_adopt(
    base_ref: str = typer.Option(..., "--base-ref", help="Git ref this branch forked from (for example `origin/main` or `feature/base`)."),
    branch: str | None = typer.Option(None, "--branch", help="Working branch to register. Defaults to the current branch."),
) -> None:
    target_branch = (branch or run_git(current_branch_args())).strip()
    if not target_branch:
        typer.echo("Branch cannot be empty.", err=True)
        raise typer.Exit(code=2)
    if working_branch_for_review(target_branch):
        typer.echo("Use a non-review working branch with `joan branch adopt`.", err=True)
        raise typer.Exit(code=2)

    branch_start_sha = run_git(merge_base_args(base_ref, target_branch))
    save_branch_start(target_branch, branch_start_sha)
    typer.echo(f"Registered branch start for {target_branch}: {branch_start_sha} (base ref: {base_ref})")


@app.command("create", help="Create a `joan-review/*` branch from the current branch and push the base branch first.")
def branch_create(
    name: str | None = typer.Argument(
        default=None,
        help="Optional review branch name. Omit this to let Joan auto-generate `joan-review/<current-branch>--rN`.",
    )
) -> None:
    config = load_config_or_exit()
    working_branch = run_git(current_branch_args())
    review_branch = name or review_branch_name(working_branch)

    if review_branch == working_branch:
        typer.echo("Review branch must be different from the current working branch.", err=True)
        raise typer.Exit(code=2)

    head_sha = run_git(rev_parse_args("HEAD"))
    state = ensure_branch_tracking(config, working_branch)
    base_sha = state.review_checkpoint_sha or state.branch_start_sha
    if not base_sha:
        typer.echo("Missing branch tracking state. Run `uv run joan branch adopt --base-ref <ref>` first.", err=True)
        raise typer.Exit(code=1)

    if base_sha == head_sha:
        typer.echo("Warning: no new commits to review (base SHA == HEAD).", err=True)

    # Push base SHA as the working branch on the review remote.
    run_git(push_refspec_args(config.remotes.review, base_sha, f"refs/heads/{working_branch}"))

    run_git(create_branch_args(review_branch))
    typer.echo(f"Created review branch: {review_branch} (base: {working_branch})")


@app.command("push", help="Push the current branch to the configured review remote for another review pass.")
def branch_push() -> None:
    config = load_config_or_exit()
    branch = run_git(current_branch_args())
    run_git(push_branch_args(config.remotes.review, branch, set_upstream=True))
    typer.echo(f"Pushed branch: {branch}")
