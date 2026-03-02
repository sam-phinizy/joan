from __future__ import annotations

import typer

from joan.cli._common import load_config_or_exit
from joan.core.branch_state import load_branch_state, save_branch_state
from joan.core.git import (
    create_branch_args,
    current_branch_args,
    merge_base_args,
    push_branch_args,
    push_refspec_args,
    rev_parse_args,
    review_branch_name,
)
from joan.shell.git_runner import run_git

app = typer.Typer(help="Create and push `joan-review/*` branches for the local Forgejo review flow.")


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

    # Determine the base SHA for the remote base branch.
    # Use stored state from a previous review round if available.
    base_sha = load_branch_state(working_branch)

    if base_sha is None:
        # First review round: find where this branch diverged from the
        # mainline.  Try several common refs in order of likelihood.
        candidates = [
            f"{config.remotes.upstream}/main",
            f"{config.remotes.upstream}/master",
            f"{config.remotes.upstream}/HEAD",
            "main",
            "master",
        ]
        for ref in candidates:
            try:
                base_sha = run_git(merge_base_args(ref, "HEAD"))
                break
            except Exception:  # noqa: BLE001
                continue
        else:
            typer.echo(
                "Could not determine base SHA. Ensure you have fetched from upstream, "
                "or create a `.joan/branch-state.json` manually.",
                err=True,
            )
            raise typer.Exit(code=1)

    if base_sha == head_sha:
        typer.echo("Warning: no new commits to review (base SHA == HEAD).", err=True)

    # Push base SHA as the working branch on the review remote.
    run_git(push_refspec_args(config.remotes.review, base_sha, f"refs/heads/{working_branch}"))

    # Save state for future rounds.
    save_branch_state(working_branch, head_sha)

    run_git(create_branch_args(review_branch))
    typer.echo(f"Created review branch: {review_branch} (base: {working_branch})")


@app.command("push", help="Push the current branch to the configured review remote for another review pass.")
def branch_push() -> None:
    config = load_config_or_exit()
    branch = run_git(current_branch_args())
    run_git(push_branch_args(config.remotes.review, branch, set_upstream=True))
    typer.echo(f"Pushed branch: {branch}")
