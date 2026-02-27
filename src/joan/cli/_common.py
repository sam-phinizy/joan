from __future__ import annotations

import json
from pathlib import Path

import typer

from joan.core.forgejo import parse_pr_response
from joan.core.models import Config, PullRequest
from joan.shell.config_io import read_config
from joan.shell.forgejo_client import ForgejoClient
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


def current_branch() -> str:
    try:
        return run_git(["rev-parse", "--abbrev-ref", "HEAD"])
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"Failed to read current branch: {exc}", err=True)
        raise typer.Exit(code=2)


def current_pr_or_exit(config: Config) -> PullRequest:
    branch = current_branch()
    client = forgejo_client(config)
    pulls = client.list_pulls(config.forgejo.owner, config.forgejo.repo, head=f"{config.forgejo.owner}:{branch}")
    if not pulls:
        typer.echo(f"No open PR found for branch '{branch}'.", err=True)
        raise typer.Exit(code=1)
    return parse_pr_response(pulls[0])


def print_json(data: object) -> None:
    typer.echo(json.dumps(data, indent=2))
