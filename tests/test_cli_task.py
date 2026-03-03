from __future__ import annotations

import json

from typer.testing import CliRunner

import joan.cli.task as task_mod


def test_task_start_creates_branch_stage_and_remote(monkeypatch, sample_config) -> None:
    runner = CliRunner()
    calls: list[list[str]] = []

    monkeypatch.setattr(task_mod, "load_config_or_exit", lambda: sample_config)

    def fake_run_git(args):
        calls.append(args)
        if args == ["show-ref", "--verify", "refs/heads/feature/cache"]:
            raise RuntimeError("missing")
        if args == ["ls-remote", "joan-review", "refs/heads/joan-stage/feature/cache"]:
            return ""
        if args == ["rev-parse", "origin/main"]:
            return "base123"
        return ""

    monkeypatch.setattr(task_mod, "run_git", fake_run_git)

    result = runner.invoke(task_mod.app, ["start", "feature/cache", "--from", "origin/main"])

    assert result.exit_code == 0, result.output
    assert ["checkout", "-b", "feature/cache", "origin/main"] in calls
    assert ["push", "joan-review", "base123:refs/heads/joan-stage/feature/cache"] in calls
    assert ["push", "-u", "joan-review", "feature/cache"] in calls
    payload = json.loads(result.output)
    assert payload["working_branch"] == "feature/cache"
    assert payload["stage_branch"] == "joan-stage/feature/cache"


def test_task_track_uses_existing_branch(monkeypatch, sample_config) -> None:
    runner = CliRunner()
    calls: list[list[str]] = []

    monkeypatch.setattr(task_mod, "load_config_or_exit", lambda: sample_config)

    def fake_run_git(args):
        calls.append(args)
        if args == ["rev-parse", "--abbrev-ref", "HEAD"]:
            return "feature/cache"
        if args == ["show-ref", "--verify", "refs/heads/feature/cache"]:
            return "abc123 refs/heads/feature/cache"
        if args == ["ls-remote", "joan-review", "refs/heads/joan-stage/feature/cache"]:
            return ""
        if args == ["rev-parse", "origin/main"]:
            return "base123"
        return ""

    monkeypatch.setattr(task_mod, "run_git", fake_run_git)

    result = runner.invoke(task_mod.app, ["track", "--from", "origin/main"])

    assert result.exit_code == 0, result.output
    assert ["push", "joan-review", "base123:refs/heads/joan-stage/feature/cache"] in calls
    assert ["push", "-u", "joan-review", "feature/cache"] in calls


def test_task_status_prints_json(monkeypatch, sample_config) -> None:
    runner = CliRunner()

    monkeypatch.setattr(task_mod, "load_config_or_exit", lambda: sample_config)
    monkeypatch.setattr(task_mod, "current_branch", lambda: "feature/cache")

    def fake_run_git(args):
        if args == ["ls-remote", "joan-review", "refs/heads/joan-stage/feature/cache"]:
            return "abc"
        if args == ["ls-remote", "joan-review", "refs/heads/feature/cache"]:
            return "def"
        raise AssertionError(args)

    class FakeClient:
        def list_pulls(self, *_args, **_kwargs):
            return [{"number": 9, "html_url": "http://forgejo.local/pr/9"}]

    monkeypatch.setattr(task_mod, "run_git", fake_run_git)
    monkeypatch.setattr(task_mod, "forgejo_client", lambda _cfg: FakeClient())

    result = runner.invoke(task_mod.app, ["status"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["working_branch"] == "feature/cache"
    assert payload["open_pr_number"] == 9


def test_task_push_rejects_main(monkeypatch, sample_config) -> None:
    runner = CliRunner()

    monkeypatch.setattr(task_mod, "load_config_or_exit", lambda: sample_config)
    monkeypatch.setattr(task_mod, "current_branch", lambda: "main")

    result = runner.invoke(task_mod.app, ["push"])

    assert result.exit_code == 2


def test_task_push_pushes_branch(monkeypatch, sample_config) -> None:
    runner = CliRunner()
    calls: list[list[str]] = []

    monkeypatch.setattr(task_mod, "load_config_or_exit", lambda: sample_config)
    monkeypatch.setattr(task_mod, "current_branch", lambda: "feature/cache")
    monkeypatch.setattr(task_mod, "run_git", lambda args: calls.append(args) or "")

    result = runner.invoke(task_mod.app, ["push"])

    assert result.exit_code == 0, result.output
    assert ["push", "-u", "joan-review", "feature/cache"] in calls
