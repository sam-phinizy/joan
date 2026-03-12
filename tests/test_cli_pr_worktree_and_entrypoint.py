from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

import joan
import joan.cli.pr as pr_mod


def test_root_cli_has_expected_commands() -> None:
    runner = CliRunner()
    result = runner.invoke(joan.app, ["--help"])

    assert result.exit_code == 0
    assert "task" in result.output
    assert "issue" in result.output
    assert "ship" in result.output


def test_pr_create_uses_stage_branch(monkeypatch, sample_config) -> None:
    runner = CliRunner()
    calls: list[list[str]] = []
    captured: dict[str, object] = {}

    class FakeClient:
        def create_pr(self, _owner, _repo, payload):
            captured["payload"] = payload
            return {
                "number": 4,
                "title": "t",
                "html_url": "http://forgejo.local/pr/4",
                "state": "open",
                "head": {"ref": "feature/cache"},
                "base": {"ref": "joan-stage/feature/cache"},
            }

    monkeypatch.setattr(pr_mod, "load_config_or_exit", lambda: sample_config)
    monkeypatch.setattr(pr_mod, "forgejo_client", lambda _cfg: FakeClient())
    monkeypatch.setattr(pr_mod, "current_branch", lambda: "feature/cache")

    def fake_run_git(args):
        calls.append(args)
        if args == ["ls-remote", "joan-review", "refs/heads/joan-stage/feature/cache"]:
            return "abc"
        return ""

    monkeypatch.setattr(pr_mod, "run_git", fake_run_git)

    result = runner.invoke(pr_mod.app, ["create"])
    assert result.exit_code == 0, result.output
    assert ["push", "-u", "joan-review", "feature/cache"] in calls
    assert captured["payload"] == {
        "title": "feature/cache",
        "head": "feature/cache",
        "base": "joan-stage/feature/cache",
    }


def test_pr_create_reads_body_file(monkeypatch, sample_config, tmp_path: Path) -> None:
    runner = CliRunner()
    calls: list[list[str]] = []
    captured: dict[str, object] = {}
    body_file = tmp_path / "body.md"
    body_file.write_text("Narrative from file", encoding="utf-8")

    class FakeClient:
        def create_pr(self, _owner, _repo, payload):
            captured["payload"] = payload
            return {
                "number": 4,
                "title": "t",
                "html_url": "http://forgejo.local/pr/4",
                "state": "open",
                "head": {"ref": "feature/cache"},
                "base": {"ref": "joan-stage/feature/cache"},
            }

    monkeypatch.setattr(pr_mod, "load_config_or_exit", lambda: sample_config)
    monkeypatch.setattr(pr_mod, "forgejo_client", lambda _cfg: FakeClient())
    monkeypatch.setattr(pr_mod, "current_branch", lambda: "feature/cache")

    def fake_run_git(args):
        calls.append(args)
        if args == ["ls-remote", "joan-review", "refs/heads/joan-stage/feature/cache"]:
            return "abc"
        return ""

    monkeypatch.setattr(pr_mod, "run_git", fake_run_git)

    result = runner.invoke(pr_mod.app, ["create", "--body-file", str(body_file)])
    assert result.exit_code == 0, result.output
    assert ["push", "-u", "joan-review", "feature/cache"] in calls
    assert captured["payload"] == {
        "title": "feature/cache",
        "head": "feature/cache",
        "base": "joan-stage/feature/cache",
        "body": "Narrative from file",
    }


def test_pr_create_rejects_stage_branch(monkeypatch, sample_config) -> None:
    runner = CliRunner()

    monkeypatch.setattr(pr_mod, "load_config_or_exit", lambda: sample_config)
    monkeypatch.setattr(pr_mod, "forgejo_client", lambda _cfg: None)
    monkeypatch.setattr(pr_mod, "current_branch", lambda: "joan-stage/feature/cache")

    result = runner.invoke(pr_mod.app, ["create"])
    assert result.exit_code == 2


def test_pr_create_requires_stage_branch(monkeypatch, sample_config) -> None:
    runner = CliRunner()

    monkeypatch.setattr(pr_mod, "load_config_or_exit", lambda: sample_config)
    monkeypatch.setattr(pr_mod, "forgejo_client", lambda _cfg: None)
    monkeypatch.setattr(pr_mod, "current_branch", lambda: "feature/cache")
    monkeypatch.setattr(
        pr_mod,
        "run_git",
        lambda args: "" if args == ["ls-remote", "joan-review", "refs/heads/joan-stage/feature/cache"] else "",
    )

    result = runner.invoke(pr_mod.app, ["create"])
    assert result.exit_code == 1
    assert "task start" in result.output


def test_pr_sync(monkeypatch, sample_config, sample_pr) -> None:
    runner = CliRunner()

    class FakeClient:
        def get_reviews(self, *_args, **_kwargs):
            return [{"id": 1, "state": "APPROVED", "submitted_at": None, "user": {"login": "r"}}]

        def get_comments(self, *_args, **_kwargs):
            return [
                {"id": 9, "resolved": False, "user": {"login": "r"}},
                {"id": 10, "resolved": False, "user": {"login": sample_config.forgejo.owner}},
            ]

    monkeypatch.setattr(pr_mod, "load_config_or_exit", lambda: sample_config)
    monkeypatch.setattr(pr_mod, "forgejo_client", lambda _cfg: FakeClient())
    monkeypatch.setattr(pr_mod, "current_pr_or_exit", lambda _cfg, **_kwargs: sample_pr)

    result = runner.invoke(pr_mod.app, ["sync"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["approved"] is True
    assert payload["unresolved_comments"] == 1


def test_pr_comments_and_resolve(monkeypatch, sample_config, sample_pr) -> None:
    runner = CliRunner()

    class FakeClient:
        def get_comments(self, *_args, **_kwargs):
            return [
                {"id": 1, "resolved": False, "user": {"login": "r"}},
                {"id": 2, "resolved": True, "user": {"login": "r"}},
                {"id": 3, "resolved": False, "user": {"login": sample_config.forgejo.owner}},
            ]

        def resolve_comment(self, *_args, **_kwargs):
            return None

    monkeypatch.setattr(pr_mod, "load_config_or_exit", lambda: sample_config)
    monkeypatch.setattr(pr_mod, "forgejo_client", lambda _cfg: FakeClient())
    monkeypatch.setattr(pr_mod, "current_pr_or_exit", lambda _cfg, **_kwargs: sample_pr)

    comments = runner.invoke(pr_mod.app, ["comments"])
    assert comments.exit_code == 0
    payload = json.loads(comments.output)
    assert [item["id"] for item in payload] == [1]

    result = runner.invoke(pr_mod.app, ["comment", "resolve", "1"])
    assert result.exit_code == 0
    assert "Resolved comment 1" in result.output


def test_pr_comments_rejects_pr_and_branch_together(monkeypatch, sample_config) -> None:
    runner = CliRunner()

    monkeypatch.setattr(pr_mod, "load_config_or_exit", lambda: sample_config)

    result = runner.invoke(pr_mod.app, ["comments", "--pr", "7", "--branch", "feature/demo"])

    assert result.exit_code == 2
    assert "either --pr or --branch" in result.output


def test_pr_finish_merges_into_stage_branch(monkeypatch, sample_config) -> None:
    runner = CliRunner()
    calls: list[list[str]] = []

    class FakeClient:
        def get_reviews(self, *_args, **_kwargs):
            return [{"id": 1, "state": "APPROVED", "submitted_at": None, "user": {"login": "r"}}]

        def get_comments(self, *_args, **_kwargs):
            return []

        def merge_pr(self, owner, repo, index):
            assert (owner, repo, index) == ("sam", "joan", 7)
            return {}

    pr = sample_config and type("PR", (), {
        "number": 7,
        "base_ref": "joan-stage/feature/cache",
        "head_ref": "feature/cache",
    })()

    monkeypatch.setattr(pr_mod, "load_config_or_exit", lambda: sample_config)
    monkeypatch.setattr(pr_mod, "forgejo_client", lambda _cfg: FakeClient())
    monkeypatch.setattr(pr_mod, "current_branch", lambda: "feature/cache")
    monkeypatch.setattr(pr_mod, "current_pr_or_exit", lambda _cfg, **_kwargs: pr)
    monkeypatch.setattr(pr_mod, "run_git", lambda args: calls.append(args) or "")

    result = runner.invoke(pr_mod.app, ["finish"])

    assert result.exit_code == 0, result.output
    assert ["fetch", "joan-review"] in calls
    assert "Merged PR #7 into joan-stage/feature/cache" in result.output


def test_pr_finish_rejects_wrong_base(monkeypatch, sample_config) -> None:
    runner = CliRunner()

    pr = type("PR", (), {"number": 7, "base_ref": "main", "head_ref": "feature/cache"})()

    monkeypatch.setattr(pr_mod, "load_config_or_exit", lambda: sample_config)
    monkeypatch.setattr(pr_mod, "forgejo_client", lambda _cfg: None)
    monkeypatch.setattr(pr_mod, "current_branch", lambda: "feature/cache")
    monkeypatch.setattr(pr_mod, "current_pr_or_exit", lambda _cfg, **_kwargs: pr)

    result = runner.invoke(pr_mod.app, ["finish"])

    assert result.exit_code == 1
    assert "expected stage branch" in result.output
