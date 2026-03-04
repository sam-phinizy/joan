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
            return {"number": 5, "title": "Five", "state": "open", "html_url": "http://forgejo.local/5"}

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
