from __future__ import annotations

from pathlib import Path

import pytest

from joan.shell.config_io import config_path, read_config, write_config


def test_config_path_uses_repo_root(tmp_path: Path) -> None:
    assert config_path(tmp_path) == tmp_path / ".joan" / "config.toml"


def test_write_then_read_config(tmp_path: Path, sample_config) -> None:
    out = write_config(sample_config, tmp_path)

    assert out.exists()
    loaded = read_config(tmp_path)
    assert loaded == sample_config


def test_read_config_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="config not found"):
        read_config(tmp_path)
