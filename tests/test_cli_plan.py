from __future__ import annotations

from datetime import date
from pathlib import Path

from typer.testing import CliRunner

import joan.cli.plan as plan_mod


class FakeDate:
    @classmethod
    def today(cls) -> date:
        return date(2026, 2, 28)


def test_plan_create_without_opening_pr(monkeypatch, sample_config) -> None:
    runner = CliRunner()
    calls: list[list[str]] = []

    monkeypatch.setattr(plan_mod, "load_config_or_exit", lambda: sample_config)
    monkeypatch.setattr(plan_mod, "current_branch", lambda: "main")
    monkeypatch.setattr(plan_mod, "run_git", lambda args: calls.append(args) or "")
    monkeypatch.setattr(plan_mod, "date", FakeDate)

    with runner.isolated_filesystem():
        result = runner.invoke(plan_mod.app, ["create", "Cache_Strategy", "--no-open-pr"])

        assert result.exit_code == 0, result.output
        assert ["push", "joan-review", "main"] in calls
        assert ["checkout", "-b", "joan-review/main--plan-cache-strategy", "main"] in calls
        plan_path = Path("docs/plans/2026-02-28-cache-strategy.md")
        assert plan_path.exists()
        content = plan_path.read_text(encoding="utf-8")
        assert 'slug: "cache-strategy"' in content
        assert 'base_branch: "main"' in content
        assert "PR #" not in result.output


def test_plan_create_opens_pr_and_requests_human_review(monkeypatch, sample_config) -> None:
    runner = CliRunner()
    calls: list[list[str]] = []
    captured: dict[str, object] = {}
    sample_config.forgejo.human_user = "alex"

    class FakeClient:
        def create_pr(self, _owner, _repo, payload):
            captured["payload"] = payload
            return {
                "number": 9,
                "title": payload["title"],
                "html_url": "http://forgejo.local/pr/9",
                "state": "open",
                "head": {"ref": "joan-review/main--plan-foo"},
                "base": {"ref": "main"},
            }

        def request_pr_reviewers(self, owner, repo, index, reviewers):
            captured["reviewer_call"] = {
                "owner": owner,
                "repo": repo,
                "index": index,
                "reviewers": reviewers,
            }
            return {}

    monkeypatch.setattr(plan_mod, "load_config_or_exit", lambda: sample_config)
    monkeypatch.setattr(plan_mod, "current_branch", lambda: "main")
    monkeypatch.setattr(plan_mod, "run_git", lambda args: calls.append(args) or "")
    monkeypatch.setattr(plan_mod, "forgejo_client", lambda _cfg: FakeClient())
    monkeypatch.setattr(plan_mod, "date", FakeDate)

    with runner.isolated_filesystem():
        result = runner.invoke(plan_mod.app, ["create", "foo"])

        assert result.exit_code == 0, result.output
        assert ["push", "-u", "joan-review", "joan-review/main--plan-foo"] in calls
        assert captured["payload"] == {
            "title": "plan: foo",
            "head": "joan-review/main--plan-foo",
            "base": "main",
        }
        assert captured["reviewer_call"] == {
            "owner": "sam",
            "repo": "joan",
            "index": 9,
            "reviewers": ["alex"],
        }
        assert "PR #9" in result.output


def test_plan_create_uses_explicit_title_and_base(monkeypatch, sample_config) -> None:
    runner = CliRunner()
    calls: list[list[str]] = []
    captured: dict[str, object] = {}

    class FakeClient:
        def create_pr(self, _owner, _repo, payload):
            captured["payload"] = payload
            return {
                "number": 10,
                "title": payload["title"],
                "html_url": "http://forgejo.local/pr/10",
                "state": "open",
                "head": {"ref": "joan-review/main--plan-cache-strategy"},
                "base": {"ref": "main"},
            }

    monkeypatch.setattr(plan_mod, "load_config_or_exit", lambda: sample_config)
    monkeypatch.setattr(plan_mod, "current_branch", lambda: "feature/wip")
    monkeypatch.setattr(plan_mod, "run_git", lambda args: calls.append(args) or "")
    monkeypatch.setattr(plan_mod, "forgejo_client", lambda _cfg: FakeClient())
    monkeypatch.setattr(plan_mod, "date", FakeDate)

    with runner.isolated_filesystem():
        result = runner.invoke(
            plan_mod.app,
            ["create", "cache_strategy", "--base", "main", "--title", "Cache strategy"],
        )

        assert result.exit_code == 0, result.output
        assert ["push", "joan-review", "main"] in calls
        assert ["checkout", "-b", "joan-review/main--plan-cache-strategy", "main"] in calls
        assert captured["payload"] == {
            "title": "plan: Cache strategy",
            "head": "joan-review/main--plan-cache-strategy",
            "base": "main",
        }
        content = Path("docs/plans/2026-02-28-cache-strategy.md").read_text(encoding="utf-8")
        assert 'title: "Cache strategy"' in content
        assert 'base_branch: "main"' in content


def test_plan_create_rejects_review_branch(monkeypatch, sample_config) -> None:
    runner = CliRunner()

    monkeypatch.setattr(plan_mod, "load_config_or_exit", lambda: sample_config)
    monkeypatch.setattr(plan_mod, "current_branch", lambda: "joan-review/main")

    result = runner.invoke(plan_mod.app, ["create", "foo"])

    assert result.exit_code == 2
    assert "already a review branch" in result.output


def test_plan_create_rejects_existing_plan_file(monkeypatch, sample_config) -> None:
    runner = CliRunner()
    calls: list[list[str]] = []

    monkeypatch.setattr(plan_mod, "load_config_or_exit", lambda: sample_config)
    monkeypatch.setattr(plan_mod, "current_branch", lambda: "main")
    monkeypatch.setattr(plan_mod, "run_git", lambda args: calls.append(args) or "")
    monkeypatch.setattr(plan_mod, "date", FakeDate)

    with runner.isolated_filesystem():
        existing = Path("docs/plans/2026-02-28-foo.md")
        existing.parent.mkdir(parents=True, exist_ok=True)
        existing.write_text("existing", encoding="utf-8")

        result = runner.invoke(plan_mod.app, ["create", "foo", "--no-open-pr"])

        assert result.exit_code == 2
        assert "plan already exists" in result.output
        assert calls == []
