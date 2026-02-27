from __future__ import annotations

import pytest

from joan.core.config import ConfigError, config_to_dict, parse_config, parse_config_dict, validate_config
from joan.core.models import Config, ForgejoConfig, RemotesConfig


def test_parse_config_valid_with_defaults() -> None:
    raw = """
[forgejo]
url = "http://localhost:3000/"
token = "abc"
owner = "sam"
repo = "joan"
"""
    config = parse_config(raw)

    assert config.forgejo.url == "http://localhost:3000"
    assert config.remotes.review == "joan-review"
    assert config.remotes.upstream == "origin"


def test_parse_config_invalid_toml() -> None:
    with pytest.raises(ConfigError, match="invalid TOML"):
        parse_config("[forgejo")


def test_parse_config_missing_forgejo_section() -> None:
    with pytest.raises(ConfigError, match=r"missing \[forgejo\] section"):
        parse_config_dict({})


def test_parse_config_invalid_remotes_type() -> None:
    data = {
        "forgejo": {"url": "http://x", "token": "t", "owner": "o", "repo": "r"},
        "remotes": "nope",
    }
    with pytest.raises(ConfigError, match=r"\[remotes\] must be a table"):
        parse_config_dict(data)


def test_parse_config_requires_non_empty_fields() -> None:
    data = {"forgejo": {"url": "http://x", "token": "", "owner": "o", "repo": "r"}}
    with pytest.raises(ConfigError, match="forgejo.token is required"):
        parse_config_dict(data)


def test_validate_config_requires_http_scheme(sample_config: Config) -> None:
    bad = Config(
        forgejo=ForgejoConfig(url="ftp://forgejo", token="a", owner="o", repo="r"),
        remotes=RemotesConfig(),
    )
    with pytest.raises(ConfigError, match="must start with"):
        validate_config(bad)

    validate_config(sample_config)


def test_config_to_dict_roundtrip(sample_config: Config) -> None:
    out = config_to_dict(sample_config)
    again = parse_config_dict(out)
    assert again == sample_config
