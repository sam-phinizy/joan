from __future__ import annotations

import secrets
import string
from datetime import UTC, datetime
from pathlib import Path

import typer

from joan.core.models import GlobalConfig, RemotesConfig, RepoConfig
from joan.shell.config_io import (
    global_config_path,
    read_global_config,
    write_global_config,
    write_repo_config,
)
from joan.shell.forgejo_client import ForgejoClient, ForgejoError

app = typer.Typer(
    help="Initialize Joan in this repository by creating/reusing the `joan` Forgejo account and writing `.joan/config.toml`."
)

_JOAN_USERNAME = "joan"


def _generate_password(length: int = 32) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


@app.command("init", help="Interactive setup for this repo's local Forgejo review flow.")
def init_command() -> None:
    global_cfg = read_global_config()

    # Phase 1: Global setup (skipped if ~/.joan/config.toml already exists)
    if global_cfg is None:
        default_url = "http://localhost:3000"
        forgejo_url = typer.prompt("Forgejo URL", default=default_url).strip().rstrip("/")
        admin_username = typer.prompt("Forgejo admin username").strip()
        admin_password = typer.prompt("Forgejo admin password", hide_input=True)

        client = ForgejoClient(forgejo_url)

        try:
            client.create_user(
                admin_username=admin_username,
                admin_password=admin_password,
                username=_JOAN_USERNAME,
                email="joan@localhost",
                password=_generate_password(),
            )
            typer.echo(f"Created Forgejo user '{_JOAN_USERNAME}'.")
        except ForgejoError as exc:
            if "already exists" not in str(exc).lower():
                raise
            typer.echo(f"Using existing Forgejo user '{_JOAN_USERNAME}'.")

        token_name = f"joan-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"
        token = client.create_token(
            username=_JOAN_USERNAME,
            password=admin_password,
            token_name=token_name,
            auth_username=admin_username,
        )

        global_cfg = GlobalConfig(
            url=forgejo_url,
            token=token,
            owner=_JOAN_USERNAME,
            human_user=admin_username,
            remotes=RemotesConfig(review="joan-review", upstream="origin"),
        )
        global_path = write_global_config(global_cfg)
        typer.echo(f"Global config written to {global_path}")
    else:
        typer.echo(f"Using existing global config from {global_config_path()}")

    # Phase 2: Per-repo setup (always runs)
    default_repo = Path.cwd().name
    repo = typer.prompt("Forgejo repo", default=default_repo).strip()

    repo_cfg = RepoConfig(repo=repo)
    path = write_repo_config(repo_cfg, Path.cwd())
    typer.echo(f"Wrote config: {path}")
    typer.echo("Next step: run `joan remote add`.")
