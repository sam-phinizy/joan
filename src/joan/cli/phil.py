from __future__ import annotations

import secrets
import string
import threading
from datetime import UTC, datetime
from pathlib import Path

import typer

from joan.core.models import AgentClaudeConfig, AgentConfig, AgentForgejoConfig, AgentServerConfig, AgentWorkerConfig, Config
from joan.phil.worker import PTYAgentRunner, run_worker_loop
from joan.shell.agent_config_io import read_agent_config, write_agent_config
from joan.shell.config_io import read_config
from joan.shell.forgejo_client import ForgejoClient, ForgejoError

app = typer.Typer(help="Manage Phil, the local AI reviewer that reacts to Forgejo review requests.")

_PHIL_USERNAME = "phil"


def _generate_password(length: int = 32) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _repo_root() -> Path:
    return Path.cwd()


def _normalize_local_host(host: str) -> str:
    if host in {"0.0.0.0", "::", ""}:
        return "127.0.0.1"
    return host


def _worker_api_url(host: str, port: int) -> str:
    return f"http://{_normalize_local_host(host)}:{port}"


def _default_webhook_url(port: int) -> str:
    return f"http://host.docker.internal:{port}/webhook"


def _load_configs() -> tuple[Config, AgentConfig]:
    try:
        joan_config = read_config(_repo_root())
    except FileNotFoundError:
        typer.echo("Missing .joan/config.toml. Run `joan init` first.", err=True)
        raise typer.Exit(code=2)

    try:
        phil_config = read_agent_config(_PHIL_USERNAME, _repo_root())
    except FileNotFoundError:
        typer.echo("Missing .joan/agents/phil.toml. Run `joan phil init` first.", err=True)
        raise typer.Exit(code=2)

    return joan_config, phil_config


@app.command("init", help="Create/reuse the `phil` Forgejo account, write `.joan/agents/phil.toml`, and try to add a webhook.")
def phil_init() -> None:
    default_url = "http://localhost:3000"
    forgejo_url = typer.prompt("Forgejo URL", default=default_url).strip().rstrip("/")
    admin_username = typer.prompt("Forgejo admin username").strip()
    admin_password = typer.prompt("Forgejo admin password", hide_input=True)

    client = ForgejoClient(forgejo_url)

    try:
        client.create_user(
            admin_username=admin_username,
            admin_password=admin_password,
            username=_PHIL_USERNAME,
            email="phil@localhost",
            password=_generate_password(),
        )
        typer.echo(f"Created Forgejo user '{_PHIL_USERNAME}'.")
    except ForgejoError as exc:
        if "already exists" not in str(exc).lower():
            raise
        typer.echo(f"Using existing Forgejo user '{_PHIL_USERNAME}'.")

    token_name = f"phil-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"
    token = client.create_token(
        username=_PHIL_USERNAME,
        password=admin_password,
        token_name=token_name,
        auth_username=admin_username,
    )

    config = AgentConfig(
        name=_PHIL_USERNAME,
        forgejo=AgentForgejoConfig(token=token),
        server=AgentServerConfig(port=9000, host="0.0.0.0", webhook_secret=secrets.token_hex(16)),
        claude=AgentClaudeConfig(model="claude-sonnet-4-6"),
        worker=AgentWorkerConfig(
            enabled=True,
            api_url=_worker_api_url("127.0.0.1", 9000),
            poll_interval_seconds=2.0,
            timeout_seconds=600.0,
            command=["codex"],
        ),
    )
    path = write_agent_config(config, _PHIL_USERNAME, _repo_root())
    typer.echo(f"Wrote config: {path}")

    # Attempt to auto-create the webhook using joan config for owner/repo.
    try:
        joan_config = read_config(_repo_root())
        default_webhook_url = _default_webhook_url(config.server.port)
        webhook_url = typer.prompt("Webhook URL", default=default_webhook_url).strip()
        client.create_webhook(
            admin_username=admin_username,
            admin_password=admin_password,
            owner=joan_config.forgejo.owner,
            repo=joan_config.forgejo.repo,
            webhook_url=webhook_url,
            secret=config.server.webhook_secret,
        )
        typer.echo(f"Created webhook pointing to {webhook_url}")
    except FileNotFoundError:
        typer.echo(
            "Next step: In Forgejo, add a webhook to your repo pointing to "
            f"{_default_webhook_url(config.server.port)} "
            "(or another host-reachable address) "
            "with the secret from your config file."
        )


@app.command("serve", help="Run only Phil's webhook server. Use this when a worker is running separately.")
def phil_serve(
    port: int | None = typer.Option(None, "--port", help="Server port. Defaults to the value in `.joan/agents/phil.toml`."),
    host: str | None = typer.Option(None, "--host", help="Server bind host. Defaults to the value in `.joan/agents/phil.toml`."),
) -> None:
    import uvicorn

    from joan.phil.server import create_app

    joan_config, phil_config = _load_configs()
    effective_port = port or phil_config.server.port
    effective_host = host or phil_config.server.host

    typer.echo(f"Starting phil server on {effective_host}:{effective_port}")
    app_instance = create_app(joan_config, phil_config)
    uvicorn.run(app_instance, host=effective_host, port=effective_port)


@app.command("work", help="Run only Phil's worker loop. Use this when the webhook server is already running.")
def phil_work(
    api_url: str | None = typer.Option(None, "--api-url", help="Worker API base URL. Defaults to the configured local Phil server."),
    poll_interval: float | None = typer.Option(None, "--poll-interval", help="Seconds between queue polls. Defaults to config."),
    timeout: float | None = typer.Option(None, "--timeout", help="Maximum seconds per review job. Defaults to config."),
) -> None:
    _joan_config, phil_config = _load_configs()
    effective_api_url = api_url or phil_config.worker.api_url or _worker_api_url(phil_config.server.host, phil_config.server.port)
    effective_poll_interval = poll_interval or phil_config.worker.poll_interval_seconds
    effective_timeout = timeout or phil_config.worker.timeout_seconds

    typer.echo(f"Starting phil worker against {effective_api_url}")
    runner = PTYAgentRunner(phil_config.worker.command, effective_timeout, _repo_root())
    run_worker_loop(effective_api_url, runner, effective_poll_interval)


@app.command("up", help="Run the Phil webhook server and one local worker together in a single process.")
def phil_up(
    port: int | None = typer.Option(None, "--port", help="Server port. Defaults to the value in `.joan/agents/phil.toml`."),
    host: str | None = typer.Option(None, "--host", help="Server bind host. Defaults to the value in `.joan/agents/phil.toml`."),
    api_url: str | None = typer.Option(None, "--api-url", help="Worker API base URL. Defaults to the local Phil server started by this command."),
    poll_interval: float | None = typer.Option(None, "--poll-interval", help="Seconds between worker queue polls. Defaults to config."),
    timeout: float | None = typer.Option(None, "--timeout", help="Maximum seconds per review job. Defaults to config."),
) -> None:
    import uvicorn

    from joan.phil.server import create_app

    joan_config, phil_config = _load_configs()
    effective_port = port or phil_config.server.port
    effective_host = host or phil_config.server.host
    effective_api_url = api_url or _worker_api_url("127.0.0.1", effective_port)
    effective_poll_interval = poll_interval or phil_config.worker.poll_interval_seconds
    effective_timeout = timeout or phil_config.worker.timeout_seconds

    stop_event = threading.Event()
    runner = PTYAgentRunner(phil_config.worker.command, effective_timeout, _repo_root())
    worker_thread = threading.Thread(
        target=run_worker_loop,
        args=(effective_api_url, runner, effective_poll_interval, stop_event),
        daemon=True,
        name="phil-worker",
    )
    worker_thread.start()

    typer.echo(f"Starting phil up on {effective_host}:{effective_port}")
    typer.echo(f"Worker polling {effective_api_url}")
    app_instance = create_app(joan_config, phil_config, worker_mode=True)
    try:
        uvicorn.run(app_instance, host=effective_host, port=effective_port)
    finally:
        stop_event.set()
        worker_thread.join(timeout=5)
