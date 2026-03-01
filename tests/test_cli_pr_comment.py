from __future__ import annotations

import joan.cli.pr as pr_mod
from joan.core.models import Config, ForgejoConfig, RemotesConfig
from typer.testing import CliRunner


def make_config() -> Config:
    return Config(
        forgejo=ForgejoConfig(url="http://forgejo.local", token="tok", owner="sam", repo="joan"),
        remotes=RemotesConfig(review="joan-review", upstream="origin"),
    )


def test_pr_comment_add_uses_agent_client(monkeypatch) -> None:
    runner = CliRunner()
    config = make_config()
    posted: list = []

    monkeypatch.setattr(pr_mod, "load_config_or_exit", lambda: config)

    class FakeClient:
        def create_inline_pr_comment(self, owner, repo, index, path, line, body):
            posted.append(
                {
                    "owner": owner,
                    "repo": repo,
                    "index": index,
                    "path": path,
                    "line": line,
                    "body": body,
                }
            )
            return {"id": 8}

    monkeypatch.setattr(pr_mod, "forgejo_client_for_agent_or_exit", lambda _cfg, _agent: FakeClient())

    result = runner.invoke(
        pr_mod.app,
        [
            "comment",
            "add",
            "--agent",
            "phil",
            "--owner",
            "sam",
            "--repo",
            "joan",
            "--pr",
            "7",
            "--path",
            "src/foo.py",
            "--line",
            "42",
            "--body",
            "This breaks.",
        ],
    )

    assert result.exit_code == 0, result.output
    assert posted == [
        {
            "owner": "sam",
            "repo": "joan",
            "index": 7,
            "path": "src/foo.py",
            "line": 42,
            "body": "This breaks.",
        }
    ]


def test_pr_comment_post_calls_create_issue_comment(monkeypatch) -> None:
    runner = CliRunner()
    config = make_config()
    posted: list = []

    monkeypatch.setattr(pr_mod, "load_config_or_exit", lambda: config)

    class FakePR:
        number = 5
        title = "test"
        url = "http://forgejo.local/owner/repo/pulls/5"
        state = "open"
        head_ref = "joan-review/main"
        base_ref = "main"

    monkeypatch.setattr(pr_mod, "current_pr_or_exit", lambda cfg: FakePR())

    class FakeClient:
        def create_issue_comment(self, owner, repo, index, body):
            posted.append({"owner": owner, "repo": repo, "index": index, "body": body})
            return {"id": 10}

    monkeypatch.setattr(pr_mod, "forgejo_client", lambda cfg: FakeClient())

    result = runner.invoke(pr_mod.app, ["comment", "post", "--body", "Hello reviewer!"])

    assert result.exit_code == 0, result.output
    assert "Posted comment on PR #5" in result.output
    assert posted == [{"owner": "sam", "repo": "joan", "index": 5, "body": "Hello reviewer!"}]
