from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

import joan
import joan.cli.skills as skills_mod


def test_skills_install_claude(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(skills_mod.Path, "home", lambda: tmp_path)

    result = runner.invoke(skills_mod.app, ["--agent", "claude"])

    assert result.exit_code == 0, result.output
    dest = tmp_path / ".claude" / "plugins" / "joan"
    assert dest.is_dir()
    assert (dest / "plugin.json").exists()
    assert (dest / "skills" / "joan-setup" / "SKILL.md").exists()
    assert (dest / "skills" / "joan-review" / "SKILL.md").exists()
    assert (dest / "skills" / "joan-resolve-pr-comments" / "SKILL.md").exists()
    assert "Installed joan plugin for claude" in result.output


def test_skills_install_reinstall(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(skills_mod.Path, "home", lambda: tmp_path)

    runner.invoke(skills_mod.app, ["--agent", "claude"])

    dest = tmp_path / ".claude" / "plugins" / "joan"
    sentinel = dest / "stale_file.txt"
    sentinel.write_text("old")

    result = runner.invoke(skills_mod.app, ["--agent", "claude"])

    assert result.exit_code == 0, result.output
    assert "Reinstalling" in result.output
    assert not sentinel.exists()
    assert (dest / "plugin.json").exists()


def test_skills_install_removes_legacy_skills_dir(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(skills_mod.Path, "home", lambda: tmp_path)

    # Simulate legacy per-repo skills install at .claude/skills/
    for name in ("joan-setup", "joan-review"):
        skill_dir = tmp_path / ".claude" / "skills" / name
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("old")

    result = runner.invoke(skills_mod.app, ["--agent", "claude"])

    assert result.exit_code == 0, result.output
    assert "legacy" in result.output.lower()
    assert not (tmp_path / ".claude" / "skills" / "joan-setup").exists()
    assert not (tmp_path / ".claude" / "skills" / "joan-review").exists()
    assert (tmp_path / ".claude" / "plugins" / "joan" / "plugin.json").exists()


def test_skills_install_removes_legacy_plugin_dir(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(skills_mod.Path, "home", lambda: tmp_path)

    # Simulate a legacy per-repo plugin install at .claude/plugins/joan/
    legacy = tmp_path / ".claude" / "plugins" / "joan"
    legacy.mkdir(parents=True)
    (legacy / "plugin.json").write_text("{}")

    result = runner.invoke(skills_mod.app, ["--agent", "claude"])

    assert result.exit_code == 0, result.output
    # Global install should succeed (it replaces the legacy dir)
    assert (tmp_path / ".claude" / "plugins" / "joan" / "plugin.json").exists()


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
    assert (dest / "joan-resolve-pr-comments" / "SKILL.md").exists()
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
