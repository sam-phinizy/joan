from __future__ import annotations

import json

import joan.cli.pr as pr_mod
from joan.core.models import Config, ForgejoConfig, PullRequest, RemotesConfig
from typer.testing import CliRunner


def make_config() -> Config:
    return Config(
        forgejo=ForgejoConfig(url="http://forgejo.local", token="tok", owner="sam", repo="joan"),
        remotes=RemotesConfig(review="joan-review", upstream="origin"),
    )


def make_pr() -> PullRequest:
    return PullRequest(
        number=7,
        title="Test PR",
        url="http://forgejo.local/sam/joan/pulls/7",
        state="open",
        head_ref="feature/x",
        base_ref="main",
    )


def test_pr_review_create(monkeypatch) -> None:
    runner = CliRunner()
    config = make_config()
    pr = make_pr()
    posted: list = []

    monkeypatch.setattr(pr_mod, "load_config_or_exit", lambda: config)
    monkeypatch.setattr(pr_mod, "current_pr_or_exit", lambda _cfg: pr)

    class FakeClient:
        def create_review(self, owner, repo, index, body, verdict, comments):
            posted.append(
                {
                    "owner": owner,
                    "repo": repo,
                    "index": index,
                    "body": body,
                    "verdict": verdict,
                    "comments": comments,
                }
            )
            return {"id": 1}

    monkeypatch.setattr(pr_mod, "forgejo_client", lambda _cfg: FakeClient())

    review_input = json.dumps(
        {
            "body": "Looks good overall.",
            "verdict": "approve",
            "comments": [{"path": "src/foo.py", "new_position": 5, "body": "nice"}],
        }
    )

    result = runner.invoke(pr_mod.app, ["review", "create", "--json-input", review_input])
    assert result.exit_code == 0, result.output
    assert len(posted) == 1
    assert posted[0]["verdict"] == "approve"
    assert posted[0]["index"] == 7


def test_pr_review_approve(monkeypatch) -> None:
    runner = CliRunner()
    config = make_config()
    pr = make_pr()
    posted: list = []

    monkeypatch.setattr(pr_mod, "load_config_or_exit", lambda: config)
    monkeypatch.setattr(pr_mod, "current_pr_or_exit", lambda _cfg: pr)

    class FakeClient:
        def create_review(self, owner, repo, index, body, verdict, comments):
            posted.append({"verdict": verdict, "body": body})
            return {"id": 1}

    monkeypatch.setattr(pr_mod, "forgejo_client", lambda _cfg: FakeClient())

    result = runner.invoke(pr_mod.app, ["review", "approve", "--body", "LGTM"])
    assert result.exit_code == 0, result.output
    assert posted[0]["verdict"] == "approve"
    assert posted[0]["body"] == "LGTM"


def test_pr_review_request_changes(monkeypatch) -> None:
    runner = CliRunner()
    config = make_config()
    pr = make_pr()
    posted: list = []

    monkeypatch.setattr(pr_mod, "load_config_or_exit", lambda: config)
    monkeypatch.setattr(pr_mod, "current_pr_or_exit", lambda _cfg: pr)

    class FakeClient:
        def create_review(self, owner, repo, index, body, verdict, comments):
            posted.append({"verdict": verdict})
            return {"id": 1}

    monkeypatch.setattr(pr_mod, "forgejo_client", lambda _cfg: FakeClient())

    result = runner.invoke(pr_mod.app, ["review", "request-changes", "--body", "Fix the tests"])
    assert result.exit_code == 0, result.output
    assert posted[0]["verdict"] == "request_changes"


def test_pr_review_submit_uses_agent_client(monkeypatch) -> None:
    runner = CliRunner()
    config = make_config()
    posted: list = []

    monkeypatch.setattr(pr_mod, "load_config_or_exit", lambda: config)

    class FakeClient:
        def create_review(self, owner, repo, index, body, verdict, comments):
            posted.append(
                {
                    "owner": owner,
                    "repo": repo,
                    "index": index,
                    "body": body,
                    "verdict": verdict,
                    "comments": comments,
                }
            )
            return {"id": 4}

    monkeypatch.setattr(pr_mod, "forgejo_client_for_agent_or_exit", lambda _cfg, _agent: FakeClient())

    result = runner.invoke(
        pr_mod.app,
        [
            "review",
            "submit",
            "--agent",
            "phil",
            "--owner",
            "sam",
            "--repo",
            "joan",
            "--pr",
            "7",
            "--verdict",
            "comment",
            "--body",
            "Looks good enough.",
        ],
    )
    assert result.exit_code == 0, result.output
    assert posted == [
        {
            "owner": "sam",
            "repo": "joan",
            "index": 7,
            "body": "Looks good enough.",
            "verdict": "comment",
            "comments": [],
        }
    ]
