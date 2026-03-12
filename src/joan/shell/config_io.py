from __future__ import annotations

from pathlib import Path

import tomli_w

from joan.core.config import (
    config_to_dict,
    global_config_to_dict,
    merge_config,
    parse_config,
    parse_global_config,
    parse_repo_config,
    repo_config_to_dict,
)
from joan.core.models import Config, GlobalConfig, RepoConfig
from joan.shell.repo_state import repo_state_candidates, repo_state_dir, repo_state_write_lock


def global_config_path() -> Path:
    return Path.home() / ".joan" / "config.toml"


def config_path(repo_root: Path | None = None, *, for_write: bool = False) -> Path:
    return repo_state_dir(repo_root, for_write=for_write) / "config.toml"


def _config_candidates(repo_root: Path | None = None) -> list[Path]:
    return [state_dir / "config.toml" for state_dir in repo_state_candidates(repo_root)]


def read_global_config() -> GlobalConfig | None:
    path = global_config_path()
    if not path.exists():
        return None
    raw = path.read_text(encoding="utf-8")
    return parse_global_config(raw)


def write_global_config(cfg: GlobalConfig) -> Path:
    path = global_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(tomli_w.dumps(global_config_to_dict(cfg)), encoding="utf-8")
    return path


def write_repo_config(cfg: RepoConfig, repo_root: Path | None = None) -> Path:
    path = config_path(repo_root, for_write=True)
    with repo_state_write_lock(repo_root):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(tomli_w.dumps(repo_config_to_dict(cfg)), encoding="utf-8")
    return path


def read_config(repo_root: Path | None = None) -> Config:
    candidate_paths = _config_candidates(repo_root)
    repo_path = candidate_paths[0]
    global_cfg = read_global_config()

    for path in candidate_paths:
        if not path.exists():
            continue
        raw = path.read_text(encoding="utf-8")
        # Backward compat: if the per-repo TOML has url + token, it's an old-style full config
        import tomllib
        try:
            raw_data = tomllib.loads(raw)
        except Exception:
            raw_data = {}
        forgejo_section = raw_data.get("forgejo", {})
        if isinstance(forgejo_section, dict) and forgejo_section.get("url") and forgejo_section.get("token"):
            return parse_config(raw)

        # New-style per-repo config
        repo_cfg = parse_repo_config(raw)
        if global_cfg is None:
            raise FileNotFoundError(
                f"global config not found at {global_config_path()}; run `joan init` to set it up"
            )
        return merge_config(global_cfg, repo_cfg)

    if global_cfg is not None:
        raise FileNotFoundError(
            f"per-repo config not found: {repo_path}; run `joan init` in this repo first"
        )

    raise FileNotFoundError(f"config not found: {repo_path}")


def write_config(config: Config, repo_root: Path | None = None) -> Path:
    path = config_path(repo_root, for_write=True)
    with repo_state_write_lock(repo_root):
        path.parent.mkdir(parents=True, exist_ok=True)
        data = config_to_dict(config)
        path.write_text(tomli_w.dumps(data), encoding="utf-8")
    return path
