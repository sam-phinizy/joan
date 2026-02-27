from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

import joan
import joan.cli.skills as skills_mod


def test_skills_install_claude(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(skills_mod.app, ["--agent", "claude"])

    assert result.exit_code == 0, result.output
    dest = tmp_path / ".claude" / "plugins" / "joan"
    assert dest.is_dir()
    assert (dest / "plugin.json").exists()
    assert (dest / "skills" / "joan-setup" / "SKILL.md").exists()
    assert (dest / "skills" / "joan-review" / "SKILL.md").exists()
    assert "Installed joan plugin for claude" in result.output


def test_skills_install_reinstall(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)

    runner.invoke(skills_mod.app, ["--agent", "claude"])

    # Place a sentinel file to confirm it gets wiped on reinstall
    dest = tmp_path / ".claude" / "plugins" / "joan"
    sentinel = dest / "stale_file.txt"
    sentinel.write_text("old")

    result = runner.invoke(skills_mod.app, ["--agent", "claude"])

    assert result.exit_code == 0, result.output
    assert "Reinstalling" in result.output
    assert not sentinel.exists()
    assert (dest / "plugin.json").exists()


def test_skills_install_unknown_agent(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(skills_mod.app, ["--agent", "unknown-agent"])
    assert result.exit_code == 1


def test_root_cli_has_skills_command() -> None:
    runner = CliRunner()
    result = runner.invoke(joan.app, ["--help"])
    assert result.exit_code == 0
    assert "skills" in result.output
