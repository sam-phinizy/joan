from __future__ import annotations

from urllib.parse import urlparse, urlunparse

import typer

from joan.cli._common import load_config_or_exit
from joan.core.forgejo import build_create_repo_payload
from joan.core.git import (
    current_branch_args,
    list_remotes_args,
    push_branch_args,
    remote_add_args,
    remote_set_url_args,
)
from joan.shell.forgejo_client import ForgejoError
from joan.shell.git_runner import run_git

app = typer.Typer(help="Manage Joan remotes.")


@app.command("add")
def remote_add() -> None:
    config = load_config_or_exit()

    from joan.cli._common import forgejo_client

    client = forgejo_client(config)
    payload = build_create_repo_payload(config.forgejo.repo, private=True)
    try:
        repo_data = client.create_repo(name=payload["name"], private=payload["private"])
    except ForgejoError as exc:
        if "already exists" not in str(exc).lower():
            raise
        repo_data = {}

    clone_url = str(repo_data.get("clone_url") or "")
    if not clone_url:
        clone_url = f"{config.forgejo.url}/{config.forgejo.owner}/{config.forgejo.repo}.git"

    parsed = urlparse(clone_url)
    auth_clone_url = urlunparse(
        parsed._replace(netloc=f"{config.forgejo.owner}:{config.forgejo.token}@{parsed.netloc}")
    )

    remotes = set(run_git(list_remotes_args()).splitlines())
    if config.remotes.review in remotes:
        run_git(remote_set_url_args(config.remotes.review, auth_clone_url))
        typer.echo(f"Updated remote {config.remotes.review} -> {clone_url}")
    else:
        run_git(remote_add_args(config.remotes.review, auth_clone_url))
        typer.echo(f"Added remote {config.remotes.review} -> {clone_url}")

    branch = run_git(current_branch_args())
    run_git(push_branch_args(config.remotes.review, branch, set_upstream=True))
    typer.echo(f"Pushed {branch} to {config.remotes.review}")
