from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import typer

from joan.core.models import Config, ForgejoConfig, RemotesConfig
from joan.shell.config_io import write_config
from joan.shell.forgejo_client import ForgejoClient

app = typer.Typer(help="Initialize Joan in the current repository.")


@app.command("init")
def init_command() -> None:
    default_url = "http://localhost:3000"
    forgejo_url = typer.prompt("Forgejo URL", default=default_url).strip().rstrip("/")
    username = typer.prompt("Forgejo username").strip()
    password = typer.prompt("Forgejo password", hide_input=True)

    token_name = f"joan-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"
    client = ForgejoClient(forgejo_url)
    token = client.create_token(username=username, password=password, token_name=token_name)

    default_repo = Path.cwd().name
    owner = typer.prompt("Forgejo owner", default=username).strip()
    repo = typer.prompt("Forgejo repo", default=default_repo).strip()

    config = Config(
        forgejo=ForgejoConfig(url=forgejo_url, token=token, owner=owner, repo=repo),
        remotes=RemotesConfig(review="joan-review", upstream="origin"),
    )
    path = write_config(config, Path.cwd())
    typer.echo(f"Wrote config: {path}")
    typer.echo("Next step: run `joan remote add`.")
