from __future__ import annotations

from pathlib import Path

import tomli_w

from joan.core.agents import agent_config_to_dict, parse_agent_config
from joan.core.models import AgentConfig
from joan.shell.repo_state import repo_state_candidates, repo_state_dir, repo_state_write_lock


def agent_config_path(name: str, repo_root: Path | None = None, *, for_write: bool = False) -> Path:
    return repo_state_dir(repo_root, for_write=for_write) / "agents" / f"{name}.toml"


def _agent_config_candidates(name: str, repo_root: Path | None = None) -> list[Path]:
    return [state_dir / "agents" / f"{name}.toml" for state_dir in repo_state_candidates(repo_root)]


def read_agent_config(name: str, repo_root: Path | None = None) -> AgentConfig:
    candidates = _agent_config_candidates(name, repo_root)
    for path in candidates:
        if path.exists():
            raw = path.read_text(encoding="utf-8")
            return parse_agent_config(raw, name)
    raise FileNotFoundError(f"agent config not found: {candidates[0]}")


def write_agent_config(config: AgentConfig, name: str, repo_root: Path | None = None) -> Path:
    path = agent_config_path(name, repo_root, for_write=True)
    with repo_state_write_lock(repo_root):
        path.parent.mkdir(parents=True, exist_ok=True)
        data = agent_config_to_dict(config)
        path.write_text(tomli_w.dumps(data), encoding="utf-8")
    return path
