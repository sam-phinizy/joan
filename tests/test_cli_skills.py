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
    assert (dest / ".claude-plugin" / "plugin.json").exists()
    assert (dest / "skills" / "joan-setup" / "SKILL.md").exists()
    assert (dest / "skills" / "joan-task" / "SKILL.md").exists()
    assert (dest / "skills" / "joan-review" / "SKILL.md").exists()
    assert not (dest / "skills" / "joan-plan").exists()
    assert not (dest / "skills" / "joan-adopt-branch").exists()


def test_skills_install_codex(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    monkeypatch.setattr(skills_mod.Path, "home", lambda: tmp_path)

    result = runner.invoke(skills_mod.app, ["--agent", "codex"])

    assert result.exit_code == 0, result.output
    dest = tmp_path / ".agents" / "skills"
    assert dest.is_dir()
    assert (dest / "joan-setup" / "SKILL.md").exists()
    assert (dest / "joan-task" / "SKILL.md").exists()
    assert (dest / "joan-review" / "SKILL.md").exists()
    assert not (dest / "joan-plan").exists()
    assert not (dest / "joan-adopt-branch").exists()


def test_skills_install_codex_preserves_unrelated_user_skill(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    monkeypatch.setattr(skills_mod.Path, "home", lambda: tmp_path)

    other_skill = tmp_path / ".agents" / "skills" / "other-skill"
    other_skill.mkdir(parents=True)
    (other_skill / "SKILL.md").write_text("custom")

    result = runner.invoke(skills_mod.app, ["--agent", "codex"])

    assert result.exit_code == 0, result.output
    assert (other_skill / "SKILL.md").read_text() == "custom"


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
