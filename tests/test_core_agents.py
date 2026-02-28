from __future__ import annotations

from pathlib import Path

import pytest

from joan.core.agents import AgentConfigError, parse_agent_config
from joan.core.models import AgentClaudeConfig, AgentConfig, AgentForgejoConfig, AgentServerConfig, AgentWorkerConfig
from joan.shell.agent_config_io import agent_config_path, read_agent_config, write_agent_config


def test_parse_agent_config_valid() -> None:
    raw = """
[forgejo]
token = "phil-token-abc"

[server]
port = 9001
host = "127.0.0.1"
webhook_secret = "s3cr3t"

[claude]
model = "claude-sonnet-4-6"

[worker]
enabled = true
api_url = "http://127.0.0.1:9001"
poll_interval_seconds = 1.5
timeout_seconds = 42
command = ["claude"]
"""
    config = parse_agent_config(raw, "phil")

    assert config.name == "phil"
    assert config.forgejo.token == "phil-token-abc"
    assert config.server.port == 9001
    assert config.server.host == "127.0.0.1"
    assert config.server.webhook_secret == "s3cr3t"
    assert config.claude.model == "claude-sonnet-4-6"
    assert config.worker.enabled is True
    assert config.worker.api_url == "http://127.0.0.1:9001"
    assert config.worker.command == ["claude"]


def test_parse_agent_config_defaults() -> None:
    raw = """
[forgejo]
token = "tok"
"""
    config = parse_agent_config(raw, "phil")

    assert config.server.port == 9000
    assert config.server.host == "0.0.0.0"
    assert config.server.webhook_secret == ""
    assert config.claude.model == "claude-sonnet-4-6"
    assert config.worker.enabled is False
    assert config.worker.api_url == ""
    assert config.worker.poll_interval_seconds == 2.0
    assert config.worker.timeout_seconds == 600.0
    assert config.worker.command == ["codex"]


def test_parse_agent_config_missing_forgejo() -> None:
    with pytest.raises(AgentConfigError, match=r"missing \[forgejo\] section"):
        parse_agent_config("[server]\nport = 9000\n", "phil")


def test_parse_agent_config_empty_token() -> None:
    raw = '[forgejo]\ntoken = ""\n'
    with pytest.raises(AgentConfigError, match="forgejo.token"):
        parse_agent_config(raw, "phil")


def test_parse_agent_config_invalid_toml() -> None:
    with pytest.raises(AgentConfigError, match="invalid TOML"):
        parse_agent_config("[forgejo", "phil")


def test_parse_agent_config_invalid_worker_command() -> None:
    raw = """
[forgejo]
token = "tok"

[worker]
command = "codex"
"""
    with pytest.raises(AgentConfigError, match="worker.command"):
        parse_agent_config(raw, "phil")


def test_agent_config_path(tmp_path: Path) -> None:
    path = agent_config_path("phil", tmp_path)
    assert path == tmp_path / ".joan" / "agents" / "phil.toml"


def test_write_and_read_agent_config(tmp_path: Path) -> None:
    config = AgentConfig(
        name="phil",
        forgejo=AgentForgejoConfig(token="my-token"),
        server=AgentServerConfig(port=9001, host="127.0.0.1", webhook_secret="s3cr3t"),
        claude=AgentClaudeConfig(model="claude-sonnet-4-6"),
        worker=AgentWorkerConfig(
            enabled=True,
            api_url="http://127.0.0.1:9001",
            poll_interval_seconds=1.5,
            timeout_seconds=45.0,
            command=["codex"],
        ),
    )
    write_agent_config(config, "phil", tmp_path)

    loaded = read_agent_config("phil", tmp_path)
    assert loaded.forgejo.token == "my-token"
    assert loaded.server.port == 9001
    assert loaded.server.webhook_secret == "s3cr3t"
    assert loaded.worker.enabled is True
    assert loaded.worker.api_url == "http://127.0.0.1:9001"
    assert loaded.worker.command == ["codex"]


def test_read_agent_config_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        read_agent_config("phil", tmp_path)
