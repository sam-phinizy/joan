from __future__ import annotations

import tomllib

from joan.core.models import (
    AgentClaudeConfig,
    AgentConfig,
    AgentForgejoConfig,
    AgentServerConfig,
    AgentWorkerConfig,
    default_worker_command,
)


class AgentConfigError(ValueError):
    pass


def parse_agent_config(raw_toml: str, name: str) -> AgentConfig:
    try:
        data = tomllib.loads(raw_toml)
    except tomllib.TOMLDecodeError as exc:
        raise AgentConfigError(f"invalid TOML in agent config: {exc}") from exc

    forgejo_data = data.get("forgejo")
    if not isinstance(forgejo_data, dict):
        raise AgentConfigError("missing [forgejo] section")

    token = forgejo_data.get("token")
    if not isinstance(token, str) or not token.strip():
        raise AgentConfigError("forgejo.token is required and must be a non-empty string")

    server_data = data.get("server", {})
    if server_data is None:
        server_data = {}
    if not isinstance(server_data, dict):
        raise AgentConfigError("[server] must be a table")
    server = AgentServerConfig(
        port=int(server_data.get("port", 9000)),
        host=str(server_data.get("host", "0.0.0.0")),
        webhook_secret=str(server_data.get("webhook_secret", "")),
    )

    claude_data = data.get("claude", {})
    if claude_data is None:
        claude_data = {}
    if not isinstance(claude_data, dict):
        raise AgentConfigError("[claude] must be a table")
    claude = AgentClaudeConfig(
        model=str(claude_data.get("model", "claude-sonnet-4-6")),
    )

    worker_data = data.get("worker", {})
    if worker_data is None:
        worker_data = {}
    if not isinstance(worker_data, dict):
        raise AgentConfigError("[worker] must be a table")

    raw_command = worker_data.get("command", default_worker_command())
    if not isinstance(raw_command, list) or not raw_command or not all(isinstance(part, str) for part in raw_command):
        raise AgentConfigError("worker.command must be a non-empty array of strings")

    worker = AgentWorkerConfig(
        enabled=bool(worker_data.get("enabled", False)),
        api_url=str(worker_data.get("api_url", "")),
        poll_interval_seconds=float(worker_data.get("poll_interval_seconds", 2.0)),
        timeout_seconds=float(worker_data.get("timeout_seconds", 600.0)),
        command=list(raw_command),
    )

    return AgentConfig(
        name=name,
        forgejo=AgentForgejoConfig(token=token.strip()),
        server=server,
        claude=claude,
        worker=worker,
    )


def agent_config_to_dict(config: AgentConfig) -> dict:
    return {
        "forgejo": {"token": config.forgejo.token},
        "server": {
            "port": config.server.port,
            "host": config.server.host,
            "webhook_secret": config.server.webhook_secret,
        },
        "claude": {"model": config.claude.model},
        "worker": {
            "enabled": config.worker.enabled,
            "api_url": config.worker.api_url,
            "poll_interval_seconds": config.worker.poll_interval_seconds,
            "timeout_seconds": config.worker.timeout_seconds,
            "command": config.worker.command,
        },
    }
