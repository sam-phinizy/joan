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
    dest = tmp_path / ".claude" / "skills"
    assert dest.is_dir()
    assert not (dest / "plugin.json").exists()
    assert (dest / "joan-setup" / "SKILL.md").exists()
    assert (dest / "joan-review" / "SKILL.md").exists()
    assert "Installed joan skills for claude" in result.output


def test_skills_install_reinstall(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)

    runner.invoke(skills_mod.app, ["--agent", "claude"])

    # Place a sentinel file inside a skill dir to confirm it gets wiped on reinstall
    dest = tmp_path / ".claude" / "skills"
    sentinel = dest / "joan-setup" / "stale_file.txt"
    sentinel.write_text("old")

    result = runner.invoke(skills_mod.app, ["--agent", "claude"])

    assert result.exit_code == 0, result.output
    assert "Reinstalling" in result.output
    assert not sentinel.exists()
    assert (dest / "joan-setup" / "SKILL.md").exists()


def test_skills_install_codex(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    codex_home = tmp_path / ".codex-home"
    monkeypatch.setenv("CODEX_HOME", str(codex_home))

    result = runner.invoke(skills_mod.app, ["--agent", "codex"])

    assert result.exit_code == 0, result.output
    dest = codex_home / "skills" / "joan"
    assert dest.is_dir()
    assert (dest / "joan-setup" / "SKILL.md").exists()
    assert (dest / "joan-review" / "SKILL.md").exists()
    assert "Installed joan skills for codex" in result.output


def test_skills_install_codex_reinstall(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    codex_home = tmp_path / ".codex-home"
    monkeypatch.setenv("CODEX_HOME", str(codex_home))

    runner.invoke(skills_mod.app, ["--agent", "codex"])

    dest = codex_home / "skills" / "joan"
    sentinel = dest / "stale_file.txt"
    sentinel.write_text("old")

    result = runner.invoke(skills_mod.app, ["--agent", "codex"])

    assert result.exit_code == 0, result.output
    assert "Reinstalling" in result.output
    assert not sentinel.exists()
    assert (dest / "joan-setup" / "SKILL.md").exists()


def test_skills_install_removes_legacy_plugin_dir(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)

    # Simulate a legacy install at .claude/plugins/joan/
    legacy = tmp_path / ".claude" / "plugins" / "joan"
    legacy.mkdir(parents=True)
    (legacy / "plugin.json").write_text("{}")
    (legacy / "skills").mkdir()
    (legacy / "skills" / "joan-setup").mkdir()

    result = runner.invoke(skills_mod.app, ["--agent", "claude"])

    assert result.exit_code == 0, result.output
    assert not legacy.exists(), "legacy plugin dir should be removed"
    assert "legacy" in result.output.lower()
    assert (tmp_path / ".claude" / "skills" / "joan-setup" / "SKILL.md").exists()


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
