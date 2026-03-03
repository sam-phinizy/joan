from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

import joan
import joan.cli.services as services_mod


def test_services_install_forgejo(tmp_path: Path) -> None:
    runner = CliRunner()

    result = runner.invoke(services_mod.app, ["install", "forgejo", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert (tmp_path / "docker-compose.yml").exists()
    assert "To start Forgejo" in result.output


def test_services_install_rejects_unknown_service(tmp_path: Path) -> None:
    runner = CliRunner()

    result = runner.invoke(services_mod.app, ["install", "unknown", str(tmp_path)])

    assert result.exit_code == 2
    assert "Unknown service 'unknown'" in result.output


def test_root_cli_has_services_command() -> None:
    runner = CliRunner()

    result = runner.invoke(joan.app, ["--help"])

    assert result.exit_code == 0
    assert "services" in result.output
