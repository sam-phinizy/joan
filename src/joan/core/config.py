from __future__ import annotations

import tomllib

from joan.core.models import Config, ForgejoConfig, GlobalConfig, RemotesConfig, RepoConfig


class ConfigError(ValueError):
    pass


def parse_config(raw_toml: str) -> Config:
    try:
        data = tomllib.loads(raw_toml)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"invalid TOML in config: {exc}") from exc

    return parse_config_dict(data)


def parse_config_dict(data: dict) -> Config:
    forgejo_data = data.get("forgejo")
    if not isinstance(forgejo_data, dict):
        raise ConfigError("missing [forgejo] section")

    url = _require_str(forgejo_data, "url")
    token = _require_str(forgejo_data, "token")
    owner = _require_str(forgejo_data, "owner")
    repo = _require_str(forgejo_data, "repo")
    human_user = _optional_str(forgejo_data, "human_user")

    remotes_data = data.get("remotes", {})
    if remotes_data is None:
        remotes_data = {}
    if not isinstance(remotes_data, dict):
        raise ConfigError("[remotes] must be a table")

    review = str(remotes_data.get("review", "joan-review"))
    upstream = str(remotes_data.get("upstream", "origin"))

    config = Config(
        forgejo=ForgejoConfig(
            url=url.rstrip("/"),
            token=token,
            owner=owner,
            repo=repo,
            human_user=human_user,
        ),
        remotes=RemotesConfig(review=review, upstream=upstream),
    )
    validate_config(config)
    return config


def validate_config(config: Config) -> None:
    if not config.forgejo.url.startswith(("http://", "https://")):
        raise ConfigError("forgejo.url must start with http:// or https://")
    if not config.forgejo.token:
        raise ConfigError("forgejo.token cannot be empty")
    if not config.forgejo.owner:
        raise ConfigError("forgejo.owner cannot be empty")
    if not config.forgejo.repo:
        raise ConfigError("forgejo.repo cannot be empty")


def config_to_dict(config: Config) -> dict:
    forgejo_data = {
            "url": config.forgejo.url,
            "token": config.forgejo.token,
            "owner": config.forgejo.owner,
            "repo": config.forgejo.repo,
    }
    if config.forgejo.human_user:
        forgejo_data["human_user"] = config.forgejo.human_user

    return {
        "forgejo": forgejo_data,
        "remotes": {
            "review": config.remotes.review,
            "upstream": config.remotes.upstream,
        },
    }


def _require_str(mapping: dict, key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"forgejo.{key} is required and must be a non-empty string")
    return value.strip()


def _optional_str(mapping: dict, key: str) -> str | None:
    value = mapping.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ConfigError(f"forgejo.{key} must be a string when set")
    stripped = value.strip()
    return stripped or None


def parse_global_config(raw_toml: str) -> GlobalConfig:
    try:
        data = tomllib.loads(raw_toml)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"invalid TOML in global config: {exc}") from exc

    forgejo_data = data.get("forgejo")
    if not isinstance(forgejo_data, dict):
        raise ConfigError("missing [forgejo] section in global config")

    url = _require_str(forgejo_data, "url")
    token = _require_str(forgejo_data, "token")
    owner = str(forgejo_data.get("owner", "joan")).strip() or "joan"
    human_user = _optional_str(forgejo_data, "human_user")

    if not url.startswith(("http://", "https://")):
        raise ConfigError("forgejo.url must start with http:// or https://")

    remotes_data = data.get("remotes", {}) or {}
    if not isinstance(remotes_data, dict):
        raise ConfigError("[remotes] must be a table")
    review = str(remotes_data.get("review", "joan-review"))
    upstream = str(remotes_data.get("upstream", "origin"))

    return GlobalConfig(
        url=url.rstrip("/"),
        token=token,
        owner=owner,
        human_user=human_user,
        remotes=RemotesConfig(review=review, upstream=upstream),
    )


def parse_repo_config(raw_toml: str) -> RepoConfig:
    try:
        data = tomllib.loads(raw_toml)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"invalid TOML in repo config: {exc}") from exc

    forgejo_data = data.get("forgejo")
    if not isinstance(forgejo_data, dict):
        raise ConfigError("missing [forgejo] section in repo config")

    repo = _require_str(forgejo_data, "repo")
    human_user = _optional_str(forgejo_data, "human_user")

    remotes_data = data.get("remotes")
    remotes: RemotesConfig | None = None
    if remotes_data is not None:
        if not isinstance(remotes_data, dict):
            raise ConfigError("[remotes] must be a table")
        review = str(remotes_data.get("review", "joan-review"))
        upstream = str(remotes_data.get("upstream", "origin"))
        remotes = RemotesConfig(review=review, upstream=upstream)

    return RepoConfig(repo=repo, human_user=human_user, remotes=remotes)


def merge_config(global_cfg: GlobalConfig, repo_cfg: RepoConfig) -> Config:
    human_user = repo_cfg.human_user if repo_cfg.human_user is not None else global_cfg.human_user
    remotes = repo_cfg.remotes if repo_cfg.remotes is not None else global_cfg.remotes
    return Config(
        forgejo=ForgejoConfig(
            url=global_cfg.url,
            token=global_cfg.token,
            owner=global_cfg.owner,
            repo=repo_cfg.repo,
            human_user=human_user,
        ),
        remotes=remotes,
    )


def global_config_to_dict(cfg: GlobalConfig) -> dict:
    forgejo_data: dict = {
        "url": cfg.url,
        "token": cfg.token,
        "owner": cfg.owner,
    }
    if cfg.human_user:
        forgejo_data["human_user"] = cfg.human_user
    return {
        "forgejo": forgejo_data,
        "remotes": {
            "review": cfg.remotes.review,
            "upstream": cfg.remotes.upstream,
        },
    }


def repo_config_to_dict(cfg: RepoConfig) -> dict:
    forgejo_data: dict = {"repo": cfg.repo}
    if cfg.human_user:
        forgejo_data["human_user"] = cfg.human_user
    result: dict = {"forgejo": forgejo_data}
    if cfg.remotes is not None:
        result["remotes"] = {
            "review": cfg.remotes.review,
            "upstream": cfg.remotes.upstream,
        }
    return result
