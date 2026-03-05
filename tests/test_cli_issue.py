from __future__ import annotations

import json

from typer.testing import CliRunner

import joan.cli.issue as issue_mod
from joan.core.models import Config, ForgejoConfig, RemotesConfig


def make_config() -> Config:
    return Config(
        forgejo=ForgejoConfig(url="http://forgejo.local", token="tok", owner="sam", repo="joan"),
        remotes=RemotesConfig(review="joan-review", upstream="origin"),
    )


def test_issue_create_calls_client(monkeypatch) -> None:
    runner = CliRunner()
    config = make_config()
    captured: dict = {}

    class FakeClient:
        def create_issue(self, owner, repo, title, body):
            captured["owner"] = owner
            captured["repo"] = repo
            captured["title"] = title
            captured["body"] = body
            return {"number": 12, "html_url": "http://forgejo.local/sam/joan/issues/12"}

    monkeypatch.setattr(issue_mod, "load_config_or_exit", lambda: config)
    monkeypatch.setattr(issue_mod, "forgejo_client", lambda _cfg: FakeClient())

    result = runner.invoke(issue_mod.app, ["create", "Fix crash", "--body", "Repro steps..."])

    assert result.exit_code == 0, result.output
    assert "Created issue #12" in result.output
    assert captured == {
        "owner": "sam",
        "repo": "joan",
        "title": "Fix crash",
        "body": "Repro steps...",
    }


def test_issue_comment_calls_client(monkeypatch) -> None:
    runner = CliRunner()
    config = make_config()
    captured: dict = {}

    class FakeClient:
        def create_issue_comment(self, owner, repo, index, body):
            captured["owner"] = owner
            captured["repo"] = repo
            captured["index"] = index
            captured["body"] = body
            return {"id": 77}

    monkeypatch.setattr(issue_mod, "load_config_or_exit", lambda: config)
    monkeypatch.setattr(issue_mod, "forgejo_client", lambda _cfg: FakeClient())

    result = runner.invoke(issue_mod.app, ["comment", "12", "--body", "Looks good."])

    assert result.exit_code == 0, result.output
    assert "Posted comment on issue #12" in result.output
    assert captured == {
        "owner": "sam",
        "repo": "joan",
        "index": 12,
        "body": "Looks good.",
    }


def test_issue_comments_reads_all_comments(monkeypatch) -> None:
    runner = CliRunner()
    config = make_config()

    class FakeClient:
        def list_issue_comments(self, owner, repo, index):
            assert (owner, repo, index) == ("sam", "joan", 12)
            return [
                {
                    "id": 1,
                    "body": "first",
                    "html_url": "http://forgejo.local/sam/joan/issues/12#issuecomment-1",
                    "created_at": "2026-03-05T14:00:00Z",
                    "updated_at": "2026-03-05T14:00:00Z",
                    "user": {"login": "sam"},
                },
                {
                    "id": 2,
                    "body": "second",
                    "html_url": "http://forgejo.local/sam/joan/issues/12#issuecomment-2",
                    "created_at": "2026-03-05T14:05:00Z",
                    "updated_at": "2026-03-05T14:05:00Z",
                    "user": {"login": "pat"},
                },
            ]

    monkeypatch.setattr(issue_mod, "load_config_or_exit", lambda: config)
    monkeypatch.setattr(issue_mod, "forgejo_client", lambda _cfg: FakeClient())

    result = runner.invoke(issue_mod.app, ["comments", "12"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert len(payload) == 2
    assert payload[0]["id"] == 1
    assert payload[0]["author"] == "sam"
    assert payload[1]["id"] == 2
    assert payload[1]["author"] == "pat"


def test_issue_link_rejects_self_reference() -> None:
    runner = CliRunner()

    result = runner.invoke(issue_mod.app, ["link", "7", "7"])

    assert result.exit_code == 2
    assert "cannot be blocked by itself" in result.output


def test_issue_read_list_and_single(monkeypatch) -> None:
    runner = CliRunner()
    config = make_config()

    class FakeClient:
        def list_issues(self, owner, repo, state="open", limit=50):
            assert owner == "sam"
            assert repo == "joan"
            assert state == "all"
            assert limit == 2
            return [
                {"number": 1, "title": "One", "state": "open", "html_url": "http://forgejo.local/1"},
                {"number": 2, "title": "Two", "state": "closed", "html_url": "http://forgejo.local/2"},
            ]

        def get_issue(self, owner, repo, index):
            assert (owner, repo, index) == ("sam", "joan", 5)
            return {
                "number": 5,
                "title": "Five",
                "body": "Issue details",
                "state": "open",
                "html_url": "http://forgejo.local/5",
            }

    monkeypatch.setattr(issue_mod, "load_config_or_exit", lambda: config)
    monkeypatch.setattr(issue_mod, "forgejo_client", lambda _cfg: FakeClient())

    list_result = runner.invoke(issue_mod.app, ["read", "--state", "all", "--limit", "2"])
    assert list_result.exit_code == 0, list_result.output
    list_payload = json.loads(list_result.output)
    assert [item["number"] for item in list_payload] == [1, 2]

    one_result = runner.invoke(issue_mod.app, ["read", "--issue", "5"])
    assert one_result.exit_code == 0, one_result.output
    one_payload = json.loads(one_result.output)
    assert one_payload["number"] == 5
    assert one_payload["body"] == "Issue details"


def test_issue_relations_and_graph_json(monkeypatch) -> None:
    runner = CliRunner()
    config = make_config()

    class FakeClient:
        def close_issue(self, owner, repo, index):
            assert (owner, repo, index) == ("sam", "joan", 8)
            return {"number": 8}

        def list_issue_blocked_by(self, owner, repo, index):
            assert owner == "sam"
            assert repo == "joan"
            if index == 7:
                return [{"number": 3, "title": "Upstream blocker", "state": "open"}]
            if index == 3:
                return []
            if index == 9:
                return [{"number": 7, "title": "Root issue", "state": "open"}]
            return []

        def list_issue_blocks(self, owner, repo, index):
            assert owner == "sam"
            assert repo == "joan"
            if index == 7:
                return [{"number": 9, "title": "Downstream", "state": "open"}]
            if index in {3, 9}:
                return []
            return []

        def get_issue(self, owner, repo, index):
            return {"number": index, "title": f"Issue {index}", "state": "open"}

    monkeypatch.setattr(issue_mod, "load_config_or_exit", lambda: config)
    monkeypatch.setattr(issue_mod, "forgejo_client", lambda _cfg: FakeClient())

    close_result = runner.invoke(issue_mod.app, ["close", "8"])
    assert close_result.exit_code == 0, close_result.output
    assert "Closed issue #8" in close_result.output

    blocked_by_result = runner.invoke(issue_mod.app, ["blocked-by", "7"])
    assert blocked_by_result.exit_code == 0, blocked_by_result.output
    blocked_by_payload = json.loads(blocked_by_result.output)
    assert blocked_by_payload[0]["number"] == 3

    blocks_result = runner.invoke(issue_mod.app, ["blocks", "7"])
    assert blocks_result.exit_code == 0, blocks_result.output
    blocks_payload = json.loads(blocks_result.output)
    assert blocks_payload[0]["number"] == 9

    graph_result = runner.invoke(issue_mod.app, ["graph", "7", "--depth", "1"])
    assert graph_result.exit_code == 0, graph_result.output
    graph_payload = json.loads(graph_result.output)
    assert graph_payload["root_issue"] == 7
    assert sorted((edge["from"], edge["to"]) for edge in graph_payload["edges"]) == [(3, 7), (7, 9)]


def test_issue_get_work_groups_ready_and_blocked(monkeypatch) -> None:
    runner = CliRunner()
    config = make_config()

    class FakeClient:
        def list_issues(self, owner, repo, state="open", limit=50):
            assert (owner, repo, state, limit) == ("sam", "joan", "open", 50)
            return [
                {"number": 1, "title": "Ready one", "state": "open"},
                {"number": 2, "title": "Blocked one", "state": "open"},
                {"number": 3, "title": "Closed blocker", "state": "open"},
                {"number": 4, "title": "PR style", "state": "open", "pull_request": {"number": 4}},
            ]

        def list_issue_blocked_by(self, owner, repo, index):
            assert owner == "sam"
            assert repo == "joan"
            if index == 1:
                return []
            if index == 2:
                return [{"number": 9, "title": "Blocker", "state": "open"}]
            if index == 3:
                return [{"number": 10, "title": "Done blocker", "state": "closed"}]
            raise AssertionError(index)

    monkeypatch.setattr(issue_mod, "load_config_or_exit", lambda: config)
    monkeypatch.setattr(issue_mod, "forgejo_client", lambda _cfg: FakeClient())

    result = runner.invoke(issue_mod.app, ["get-work", "--limit", "50", "--ready-limit", "1"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)

    assert payload["summary"] == {
        "open_issue_count": 3,
        "ready_count": 2,
        "blocked_count": 1,
    }
    assert len(payload["ready"]) == 1
    assert payload["ready"][0]["issue"]["number"] == 1
    assert payload["blocked"][0]["issue"]["number"] == 2
    assert payload["blocked"][0]["open_blockers"][0]["number"] == 9
