from __future__ import annotations

from typing import Any

import typer

from joan.cli._common import current_branch, forgejo_client, load_config_or_exit, print_json
from joan.core.git import (
    create_branch_args,
    current_branch_args,
    ls_remote_ref_args,
    push_branch_args,
    push_refspec_args,
    rev_parse_args,
    stage_branch_name,
    working_branch_for_stage,
)
from joan.shell.forgejo_client import ForgejoError
from joan.shell.git_runner import run_git

app = typer.Typer(help="Start and manage Joan task branches that review into long-lived stage branches.")


def _is_disallowed_task_branch(branch: str) -> bool:
    return branch in {"main", "master"} or branch.startswith("joan-review/") or working_branch_for_stage(branch) is not None


def _ensure_allowed_task_branch(branch: str) -> None:
    if _is_disallowed_task_branch(branch):
        typer.echo(
            "Use a normal working branch, not main/master or a Joan-managed stage/review branch.",
            err=True,
        )
        raise typer.Exit(code=2)


def _ensure_local_branch_missing(branch: str) -> None:
    try:
        run_git(["show-ref", "--verify", f"refs/heads/{branch}"])
    except Exception:  # noqa: BLE001
        return
    typer.echo(f"Local branch already exists: {branch}", err=True)
    raise typer.Exit(code=2)


def _ensure_local_branch_exists(branch: str) -> None:
    try:
        run_git(["show-ref", "--verify", f"refs/heads/{branch}"])
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"Local branch not found: {branch} ({exc})", err=True)
        raise typer.Exit(code=2) from exc


def _branch_exists_on_remote(remote: str, branch: str) -> bool:
    return bool(run_git(ls_remote_ref_args(remote, branch)))


def _ensure_stage_missing(remote: str, branch: str) -> None:
    stage_branch = stage_branch_name(branch)
    if _branch_exists_on_remote(remote, stage_branch):
        typer.echo(f"Stage branch already exists on {remote}: {stage_branch}", err=True)
        raise typer.Exit(code=2)


def _resolve_start_ref(explicit_ref: str | None, upstream_remote: str) -> tuple[str, str]:
    candidates = [explicit_ref.strip()] if explicit_ref else [
        f"{upstream_remote}/main",
        f"{upstream_remote}/master",
        "main",
        "master",
    ]
    for ref in candidates:
        try:
            sha = run_git(rev_parse_args(ref))
            return ref, sha
        except Exception:  # noqa: BLE001
            continue
    typer.echo(
        "Could not resolve a starting ref. Pass `--from <ref>` or ensure your upstream main/master exists.",
        err=True,
    )
    raise typer.Exit(code=1)


def _print_topology(branch: str, start_ref: str) -> None:
    stage_branch = stage_branch_name(branch)
    print_json(
        {
            "working_branch": branch,
            "stage_branch": stage_branch,
            "started_from": start_ref,
            "pr_flow": f"{branch} -> {stage_branch}",
        }
    )


def _open_pr_for_branch(config: Any, branch: str) -> dict[str, Any] | None:
    client = forgejo_client(config)
    try:
        pulls = client.list_pulls(config.forgejo.owner, config.forgejo.repo, head=f"{config.forgejo.owner}:{branch}")
    except ForgejoError as exc:
        typer.echo(f"Forgejo request failed: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    if not pulls:
        return None
    return pulls[0]


@app.command("start", help="Create a new task branch and its remote Joan stage branch.")
def task_start(
    branch_name: str = typer.Argument(..., help="New working branch name to create."),
    from_ref: str | None = typer.Option(None, "--from", help="Optional starting ref. Defaults to upstream/main or upstream/master."),
) -> None:
    config = load_config_or_exit()
    branch_name = branch_name.strip()
    if not branch_name:
        typer.echo("Branch name cannot be empty.", err=True)
        raise typer.Exit(code=2)
    _ensure_allowed_task_branch(branch_name)
    _ensure_local_branch_missing(branch_name)
    _ensure_stage_missing(config.remotes.review, branch_name)

    start_ref, start_sha = _resolve_start_ref(from_ref, config.remotes.upstream)

    run_git(create_branch_args(branch_name, start_ref))
    run_git(push_refspec_args(config.remotes.review, start_sha, f"refs/heads/{stage_branch_name(branch_name)}"))
    run_git(push_branch_args(config.remotes.review, branch_name, set_upstream=True))
    _print_topology(branch_name, start_ref)


@app.command("track", help="Create a Joan stage branch for an existing local working branch.")
def task_track(
    from_ref: str = typer.Option(..., "--from", help="Git ref that should seed the new stage branch."),
    branch: str | None = typer.Option(None, "--branch", help="Existing local branch to track. Defaults to the current branch."),
) -> None:
    config = load_config_or_exit()
    target_branch = (branch or run_git(current_branch_args())).strip()
    if not target_branch:
        typer.echo("Branch cannot be empty.", err=True)
        raise typer.Exit(code=2)
    _ensure_allowed_task_branch(target_branch)
    _ensure_local_branch_exists(target_branch)
    _ensure_stage_missing(config.remotes.review, target_branch)

    start_ref, start_sha = _resolve_start_ref(from_ref, config.remotes.upstream)

    run_git(push_refspec_args(config.remotes.review, start_sha, f"refs/heads/{stage_branch_name(target_branch)}"))
    run_git(push_branch_args(config.remotes.review, target_branch, set_upstream=True))
    _print_topology(target_branch, start_ref)


@app.command("status", help="Show the current task branch, its stage branch, and any open PR.")
def task_status(
    branch: str | None = typer.Option(None, "--branch", help="Working branch to inspect. Defaults to the current branch."),
) -> None:
    config = load_config_or_exit()
    target_branch = (branch or current_branch()).strip()
    if not target_branch:
        typer.echo("Branch cannot be empty.", err=True)
        raise typer.Exit(code=2)

    open_pr = _open_pr_for_branch(config, target_branch)
    print_json(
        {
            "working_branch": target_branch,
            "stage_branch": stage_branch_name(target_branch),
            "stage_branch_exists": _branch_exists_on_remote(config.remotes.review, stage_branch_name(target_branch)),
            "review_remote_branch_exists": _branch_exists_on_remote(config.remotes.review, target_branch),
            "open_pr_number": None if open_pr is None else open_pr.get("number"),
            "open_pr_url": None if open_pr is None else open_pr.get("html_url"),
        }
    )


@app.command("push", help="Push the current working task branch to the Joan review remote.")
def task_push() -> None:
    config = load_config_or_exit()
    branch = current_branch()
    _ensure_allowed_task_branch(branch)
    run_git(push_branch_args(config.remotes.review, branch, set_upstream=True))
    typer.echo(f"Pushed task branch: {branch}")
