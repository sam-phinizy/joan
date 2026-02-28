from __future__ import annotations

from pathlib import Path

import tomli_w

from joan.core.agents import agent_config_to_dict, parse_agent_config
from joan.core.models import AgentConfig


def agent_config_path(name: str, repo_root: Path | None = None) -> Path:
    root = repo_root or Path.cwd()
    return root / ".joan" / "agents" / f"{name}.toml"


def read_agent_config(name: str, repo_root: Path | None = None) -> AgentConfig:
    path = agent_config_path(name, repo_root)
    if not path.exists():
        raise FileNotFoundError(f"agent config not found: {path}")
    raw = path.read_text(encoding="utf-8")
    return parse_agent_config(raw, name)


def write_agent_config(config: AgentConfig, name: str, repo_root: Path | None = None) -> Path:
    path = agent_config_path(name, repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = agent_config_to_dict(config)
    path.write_text(tomli_w.dumps(data), encoding="utf-8")
    return path
