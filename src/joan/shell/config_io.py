from __future__ import annotations

from pathlib import Path

import tomli_w

from joan.core.config import config_to_dict, parse_config
from joan.core.models import Config


def config_path(repo_root: Path | None = None) -> Path:
    root = repo_root or Path.cwd()
    return root / ".joan" / "config.toml"


def read_config(repo_root: Path | None = None) -> Config:
    path = config_path(repo_root)
    if not path.exists():
        raise FileNotFoundError(f"config not found: {path}")
    raw = path.read_text(encoding="utf-8")
    return parse_config(raw)


def write_config(config: Config, repo_root: Path | None = None) -> Path:
    path = config_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = config_to_dict(config)
    path.write_text(tomli_w.dumps(data), encoding="utf-8")
    return path
