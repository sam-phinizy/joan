from __future__ import annotations

from typer.testing import CliRunner

import joan
import joan.cli.ship as ship_mod


def test_root_cli_has_ship_command() -> None:
    runner = CliRunner()
    result = runner.invoke(joan.app, ["--help"])
    assert result.exit_code == 0
    assert "ship" in result.output


def test_ship_creates_publish_branch_and_pushes(monkeypatch, sample_config) -> None:
    runner = CliRunner()
    calls: list[list[str]] = []

    monkeypatch.setattr(ship_mod, "load_config_or_exit", lambda: sample_config)
    monkeypatch.setattr(ship_mod, "current_branch", lambda: "feature/cache")

    def fake_run_git(args):
        calls.append(args)
        if args == ["ls-remote", "joan-review", "refs/heads/joan-stage/feature/cache"]:
            return "abc"
        return ""

    monkeypatch.setattr(ship_mod, "run_git", fake_run_git)

    result = runner.invoke(joan.app, ["ship"])

    assert result.exit_code == 0, result.output
    assert ["fetch", "joan-review"] in calls
    assert ["branch", "-f", "publish/feature-cache", "joan-review/joan-stage/feature/cache"] in calls
    assert ["push", "-u", "origin", "publish/feature-cache"] in calls


def test_ship_allows_custom_publish_branch(monkeypatch, sample_config) -> None:
    runner = CliRunner()
    calls: list[list[str]] = []

    monkeypatch.setattr(ship_mod, "load_config_or_exit", lambda: sample_config)
    monkeypatch.setattr(ship_mod, "current_branch", lambda: "feature/cache")

    def fake_run_git(args):
        calls.append(args)
        if args == ["ls-remote", "joan-review", "refs/heads/joan-stage/feature/cache"]:
            return "abc"
        return ""

    monkeypatch.setattr(ship_mod, "run_git", fake_run_git)

    result = runner.invoke(joan.app, ["ship", "--as", "sam/cache"])

    assert result.exit_code == 0, result.output
    assert ["branch", "-f", "sam/cache", "joan-review/joan-stage/feature/cache"] in calls
    assert ["push", "-u", "origin", "sam/cache"] in calls


def test_ship_rejects_stage_branch(monkeypatch, sample_config) -> None:
    runner = CliRunner()

    monkeypatch.setattr(ship_mod, "load_config_or_exit", lambda: sample_config)
    monkeypatch.setattr(ship_mod, "current_branch", lambda: "joan-stage/feature/cache")

    result = runner.invoke(joan.app, ["ship"])

    assert result.exit_code == 2
