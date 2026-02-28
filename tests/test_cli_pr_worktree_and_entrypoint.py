from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

import joan
import joan.cli.pr as pr_mod
import joan.cli.worktree as wt_mod


def test_root_cli_has_expected_commands() -> None:
    runner = CliRunner()
    result = runner.invoke(joan.app, ["--help"])

    assert result.exit_code == 0
    assert "init" in result.output
    assert "remote" in result.output
    assert "branch" in result.output
    assert "plan" in result.output
    assert "pr" in result.output
    assert "ssh" in result.output
    assert "worktree" in result.output


def test_pr_create(monkeypatch, sample_config) -> None:
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
                "head": {"ref": "joan-review/feat"},
                "base": {"ref": "feat"},
            }

    monkeypatch.setattr(pr_mod, "load_config_or_exit", lambda: sample_config)
    monkeypatch.setattr(pr_mod, "forgejo_client", lambda _cfg: FakeClient())
    monkeypatch.setattr(pr_mod, "current_branch", lambda: "joan-review/feat")
    monkeypatch.setattr(pr_mod, "run_git", lambda args: calls.append(args) or "")

    result = runner.invoke(pr_mod.app, ["create"])
    assert result.exit_code == 0
    assert ["push", "joan-review", "feat"] in calls
    assert ["push", "-u", "joan-review", "joan-review/feat"] in calls
    assert captured["payload"] == {"title": "joan-review/feat", "head": "joan-review/feat", "base": "feat"}
    assert "PR #4" in result.output


def test_pr_create_requests_human_review_by_default(monkeypatch, sample_config) -> None:
    runner = CliRunner()
    sample_config.forgejo.human_user = "alex"
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
                "head": {"ref": "joan-review/feat"},
                "base": {"ref": "feat"},
            }

        def request_pr_reviewers(self, owner, repo, index, reviewers):
            captured["reviewer_call"] = {
                "owner": owner,
                "repo": repo,
                "index": index,
                "reviewers": reviewers,
            }
            return {}

    monkeypatch.setattr(pr_mod, "load_config_or_exit", lambda: sample_config)
    monkeypatch.setattr(pr_mod, "forgejo_client", lambda _cfg: FakeClient())
    monkeypatch.setattr(pr_mod, "current_branch", lambda: "joan-review/feat")
    monkeypatch.setattr(pr_mod, "run_git", lambda args: calls.append(args) or "")

    result = runner.invoke(pr_mod.app, ["create"])

    assert result.exit_code == 0
    assert ["push", "joan-review", "feat"] in calls
    assert ["push", "-u", "joan-review", "joan-review/feat"] in calls
    assert captured["payload"] == {"title": "joan-review/feat", "head": "joan-review/feat", "base": "feat"}
    assert captured["reviewer_call"] == {
        "owner": "sam",
        "repo": "joan",
        "index": 4,
        "reviewers": ["alex"],
    }


def test_pr_create_accepts_suffixed_review_branch(monkeypatch, sample_config) -> None:
    runner = CliRunner()
    calls: list[list[str]] = []
    captured: dict[str, object] = {}

    class FakeClient:
        def create_pr(self, _owner, _repo, payload):
            captured["payload"] = payload
            return {
                "number": 5,
                "title": "t",
                "html_url": "http://forgejo.local/pr/5",
                "state": "open",
                "head": {"ref": "joan-review/feat--plan-cache"},
                "base": {"ref": "feat"},
            }

    monkeypatch.setattr(pr_mod, "load_config_or_exit", lambda: sample_config)
    monkeypatch.setattr(pr_mod, "forgejo_client", lambda _cfg: FakeClient())
    monkeypatch.setattr(pr_mod, "current_branch", lambda: "joan-review/feat--plan-cache")
    monkeypatch.setattr(pr_mod, "run_git", lambda args: calls.append(args) or "")

    result = runner.invoke(pr_mod.app, ["create"])

    assert result.exit_code == 0, result.output
    assert ["push", "joan-review", "feat"] in calls
    assert ["push", "-u", "joan-review", "joan-review/feat--plan-cache"] in calls
    assert captured["payload"] == {
        "title": "joan-review/feat--plan-cache",
        "head": "joan-review/feat--plan-cache",
        "base": "feat",
    }


def test_pr_create_can_skip_human_review_request(monkeypatch, sample_config) -> None:
    runner = CliRunner()
    sample_config.forgejo.human_user = "alex"
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
                "head": {"ref": "joan-review/feat"},
                "base": {"ref": "feat"},
            }

        def request_pr_reviewers(self, *_args, **_kwargs):
            raise AssertionError("human review should not be requested")

    monkeypatch.setattr(pr_mod, "load_config_or_exit", lambda: sample_config)
    monkeypatch.setattr(pr_mod, "forgejo_client", lambda _cfg: FakeClient())
    monkeypatch.setattr(pr_mod, "current_branch", lambda: "joan-review/feat")
    monkeypatch.setattr(pr_mod, "run_git", lambda args: calls.append(args) or "")

    result = runner.invoke(pr_mod.app, ["create", "--no-request-human-review"])

    assert result.exit_code == 0
    assert ["push", "joan-review", "feat"] in calls
    assert ["push", "-u", "joan-review", "joan-review/feat"] in calls
    assert captured["payload"] == {"title": "joan-review/feat", "head": "joan-review/feat", "base": "feat"}
    assert "PR #4" in result.output


def test_pr_create_requires_review_branch_without_base(monkeypatch, sample_config) -> None:
    runner = CliRunner()

    monkeypatch.setattr(pr_mod, "load_config_or_exit", lambda: sample_config)
    monkeypatch.setattr(pr_mod, "forgejo_client", lambda _cfg: None)
    monkeypatch.setattr(pr_mod, "current_branch", lambda: "feat")

    result = runner.invoke(pr_mod.app, ["create"])
    assert result.exit_code == 2
    assert "Current branch is not a review branch" in result.output


def test_pr_sync(monkeypatch, sample_config, sample_pr) -> None:
    runner = CliRunner()

    class FakeClient:
        def get_reviews(self, *_args, **_kwargs):
            return [{"id": 1, "state": "APPROVED", "submitted_at": None, "user": {"login": "r"}}]

        def get_comments(self, *_args, **_kwargs):
            return [{"id": 9, "resolved": False, "user": {"login": "r"}}]

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
            ]

        def resolve_comment(self, *_args, **_kwargs):
            return None

    monkeypatch.setattr(pr_mod, "load_config_or_exit", lambda: sample_config)
    monkeypatch.setattr(pr_mod, "forgejo_client", lambda _cfg: FakeClient())
    monkeypatch.setattr(pr_mod, "current_pr_or_exit", lambda _cfg, **_kwargs: sample_pr)

    comments = runner.invoke(pr_mod.app, ["comments"])
    assert comments.exit_code == 0
    payload = json.loads(comments.output)
    assert len(payload) == 1

    resolve = runner.invoke(pr_mod.app, ["comment", "resolve", "22"])
    assert resolve.exit_code == 0
    assert "Resolved comment 22" in resolve.output


def test_pr_comments_can_target_explicit_pr(monkeypatch, sample_config, sample_pr) -> None:
    runner = CliRunner()
    captured: dict[str, object] = {}

    class FakeClient:
        def get_comments(self, *_args, **_kwargs):
            return [{"id": 1, "resolved": False, "user": {"login": "r"}}]

    def fake_current_pr_or_exit(_config, pr_number=None, branch=None):
        captured["pr_number"] = pr_number
        captured["branch"] = branch
        return sample_pr

    monkeypatch.setattr(pr_mod, "load_config_or_exit", lambda: sample_config)
    monkeypatch.setattr(pr_mod, "forgejo_client", lambda _cfg: FakeClient())
    monkeypatch.setattr(pr_mod, "current_pr_or_exit", fake_current_pr_or_exit)

    result = runner.invoke(pr_mod.app, ["comments", "--pr", "7"])

    assert result.exit_code == 0
    assert captured == {"pr_number": 7, "branch": None}


def test_pr_comments_rejects_pr_and_branch_together(monkeypatch, sample_config) -> None:
    runner = CliRunner()

    monkeypatch.setattr(pr_mod, "load_config_or_exit", lambda: sample_config)

    result = runner.invoke(pr_mod.app, ["comments", "--pr", "7", "--branch", "feature/demo"])

    assert result.exit_code == 2
    assert "either --pr or --branch" in result.output


def test_pr_finish_approval_gates_and_merges(monkeypatch, sample_config, sample_pr) -> None:
    runner = CliRunner()
    calls: list[list[str]] = []

    class FakeClient:
        def __init__(self, reviews, comments):
            self._reviews = reviews
            self._comments = comments

        def get_reviews(self, *_args, **_kwargs):
            return self._reviews

        def get_comments(self, *_args, **_kwargs):
            return self._comments

    monkeypatch.setattr(pr_mod, "load_config_or_exit", lambda: sample_config)
    sample_pr.base_ref = "feat"
    monkeypatch.setattr(pr_mod, "current_pr_or_exit", lambda _cfg: sample_pr)
    monkeypatch.setattr(pr_mod, "current_branch", lambda: "joan-review/feat")
    monkeypatch.setattr(pr_mod, "run_git", lambda args: calls.append(args) or "")

    monkeypatch.setattr(
        pr_mod,
        "forgejo_client",
        lambda _cfg: FakeClient(reviews=[{"id": 1, "state": "COMMENTED", "user": {"login": "r"}}], comments=[]),
    )
    not_approved = runner.invoke(pr_mod.app, ["finish"])
    assert not_approved.exit_code == 1
    assert "not approved" in not_approved.output

    monkeypatch.setattr(
        pr_mod,
        "forgejo_client",
        lambda _cfg: FakeClient(
            reviews=[{"id": 2, "state": "APPROVED", "user": {"login": "r"}}],
            comments=[{"id": 1, "resolved": False, "user": {"login": "r"}}],
        ),
    )
    unresolved = runner.invoke(pr_mod.app, ["finish"])
    assert unresolved.exit_code == 1
    assert "unresolved comments" in unresolved.output

    monkeypatch.setattr(
        pr_mod,
        "forgejo_client",
        lambda _cfg: FakeClient(
            reviews=[{"id": 2, "state": "APPROVED", "user": {"login": "r"}}],
            comments=[{"id": 1, "resolved": True, "user": {"login": "r"}}],
        ),
    )
    ok = runner.invoke(pr_mod.app, ["finish"])
    assert ok.exit_code == 0
    assert ["checkout", "feat"] in calls
    assert ["merge", "--ff-only", "joan-review/feat"] in calls


def test_pr_push_requires_finished_branch(monkeypatch, sample_config) -> None:
    runner = CliRunner()

    monkeypatch.setattr(pr_mod, "load_config_or_exit", lambda: sample_config)
    monkeypatch.setattr(pr_mod, "current_branch", lambda: "joan-review/feat")

    result = runner.invoke(pr_mod.app, ["push"])

    assert result.exit_code == 2
    assert "pr finish" in result.output


def test_pr_finish_merges_suffixed_review_branch(monkeypatch, sample_config, sample_pr) -> None:
    runner = CliRunner()
    calls: list[list[str]] = []

    class FakeClient:
        def get_reviews(self, *_args, **_kwargs):
            return [{"id": 2, "state": "APPROVED", "user": {"login": "r"}}]

        def get_comments(self, *_args, **_kwargs):
            return [{"id": 1, "resolved": True, "user": {"login": "r"}}]

    monkeypatch.setattr(pr_mod, "load_config_or_exit", lambda: sample_config)
    sample_pr.base_ref = "feat"
    monkeypatch.setattr(pr_mod, "current_pr_or_exit", lambda _cfg: sample_pr)
    monkeypatch.setattr(pr_mod, "current_branch", lambda: "joan-review/feat--plan-cache")
    monkeypatch.setattr(pr_mod, "run_git", lambda args: calls.append(args) or "")
    monkeypatch.setattr(pr_mod, "forgejo_client", lambda _cfg: FakeClient())

    result = runner.invoke(pr_mod.app, ["finish"])

    assert result.exit_code == 0, result.output
    assert ["checkout", "feat"] in calls
    assert ["merge", "--ff-only", "joan-review/feat--plan-cache"] in calls


def test_pr_push_pushes_current_branch(monkeypatch, sample_config) -> None:
    runner = CliRunner()
    calls: list[list[str]] = []

    monkeypatch.setattr(pr_mod, "load_config_or_exit", lambda: sample_config)
    monkeypatch.setattr(pr_mod, "current_branch", lambda: "main")
    monkeypatch.setattr(pr_mod, "run_git", lambda args: calls.append(args) or "")

    result = runner.invoke(pr_mod.app, ["push"])

    assert result.exit_code == 0
    assert ["push", "origin", "main"] in calls
    assert "Pushed main to origin/main" in result.output


def test_worktree_create_and_remove(monkeypatch, tmp_path: Path) -> None:
    runner = CliRunner()
    calls: list[list[str]] = []

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(wt_mod, "run_git", lambda args: calls.append(args) or "")

    create = runner.invoke(wt_mod.app, ["create", "codex/wt-test"])
    assert create.exit_code == 0
    assert calls[0][0:3] == ["worktree", "add", "-b"]

    tracking_file = tmp_path / ".joan" / "worktrees.json"
    tracking = json.loads(tracking_file.read_text(encoding="utf-8"))
    assert "codex/wt-test" in tracking

    remove = runner.invoke(wt_mod.app, ["remove", "codex/wt-test"])
    assert remove.exit_code == 0
    tracking_after = json.loads(tracking_file.read_text(encoding="utf-8"))
    assert "codex/wt-test" not in tracking_after


def test_worktree_remove_unknown(monkeypatch, tmp_path: Path) -> None:
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(wt_mod.app, ["remove", "missing"])
    assert result.exit_code == 1
    assert "Unknown worktree" in result.output
