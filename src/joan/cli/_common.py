from __future__ import annotations

import json
from pathlib import Path

import typer

from joan.core.branch_state import BranchState, load_branch_state, save_branch_start
from joan.core.forgejo import parse_pr_response
from joan.core.git import merge_base_args
from joan.core.models import Config, PullRequest
from joan.shell.agent_config_io import read_agent_config
from joan.shell.config_io import read_config
from joan.shell.forgejo_client import ForgejoClient, ForgejoError
from joan.shell.git_runner import run_git


def load_config_or_exit() -> Config:
    try:
        return read_config(Path.cwd())
    except FileNotFoundError:
        typer.echo("Missing .joan/config.toml. Run `joan init` first.", err=True)
        raise typer.Exit(code=2)
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"Failed to read config: {exc}", err=True)
        raise typer.Exit(code=2)


def forgejo_client(config: Config) -> ForgejoClient:
    return ForgejoClient(config.forgejo.url, config.forgejo.token)


def forgejo_client_for_agent_or_exit(config: Config, agent_name: str) -> ForgejoClient:
    try:
        agent_config = read_agent_config(agent_name, Path.cwd())
    except FileNotFoundError:
        typer.echo(f"Missing .joan/agents/{agent_name}.toml. Run `joan phil init` first.", err=True)
        raise typer.Exit(code=2)
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"Failed to read agent config '{agent_name}': {exc}", err=True)
        raise typer.Exit(code=2)
    return ForgejoClient(config.forgejo.url, agent_config.forgejo.token)


def current_branch() -> str:
    try:
        return run_git(["rev-parse", "--abbrev-ref", "HEAD"])
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"Failed to read current branch: {exc}", err=True)
        raise typer.Exit(code=2)


def ensure_branch_tracking(config: Config, branch: str) -> BranchState:
    state = load_branch_state(branch)
    if state.branch_start_sha or state.review_checkpoint_sha:
        return state

    candidates = [
        f"{config.remotes.upstream}/main",
        f"{config.remotes.upstream}/master",
        f"{config.remotes.upstream}/HEAD",
        "main",
        "master",
    ]
    for ref in candidates:
        try:
            branch_start_sha = run_git(merge_base_args(ref, "HEAD"))
            save_branch_start(branch, branch_start_sha)
            return BranchState(branch_start_sha=branch_start_sha)
        except Exception:  # noqa: BLE001
            continue

    typer.echo(
        "Could not determine branch start SHA. Ensure you have fetched from upstream, "
        "or create a `.joan/branch-state.json` entry manually.",
        err=True,
    )
    raise typer.Exit(code=1)


def current_pr_or_exit(
    config: Config,
    pr_number: int | None = None,
    branch: str | None = None,
) -> PullRequest:
    client = forgejo_client(config)
    if pr_number is not None:
        try:
            pr_raw = client.get_pr(config.forgejo.owner, config.forgejo.repo, pr_number)
        except ForgejoError as exc:
            if "Forgejo API 404" in str(exc):
                typer.echo(f"Pull request #{pr_number} was not found.", err=True)
                raise typer.Exit(code=1)
            typer.echo(f"Forgejo request failed: {exc}", err=True)
            raise typer.Exit(code=2)
        return parse_pr_response(pr_raw)

    resolved_branch = branch or current_branch()
    try:
        pulls = client.list_pulls(config.forgejo.owner, config.forgejo.repo, head=f"{config.forgejo.owner}:{resolved_branch}")
    except ForgejoError as exc:
        if "Forgejo API 404" in str(exc):
            typer.echo(
                "Forgejo repo not found or token cannot access it. "
                f"Check .joan/config.toml owner/repo ('{config.forgejo.owner}/{config.forgejo.repo}') "
                "and run `uv run joan remote add` if needed.",
                err=True,
            )
            raise typer.Exit(code=2)
        typer.echo(f"Forgejo request failed: {exc}", err=True)
        raise typer.Exit(code=2)
    if not pulls:
        typer.echo(f"No open PR found for branch '{resolved_branch}'.", err=True)
        raise typer.Exit(code=1)
    return parse_pr_response(pulls[0])


def print_json(data: object) -> None:
    typer.echo(json.dumps(data, indent=2))
