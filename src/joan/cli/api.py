from __future__ import annotations

import json
from typing import Optional

import typer

from joan.cli._common import forgejo_client, load_config_or_exit


def api_command(
    method_or_subcommand: str = typer.Argument(
        ...,
        help="HTTP method (GET/POST/...) or the literal subcommand `swagger`.",
    ),
    path: str | None = typer.Argument(
        None,
        help=(
            "API path for raw requests. Optional when using `swagger`. "
            "Placeholders {owner} and {repo} are auto-filled from config."
        ),
    ),
    data: Optional[str] = typer.Option(None, "--data", "-d", help="JSON request body."),
    query: Optional[list[str]] = typer.Option(None, "--query", "-q", help="Query params as key=value. Repeatable."),
) -> None:
    """Send raw API requests, or fetch Swagger/OpenAPI JSON for agents."""
    verb = method_or_subcommand.strip()
    if not verb:
        typer.echo("METHOD cannot be empty.", err=True)
        raise typer.Exit(code=2)

    if verb.lower() == "swagger":
        _api_swagger(path)
        return

    if path is None:
        typer.echo("PATH is required for raw API requests.", err=True)
        raise typer.Exit(code=2)
    _send_api_request(verb, path, data, query)


def _send_api_request(method: str, path: str, data: str | None, query: list[str] | None) -> None:
    config = load_config_or_exit()
    client = forgejo_client(config)

    resolved_path = path.replace("{owner}", config.forgejo.owner).replace("{repo}", config.forgejo.repo)
    if not resolved_path.startswith("/"):
        resolved_path = f"/{resolved_path}"

    json_body = None
    if data:
        try:
            json_body = json.loads(data)
        except json.JSONDecodeError as exc:
            typer.echo(f"Invalid JSON in --data: {exc}", err=True)
            raise typer.Exit(code=2) from exc

    params = None
    if query:
        params = {}
        for item in query:
            if "=" not in item:
                typer.echo(f"Invalid query param (expected key=value): {item}", err=True)
                raise typer.Exit(code=2)
            key, value = item.split("=", 1)
            params[key] = value

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
        raise typer.Exit(code=1) from exc

    if not response.is_success:
        typer.echo(f"HTTP {response.status_code}", err=True)

    body = response.text.strip()
    if body:
        try:
            parsed = json.loads(body)
            typer.echo(json.dumps(parsed, indent=2))
        except json.JSONDecodeError:
            typer.echo(body)

    if not response.is_success:
        raise typer.Exit(code=1)


def _api_swagger(path: str | None) -> None:
    config = load_config_or_exit()
    client = forgejo_client(config)

    candidates = [path] if path else ["/swagger.v1.json", "/api/v1/swagger", "/api/swagger"]
    errors: list[str] = []
    for candidate in candidates:
        resolved = candidate if candidate.startswith("/") else f"/{candidate}"
        try:
            response = client._request_raw("GET", resolved)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{resolved}: request failed ({exc})")
            continue
        if not response.is_success:
            errors.append(f"{resolved}: HTTP {response.status_code}")
            continue
        body = response.text.strip()
        if not body:
            errors.append(f"{resolved}: empty response body")
            continue
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            errors.append(f"{resolved}: response was not JSON")
            continue
        typer.echo(json.dumps(parsed, indent=2))
        return

    typer.echo("Unable to fetch a JSON swagger document from known endpoints:", err=True)
    for item in errors:
        typer.echo(f"- {item}", err=True)
    raise typer.Exit(code=1)
