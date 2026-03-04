from __future__ import annotations

import json
from typing import Optional

import typer

from joan.cli._common import forgejo_client, load_config_or_exit

app = typer.Typer(help="Send raw API requests to the local Forgejo instance.")


@app.callback(invoke_without_command=True)
def api_call(
    method: str = typer.Argument(help="HTTP method: GET, POST, PUT, PATCH, DELETE."),
    path: str = typer.Argument(help="API path, e.g. /api/v1/repos/{owner}/{repo}/pulls. Placeholders {owner} and {repo} are auto-filled from config."),
    data: Optional[str] = typer.Option(None, "--data", "-d", help="JSON request body."),
    query: Optional[list[str]] = typer.Option(None, "--query", "-q", help="Query params as key=value. Repeatable."),
) -> None:
    """Send a raw API request to the Forgejo instance.

    Automatically authenticates using the token from .joan/config.toml.
    Placeholders {owner} and {repo} in PATH are replaced with config values.

    Examples:

        joan api GET /api/v1/repos/{owner}/{repo}/pulls

        joan api POST /api/v1/repos/{owner}/{repo}/issues -d '{"title":"test"}'

        joan api GET /api/v1/repos/{owner}/{repo}/pulls -q state=closed -q limit=5
    """
    config = load_config_or_exit()
    client = forgejo_client(config)

    # Expand {owner} and {repo} placeholders
    resolved_path = path.replace("{owner}", config.forgejo.owner).replace("{repo}", config.forgejo.repo)

    # Ensure path starts with /
    if not resolved_path.startswith("/"):
        resolved_path = f"/{resolved_path}"

    # Parse JSON body
    json_body = None
    if data:
        try:
            json_body = json.loads(data)
        except json.JSONDecodeError as exc:
            typer.echo(f"Invalid JSON in --data: {exc}", err=True)
            raise typer.Exit(code=2)

    # Parse query params
    params = None
    if query:
        params = {}
        for item in query:
            if "=" not in item:
                typer.echo(f"Invalid query param (expected key=value): {item}", err=True)
                raise typer.Exit(code=2)
            key, value = item.split("=", 1)
            params[key] = value

    # Build kwargs
    kwargs: dict = {}
    if json_body is not None:
        kwargs["json"] = json_body
    if params:
        kwargs["params"] = params

    method_upper = method.upper()
    if method_upper not in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}:
        typer.echo(f"Unsupported HTTP method: {method}", err=True)
        raise typer.Exit(code=2)

    try:
        response = client._request_raw(method_upper, resolved_path, **kwargs)
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"Request failed: {exc}", err=True)
        raise typer.Exit(code=1)

    # Print status and body
    if not response.is_success:
        typer.echo(f"HTTP {response.status_code}", err=True)

    body = response.text.strip()
    if body:
        # Try to pretty-print JSON
        try:
            parsed = json.loads(body)
            typer.echo(json.dumps(parsed, indent=2))
        except json.JSONDecodeError:
            typer.echo(body)

    if not response.is_success:
        raise typer.Exit(code=1)
